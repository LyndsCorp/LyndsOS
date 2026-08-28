#!/bin/python3

# Copyright (C) 2026 David Baña Szymaniak
# Licencia GPL v3 o posterior
# Proyecto: Monojo Project

import socket
import threading
import sys
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, Menu
from PIL import Image, ImageTk
import os
import time
import hashlib
import base64

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("Advertencia: La librería 'cryptography' no está instalada.")
    print("El servidor no podrá descifrar mensajes sin ella. Instálala con: pip install cryptography")
    print("O con: sudo apt install python3-cryptography")

# ============================
# CONFIGURACIÓN
# ============================
TCP_PORT = 6405
UDP_PORT = 6406
BUFFER = 4096

clientes_map = {}
banned_ips = {}
stop_event = threading.Event()
server_socket = None

BASE_DIR = "/usr/share/icons/hicolor/512x512/apps"
ICON_PATH = os.path.join(BASE_DIR, "monojo-server.png")
NOMBRE_SALA = None
PASSWORD_REQUIRED = False
PASSWORD = None
crypto = None

class CryptoHandler:
    def __init__(self, password=None):
        self.password = password
        if password is not None:
            self.key = hashlib.sha256(password.encode()).digest()
        else:
            self.key = None

    def encrypt(self, plaintext: str) -> str:
        if self.key is None:
            return plaintext
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(self.key), modes.ECB())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode()

    def decrypt(self, ciphertext_str: str) -> str | None:
        if self.key is None:
            return ciphertext_str
        try:
            data = base64.b64decode(ciphertext_str)
            cipher = Cipher(algorithms.AES(self.key), modes.ECB())
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(data) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            return plaintext.decode()
        except Exception:
            return None

def get_local_ip():
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

def is_banned(ip):
    if ip in banned_ips:
        exp = banned_ips[ip]
        if exp is None:
            return True
        if time.time() < exp:
            return True
        else:
            del banned_ips[ip]
            return False
    return False

def transmitir(mensaje, cliente_excluir=None):
    for client in list(clientes_map.keys()):
        if client != cliente_excluir:
            try:
                client.send((mensaje + "\n").encode("utf-8"))
            except:
                clientes_map.pop(client, None)
                try: client.close()
                except: pass

def manejar_cliente(client_socket, addr, text_area):
    ip_cliente = addr[0]
    if is_banned(ip_cliente):
        try: client_socket.close()
        except: pass
        return

    nombre_usuario = f"Usuario_{ip_cliente}"
    try:
        nombre_data = client_socket.recv(BUFFER)
        if not nombre_data: raise ConnectionResetError("No se recibió el nombre")
        nombre_usuario = nombre_data.decode("utf-8")
        clientes_map[client_socket] = (nombre_usuario, ip_cliente)

        if PASSWORD_REQUIRED:
            client_socket.send(b"PASSWORD_REQUIRED\n")
        else:
            client_socket.send(b"NO_PASSWORD\n")

        msg_conexion = f"[Entró {nombre_usuario} ({ip_cliente})]"
        mostrar_mensaje(text_area, msg_conexion, "verde")
        transmitir(msg_conexion, client_socket)
        actualizar_lista()
    except:
        try: client_socket.close()
        except: pass
        return

    while not stop_event.is_set():
        try:
            data = client_socket.recv(BUFFER)
            if not data: break
            buffer = data.decode("utf-8")
            for linea in buffer.split('\n'):
                if linea.strip():
                    mensaje = linea.strip()
                    if crypto is not None:
                        texto_claro = crypto.decrypt(mensaje)
                        if texto_claro is not None:
                            mostrar_mensaje(text_area, f"{nombre_usuario}: {texto_claro}", "negro")
                        else:
                            mostrar_mensaje(text_area, f"{nombre_usuario}: [PUSO CONTRASEÑA INCORRECTA] {mensaje}", "rojo")
                    else:
                        mostrar_mensaje(text_area, f"{nombre_usuario}: {mensaje}", "negro")
                    # Retransmitir sin salto de línea inicial
                    transmitir(f"{nombre_usuario} ({ip_cliente}): {mensaje}", client_socket)
        except:
            break

    if client_socket in clientes_map:
        del clientes_map[client_socket]
    msg_desconexion = f"[Salió {nombre_usuario} ({ip_cliente})]"
    mostrar_mensaje(text_area, msg_desconexion, "rojo")
    transmitir(msg_desconexion, None)
    try: client_socket.close()
    except: pass
    actualizar_lista()

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

def responder_broadcast():
    global NOMBRE_SALA, PASSWORD_REQUIRED
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.bind(('', UDP_PORT))
    while not stop_event.is_set():
        try:
            data, addr = udp_sock.recvfrom(1024)
            if data.decode() == "DISCOVER" and NOMBRE_SALA:
                respuesta = f"{NOMBRE_SALA}|{get_local_ip()}|{1 if PASSWORD_REQUIRED else 0}"
                udp_sock.sendto(respuesta.encode(), addr)
        except:
            break
    udp_sock.close()

def actualizar_lista():
    lista_usuarios.delete(0, tk.END)
    for sock, (nombre, ip) in clientes_map.items():
        lista_usuarios.insert(tk.END, f"{nombre} ({ip})")

def obtener_socket_seleccionado():
    seleccion = lista_usuarios.curselection()
    if not seleccion:
        return None
    indice = seleccion[0]
    sockets = list(clientes_map.keys())
    if indice < len(sockets):
        return sockets[indice]
    return None

def renombrar_usuario():
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    nombre_actual, ip = clientes_map[sock]
    nuevo_nombre = simpledialog.askstring("Renombrar", f"Nuevo nombre para {nombre_actual}:")
    if nuevo_nombre and nuevo_nombre.strip():
        clientes_map[sock] = (nuevo_nombre.strip(), ip)
        actualizar_lista()
        transmitir(f"[Admin] {nombre_actual} ahora es {nuevo_nombre.strip()}", None)
        mostrar_mensaje(text_area, f"[Admin] {nombre_actual} renombrado a {nuevo_nombre.strip()}", "azul")

def expulsar_usuario():
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    nombre, ip = clientes_map[sock]
    try:
        sock.send(b"[KICKED]\n")
    except:
        pass
    sock.close()
    transmitir(f"[Admin] {nombre} fue expulsado", None)
    mostrar_mensaje(text_area, f"[Admin] {nombre} expulsado", "azul")

def banear_ip():
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    nombre, ip = clientes_map[sock]
    banned_ips[ip] = None
    for s, (n, i) in list(clientes_map.items()):
        if i == ip:
            try:
                s.send(b"[KICKED]\n")
            except:
                pass
            s.close()
    transmitir(f"[Admin] IP {ip} baneada permanentemente", None)
    mostrar_mensaje(text_area, f"[Admin] IP {ip} baneada permanentemente", "azul")

def banear_temporal():
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    nombre, ip = clientes_map[sock]
    segundos = simpledialog.askinteger("Ban temporal", f"Segundos para banear {ip}:", minvalue=1)
    if segundos:
        banned_ips[ip] = time.time() + segundos
        for s, (n, i) in list(clientes_map.items()):
            if i == ip:
                try:
                    s.send(b"[KICKED]\n")
                except:
                    pass
                s.close()
        transmitir(f"[Admin] IP {ip} baneada por {segundos} segundos", None)
        mostrar_mensaje(text_area, f"[Admin] IP {ip} baneada temporalmente por {segundos}s", "azul")

def desbanear_ip():
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    nombre, ip = clientes_map[sock]
    if ip in banned_ips:
        del banned_ips[ip]
        transmitir(f"[Admin] IP {ip} desbaneada", None)
        mostrar_mensaje(text_area, f"[Admin] IP {ip} desbaneada", "azul")
    else:
        messagebox.showinfo("Info", f"La IP {ip} no está baneada.")

def mostrar_menu_contextual(event):
    sock = obtener_socket_seleccionado()
    if not sock:
        return
    menu = Menu(root, tearoff=0)
    menu.add_command(label="Renombrar", command=renombrar_usuario)
    menu.add_command(label="Expulsar", command=expulsar_usuario)
    menu.add_command(label="Banear IP", command=banear_ip)
    menu.add_command(label="Ban temporal", command=banear_temporal)
    menu.add_command(label="Desbanear IP", command=desbanear_ip)
    menu.tk_popup(event.x_root, event.y_root)

def main_servidor():
    global NOMBRE_SALA, PASSWORD_REQUIRED, PASSWORD, crypto, root, text_area, lista_usuarios
    root_temp = tk.Tk()
    root_temp.withdraw()

    NOMBRE_SALA = simpledialog.askstring("Nombre de la Sala", "Ingresa el nombre de la sala de chat:")
    if not NOMBRE_SALA:
        sys.exit()

    quiere_contrasena = messagebox.askyesno("Contraseña", "¿Desea que la sala requiera contraseña?")
    if quiere_contrasena:
        contrasena = simpledialog.askstring("Contraseña", "Ingrese la contraseña (se usará para descifrar mensajes):", show='*')
        if contrasena is None:
            sys.exit()
        PASSWORD_REQUIRED = True
        PASSWORD = contrasena
        crypto = CryptoHandler(PASSWORD)
    else:
        PASSWORD_REQUIRED = False
        PASSWORD = None
        crypto = None

    root_temp.destroy()

    local_ip = get_local_ip()
    root = tk.Tk()
    root.title(f"MonojoChat LAN - SERVIDOR (IP: {local_ip})")
    root.geometry("900x500")
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

    try:
        img = Image.open(ICON_PATH)
        icon = ImageTk.PhotoImage(img)
        root.iconphoto(True, icon)
    except: pass

    text_area = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD)
    text_area.tag_config('verde', foreground='green')
    text_area.tag_config('rojo', foreground='red')
    text_area.tag_config('azul', foreground='blue')
    text_area.tag_config('negro', foreground='black')
    text_area.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

    frame_usuarios = tk.Frame(root)
    frame_usuarios.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.Y)
    tk.Label(frame_usuarios, text="Usuarios conectados").pack()
    lista_usuarios = tk.Listbox(frame_usuarios, width=30)
    lista_usuarios.pack(fill=tk.BOTH, expand=True)
    lista_usuarios.bind("<Button-3>", mostrar_menu_contextual)

    threading.Thread(target=iniciar_servidor_tcp, args=(text_area,), daemon=True).start()
    threading.Thread(target=responder_broadcast, daemon=True).start()

    root.mainloop()

if __name__ == "__main__":
    main_servidor()
