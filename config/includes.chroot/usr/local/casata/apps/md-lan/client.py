#!/usr/bin/env python3

# Monojo Drive LAN 2.1, Monojo Project, David Baña Szymaniak

import os, json, socket, struct, threading, time, queue, subprocess, uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog

PUERTO_DESCUBRIMIENTO = 64000
PUERTO_CONTROL = 64001
TAM_BUFFER = 64 * 1024
DISCOVERY_MAGIC = b"MONOJO_DRIVE_V1"
PROBE_MSG = b"MONOJO_DISCOVER"

def zenity_askstring(title, prompt, default=""):
    try:
        res = subprocess.run(['zenity','--entry',f'--title={title}',f'--text={prompt}',
                              f'--entry-text={default}'], capture_output=True, text=True, timeout=30)
        if res.returncode == 0: return res.stdout.strip('\n')
        if res.returncode == 1: return ""
    except: pass
    return simpledialog.askstring(title, prompt, initialvalue=default)

def zenity_asksaveas(default_name=""):
    try:
        res = subprocess.run(['zenity','--file-selection','--save','--confirm-overwrite',
                              f'--filename={default_name}'], capture_output=True, text=True, timeout=30)
        if res.returncode == 0: return res.stdout.strip('\n')
        if res.returncode == 1: return ""
    except: pass
    return filedialog.asksaveasfilename(initialfile=default_name)

def zenity_askopenfilename():
    try:
        res = subprocess.run(['zenity','--file-selection'], capture_output=True, text=True, timeout=30)
        if res.returncode == 0: return res.stdout.strip('\n')
        if res.returncode == 1: return ""
    except: pass
    return filedialog.askopenfilename()

def recv_n(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk: return None
        buf += chunk
    return buf

def enviar_json(sock, obj):
    try:
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        hdr = struct.pack('!I', len(data))
        sock.sendall(hdr + data)
        return True
    except: return False

def recibir_json(sock):
    try:
        hdr = recv_n(sock, 4)
        if not hdr: return None
        length, = struct.unpack('!I', hdr)
        if length > 10*1024*1024: return None
        body = recv_n(sock, length)
        if not body: return None
        return json.loads(body.decode('utf-8'))
    except: return None

def buscar_servidores(timeout=2.0):
    servidores = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except: pass
    s.settimeout(0.5)
    try:
        s.sendto(PROBE_MSG, ('<broadcast>', PUERTO_DESCUBRIMIENTO))
        s.sendto(PROBE_MSG, ('255.255.255.255', PUERTO_DESCUBRIMIENTO))
    except: pass
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            data, addr = s.recvfrom(4096)
            if not data or not data.startswith(DISCOVERY_MAGIC+b"|"): continue
            if data.startswith(DISCOVERY_MAGIC+b"|UPDATE|"): continue
            payload = data.split(b"|",1)[1]
            info = json.loads(payload.decode('utf-8'))
            nombre = info.get('nombre', addr[0])
            port = int(info.get('port', PUERTO_CONTROL))
            servidores[nombre] = (addr[0], port)
        except socket.timeout: continue
        except: break
    try: s.close()
    except: pass
    return servidores

def format_size(size_bytes, unit_type):
    if unit_type == "Bytes": return f"{size_bytes} B"
    elif unit_type == "KB": return f"{size_bytes/1024:.2f} KB"
    elif unit_type == "MB": return f"{size_bytes/(1024**2):.2f} MB"
    elif unit_type == "GB": return f"{size_bytes/(1024**3):.2f} GB"
    else:
        if size_bytes < 1024: return f"{size_bytes} B"
        elif size_bytes < 1024**2: return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024**3: return f"{size_bytes/(1024**2):.2f} MB"
        else: return f"{size_bytes/(1024**3):.2f} GB"

class ClienteGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Monojo Drive LAN - Cliente")
        self.root.geometry("1100x700")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.servidores = {}
        self.sock = None
        self.mode = None
        self.nombre_cliente = None
        self.servidor_conectado = None

        self.current_path = ""
        self.current_items = []
        self.displayed_items = []
        self.show_hidden = False

        self.root.bind('<Control-h>', self._toggle_hidden)
        self.root.bind('<Control-H>', self._toggle_hidden)

        # Sistema de futuros para respuestas
        self.futures = {}           # req_id -> list (con un solo elemento, la respuesta)
        self.send_lock = threading.Lock()
        self.reader_thread = None
        self.reader_running = threading.Event()
        self.incoming = queue.Queue()  # cola para mensajes entrantes

        self.buscar_thread = None
        self.udp_listener_thread = None

        self.transferring = threading.Event()

        self._last_tree_click = 0.0
        self.log_queue = queue.Queue()

        # Cola de operaciones (secuencial)
        self.op_queue = queue.Queue()
        self.worker_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill='both', expand=True)
        self._crear_ui_login()

        self.root.after(100, self._procesar_mensajes)
        self.root.after(100, self._procesar_logs)

    def _on_close(self):
        self.desconectar(forzar=True)
        self.root.destroy()

    def _log(self, msg):
        self.log_queue.put(msg)

    def _procesar_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            if hasattr(self, 'log_text') and self.log_text:
                self.log_text.config(state='normal')
                self.log_text.insert('end', msg + '\n')
                self.log_text.see('end')
                self.log_text.config(state='disabled')
        self.root.after(100, self._procesar_logs)

    def _crear_ui_login(self):
        for widget in self.main_frame.winfo_children(): widget.destroy()
        login_frame = ttk.Frame(self.main_frame, padding=20)
        login_frame.pack(fill='both', expand=True)

        title_frame = ttk.Frame(login_frame)
        title_frame.pack(fill='x', pady=20)
        ttk.Label(title_frame, text="📄 Monojo Drive LAN 📁", font=('Arial',16,'bold')).pack()
        ttk.Label(title_frame, text="Conéctate a un servidor", font=('Arial',10)).pack()

        name_frame = ttk.LabelFrame(login_frame, text="Tu nombre", padding=10)
        name_frame.pack(fill='x', pady=10)
        self.nombre_var = tk.StringVar(value="Cliente")
        ttk.Entry(name_frame, textvariable=self.nombre_var, font=('Arial',12), width=30).pack(fill='x')

        servers_frame = ttk.LabelFrame(login_frame, text="Servidores disponibles", padding=10)
        servers_frame.pack(fill='both', expand=True, pady=10)

        btn_frame = ttk.Frame(servers_frame)
        btn_frame.pack(fill='x', pady=(0,10))
        ttk.Button(btn_frame, text="🔄 Buscar servidores", command=self.refrescar).pack(side='left', padx=5)

        self.serv_tree = ttk.Treeview(servers_frame, columns=('ip','puerto','nombre'), show='headings', height=8)
        self.serv_tree.heading('nombre', text='Nombre del servidor')
        self.serv_tree.heading('ip', text='IP')
        self.serv_tree.heading('puerto', text='Puerto')
        self.serv_tree.column('nombre', width=250)
        self.serv_tree.column('ip', width=150)
        self.serv_tree.column('puerto', width=80)
        self.serv_tree.pack(fill='both', expand=True)

        self.serv_tree.bind('<Double-1>', lambda e: self.conectar())
        self.serv_tree.bind('<ButtonRelease-1>', self._on_tree_click_release)
        self.serv_tree.bind('<Return>', lambda e: self.conectar())

        ttk.Button(login_frame, text="🔗 Conectar", command=self.conectar, width=30).pack(pady=20)
        self.buscar_automatico()

    def _on_tree_click_release(self, event):
        ahora = time.time()
        if ahora - self._last_tree_click < 0.5:
            self.conectar()
            self._last_tree_click = 0.0
        else:
            self._last_tree_click = ahora

    def _crear_ui_principal(self):
        for widget in self.main_frame.winfo_children(): widget.destroy()

        header_frame = ttk.Frame(self.main_frame, padding=8)
        header_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(header_frame, text=f"✓ Conectado a: {self.servidor_conectado}",
                  font=('Arial',11,'bold'), foreground='green').pack(side='left')
        ttk.Label(header_frame, text=f"Como: {self.nombre_cliente}", font=('Arial',10)).pack(side='left', padx=20)
        ttk.Label(header_frame, text=f"Permisos: {self.mode}", font=('Arial',10)).pack(side='left', padx=20)
        ttk.Button(header_frame, text="🔌 Desconectar", command=self.desconectar).pack(side='right', padx=5)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        frm_archivos = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frm_archivos, text="📁 Archivos")

        nav_frame = ttk.Frame(frm_archivos)
        nav_frame.pack(fill='x', pady=5)
        ttk.Button(nav_frame, text="⬅️ Atrás", command=self._ir_atras).pack(side='left', padx=5)
        self.lbl_ruta = ttk.Label(nav_frame, text="Ruta: /", font=('Arial',10,'bold'))
        self.lbl_ruta.pack(side='left', padx=10)
        self.lbl_ocultos = ttk.Label(nav_frame, text="(Ocultos: No - CTRL+H)", font=('Arial',9,'italic'), foreground='gray')
        self.lbl_ocultos.pack(side='left', padx=10)

        self.unit_var = tk.StringVar(value="Auto")
        cmb_units = ttk.Combobox(nav_frame, textvariable=self.unit_var,
                                 values=["Auto","Bytes","KB","MB","GB"], state="readonly", width=8)
        cmb_units.pack(side='right', padx=5)
        cmb_units.bind("<<ComboboxSelected>>", lambda e: self.op_queue.put(self._listar_archivos_hilo))
        ttk.Label(nav_frame, text="Medida:").pack(side='right')

        self.btn_nuevo_archivo = ttk.Button(nav_frame, text="📄 Nuevo archivo",
                                            command=lambda: self.op_queue.put(self._crear_archivo_vacio_hilo), state='disabled')
        self.btn_nuevo_archivo.pack(side='right', padx=5)
        self.btn_nueva_carpeta = ttk.Button(nav_frame, text="📁 Nueva carpeta",
                                            command=lambda: self.op_queue.put(self._crear_carpeta_hilo), state='disabled')
        self.btn_nueva_carpeta.pack(side='right', padx=5)

        scroll = ttk.Scrollbar(frm_archivos)
        scroll.pack(side='right', fill='y')
        self.remote_list = tk.Listbox(frm_archivos, height=15, yscrollcommand=scroll.set, font=('Arial',11))
        self.remote_list.pack(fill='both', expand=True, pady=5)
        scroll.config(command=self.remote_list.yview)
        self.remote_list.bind('<Double-1>', self._on_doble_click)

        btn_archivos = ttk.Frame(frm_archivos)
        btn_archivos.pack(fill='x', pady=5)
        ttk.Button(btn_archivos, text="⬇️ Descargar", command=self.descargar).pack(side='left', padx=5)
        self.btn_subir = ttk.Button(btn_archivos, text="⬆️ Subir archivo", command=self.subir, state='disabled')
        self.btn_subir.pack(side='left', padx=5)
        self.btn_renombrar = ttk.Button(btn_archivos, text="✏️ Renombrar/Mover", command=self.renombrar, state='disabled')
        self.btn_renombrar.pack(side='left', padx=5)
        self.btn_editar = ttk.Button(btn_archivos, text="📝 Editar Texto", command=self.editar_texto, state='disabled')
        self.btn_editar.pack(side='left', padx=5)

        frm_log = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frm_log, text="📋 Log")
        self.log_text = scrolledtext.ScrolledText(frm_log, height=20, state='disabled',
                                                  wrap='word', font=('Courier',9))
        self.log_text.pack(fill='both', expand=True)

        self._log("✓ Conectado al servidor")
        self._actualizar_botones_permisos()
        self.notebook.select(0)
        self.current_path = ""

        self.reader_running.set()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

        # Primera carga
        self.op_queue.put(self._listar_archivos_hilo)
        self._iniciar_escucha_udp()

    def _actualizar_botones_permisos(self):
        estado = 'normal' if self.mode == 'completo' else 'disabled'
        for btn in [self.btn_subir, self.btn_nueva_carpeta, self.btn_nuevo_archivo, self.btn_renombrar, self.btn_editar]:
            try: btn.config(state=estado)
            except: pass

    def _toggle_hidden(self, event=None):
        self.show_hidden = not self.show_hidden
        if hasattr(self, 'lbl_ocultos'):
            self.lbl_ocultos.config(text=f"(Ocultos: {'Sí' if self.show_hidden else 'No'} - CTRL+H)")
        self.op_queue.put(self._listar_archivos_hilo)

    # -----------------------------------------------------------------
    # Worker secuencial
    # -----------------------------------------------------------------
    def _worker_loop(self):
        while self.worker_running:
            func = self.op_queue.get()
            if func is None:
                break
            try:
                func()
            except Exception as e:
                self._log(f"[WORKER] Error: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.op_queue.task_done()

    # -----------------------------------------------------------------
    # Procesamiento de mensajes entrantes en el hilo principal
    # -----------------------------------------------------------------
    def _procesar_mensajes(self):
        while not self.incoming.empty():
            msg = self.incoming.get_nowait()
            tipo = msg.get('type', '?')
            req_id = msg.get('request_id', None)
            self._log(f"[PROC] Mensaje: {tipo} req_id={req_id}")
            # Si es una actualización broadcast, refrescar
            if tipo == 'update' and req_id == 'update_broadcast':
                self.op_queue.put(self._listar_archivos_hilo)
                continue
            # Si hay un futuro esperando este req_id, resolverlo
            if req_id and req_id in self.futures:
                future = self.futures.pop(req_id)
                if future is not None:
                    future.append(msg)  # la respuesta se guarda como segundo elemento
            else:
                # Podría ser una respuesta tardía, ignorar
                pass
        self.root.after(100, self._procesar_mensajes)

    def _reader_loop(self):
        self._log("[LECTOR] Hilo iniciado.")
        while self.reader_running.is_set() and self.sock:
            try:
                msg = recibir_json(self.sock)
                if msg is None:
                    self._log("[LECTOR] Recibido None (desconexión).")
                    self.root.after(0, self._notificar_cierre_servidor)
                    break
                tipo = msg.get('type', '?')
                self._log(f"[LECTOR] Recibido: {tipo} req_id={msg.get('request_id')}")
                self.incoming.put(msg)
            except Exception as e:
                self._log(f"[LECTOR] Excepción: {e}")
                self.root.after(0, self._notificar_cierre_servidor)
                break
        self._log("[LECTOR] Hilo terminado.")

    def _send_request(self, msg, timeout=15):
        if not self.sock:
            raise Exception("Sin conexión")
        req_id = msg.get('request_id')
        if not req_id:
            req_id = uuid.uuid4().hex[:8]
            msg['request_id'] = req_id
        future = []   # se convertirá en [respuesta] cuando llegue
        self.futures[req_id] = future
        self._log(f"[ENVIAR] Enviando {msg.get('type')} req_id={req_id}")
        with self.send_lock:
            if not enviar_json(self.sock, msg):
                self.futures.pop(req_id, None)
                raise Exception("Error al enviar datos")
        # Esperar activamente (el worker se bloquea aquí, pero es aceptable porque es secuencial)
        inicio = time.time()
        while time.time() - inicio < timeout:
            if len(future) > 0:
                resp = future[0]
                if resp.get('type') == 'error':
                    raise Exception(resp.get('message', 'Error del servidor'))
                return resp
            time.sleep(0.05)
        self.futures.pop(req_id, None)
        raise Exception("Timeout esperando respuesta del servidor")

    # -----------------------------------------------------------------
    # Conexión / Desconexión
    # -----------------------------------------------------------------
    def conectar(self):
        if getattr(self, 'conectando', False): return
        nombre = self.nombre_var.get().strip()
        if not nombre or len(nombre) < 2:
            messagebox.showwarning("Error", "Nombre inválido"); return
        sel = self.serv_tree.selection()
        if not sel:
            messagebox.showwarning("Conectar", "Selecciona un servidor."); return
        vals = self.serv_tree.item(sel[0], 'values')
        ip, puerto, servidor_nombre = vals[0], int(vals[1]), vals[2]

        self.conectando = True
        dlg = tk.Toplevel(self.root)
        dlg.title("Conectando...")
        dlg.geometry("400x170")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.focus_set()
        ttk.Label(dlg, text=f"Conectando a {servidor_nombre}...\nEsperando respuesta del servidor.",
                  font=('Arial',11), justify='center').pack(pady=20)
        progress = ttk.Progressbar(dlg, mode='indeterminate')
        progress.pack(fill='x', padx=20, pady=10)
        progress.start()

        resultado = {'success': False, 'error': None}
        cancelado = threading.Event()
        conn_sock = None

        def tarea():
            nonlocal conn_sock
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn_sock = sock
                sock.settimeout(10)
                sock.connect((ip, puerto))
                if cancelado.is_set(): sock.close(); return
                if not enviar_json(sock, {'type':'join','name':nombre}):
                    raise Exception("Fallo al enviar")
                resp = recibir_json(sock)
                if not resp or resp.get('status') != 'ok':
                    raise Exception(resp.get('message','Rechazado'))
                self.sock = sock
                self.sock.settimeout(None)
                self.mode = resp.get('mode','desconocido')
                self.nombre_cliente = nombre
                self.servidor_conectado = servidor_nombre
                resultado['success'] = True
            except Exception as e:
                resultado['error'] = str(e)
                if conn_sock:
                    try: conn_sock.close()
                    except: pass

        hilo = threading.Thread(target=tarea, daemon=True)
        hilo.start()

        def cancelar():
            cancelado.set()
            if conn_sock:
                try: conn_sock.close()
                except: pass
            dlg.destroy()
            self.conectando = False

        dlg.protocol("WM_DELETE_WINDOW", cancelar)

        def verificar():
            if not dlg.winfo_exists(): return
            if hilo.is_alive():
                dlg.after(100, verificar)
            else:
                progress.stop()
                dlg.destroy()
                self.conectando = False
                if resultado['success']:
                    self._log("[INFO] Conexión establecida, creando UI...")
                    self._crear_ui_principal()
                else:
                    messagebox.showerror("Error", f"No se pudo conectar:\n{resultado['error']}")

        dlg.after(100, verificar)

    def desconectar(self, forzar=False):
        self.reader_running.clear()
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None
        self.mode = None
        self.futures.clear()
        self.conectando = False
        if not forzar and self.root.winfo_exists():
            self._crear_ui_login()

    def _notificar_cierre_servidor(self):
        if self.root.winfo_exists():
            try: messagebox.showwarning("Servidor desconectado", "El servidor se ha cerrado.")
            except: pass
            self.desconectar()

    # -----------------------------------------------------------------
    # Operaciones de archivos (tareas encolables)
    # -----------------------------------------------------------------
    def _listar_archivos_hilo(self):
        try:
            if not self.sock:
                self._log("[LISTAR] Sin conexión.")
                return
            self.root.after(0, lambda: self.lbl_ruta.config(text=f"Ruta: /{self.current_path}"))
            req_id = 'list_' + uuid.uuid4().hex[:8]
            resp = self._send_request({'type':'list','path':self.current_path,'request_id':req_id})
            items = resp.get('items', [])
            self._log(f"[LISTAR] Recibidos {len(items)} elementos.")
            self.root.after(0, lambda: self._actualizar_lista(items))
        except Exception as e:
            self._log(f"[LISTAR] Error: {e}")

    def _actualizar_lista(self, items):
        self.remote_list.delete(0, 'end')
        self.current_items = items
        self.displayed_items = []
        img_exts = {'.png','.jpg','.jpeg','.gif','.bmp','.webp','.svg'}
        for item in items:
            if not self.show_hidden and item['name'].startswith('.'): continue
            self.displayed_items.append(item)
            if item['is_dir']:
                self.remote_list.insert('end', f"📁 {item['name']}")
            else:
                ext = os.path.splitext(item['name'])[1].lower()
                emoji = "🖼️" if ext in img_exts else "📄"
                self.remote_list.insert('end', f"{emoji} {item['name']} ({format_size(item['size'], self.unit_var.get())})")

    def _ir_atras(self):
        if self.current_path:
            self.current_path = os.path.dirname(self.current_path)
            self.op_queue.put(self._listar_archivos_hilo)

    def _on_doble_click(self, event):
        sel = self.remote_list.curselection()
        if not sel: return
        item = self.displayed_items[sel[0]]
        if item['is_dir']:
            self.current_path = os.path.join(self.current_path, item['name']).replace('\\', '/')
            self.op_queue.put(self._listar_archivos_hilo)

    def _crear_carpeta_hilo(self):
        if self.mode != 'completo': return
        nombre = zenity_askstring("Nueva Carpeta", "Nombre:")
        if not nombre: return
        path = os.path.join(self.current_path, nombre).replace('\\', '/')
        try:
            req_id = 'create_folder_' + uuid.uuid4().hex[:8]
            self._send_request({'type':'create_folder','path':path,'request_id':req_id})
            self.op_queue.put(self._listar_archivos_hilo)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _crear_archivo_vacio_hilo(self):
        if self.mode != 'completo': return
        nombre = zenity_askstring("Nuevo Archivo", "Nombre:")
        if not nombre: return
        path = os.path.join(self.current_path, nombre).replace('\\', '/')
        try:
            req_id = 'create_file_' + uuid.uuid4().hex[:8]
            self._send_request({'type':'create_file','path':path,'request_id':req_id})
            self.op_queue.put(self._listar_archivos_hilo)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def renombrar(self):
        if self.mode != 'completo': return
        sel = self.remote_list.curselection()
        if not sel: return
        item = self.displayed_items[sel[0]]
        old = os.path.join(self.current_path, item['name']).replace('\\', '/')
        new_name = zenity_askstring("Renombrar", "Nuevo nombre:", default=item['name'])
        if not new_name or new_name == item['name']: return
        new = os.path.join(self.current_path, new_name).replace('\\', '/')
        self.op_queue.put(lambda: self._renombrar_hilo(old, new))

    def _renombrar_hilo(self, old, new):
        try:
            req_id = 'rename_' + uuid.uuid4().hex[:8]
            self._send_request({'type':'rename','old':old,'new':new,'request_id':req_id})
            self.op_queue.put(self._listar_archivos_hilo)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def editar_texto(self):
        if self.mode != 'completo': return
        sel = self.remote_list.curselection()
        if not sel: return
        item = self.displayed_items[sel[0]]
        if item['is_dir']:
            messagebox.showinfo("Info", "Selecciona un archivo, no una carpeta.")
            return
        path = os.path.join(self.current_path, item['name']).replace('\\', '/')
        self.op_queue.put(lambda: self._editar_texto_hilo(path))

    def _editar_texto_hilo(self, path):
        try:
            req_id = 'read_text_' + uuid.uuid4().hex[:8]
            resp = self._send_request({'type':'read_text','filepath':path,'request_id':req_id})
            content = resp.get('content','')
            self.root.after(0, lambda: self._abrir_editor(path, content))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error al leer archivo", str(e)))

    def _abrir_editor(self, path, content):
        top = tk.Toplevel(self.root)
        top.title(f"Editor - {os.path.basename(path)}")
        top.geometry("700x500")
        txt = scrolledtext.ScrolledText(top, wrap='word', font=('Consolas',11))
        txt.pack(fill='both', expand=True, padx=5, pady=5)
        txt.insert('1.0', content)
        def guardar():
            nuevo = txt.get('1.0','end-1c')
            self.op_queue.put(lambda: self._guardar_texto_hilo(path, nuevo, top))
        ttk.Button(top, text="💾 Guardar", command=guardar).pack(side='right', padx=5, pady=5)
        ttk.Button(top, text="Cancelar", command=top.destroy).pack(side='right', padx=5, pady=5)

    def _guardar_texto_hilo(self, path, content, top):
        try:
            req_id = 'save_text_' + uuid.uuid4().hex[:8]
            self._send_request({'type':'save_text','filepath':path,'content':content,'request_id':req_id})
            self.root.after(0, lambda: [messagebox.showinfo("Guardado","OK",parent=top), top.destroy(), self.op_queue.put(self._listar_archivos_hilo)])
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error al guardar", str(e), parent=top))

    def descargar(self):
        sel = self.remote_list.curselection()
        if not sel: return
        item = self.displayed_items[sel[0]]
        path = os.path.join(self.current_path, item['name']).replace('\\', '/')
        if self.transferring.is_set(): return
        if item['is_dir']:
            ruta = zenity_asksaveas(default_name=item['name']+".zip")
            tipo = 'download_folder'
        else:
            ruta = zenity_asksaveas(default_name=item['name'])
            tipo = 'download'
        if not ruta: return
        self.transferring.set()
        self.op_queue.put(lambda: self._descargar_hilo(path, ruta, tipo))

    def _descargar_hilo(self, path, ruta, tipo):
        try:
            req_id = 'download_' + uuid.uuid4().hex[:8]
            resp = self._send_request({'type':tipo, 'path' if tipo=='download_folder' else 'filepath':path, 'request_id':req_id})
            size = int(resp.get('size',0))
            # El lector se mantiene activo, no hay pausa (el servidor envía los bytes justo después del JSON)
            # Pero debemos evitar que el lector intente parsear los bytes como JSON. Por eso pausamos el lector solo durante la recepción de bytes.
            self.reader_running.clear()   # detenemos el hilo lector
            recibidos = 0
            with open(ruta, 'wb') as f:
                while recibidos < size:
                    chunk = self.sock.recv(min(TAM_BUFFER, size-recibidos))
                    if not chunk: break
                    f.write(chunk)
                    recibidos += len(chunk)
            self.reader_running.set()      # reactivamos el lector
            if recibidos == size:
                self.root.after(0, lambda: messagebox.showinfo("Descarga","Completada."))
            else:
                raise Exception("Transferencia incompleta")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error",str(e)))
        finally:
            self.transferring.clear()
            self.reader_running.set()

    def subir(self):
        if self.mode != 'completo' or self.transferring.is_set(): return
        ruta = zenity_askopenfilename()
        if not ruta: return
        nombre = os.path.basename(ruta)
        size = os.path.getsize(ruta)
        self.transferring.set()
        self.op_queue.put(lambda: self._subir_hilo(ruta, nombre, size))

    def _subir_hilo(self, ruta, nombre, size):
        try:
            req_id = 'upload_' + uuid.uuid4().hex[:8]
            # Registrar futuro para upload_done
            future = []
            self.futures[req_id] = future
            with self.send_lock:
                if not enviar_json(self.sock, {'type':'upload','filename':nombre,'path':self.current_path,'size':size,'request_id':req_id}):
                    raise Exception("Error al enviar comando de subida")
            # Enviar bytes (el lector sigue activo, pero no hay problema porque el servidor solo lee bytes después del comando)
            self.reader_running.clear()
            with open(ruta, 'rb') as f:
                while True:
                    chunk = f.read(TAM_BUFFER)
                    if not chunk: break
                    self.sock.sendall(chunk)
            self.reader_running.set()
            # Esperar respuesta upload_done
            inicio = time.time()
            while time.time() - inicio < 30:
                if len(future) > 0:
                    resp = future[0]
                    if resp.get('type') == 'error':
                        raise Exception(resp.get('message', 'Error en subida'))
                    break
                time.sleep(0.05)
            else:
                raise Exception("Timeout esperando confirmación de subida")
            self.futures.pop(req_id, None)
            self.op_queue.put(self._listar_archivos_hilo)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error",str(e)))
        finally:
            self.transferring.clear()
            self.reader_running.set()

    # Búsqueda y UDP
    def buscar_automatico(self):
        def buscar():
            while self.root.winfo_exists() and not self.sock:
                try:
                    nuevos = buscar_servidores(timeout=2.0)
                    if nuevos != self.servidores:
                        self.servidores = nuevos
                        if hasattr(self, 'serv_tree'):
                            self.root.after(0, self._actualizar_lista_servidores)
                except: pass
                for _ in range(50):
                    if not self.root.winfo_exists() or self.sock: return
                    time.sleep(0.1)
        if self.buscar_thread is None or not self.buscar_thread.is_alive():
            self.buscar_thread = threading.Thread(target=buscar, daemon=True)
            self.buscar_thread.start()

    def _iniciar_escucha_udp(self):
        def escuchar():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', PUERTO_DESCUBRIMIENTO))
            except: return
            s.settimeout(1.0)
            while self.root.winfo_exists() and self.sock:
                try:
                    data, addr = s.recvfrom(4096)
                    if data.startswith(DISCOVERY_MAGIC+b"|UPDATE|"):
                        info = json.loads(data.split(b"|",2)[2].decode('utf-8'))
                        if info.get('nombre') == self.servidor_conectado and not self.transferring.is_set():
                            self._log("[UDP] Actualización detectada.")
                            self.incoming.put({'type': 'update', 'request_id': 'update_broadcast'})
                except socket.timeout: continue
                except: break
            try: s.close()
            except: pass
        if self.udp_listener_thread is None or not self.udp_listener_thread.is_alive():
            self.udp_listener_thread = threading.Thread(target=escuchar, daemon=True)
            self.udp_listener_thread.start()

    def refrescar(self):
        try:
            self.servidores = buscar_servidores(timeout=2.0)
            self._actualizar_lista_servidores()
        except Exception as e:
            messagebox.showerror("Error", f"Error al buscar: {e}")

    def _actualizar_lista_servidores(self):
        if not hasattr(self, 'serv_tree'): return
        for i in self.serv_tree.get_children(): self.serv_tree.delete(i)
        for nombre, (ip, port) in self.servidores.items():
            self.serv_tree.insert('', 'end', values=(ip, port, nombre))

if __name__ == "__main__":
    root = tk.Tk(className="monojo_drive_lan_client")
    app = ClienteGUI(root)
    root.mainloop()
