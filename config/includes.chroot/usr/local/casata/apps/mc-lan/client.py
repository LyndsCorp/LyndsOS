#!/bin/python3

# Monojo Chats LAN 2.1: Ahora incluye notificaciones :)
# Licencia GPL v3, Monojo Project, David Baña Szymaniak

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import socket
import threading
import sys
import os
from PIL import Image, ImageTk
import time
import subprocess

# ============================
# CONFIGURACIÓN
# ============================

TCP_PORT = 6405
UDP_PORT = 6406
BUFFER = 4096
stop_event = threading.Event()
client_socket = None

BASE_DIR = "/usr/share/icons/hicolor/512x512/apps"
ICON_PATH = os.path.join(BASE_DIR, "monojo-azul.png")

CLIENT_USERNAME = None
LAST_SENDER = None  # Último remitente mostrado

# ============================
# FUNCIONES AUXILIARES
# ============================

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def mostrar_mensaje(text_area, mensaje, color="negro", needs_separator=True):
    """Muestra mensajes en el área de texto con saltos condicionales"""
    text_area.config(state=tk.NORMAL)
    if needs_separator:
        text_area.insert(tk.END, "\n")
    text_area.insert(tk.END, mensaje + "\n", color)
    text_area.config(state=tk.DISABLED)
    text_area.yview(tk.END)

def on_closing(root):
    global client_socket
    stop_event.set()
    try:
        if client_socket:
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
    except:
        pass
    root.destroy()

# ============================
# DESCUBRIMIENTO DE SALAS
# ============================

def descubrir_salas(timeout=2):
    """Busca servidores en LAN usando broadcast UDP"""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.settimeout(timeout)
    try:
        udp_sock.sendto(b"DISCOVER", ('255.255.255.255', UDP_PORT))
    except:
        pass

    salas = {}
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            data, addr = udp_sock.recvfrom(1024)
            nombre, ip = data.decode().split("|")
            salas[nombre] = ip
        except:
            continue
    udp_sock.close()
    return salas

# ============================
# CHAT
# ============================

def recibir_mensajes(sock, text_area, root):
    global LAST_SENDER
    while not stop_event.is_set():
        try:
            data = sock.recv(BUFFER)
            if not data:
                break
            mensaje = data.decode("utf-8").strip()
            current_sender = None
            needs_separator = True
            mensaje_content_raw = mensaje  # por defecto

            # Detectar remitente eliminando la IP entre paréntesis
            start_paren = mensaje.find('(')
            if start_paren != -1:
                end_paren = mensaje.find(')', start_paren)
                if end_paren != -1:
                    current_sender = mensaje[:start_paren].strip()
                    # Extraer el contenido real del mensaje (quitando ':' y espacios)
                    mensaje_content_raw = mensaje[end_paren+1:].lstrip(':').strip()
                    # Reconstruir para mostrar en el chat con formato "Remitente: contenido"
                    mensaje = f"{current_sender}: {mensaje_content_raw}"
                else:
                    # Si no hay cierre de paréntesis, dejamos como está
                    mensaje_content_raw = mensaje
            else:
                # Sin paréntesis, asumimos que no hay remitente identificable
                mensaje_content_raw = mensaje

            if current_sender and current_sender == LAST_SENDER:
                needs_separator = False

            # Mensajes de sistema
            if mensaje.startswith('[Entró'):
                LAST_SENDER = None
                mostrar_mensaje(text_area, mensaje, "verde", needs_separator=False)

            elif mensaje.startswith('[Salió'):
                LAST_SENDER = None
                mostrar_mensaje(text_area, mensaje, "rojo", needs_separator=False)

            else:
                LAST_SENDER = current_sender
                # Mostrar en el chat
                mostrar_mensaje(text_area,
                                mensaje if current_sender != CLIENT_USERNAME else f"Tú: {mensaje_content_raw}",
                                "negro", needs_separator=needs_separator)

                # NOTIFICACIÓN NATIVA: solo para mensajes de otros usuarios y si la ventana NO está activa
                if not mensaje.startswith('[') and current_sender and current_sender != CLIENT_USERNAME:
                    if not getattr(root, 'window_focused', True):
                        try:
                            subprocess.run(
                                ['notify-send', '--app-name', 'Monojo Chats LAN', '-i', ICON_PATH,
                                 current_sender, mensaje_content_raw],
                                timeout=1
                            )
                        except Exception:
                            pass  # Si notify-send falla, simplemente se ignora
        except:
            if not stop_event.is_set():
                mostrar_mensaje(text_area, "[Conexión perdida o error]", "rojo")
            LAST_SENDER = None
            break
    if not stop_event.is_set():
        root.after(0, lambda: on_closing(root))

def configurar_envio(sock, entry, text_area):
    def _enviar_real(event=None):
        global LAST_SENDER
        mensaje = entry.get()
        if mensaje.strip():
            try:
                sock.sendall(mensaje.encode("utf-8"))
                needs_separator = True
                if CLIENT_USERNAME == LAST_SENDER:
                    needs_separator = False
                LAST_SENDER = CLIENT_USERNAME
                mostrar_mensaje(text_area, f"Tú: {mensaje}", "negro", needs_separator=needs_separator)
            except Exception as e:
                mostrar_mensaje(text_area, f"[Error al enviar: {e}]", "rojo")
            finally:
                entry.delete(0, tk.END)
    return _enviar_real

# ============================
# INICIAR CHAT CON IP
# ============================

def iniciar_chat_con_ip(ip_server):
    global client_socket, CLIENT_USERNAME
    stop_event.clear()

    root = tk.Tk(className="monojo_chats_lan_main")
    root.title(f"Monojo Chats LAN - {CLIENT_USERNAME} -> Conectado a {ip_server}")
    root.geometry("500x500")
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

    # Variable para rastrear el foco de la ventana
    root.window_focused = True

    def on_focus_in(event):
        root.window_focused = True

    def on_focus_out(event):
        root.window_focused = False

    root.bind("<FocusIn>", on_focus_in)
    root.bind("<FocusOut>", on_focus_out)

    text_area = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
    text_area.tag_config('verde', foreground='green')
    text_area.tag_config('rojo', foreground='red')
    text_area.tag_config('negro', foreground='black')
    text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    try:
        img = Image.open(ICON_PATH)
        icon = ImageTk.PhotoImage(img)
        root.iconphoto(True, icon)
    except:
        pass

    entry = tk.Entry(root)
    entry.pack(padx=10, pady=5, fill=tk.X)
    entry.config(state=tk.DISABLED)
    boton = tk.Button(root, text="Enviar", state=tk.DISABLED)
    boton.pack(padx=10, pady=5)

    mostrar_mensaje(text_area, f"[Tu nombre: {CLIENT_USERNAME}]", needs_separator=True)
    mostrar_mensaje(text_area, f"[Conectando a Servidor: {ip_server}:{TCP_PORT}...]", needs_separator=False)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip_server, TCP_PORT))
        client_socket = sock
        sock.sendall(CLIENT_USERNAME.encode("utf-8"))

        mostrar_mensaje(text_area, "[Conectado al servidor]", "verde", needs_separator=False)

        entry.config(state=tk.NORMAL)
        envio_handler = configurar_envio(client_socket, entry, text_area)
        boton.config(state=tk.NORMAL, command=envio_handler)
        entry.bind("<Return>", envio_handler)

        threading.Thread(target=recibir_mensajes, args=(sock, text_area, root), daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error de Conexión", f"No se pudo conectar a {ip_server}. Error: {e}")
        root.destroy()
        return

    root.mainloop()

# ============================
# SELECCIÓN DE SALA
# ============================

def seleccionar_sala():
    global CLIENT_USERNAME
    salas = descubrir_salas()
    if not salas:
        messagebox.showinfo("No hay salas", "No se encontraron salas disponibles en LAN.")
        sys.exit()

    root = tk.Tk(className="monojo_chats_lan_seleccionar_sala")
    root.title("Selecciona Sala Monojo Chats LAN")
    root.geometry("300x300")

    lista_salas = tk.Listbox(root)
    lista_salas.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    for nombre in salas:
        lista_salas.insert(tk.END, nombre)

    def conectar_desde_lista(event):
        seleccion = lista_salas.curselection()
        if seleccion:
            nombre = lista_salas.get(seleccion[0])
            ip_server = salas[nombre]
            root.destroy()
            iniciar_chat_con_ip(ip_server)

    lista_salas.bind("<Double-1>", conectar_desde_lista)
    root.mainloop()

# ============================
# INICIO
# ============================

if __name__ == "__main__":
    CLIENT_USERNAME = simpledialog.askstring("Nombre de Usuario", "Ingresa tu nombre de usuario:")
    if not CLIENT_USERNAME:
        sys.exit()
    seleccionar_sala()
