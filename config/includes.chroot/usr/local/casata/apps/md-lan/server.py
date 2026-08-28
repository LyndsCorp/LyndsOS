#!/usr/bin/env python3

# Monojo Drive LAN 2.1, Monojo Project, David Baña Szymaniak

import os, json, socket, struct, threading, time, queue, zipfile, tempfile, sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

SETTINGS_FILE = os.path.expanduser("~/.config/MonojoDriveLAN/monojo_settings.json")
os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)

PUERTO_DESCUBRIMIENTO = 64000
PUERTO_CONTROL = 64001
INTERVALO_ANNOUNCE = 2.0
TAM_BUFFER = 64 * 1024
DISCOVERY_MAGIC = b"MONOJO_DRIVE_V1"
PROBE_MSG = b"MONOJO_DISCOVER"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

def recv_n(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk: return None
        buf += chunk
    return buf

def enviar_json(sock, obj, lock=None):
    try:
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        hdr = struct.pack('!I', len(data))
        if lock:
            with lock:
                sock.sendall(hdr + data)
        else:
            sock.sendall(hdr + data)
        return True
    except Exception as e:
        log(f"ERROR enviar_json: {e}")
        return False

def recibir_json(sock):
    try:
        hdr = recv_n(sock, 4)
        if not hdr: return None
        length, = struct.unpack('!I', hdr)
        if length > 10 * 1024 * 1024: return None
        body = recv_n(sock, length)
        if not body: return None
        return json.loads(body.decode('utf-8'))
    except Exception as e:
        log(f"ERROR recibir_json: {e}")
        return None

def safe_rel_path(base_dir, user_path):
    if not user_path: return os.path.abspath(base_dir)
    user_path = user_path.replace('\\', '/').lstrip('/')
    target_path = os.path.join(base_dir, user_path)
    target_path = os.path.normpath(target_path)
    real_base = os.path.normpath(os.path.abspath(base_dir))
    if os.path.commonpath([real_base, target_path]) != real_base:
        return None
    return target_path

class DiscoveryThread(threading.Thread):
    def __init__(self, nombre, puerto_udp, puerto_tcp):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.puerto_udp = puerto_udp
        self.puerto_tcp = puerto_tcp
        self._running = threading.Event()
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try: self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except: pass
            try: self.sock.bind(('', self.puerto_udp))
            except: pass
            try: self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except: pass
            self.sock.settimeout(0.5)
            self._running.set()
            last_announce = 0.0
            while self._running.is_set():
                now = time.time()
                if now - last_announce >= INTERVALO_ANNOUNCE:
                    try:
                        payload = json.dumps({"nombre": self.nombre, "port": self.puerto_tcp}).encode('utf-8')
                        msg = DISCOVERY_MAGIC + b"|" + payload
                        try: self.sock.sendto(msg, ('<broadcast>', self.puerto_udp))
                        except: pass
                        try: self.sock.sendto(msg, ('255.255.255.255', self.puerto_udp))
                        except: pass
                    except: pass
                    last_announce = now
                try:
                    data, addr = self.sock.recvfrom(4096)
                    if data.startswith(PROBE_MSG):
                        payload = json.dumps({"nombre": self.nombre, "port": self.puerto_tcp}).encode('utf-8')
                        self.sock.sendto(DISCOVERY_MAGIC + b"|" + payload, addr)
                except: continue
        except Exception as e:
            log(f"DiscoveryThread error: {e}")
        finally:
            if self.sock: self.sock.close()

    def trigger_update(self):
        if not self.sock: return
        try:
            payload = json.dumps({"nombre": self.nombre, "action": "update"}).encode('utf-8')
            msg = DISCOVERY_MAGIC + b"|UPDATE|" + payload
            self.sock.sendto(msg, ('<broadcast>', self.puerto_udp))
            self.sock.sendto(msg, ('255.255.255.255', self.puerto_udp))
        except: pass

    def stop(self):
        self._running.clear()
        if self.sock: self.sock.close()

class MonojoServer(threading.Thread):
    def __init__(self, carpeta_drive, nombre, gui_queue):
        super().__init__(daemon=True)
        self.carpeta_drive = os.path.abspath(carpeta_drive)
        os.makedirs(self.carpeta_drive, exist_ok=True)
        self.nombre = nombre
        self.gui_queue = gui_queue

        self.running = threading.Event()
        self.lock = threading.RLock()
        self.pending_requests = {}
        self.client_permissions = {}
        self.client_connections = {}
        self.send_locks = {}
        self.next_client_id = 1
        self.tcp_sock = None
        self.discovery = None

    def _get_fs_state(self):
        count, mtime_sum = 0, 0
        try:
            for root, dirs, files in os.walk(self.carpeta_drive):
                count += len(dirs) + len(files)
                for f in files:
                    try: mtime_sum += os.path.getmtime(os.path.join(root, f))
                    except: pass
                for d in dirs:
                    try: mtime_sum += os.path.getmtime(os.path.join(root, d))
                    except: pass
        except: pass
        return f"{count}-{mtime_sum}"

    def _monitor_fs(self):
        last_state = self._get_fs_state()
        while self.running.is_set():
            time.sleep(1.5)
            current_state = self._get_fs_state()
            if current_state != last_state:
                last_state = current_state
                if self.discovery: self.discovery.trigger_update()
                self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})
                self.gui_queue.put(('refresh_files',))

    def broadcast(self, msg):
        with self.lock:
            clients = [(cid, conn, mode) for cid, (conn, _, name, ip, mode) in self.client_connections.items() if mode is not None]
        for cid, conn, mode in clients:
            lock = self.send_locks.get(cid)
            if lock:
                with lock:
                    try: enviar_json(conn, msg)
                    except: pass

    def run(self):
        try:
            self.discovery = DiscoveryThread(self.nombre, PUERTO_DESCUBRIMIENTO, PUERTO_CONTROL)
            self.discovery.start()
            threading.Thread(target=self._monitor_fs, daemon=True).start()

            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_sock.bind(('', PUERTO_CONTROL))
            self.tcp_sock.listen(8)
            self.tcp_sock.settimeout(1.0)

            self.running.set()
            self.gui_queue.put(('server_started',))
            log(f"Servidor '{self.nombre}' iniciado en TCP:{PUERTO_CONTROL} UDP:{PUERTO_DESCUBRIMIENTO}")

            while self.running.is_set():
                try:
                    conn, addr = self.tcp_sock.accept()
                    threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
                except socket.timeout: continue
                except Exception as e:
                    if self.running.is_set(): time.sleep(0.1)
        except Exception as e:
            log(f"Error fatal del servidor: {e}")
            self.gui_queue.put(('server_error', str(e)))
        finally:
            self.stop()

    def stop(self):
        self.running.clear()
        if self.discovery: self.discovery.stop()
        if self.tcp_sock: self.tcp_sock.close()
        with self.lock:
            for cid, (conn, *_) in list(self.client_connections.items()):
                try: conn.close()
                except: pass
            self.client_connections.clear()
            self.send_locks.clear()

    def _handle_client(self, conn, addr):
        client_id = None
        send_lock = threading.Lock()
        try:
            conn.settimeout(30)
            mensaje = recibir_json(conn)
            if not mensaje or mensaje.get('type') != 'join':
                conn.close()
                return

            client_name = mensaje.get('name', 'desconocido')
            with self.lock:
                client_id = f"c{self.next_client_id}"
                self.next_client_id += 1
                self.pending_requests[client_id] = {'name': client_name, 'ip': addr[0], 'conn': conn}
                self.client_connections[client_id] = (conn, threading.current_thread(), client_name, addr[0], None)
                self.send_locks[client_id] = send_lock

            self.gui_queue.put(('join_request', client_id, client_name, addr[0]))

            permiso, waited = None, 0
            while self.running.is_set() and waited < 300:
                with self.lock: permiso = self.client_permissions.get(client_id)
                if permiso is not None: break
                time.sleep(0.1)
                waited += 0.1

            if permiso == 'rechazar' or permiso is None:
                enviar_json(conn, {'type': 'join_response', 'status': 'rejected'}, send_lock)
                conn.close()
                with self.lock:
                    self.pending_requests.pop(client_id, None)
                    self.client_connections.pop(client_id, None)
                    self.send_locks.pop(client_id, None)
                self.gui_queue.put(('client_rejected', client_id))
                return

            mode = permiso
            if not enviar_json(conn, {'type': 'join_response', 'status': 'ok', 'mode': mode}, send_lock):
                conn.close()
                return

            with self.lock:
                self.pending_requests.pop(client_id, None)
                self.client_connections[client_id] = (conn, threading.current_thread(), client_name, addr[0], mode)

            self.gui_queue.put(('client_accepted', client_id, client_name, addr[0], mode))
            conn.settimeout(None)

            while self.running.is_set():
                msg = recibir_json(conn)
                if not msg: break
                msg_type = msg.get('type')
                req_id = msg.get('request_id', '')

                try:
                    if msg_type == 'list':
                        target_dir = safe_rel_path(self.carpeta_drive, msg.get('path', ''))
                        if not target_dir or not os.path.isdir(target_dir):
                            raise Exception('Ruta inválida')
                        items = []
                        for it in os.listdir(target_dir):
                            full = os.path.join(target_dir, it)
                            is_dir = os.path.isdir(full)
                            size = os.path.getsize(full) if not is_dir else 0
                            items.append({'name': it, 'is_dir': is_dir, 'size': size})
                        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                        enviar_json(conn, {'type': 'list_response', 'items': items, 'request_id': req_id}, send_lock)

                    elif msg_type == 'create_folder' and mode == 'completo':
                        target = safe_rel_path(self.carpeta_drive, msg.get('path', ''))
                        if not target: raise Exception('Ruta inválida')
                        os.makedirs(target, exist_ok=True)
                        enviar_json(conn, {'type': 'folder_created', 'request_id': req_id}, send_lock)
                        self.gui_queue.put(('refresh_files',))
                        self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})

                    elif msg_type == 'create_file' and mode == 'completo':
                        target = safe_rel_path(self.carpeta_drive, msg.get('path', ''))
                        if not target: raise Exception('Ruta inválida')
                        open(target, 'a').close()
                        enviar_json(conn, {'type': 'file_created', 'request_id': req_id}, send_lock)
                        self.gui_queue.put(('refresh_files',))
                        self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})

                    elif msg_type == 'rename' and mode == 'completo':
                        old = safe_rel_path(self.carpeta_drive, msg.get('old', ''))
                        new = safe_rel_path(self.carpeta_drive, msg.get('new', ''))
                        if not old or not new: raise Exception('Ruta inválida')
                        os.makedirs(os.path.dirname(new), exist_ok=True)
                        os.rename(old, new)
                        enviar_json(conn, {'type': 'rename_done', 'request_id': req_id}, send_lock)
                        self.gui_queue.put(('refresh_files',))
                        self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})

                    elif msg_type == 'read_text':
                        target = safe_rel_path(self.carpeta_drive, msg.get('filepath', ''))
                        if not target or not os.path.isfile(target): raise Exception('Archivo no encontrado')
                        if os.path.getsize(target) > 5*1024*1024:
                            raise Exception('Archivo demasiado grande (máx 5MB)')
                        with open(target, 'r', encoding='utf-8') as f:
                            content = f.read()
                        enviar_json(conn, {'type': 'text_content', 'content': content, 'request_id': req_id}, send_lock)

                    elif msg_type == 'save_text' and mode == 'completo':
                        target = safe_rel_path(self.carpeta_drive, msg.get('filepath', ''))
                        if not target: raise Exception('Ruta inválida')
                        with open(target, 'w', encoding='utf-8') as f:
                            f.write(msg.get('content', ''))
                        enviar_json(conn, {'type': 'save_done', 'request_id': req_id}, send_lock)
                        self.gui_queue.put(('refresh_files',))
                        self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})

                    elif msg_type == 'download':
                        target = safe_rel_path(self.carpeta_drive, msg.get('filepath', ''))
                        if not target or not os.path.isfile(target): raise Exception('Archivo no encontrado')
                        size = os.path.getsize(target)
                        with send_lock:
                            enviar_json(conn, {'type': 'download_ready', 'size': size, 'request_id': req_id})
                            with open(target, 'rb') as f:
                                while True:
                                    chunk = f.read(TAM_BUFFER)
                                    if not chunk: break
                                    conn.sendall(chunk)
                        self.gui_queue.put(('file_downloaded', client_name, os.path.basename(target)))

                    elif msg_type == 'download_folder':
                        target_dir = safe_rel_path(self.carpeta_drive, msg.get('path', ''))
                        if not target_dir or not os.path.isdir(target_dir): raise Exception('Directorio no encontrado')
                        fd, temp_zip = tempfile.mkstemp(suffix='.zip')
                        os.close(fd)
                        try:
                            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for root_dir, _, files in os.walk(target_dir):
                                    for f in files:
                                        abs_file = os.path.join(root_dir, f)
                                        rel_file = os.path.relpath(abs_file, target_dir)
                                        zf.write(abs_file, arcname=rel_file)
                            size = os.path.getsize(temp_zip)
                            with send_lock:
                                enviar_json(conn, {'type': 'download_ready', 'size': size, 'request_id': req_id})
                                with open(temp_zip, 'rb') as f:
                                    while True:
                                        chunk = f.read(TAM_BUFFER)
                                        if not chunk: break
                                        conn.sendall(chunk)
                            self.gui_queue.put(('file_downloaded', client_name, os.path.basename(target_dir)+".zip"))
                        finally:
                            try: os.remove(temp_zip)
                            except: pass

                    elif msg_type == 'upload' and mode == 'completo':
                        fname = os.path.basename(msg.get('filename', ''))
                        target_dir = safe_rel_path(self.carpeta_drive, msg.get('path', ''))
                        size = int(msg.get('size', 0))
                        if not fname or not target_dir or size <= 0: raise Exception('Petición inválida')
                        target_file = os.path.join(target_dir, fname)
                        received = 0
                        with open(target_file, 'wb') as f:
                            while received < size:
                                chunk = conn.recv(min(TAM_BUFFER, size - received))
                                if not chunk: break
                                f.write(chunk)
                                received += len(chunk)
                        if received == size:
                            enviar_json(conn, {'type': 'upload_done', 'request_id': req_id}, send_lock)
                            self.gui_queue.put(('file_uploaded', client_name, fname))
                            self.broadcast({'type': 'update', 'request_id': 'update_broadcast'})
                        else:
                            try: os.remove(target_file)
                            except: pass
                            raise Exception('Transferencia incompleta')

                    else:
                        raise Exception('Comando desconocido o sin permisos')

                except Exception as e:
                    log(f"Error manejando {msg_type} de {client_name}: {e}")
                    try:
                        enviar_json(conn, {'type': 'error', 'message': str(e), 'request_id': req_id}, send_lock)
                    except: pass

        except Exception as e:
            log(f"Excepción en hilo de {client_name}: {e}")
        finally:
            try: conn.close()
            except: pass
            if client_id:
                with self.lock:
                    self.pending_requests.pop(client_id, None)
                    self.client_permissions.pop(client_id, None)
                    self.client_connections.pop(client_id, None)
                    self.send_locks.pop(client_id, None)
                self.gui_queue.put(('client_disconnected', client_id))

    def set_permission(self, client_id, permiso):
        with self.lock: self.client_permissions[client_id] = permiso

    def get_connected_clients(self):
        with self.lock:
            return {cid: (name, ip, mode) for cid, (_, _, name, ip, mode) in self.client_connections.items() if mode is not None}

    def change_client_permission(self, client_id, new_permission):
        with self.lock:
            if client_id in self.client_connections:
                conn, thread, name, ip, _ = self.client_connections[client_id]
                self.client_connections[client_id] = (conn, thread, name, ip, new_permission)
                self.gui_queue.put(('permission_changed', client_id, name, new_permission))

    def disconnect_client(self, client_id):
        with self.lock:
            if client_id in self.client_connections:
                conn, *_ = self.client_connections.pop(client_id)
                try: conn.close()
                except: pass
                self.gui_queue.put(('client_kicked', client_id))
                self.send_locks.pop(client_id, None)

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Monojo Drive LAN - Servidor")
        self.root.geometry("1200x850")

        self.settings = {"nombre": "MonojoDrive", "carpeta": os.path.abspath("MonojoDrive")}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f: self.settings.update(json.load(f))
            except: pass

        self.gui_queue = queue.Queue()
        self.server = None
        self._crear_ui()
        self.root.after(200, self._process_queue)

    def _crear_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill='both', expand=True)

        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding=8)
        config_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(config_frame, text="Nombre:").grid(row=0, column=0, sticky='w', padx=5)
        self.nombre_var = tk.StringVar(value=self.settings.get("nombre"))
        self.entry_nombre = ttk.Entry(config_frame, textvariable=self.nombre_var, width=30)
        self.entry_nombre.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(config_frame, text="Carpeta base:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.carpeta_var = tk.StringVar(value=self.settings.get("carpeta"))
        self.entry_carpeta = ttk.Entry(config_frame, textvariable=self.carpeta_var, width=30)
        self.entry_carpeta.grid(row=1, column=1, sticky='w', padx=5)
        ttk.Button(config_frame, text="📁 Elegir", command=self._elegir_carpeta).grid(row=1, column=2, padx=5)

        ctrl_frame = ttk.Frame(config_frame)
        ctrl_frame.grid(row=2, column=0, columnspan=3, sticky='w', padx=5, pady=8)

        self.btn_iniciar = ttk.Button(ctrl_frame, text="▶️ Iniciar servidor", command=self._iniciar_servidor)
        self.btn_iniciar.pack(side='left', padx=5)
        self.btn_detener = ttk.Button(ctrl_frame, text="⏹️ Detener", command=self._detener_servidor, state='disabled')
        self.btn_detener.pack(side='left', padx=5)
        self.estado_lbl = ttk.Label(ctrl_frame, text="● Detenido", foreground="red", font=('Arial', 10, 'bold'))
        self.estado_lbl.pack(side='left', padx=20)

        contenedor = ttk.Frame(main_frame)
        contenedor.pack(fill='both', expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(contenedor)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 2))
        ttk.Label(left_frame, text="Solicitudes pendientes", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        self.pending_list = tk.Listbox(left_frame, height=8)
        self.pending_list.pack(fill='both', expand=True, side='left')
        scroll = ttk.Scrollbar(left_frame, command=self.pending_list.yview)
        scroll.pack(side='right', fill='y')
        self.pending_list.config(yscrollcommand=scroll.set)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(action_frame, text="✗ Rechazar", command=lambda: self._handle_action("rechazar")).pack(side='left', padx=5)
        ttk.Button(action_frame, text="⬇️ Solo descarga", command=lambda: self._handle_action("descarga")).pack(side='left', padx=5)
        ttk.Button(action_frame, text="↕️ Completo", command=lambda: self._handle_action("completo")).pack(side='left', padx=5)

        right_frame = ttk.Frame(contenedor)
        right_frame.pack(side='right', fill='both', expand=True, padx=(2, 0))
        ttk.Label(right_frame, text="Miembros activos", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        self.members_tree = ttk.Treeview(right_frame, columns=('nombre', 'ip', 'permisos'), show='headings', height=8)
        self.members_tree.heading('nombre', text='Nombre')
        self.members_tree.heading('ip', text='IP')
        self.members_tree.heading('permisos', text='Permisos')
        self.members_tree.pack(fill='both', expand=True, side='left')
        scroll2 = ttk.Scrollbar(right_frame, command=self.members_tree.yview)
        scroll2.pack(side='right', fill='y')
        self.members_tree.config(yscrollcommand=scroll2.set)

        members_action_frame = ttk.Frame(main_frame)
        members_action_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(members_action_frame, text="📝 Permisos", command=self._cambiar_permisos).pack(side='left', padx=5)
        ttk.Button(members_action_frame, text="🔌 Expulsar", command=self._expulsar).pack(side='left', padx=5)

        files_frame = ttk.LabelFrame(main_frame, text="Contenido del Drive (Server)", padding=8)
        files_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.files_list = tk.Listbox(files_frame)
        self.files_list.pack(fill='both', expand=True, side='left')
        scroll3 = ttk.Scrollbar(files_frame, command=self.files_list.yview)
        scroll3.pack(side='right', fill='y')
        self.files_list.config(yscrollcommand=scroll3.set)

        ttk.Button(main_frame, text="🔄 Refrescar contenido manual", command=self._refresh_files).pack(pady=5)

    def _elegir_carpeta(self):
        sel = filedialog.askdirectory()
        if sel: self.carpeta_var.set(sel)

    def _iniciar_servidor(self):
        if self.server: return
        carpeta = self.carpeta_var.get().strip()
        nombre = self.nombre_var.get().strip() or "MonojoDrive"
        if not os.path.isdir(carpeta):
            try: os.makedirs(carpeta, exist_ok=True)
            except: return messagebox.showerror("Error", "Ruta inválida")
        with open(SETTINGS_FILE, "w") as f: json.dump({"nombre": nombre, "carpeta": carpeta}, f)
        self.server = MonojoServer(carpeta, nombre, self.gui_queue)
        self.server.start()
        self.entry_nombre.config(state='disabled')
        self.entry_carpeta.config(state='disabled')
        self.btn_iniciar.config(state='disabled')
        self.btn_detener.config(state='normal')
        self.estado_lbl.config(text="● En ejecución", foreground="green")

    def _detener_servidor(self):
        if not self.server: return
        if messagebox.askyesno("Detener", "¿Detener el servidor?"):
            self.server.stop()
            self.server = None
            self.entry_nombre.config(state='normal')
            self.entry_carpeta.config(state='normal')
            self.btn_iniciar.config(state='normal')
            self.btn_detener.config(state='disabled')
            self.estado_lbl.config(text="● Detenido", foreground="red")
            self.pending_list.delete(0, 'end')
            self.members_tree.delete(*self.members_tree.get_children())

    def _handle_action(self, permiso):
        sel = self.pending_list.curselection()
        if not sel: return
        try: client_id = self.pending_list.get(sel[0]).split(' ')[0]
        except: return
        if self.server:
            self.server.set_permission(client_id, permiso)
            self.pending_list.delete(sel[0])

    def _cambiar_permisos(self):
        sel = self.members_tree.selection()
        if not sel: return
        client_id = sel[0]
        v = tk.Toplevel(self.root)
        v.geometry("300x150")
        var = tk.StringVar(value="")
        ttk.Radiobutton(v, text="Descarga", variable=var, value="descarga").pack(pady=5)
        ttk.Radiobutton(v, text="Completo", variable=var, value="completo").pack(pady=5)
        def aplicar():
            if var.get(): self.server.change_client_permission(client_id, var.get()); v.destroy()
        ttk.Button(v, text="Aplicar", command=aplicar).pack(pady=10)

    def _expulsar(self):
        sel = self.members_tree.selection()
        if sel and self.server: self.server.disconnect_client(sel[0])

    def _refrescar_miembros(self):
        self.members_tree.delete(*self.members_tree.get_children())
        if self.server:
            for cid, (nombre, ip, modo) in self.server.get_connected_clients().items():
                self.members_tree.insert('', 'end', iid=cid, values=(nombre, ip, modo))

    def _refresh_files(self):
        self.files_list.delete(0, 'end')
        carpeta = self.carpeta_var.get()
        if not os.path.isdir(carpeta): return
        try:
            for root, _, files in os.walk(carpeta):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), carpeta)
                    self.files_list.insert('end', rel)
        except: pass

    def _process_queue(self):
        while True:
            try: item = self.gui_queue.get_nowait()
            except queue.Empty: break
            ev = item[0]
            if ev == 'join_request':
                self.pending_list.insert('end', f"{item[1]} {item[2]} @ {item[3]}")
            elif ev in ('client_accepted', 'client_disconnected', 'client_kicked', 'permission_changed'):
                for i in range(self.pending_list.size()):
                    if self.pending_list.get(i).startswith(item[1] + ' '):
                        self.pending_list.delete(i); break
                self._refrescar_miembros()
            elif ev == 'refresh_files':
                self._refresh_files()
        self.root.after(200, self._process_queue)

if __name__ == "__main__":
    root = tk.Tk(className="monojo_drive_lan_server")
    app = ServerGUI(root)
    root.mainloop()
