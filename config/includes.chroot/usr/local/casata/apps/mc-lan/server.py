#!/bin/python3
import socket
import threading
import sys
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from PIL import Image, ImageTk
import os

# ============================
# CONFIGURACIÓN
# ============================
TCP_PORT = 6405
UDP_PORT = 6406
BUFFER = 4096

clientes_map = {}
stop_event = threading.Event()
server_socket = None

BASE_DIR = "/usr/share/icons/hicolor/512x512/apps"
ICON_PATH = os.path.join(BASE_DIR, "monojo-server.png")
NOMBRE_SALA = None

# ============================
# UTILIDADES
# ============================

def get_local_ip():
    """Devuelve la IP LAN de la máquina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def mostrar_mensaje(text_area, mensaje, color="negro"):
    text_area.config(state=tk.NORMAL)
    text_area.insert(tk.END, mensaje + "\n", color)
    text_area.config(state=tk.DISABLED)
    text_area.yview(tk.END)

def on_closing(root):
    global server_socket
    stop_event.set()
    for client in list(clientes_map.keys()):
        try: client.close()
        except: pass
    if server_socket:
        try: server_socket.close()
        except: pass
    root.destroy()

# ============================
# SERVIDOR TCP
# ============================

def transmitir(mensaje, cliente_excluir=None):
    for client in list(clientes_map.keys()):
        if client != cliente_excluir:
            try:
                client.send(mensaje.encode("utf-8"))
            except:
                clientes_map.pop(client, None)
                try: client.close()
                except: pass

def manejar_cliente(client_socket, addr, text_area):
    ip_cliente = addr[0]
    nombre_usuario = f"Usuario_{ip_cliente}"
    try:
        nombre_data = client_socket.recv(BUFFER)
        if not nombre_data: raise ConnectionResetError("No se recibió el nombre")
        nombre_usuario = nombre_data.decode("utf-8")
        clientes_map[client_socket] = nombre_usuario
        msg_conexion = f"[Entró {nombre_usuario} ({ip_cliente})]"
        mostrar_mensaje(text_area, msg_conexion, "verde")
        transmitir(msg_conexion, client_socket)
    except:
        try: client_socket.close()
        except: pass
        return

    while not stop_event.is_set():
        try:
            data = client_socket.recv(BUFFER)
            if not data: break
            mensaje = data.decode("utf-8")
            mostrar_mensaje(text_area, f"{nombre_usuario}: {mensaje}", "negro")
            transmitir(f"\n{nombre_usuario} ({ip_cliente}): {mensaje}", client_socket)
        except: break

    if client_socket in clientes_map:
        del clientes_map[client_socket]
    msg_desconexion = f"[Salió {nombre_usuario} ({ip_cliente})]"
    mostrar_mensaje(text_area, msg_desconexion, "rojo")
    transmitir(msg_desconexion, None)
    try: client_socket.close()
    except: pass

def iniciar_servidor_tcp(text_area):
    global server_socket
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', TCP_PORT))
        server_socket.listen()
        local_ip = get_local_ip()
        mostrar_mensaje(text_area, f"*** SERVIDOR INICIADO ***\nIP: {local_ip}:{TCP_PORT}\nEscuchando conexiones...", "verde")
        while not stop_event.is_set():
            try:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=manejar_cliente, args=(client_socket, addr, text_area), daemon=True).start()
            except Exception as e:
                if not stop_event.is_set():
                    mostrar_mensaje(text_area, f"[ERROR al aceptar conexión: {e}]", "rojo")
                break
    except Exception as e:
        messagebox.showerror("Error del Servidor", f"No se pudo iniciar el servidor. Error: {e}")
        root = text_area.winfo_toplevel()
        root.after(0, lambda: on_closing(root))

# ============================
# SERVIDOR UDP PARA DESCUBRIMIENTO
# ============================

def responder_broadcast():
    global NOMBRE_SALA
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.bind(('', UDP_PORT))
    while not stop_event.is_set():
        try:
            data, addr = udp_sock.recvfrom(1024)
            if data.decode() == "DISCOVER" and NOMBRE_SALA:
                respuesta = f"{NOMBRE_SALA}|{get_local_ip()}"
                udp_sock.sendto(respuesta.encode(), addr)
        except:
            break
    udp_sock.close()

# ============================
# INTERFAZ
# ============================

def main_servidor():
    global NOMBRE_SALA
    root_temp = tk.Tk()
    root_temp.withdraw()
    NOMBRE_SALA = simpledialog.askstring("Nombre de la Sala", "Ingresa el nombre de la sala de chat:")
    if not NOMBRE_SALA: sys.exit()
    root_temp.destroy()

    local_ip = get_local_ip()
    root = tk.Tk()
    root.title(f"MonojoChat LAN - SERVIDOR (IP: {local_ip})")
    root.geometry("600x450")
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

    try:
        img = Image.open(ICON_PATH)
        icon = ImageTk.PhotoImage(img)
        root.iconphoto(True, icon)
    except: pass

    text_area = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
    text_area.tag_config('verde', foreground='green')
    text_area.tag_config('rojo', foreground='red')
    text_area.tag_config('negro', foreground='black')
    text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    threading.Thread(target=iniciar_servidor_tcp, args=(text_area,), daemon=True).start()
    threading.Thread(target=responder_broadcast, daemon=True).start()

    root.mainloop()

if __name__ == "__main__":
    main_servidor()

