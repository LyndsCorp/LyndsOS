#!/bin/python3

# Copyright (C) 2026 David Baña Szymaniak
# Licencia GPL v3 o posterior
# Proyecto: Monojo Project

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import socket
import threading
import sys
import os
from PIL import Image, ImageTk
import time
import subprocess
import hashlib
import base64

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
except ImportError:
    print("Error: La librería 'cryptography' no está instalada.")
    print("Instálala con: pip install cryptography")
    print("O con: sudo apt install python3-cryptography")
    sys.exit(1)

TCP_PORT = 6405
UDP_PORT = 6406
BUFFER = 4096
stop_event = threading.Event()
client_socket = None

BASE_DIR = "/usr/share/icons/hicolor/512x512/apps"
ICON_PATH = os.path.join(BASE_DIR, "monojo-azul.png")

CLIENT_USERNAME = None
LAST_SENDER = None

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
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def mostrar_mensaje(text_area, mensaje, color="negro", needs_separator=True):
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

def descubrir_salas(timeout=2):
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
            partes = data.decode().split("|")
            nombre = partes[0]
            ip = partes[1]
            has_pass = partes[2] == "1" if len(partes) > 2 else False
            salas[nombre] = (ip, has_pass)
        except:
            continue
    udp_sock.close()
    return salas

def procesar_linea(linea, text_area, root, crypto):
    global LAST_SENDER
    mensaje = linea.strip()
    if not mensaje:
        return  # ignorar líneas vacías

    current_sender = None
    needs_separator = True
    mensaje_content_raw = mensaje
    color = "negro"

    if mensaje == "[KICKED]":
        mostrar_mensaje(text_area, "[Has sido expulsado del chat]", "rojo", needs_separator=False)
        root.after(500, lambda: on_closing(root))
        return

    start_paren = mensaje.find('(')
    if start_paren != -1:
        end_paren = mensaje.find(')', start_paren)
        if end_paren != -1:
            current_sender = mensaje[:start_paren].strip()
            mensaje_content_raw = mensaje[end_paren+1:].lstrip(':').strip()
            if not mensaje.startswith('['):
                decrypted = crypto.decrypt(mensaje_content_raw)
                if decrypted is not None:
                    display_content = decrypted
                else:
                    display_content = mensaje_content_raw
                    color = "rojo"
                    if current_sender == CLIENT_USERNAME:
                        mensaje = f"Tú: [CIFRADO] {display_content}"
                    else:
                        mensaje = f"{current_sender}: [PUSO CONTRASEÑA INCORRECTA] {display_content}"
                if color == "negro":
                    if current_sender == CLIENT_USERNAME:
                        mensaje = f"Tú: {display_content}"
                    else:
                        mensaje = f"{current_sender}: {display_content}"

    if mensaje.startswith('[Entró'):
        LAST_SENDER = None
        mostrar_mensaje(text_area, mensaje, "verde", needs_separator=False)
    elif mensaje.startswith('[Salió'):
        LAST_SENDER = None
        mostrar_mensaje(text_area, mensaje, "rojo", needs_separator=False)
    elif mensaje.startswith('[Admin]'):
        LAST_SENDER = None
        mostrar_mensaje(text_area, mensaje, "azul", needs_separator=False)
    else:
        if current_sender and current_sender == LAST_SENDER:
            needs_separator = False
        LAST_SENDER = current_sender
        mostrar_mensaje(text_area, mensaje, color, needs_separator=needs_separator)

        if (not mensaje.startswith('[') and current_sender
            and current_sender != CLIENT_USERNAME and color == "negro"):
            if not getattr(root, 'window_focused', True):
                try:
                    subprocess.run(
                        ['notify-send', '--app-name', 'Monojo Chats LAN', '-i', ICON_PATH,
                         current_sender, display_content if 'display_content' in locals() else mensaje],
                        timeout=1
                    )
                except Exception:
                    pass

def recibir_mensajes(sock, text_area, root, crypto):
    global LAST_SENDER
    buffer = ""
    while not stop_event.is_set():
        try:
            data = sock.recv(BUFFER)
            if not data:
                break
            buffer += data.decode("utf-8")
            while '\n' in buffer:
                linea, buffer = buffer.split('\n', 1)
                if linea.strip():  # solo procesar líneas no vacías
                    procesar_linea(linea, text_area, root, crypto)
        except socket.error:
            if not stop_event.is_set():
                mostrar_mensaje(text_area, "[Conexión perdida]", "rojo")
            break
    if not stop_event.is_set():
        root.after(0, lambda: on_closing(root))

def configurar_envio(sock, entry, text_area, crypto):
    def _enviar_real(event=None):
        global LAST_SENDER
        mensaje_plain = entry.get()
        if mensaje_plain.strip():
            try:
                mensaje_cifrado = crypto.encrypt(mensaje_plain)
                sock.sendall((mensaje_cifrado + "\n").encode("utf-8"))
                needs_separator = True
                if CLIENT_USERNAME == LAST_SENDER:
                    needs_separator = False
                LAST_SENDER = CLIENT_USERNAME
                mostrar_mensaje(text_area, f"Tú: {mensaje_plain}", "negro", needs_separator=needs_separator)
            except Exception as e:
                mostrar_mensaje(text_area, f"[Error al enviar: {e}]", "rojo")
            finally:
                entry.delete(0, tk.END)
    return _enviar_real

def iniciar_chat_con_ip(ip_server):
    global client_socket, CLIENT_USERNAME
    stop_event.clear()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip_server, TCP_PORT))
        client_socket = sock
        sock.sendall(CLIENT_USERNAME.encode("utf-8"))

        control_msg = sock.recv(BUFFER).decode().strip()
        sock.settimeout(None)

        password = None
        if control_msg == "PASSWORD_REQUIRED":
            password = simpledialog.askstring("Contraseña", "Esta sala requiere contraseña.\nIngresa la contraseña:", show='*')
            if password is None:
                sock.close()
                return

        crypto = CryptoHandler(password)
    except Exception as e:
        messagebox.showerror("Error de Conexión", f"No se pudo conectar a {ip_server}. Error: {e}")
        return

    root = tk.Tk(className="monojo_chats_lan_main")
    root.title(f"Monojo Chats LAN - {CLIENT_USERNAME} -> Conectado a {ip_server}")
    root.geometry("500x510")
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

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
    text_area.tag_config('azul', foreground='blue')
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
    mostrar_mensaje(text_area, f"[Conectado a {ip_server}:{TCP_PORT}]", "verde", needs_separator=False)

    entry.config(state=tk.NORMAL)
    envio_handler = configurar_envio(client_socket, entry, text_area, crypto)
    boton.config(state=tk.NORMAL, command=envio_handler)
    entry.bind("<Return>", envio_handler)

    threading.Thread(target=recibir_mensajes, args=(sock, text_area, root, crypto), daemon=True).start()

    root.mainloop()

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
        display = f"{nombre} {'(con contraseña)' if salas[nombre][1] else ''}"
        lista_salas.insert(tk.END, display)

    def conectar_desde_lista(event):
        seleccion = lista_salas.curselection()
        if seleccion:
            nombre = list(salas.keys())[seleccion[0]]
            ip_server = salas[nombre][0]
            root.destroy()
            iniciar_chat_con_ip(ip_server)

    lista_salas.bind("<Double-1>", conectar_desde_lista)
    root.mainloop()

if __name__ == "__main__":
    CLIENT_USERNAME = simpledialog.askstring("Nombre de Usuario", "Ingresa tu nombre de usuario:")
    if not CLIENT_USERNAME:
        sys.exit()
    seleccionar_sala()
