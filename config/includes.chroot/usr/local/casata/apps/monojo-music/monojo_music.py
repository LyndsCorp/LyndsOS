#!/usr/bin/env python3

# MonojoMusic — Tkinter + ffplay/ffprobe + MPRIS2 (stream renombrado)
# Requisitos: ffplay, ffprobe, python3-dbus, python3-gi
# Depuración en /tmp/monojo_music_debug.log

# Monojo Music 2.0: integración con KDE Connect
# GPL v3 License, Monojo Project, David Baña Szymaniak

import os
import sys
import subprocess
import time
import random
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
import shutil
import threading

# ------------------- Depuración -------------------
DEBUG_LOG = "/tmp/monojo_music_debug.log"
def debug(msg):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(msg, file=sys.stderr)

debug("Iniciando Monojo Music...")

# ------------------- Dependencias MPRIS -------------------
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
    MPRIS_AVAILABLE = True
    debug("Dependencias MPRIS cargadas correctamente.")
except Exception as e:
    MPRIS_AVAILABLE = False
    debug(f"Error al cargar dependencias MPRIS: {e}. Integración multimedia deshabilitada.")

# ------------------- Configuración de rutas -------------------
BASE = Path.home() / ".config" / "MonojoMusic"
MUSIC_DIR = BASE / "Musicas"
PLAYLIST_DIR = BASE / "Playlists"

ICON_PATHS = [
    Path("/usr/share/icons/hicolor/512x512/apps/monojo-amarillo.png"),
    Path.home() / ".local" / "share" / "icons" / "Monojo" / "monojo-amarillo.png",
    Path(__file__).resolve().parent / "monojo-amarillo.png",
]
ICON_PATH = next((p for p in ICON_PATHS if p.exists()), ICON_PATHS[-1])

BASE.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_MS = 250

# ------------------- Detectar ffplay -------------------
FFPLAY_PATH = shutil.which("ffplay")
if not FFPLAY_PATH:
    debug("ERROR: ffplay no encontrado en el sistema.")
    sys.exit(1)

FFPLAY_EXEC = FFPLAY_PATH

# --------------- Nombre que queremos en el panel de sonido ---------------
STREAM_NAME = "Monojo Music"   # Se verá en el mezclador de aplicaciones

# ---------------- Utilidades de audio ----------------
def ffprobe_duration(path):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.DEVNULL, universal_newlines=True
        )
        return float(out.strip())
    except Exception:
        return 0.0

def zenity_select_multiple_files(title="Selecciona archivos", initial_dir=None):
    try:
        cmd = ["zenity", "--file-selection", "--multiple", "--separator=|", "--title=" + title]
        if initial_dir:
            cmd += ["--filename=" + os.path.join(initial_dir, "")]
        out = subprocess.check_output(cmd, universal_newlines=True).strip()
        if not out:
            return []
        return out.split("|")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

# --------------- Clase MPRIS2 ---------------
if MPRIS_AVAILABLE:
    class MonojoMPRIS(dbus.service.Object):
        MEDIA_PLAYER2_IFACE = "org.mpris.MediaPlayer2"
        MEDIA_PLAYER2_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
        PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

        def __init__(self, app, bus):
            self.app = app
            bus_name = dbus.service.BusName("org.mpris.MediaPlayer2.monojo_music", bus)
            super().__init__(bus_name, "/org/mpris/MediaPlayer2")
            self._metadata = {}

        @dbus.service.method(MEDIA_PLAYER2_IFACE, in_signature='', out_signature='')
        def Raise(self):
            try:
                self.app.root.deiconify()
                self.app.root.lift()
            except Exception:
                pass

        @dbus.service.method(MEDIA_PLAYER2_IFACE, in_signature='', out_signature='')
        def Quit(self):
            self.app.on_close()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def PlayPause(self):
            if self.app.is_playing:
                self.app.pause_toggle()
            else:
                self.app.play_selected_or_resume()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def Play(self):
            if not self.app.is_playing:
                self.app.play_selected_or_resume()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def Pause(self):
            if self.app.is_playing:
                self.app.pause_toggle()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def Next(self):
            self.app.next_track()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def Previous(self):
            self.app.prev_track()

        @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='', out_signature='')
        def Stop(self):
            self.app.stop_action()

        @dbus.service.method(PROPERTIES_IFACE, in_signature='ss', out_signature='v')
        def Get(self, interface_name, property_name):
            if interface_name == self.MEDIA_PLAYER2_IFACE:
                return self._get_root_property(property_name)
            elif interface_name == self.MEDIA_PLAYER2_PLAYER_IFACE:
                return self._get_player_property(property_name)
            else:
                return dbus.String("")

        def _get_root_property(self, prop):
            props = {
                "CanQuit": True,
                "CanRaise": True,
                "Identity": "Monojo Music",
                "DesktopEntry": "monojo-music",
                "SupportedUriSchemes": dbus.Array(["file"], signature='s'),
                "SupportedMimeTypes": dbus.Array(["audio/mpeg","audio/ogg","audio/flac","audio/x-wav"], signature='s')
            }
            return props.get(prop, dbus.String(""))

        def _get_player_property(self, prop):
            if prop == "PlaybackStatus":
                if self.app.is_playing:
                    return "Playing"
                elif self.app.paused_flag:
                    return "Paused"
                else:
                    return "Stopped"
            elif prop == "Metadata":
                return dbus.Dictionary(self._metadata, signature="sv", variant_level=1)
            elif prop == "Volume":
                return 1.0
            elif prop == "Position":
                return dbus.Int64(self.app.get_playback_time() * 1000000)
            elif prop == "CanGoNext":
                return True
            elif prop == "CanGoPrevious":
                return True
            elif prop == "CanPlay":
                return True
            elif prop == "CanPause":
                return True
            elif prop == "CanSeek":
                return True
            elif prop == "LoopStatus":
                return "Playlist" if self.app.loop_flag else "None"
            elif prop == "Shuffle":
                return self.app.shuffle_flag
            else:
                return dbus.String("")

        @dbus.service.method(PROPERTIES_IFACE, in_signature='ssv', out_signature='')
        def Set(self, interface_name, property_name, new_value):
            if interface_name == self.MEDIA_PLAYER2_PLAYER_IFACE:
                if property_name == "LoopStatus":
                    self.app.loop_flag = (new_value == "Playlist")
                    self.app.loop_btn.config(text=f"Bucle: {'ON' if self.app.loop_flag else 'OFF'}")
                elif property_name == "Shuffle":
                    self.app.shuffle_flag = bool(new_value)
                    self.app.shuffle_btn.config(text=f"Aleatorio: {'ON' if self.app.shuffle_flag else 'OFF'}")
                    self.app.shuffle_history = []

        @dbus.service.method(PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface_name):
            if interface_name == self.MEDIA_PLAYER2_IFACE:
                return {
                    "CanQuit": True,
                    "CanRaise": True,
                    "Identity": "Monojo Music",
                    "DesktopEntry": "monojo-music",
                    "SupportedUriSchemes": dbus.Array(["file"], signature='s'),
                    "SupportedMimeTypes": dbus.Array(["audio/mpeg","audio/ogg","audio/flac","audio/x-wav"], signature='s')
                }
            elif interface_name == self.MEDIA_PLAYER2_PLAYER_IFACE:
                status = "Playing" if self.app.is_playing else ("Paused" if self.app.paused_flag else "Stopped")
                return {
                    "PlaybackStatus": status,
                    "Metadata": dbus.Dictionary(self._metadata, signature="sv"),
                    "Volume": 1.0,
                    "Position": dbus.Int64(self.app.get_playback_time() * 1000000),
                    "CanGoNext": True,
                    "CanGoPrevious": True,
                    "CanPlay": True,
                    "CanPause": True,
                    "CanSeek": True,
                    "LoopStatus": "Playlist" if self.app.loop_flag else "None",
                    "Shuffle": self.app.shuffle_flag
                }
            else:
                return {}

        def update_metadata(self):
            if not self.app.current_path or not os.path.exists(self.app.current_path):
                self._metadata = {}
            else:
                path = self.app.current_path
                base = os.path.basename(path)
                title = os.path.splitext(base)[0]
                dur_sec = self.app.current_duration
                duration_us = dbus.Int64(dur_sec * 1000000)
                # --- CAMBIO: artista = playlist o Biblioteca ---
                artist = "Biblioteca"
                if self.app.from_playlist and self.app.playlist_name:
                    artist = self.app.playlist_name
                # -------------------------------------------------
                self._metadata = {
                    "xesam:title": title,
                    "xesam:artist": [artist],
                    "mpris:length": duration_us,
                    "mpris:artUrl": "file://" + (ICON_PATH.as_posix() if ICON_PATH else "")
                }
            self.emit_properties_changed()

        def emit_properties_changed(self):
            try:
                self.PropertiesChanged(
                    self.MEDIA_PLAYER2_PLAYER_IFACE,
                    {
                        "PlaybackStatus": self.Get(self.MEDIA_PLAYER2_PLAYER_IFACE, "PlaybackStatus"),
                        "Metadata": dbus.Dictionary(self._metadata, signature="sv"),
                        "LoopStatus": self.Get(self.MEDIA_PLAYER2_PLAYER_IFACE, "LoopStatus"),
                        "Shuffle": self.Get(self.MEDIA_PLAYER2_PLAYER_IFACE, "Shuffle")
                    },
                    []
                )
            except Exception as e:
                debug(f"Error al emitir PropertiesChanged: {e}")

        @dbus.service.signal(PROPERTIES_IFACE, signature='sa{sv}as')
        def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
            pass

# ---------------- Aplicación principal ----------------
class MonojoMusicApp:
    def __init__(self, root):
        self.root = root
        root.title("Monojo Music")
        try:
            root.iconphoto(True, tk.PhotoImage(file=ICON_PATH))
        except Exception:
            pass

        # Estado de reproducción
        self.play_proc = None
        self.current_path = None
        self.current_duration = 0.0
        self.play_start_time = 0.0
        self.play_time_offset = 0.0
        self.is_playing = False
        self.paused_flag = False

        # Banderas
        self.loop_flag = False
        self.shuffle_flag = False
        self.from_playlist = False

        # Biblioteca y playlist
        self.lib_files = []
        self.playlist_name = ""
        self.playlist_items = []
        self.playlist_index = 0

        # Historiales
        self.shuffle_history = []
        self.undo_stack = []

        # Construir interfaz
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Inicializar datos
        self.refresh_library()
        self.reload_playlist_listbox()
        self.root.after(POLL_INTERVAL_MS, self.poll_playback)

        # MPRIS
        self.mpris = None
        if MPRIS_AVAILABLE:
            try:
                bus = dbus.SessionBus()
                self.mpris = MonojoMPRIS(self, bus)
                self.mpris.update_metadata()
                debug("MPRIS iniciado correctamente.")
            except Exception as e:
                debug(f"No se pudo iniciar MPRIS: {e}")
        else:
            debug("MPRIS no disponible. La integración multimedia no se activará.")

    # ==================== INTERFAZ GRÁFICA ====================
    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=6, pady=6)
        tk.Button(top, text="Nueva Playlist", command=self.new_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Guardar Playlist", command=self.save_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Cargar Playlist", command=self.choose_and_load_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Atajos de teclado", command=self.show_guide).pack(side="right", padx=4)

        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=6, pady=6)

        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Biblioteca (Músicas)").pack(anchor="w")
        self.lib_listbox = tk.Listbox(left, selectmode="extended")
        self.lib_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        lib_controls = tk.Frame(left)
        lib_controls.pack(fill="x")
        tk.Button(lib_controls, text="Añadir música", command=self.add_music).pack(side="left", padx=2)
        tk.Button(lib_controls, text="Eliminar música", command=self.delete_music).pack(side="left", padx=2)
        tk.Button(lib_controls, text="Renombrar", command=self.rename_music).pack(side="left", padx=2)
        tk.Button(lib_controls, text="Añadir a Playlist →", command=self.add_selected_to_playlist).pack(side="right", padx=2)

        right = tk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(10,0))
        self.playlist_label = tk.Label(right, text="Playlist actual: (sin nombre)")
        self.playlist_label.pack(anchor="w")
        self.pl_listbox = tk.Listbox(right)
        self.pl_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        pl_controls = tk.Frame(right)
        pl_controls.pack(fill="x")
        tk.Button(pl_controls, text="← Quitar de Playlist", command=self.remove_selected_from_playlist).pack(side="left", padx=2)
        tk.Button(pl_controls, text="↑", width=3, command=lambda: self.move_in_playlist(-1)).pack(side="left", padx=2)
        tk.Button(pl_controls, text="↓", width=3, command=lambda: self.move_in_playlist(1)).pack(side="left", padx=2)
        tk.Button(pl_controls, text="▶ Reproducir Playlist", command=self.play_playlist).pack(side="right", padx=2)

        bottom = tk.Frame(self.root)
        bottom.pack(fill="x", padx=6, pady=6)

        controls = tk.Frame(bottom)
        controls.pack(side="left")
        tk.Button(controls, text="⬅", width=3, command=self.prev_track).pack(side="left", padx=2)
        self.play_btn = tk.Button(controls, text="▶ Reproducir", command=self.play_selected_or_resume)
        self.play_btn.pack(side="left", padx=4)
        self.pause_btn = tk.Button(controls, text="Pausar", command=self.pause_toggle)
        self.pause_btn.pack(side="left", padx=4)
        self.stop_btn = tk.Button(controls, text="Parar", command=self.stop_action)
        self.stop_btn.pack(side="left", padx=4)
        tk.Button(controls, text="➡", width=3, command=self.next_track).pack(side="left", padx=2)

        aux = tk.Frame(bottom)
        aux.pack(side="left", padx=(10,0))
        self.loop_btn = tk.Button(aux, text="Bucle: OFF", command=self.toggle_loop)
        self.loop_btn.pack(side="left", padx=4)
        self.shuffle_btn = tk.Button(aux, text="Aleatorio: OFF", command=self.toggle_shuffle)
        self.shuffle_btn.pack(side="left", padx=4)

        self.now_lbl = tk.Label(bottom, text="Ninguna canción seleccionada")
        self.now_lbl.pack(side="left", padx=10)

        right_prog = tk.Frame(bottom)
        right_prog.pack(side="right")
        self.time_lbl = tk.Label(right_prog, text="00:00 / 00:00")
        self.time_lbl.pack(side="right", padx=6)
        self.progress = tk.Scale(right_prog, from_=0, to=1, orient="horizontal", length=380,
                                 showvalue=False, command=self.on_progress_drag)
        self.progress.pack(side="right")
        self.progress.bind("<ButtonRelease-1>", self.on_progress_release)

        self.root.bind("<Key>", self.on_key_press)

    def show_guide(self):
        guia = (
            "--- Atajos de Teclado ---\n\n"
            "• Control + Z: Deshacer última acción\n"
            "• Eliminar (Backspace): Elimina de la biblioteca los archivos seleccionados\n"
            "• Tecla A: Añadir nueva música a la biblioteca\n"
            "• Tecla R: Renombrar canción seleccionada de la biblioteca\n"
            "• Tecla M: Añadir canción seleccionada a la playlist\n"
            "• Tecla N: Quitar canción seleccionada de la playlist\n"
            "• Tecla I: Subir archivo en la playlist ↑\n"
            "• Tecla K: Bajar archivo en la playlist ↓\n"
            "• Flecha Derecha (→): Mover foco a Playlist\n"
            "• Flecha Izquierda (←): Mover foco a Biblioteca\n"
            "• Flecha Arriba (↑): Seleccionar la canción de arriba\n"
            "• Flecha Abajo (↓): Seleccionar la canción de abajo\n"
            "• Enter o Tecla Z: Reproducir canción seleccionada\n"
            "• Tecla X: Detener reproducción (Parar)\n"
            "• Tecla C: Pausar / Reanudar la reproducción\n"
            "• Tecla V: Reproducir toda la playlist activa"
        )
        messagebox.showinfo("Guía de Controles", guia)

    def on_key_press(self, event):
        try:
            if event.widget.winfo_class() in ("Entry", "Text", "Spinbox"):
                return
        except Exception:
            pass
        is_ctrl = (event.state & 0x0004) != 0
        sym = event.keysym
        char = event.char.lower() if event.char else ""

        if is_ctrl and sym.lower() == "z":
            self.undo_action()
            return
        if sym == "BackSpace":
            self.delete_music()
        elif sym == "Right":
            self.switch_focus_to_playlist()
        elif sym == "Left":
            self.switch_focus_to_library()
        elif sym == "Return" or (char == "z" and not is_ctrl):
            self.play_selected_or_resume()
        elif char == "a":
            self.add_music()
        elif char == "r":
            self.rename_music()
        elif char == "x":
            self.stop_action()
        elif char == "c":
            self.pause_toggle()
        elif char == "v":
            self.play_playlist()
        elif char == "m":
            self.add_selected_to_playlist()
        elif char == "n":
            self.remove_selected_from_playlist()
        elif char == "i":
            self.move_in_playlist_up()
        elif char == "k":
            self.move_in_playlist_down()

    def undo_action(self):
        if not self.undo_stack:
            return
        last = self.undo_stack.pop()
        action = last["action"]
        if action == "add_pl":
            for item in last["items"]:
                if item in self.playlist_items:
                    self.playlist_items.remove(item)
            self.reload_playlist_listbox()
        elif action == "rm_pl":
            items = sorted(last["items"], key=lambda x: x[0])
            for idx, item in items:
                self.playlist_items.insert(idx, item)
            self.reload_playlist_listbox()
        elif action == "move_pl":
            i, j = last["idx1"], last["idx2"]
            self.playlist_items[i], self.playlist_items[j] = self.playlist_items[j], self.playlist_items[i]
            self.reload_playlist_listbox()
            self.pl_listbox.selection_clear(0, tk.END)
            self.pl_listbox.select_set(i)
        elif action == "rename":
            old_path, new_path = last["old_path"], last["new_path"]
            old_name, new_name = last["old_name"], last["new_name"]
            try:
                if os.path.exists(new_path):
                    os.rename(new_path, old_path)
                    for k in range(len(self.playlist_items)):
                        if self.playlist_items[k] == new_name:
                            self.playlist_items[k] = old_name
                    if self.current_path == new_path:
                        self.current_path = old_path
                        self.update_now_label()
                    self.refresh_library()
                    self.reload_playlist_listbox()
            except Exception as e:
                messagebox.showerror("Error Deshacer", f"No se pudo revertir el renombrado:\n{e}")

    def switch_focus_to_playlist(self):
        sel = self.lib_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        pl_size = self.pl_listbox.size()
        if pl_size == 0:
            return
        target_idx = idx if idx < pl_size else pl_size - 1
        self.lib_listbox.selection_clear(0, tk.END)
        self.pl_listbox.selection_clear(0, tk.END)
        self.pl_listbox.selection_set(target_idx)
        self.pl_listbox.activate(target_idx)
        self.pl_listbox.see(target_idx)
        self.pl_listbox.focus_set()

    def switch_focus_to_library(self):
        sel = self.pl_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        lib_size = self.lib_listbox.size()
        if lib_size == 0:
            return
        target_idx = idx if idx < lib_size else lib_size - 1
        self.pl_listbox.selection_clear(0, tk.END)
        self.lib_listbox.selection_clear(0, tk.END)
        self.lib_listbox.selection_set(target_idx)
        self.lib_listbox.activate(target_idx)
        self.lib_listbox.see(target_idx)
        self.lib_listbox.focus_set()

    # ==================== BIBLIOTECA ====================
    def refresh_library(self):
        self.lib_listbox.delete(0, tk.END)
        self.lib_files = []
        try:
            VALID_EXT = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus", ".mp4", ".mkv")
            items = sorted([
                f for f in os.listdir(MUSIC_DIR)
                if f.lower().endswith(VALID_EXT)
            ])
        except Exception:
            items = []
        for it in items:
            self.lib_files.append(it)
            base_name = os.path.splitext(it)[0]
            self.lib_listbox.insert(tk.END, base_name)

    def add_music(self):
        paths = zenity_select_multiple_files(title="Selecciona MP3 para añadir", initial_dir=MUSIC_DIR)
        if not paths:
            paths = filedialog.askopenfilenames(
                title="Selecciona MP3", initialdir=MUSIC_DIR,
                filetypes=[("Archivos de audio/video", "*.mp3 *.wav *.flac *.ogg *.m4a *.opus *.mp4 *.mkv")]
            )
            if not paths:
                return
        added = 0
        for p in paths:
            if not p:
                continue
            try:
                dest = os.path.join(MUSIC_DIR, os.path.basename(p))
                if os.path.exists(dest) and os.path.realpath(p) == os.path.realpath(dest):
                    continue
                if os.path.exists(dest):
                    base, ext = os.path.splitext(os.path.basename(p))
                    k = 1
                    while os.path.exists(os.path.join(MUSIC_DIR, f"{base}_{k}{ext}")):
                        k += 1
                    dest = os.path.join(MUSIC_DIR, f"{base}_{k}{ext}")
                with open(p, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                added += 1
            except Exception:
                messagebox.showwarning("Error", f"No se pudo copiar: {p}")
        if added:
            self.refresh_library()

    def delete_music(self):
        sel = list(self.lib_listbox.curselection())
        if not sel:
            messagebox.showinfo("Eliminar MP3", "Selecciona archivos en la biblioteca para eliminar.")
            return
        names = [self.lib_files[i] for i in sel]
        if not messagebox.askyesno("Confirmar", f"¿Eliminar {len(names)} archivo(s) de Músicas?"):
            return
        for n in names:
            try:
                full = os.path.join(MUSIC_DIR, n)
                if os.path.exists(full):
                    os.remove(full)
            except Exception:
                messagebox.showwarning("Error", f"No se pudo borrar: {n}")
        self.undo_stack.clear()
        self.refresh_library()
        self.playlist_items = [x for x in self.playlist_items if x not in names]
        self.reload_playlist_listbox()

    def rename_music(self):
        sel = self.lib_listbox.curselection()
        if not sel:
            messagebox.showinfo("Renombrar", "Selecciona una canción en la biblioteca para renombrar.")
            return
        idx = sel[0]
        old_fullname = self.lib_files[idx]
        base_name, ext = os.path.splitext(old_fullname)
        new_base = simpledialog.askstring("Renombrar", "Nuevo nombre (sin extensión):", initialvalue=base_name)
        if not new_base or new_base == base_name:
            return
        new_fullname = new_base + ext
        old_path = os.path.join(MUSIC_DIR, old_fullname)
        new_path = os.path.join(MUSIC_DIR, new_fullname)
        if os.path.exists(new_path):
            messagebox.showwarning("Atención", f"Ya existe una canción con el nombre '{new_base}'. No se hará nada.")
            return
        try:
            os.rename(old_path, new_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar el archivo:\n{e}")
            return
        self.undo_stack.append({
            "action": "rename",
            "old_path": old_path, "new_path": new_path,
            "old_name": old_fullname, "new_name": new_fullname
        })
        for i in range(len(self.playlist_items)):
            if self.playlist_items[i] == old_fullname:
                self.playlist_items[i] = new_fullname
        if self.current_path == old_path:
            self.current_path = new_path
            self.update_now_label()
        self.refresh_library()
        self.reload_playlist_listbox()

    # ==================== PLAYLIST ====================
    def new_playlist(self):
        name = simpledialog.askstring("Nueva Playlist", "Nombre de la playlist (sin extensión):")
        if not name:
            return
        self.playlist_name = name
        self.playlist_items = []
        self.undo_stack.clear()
        self.reload_playlist_listbox()
        self.update_playlist_label()
        messagebox.showinfo("Playlist", f"Playlist '{name}' creada (vacía).")

    def save_playlist(self):
        if not self.playlist_name:
            name = simpledialog.askstring("Guardar Playlist", "Nombre de la playlist (sin extensión):")
            if not name:
                return
            self.playlist_name = name
        path = os.path.join(PLAYLIST_DIR, self.playlist_name + ".txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                for it in self.playlist_items:
                    f.write(it + "\n")
            self.update_playlist_label()
            messagebox.showinfo("Guardado", f"Playlist guardada: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar playlist:\n{e}")

    def choose_and_load_playlist(self):
        files = [f for f in os.listdir(PLAYLIST_DIR) if f.endswith(".txt")]
        if not files:
            messagebox.showinfo("Playlists", "No hay playlists guardadas.")
            return
        top = tk.Toplevel(self.root)
        top.title("Seleccionar Playlist")
        top.geometry("300x400")
        top.transient(self.root)
        top.grab_set()
        tk.Label(top, text="Selecciona una playlist para cargar:").pack(pady=10)
        frame = tk.Frame(top)
        frame.pack(fill="both", expand=True, padx=15, pady=5)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, selectmode="single")
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        for f in files:
            listbox.insert(tk.END, f[:-4])

        def on_load():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Atención", "Selecciona una playlist de la lista.")
                return
            choice = listbox.get(sel[0])
            top.destroy()
            self._load_playlist_file(choice)

        listbox.bind("<Double-Button-1>", lambda e: on_load())
        btn_frame = tk.Frame(top)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Cargar", command=on_load).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancelar", command=top.destroy).pack(side="right", padx=10)

    def _load_playlist_file(self, choice):
        path = os.path.join(PLAYLIST_DIR, choice + ".txt")
        if not os.path.exists(path):
            messagebox.showerror("Error", "No existe esa playlist.")
            return
        self.playlist_name = choice
        loaded = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if os.path.exists(os.path.join(MUSIC_DIR, name)):
                    loaded.append(name)
        self.playlist_items = loaded
        self.undo_stack.clear()
        self.reload_playlist_listbox()
        self.update_playlist_label()
        messagebox.showinfo("Cargada", f"Playlist '{choice}' cargada con {len(loaded)} canciones.")

    def reload_playlist_listbox(self):
        self.pl_listbox.delete(0, tk.END)
        for it in self.playlist_items:
            base_name = os.path.splitext(it)[0]
            self.pl_listbox.insert(tk.END, base_name)
        self.update_playlist_label()

    def update_playlist_label(self):
        display = self.playlist_name if self.playlist_name else "(sin nombre)"
        self.playlist_label.config(text=f"Playlist actual: {display}")

    def add_selected_to_playlist(self):
        if not self.playlist_items:
            messagebox.showwarning("Sin Playlist", "No hay ninguna playlist abierta. Crea o carga una playlist primero.")
            return
        sel = list(self.lib_listbox.curselection())
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una canción en la Biblioteca para añadir a Playlist.")
            return
        added_items = []
        for i in sel:
            name = self.lib_files[i]
            if name not in self.playlist_items:
                self.playlist_items.append(name)
                added_items.append(name)
        if added_items:
            self.undo_stack.append({"action": "add_pl", "items": added_items})
        self.reload_playlist_listbox()

    def remove_selected_from_playlist(self):
        sel = list(self.pl_listbox.curselection())
        if not sel:
            return
        removed_items = []
        for i in reversed(sel):
            try:
                removed_items.append((i, self.playlist_items[i]))
                del self.playlist_items[i]
            except Exception:
                pass
        if removed_items:
            self.undo_stack.append({"action": "rm_pl", "items": removed_items})
        self.reload_playlist_listbox()

    def move_in_playlist(self, direction):
        sel = self.pl_listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + direction
        if j < 0 or j >= len(self.playlist_items):
            return
        self.playlist_items[i], self.playlist_items[j] = self.playlist_items[j], self.playlist_items[i]
        self.undo_stack.append({"action": "move_pl", "idx1": i, "idx2": j})
        self.reload_playlist_listbox()
        self.pl_listbox.select_set(j)

    def move_in_playlist_up(self):
        if not self.playlist_items:
            messagebox.showwarning("Sin Playlist", "No hay ninguna playlist abierta.")
            return
        sel = self.pl_listbox.curselection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una canción en la Playlist para mover.")
            return
        i = sel[0]
        if i == 0:
            messagebox.showinfo("Límite", "Esta canción ya está en la primera posición.")
            return
        j = i - 1
        self.playlist_items[i], self.playlist_items[j] = self.playlist_items[j], self.playlist_items[i]
        self.undo_stack.append({"action": "move_pl", "idx1": i, "idx2": j})
        self.reload_playlist_listbox()
        self.pl_listbox.select_set(j)

    def move_in_playlist_down(self):
        if not self.playlist_items:
            messagebox.showwarning("Sin Playlist", "No hay ninguna playlist abierta.")
            return
        sel = self.pl_listbox.curselection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una canción en la Playlist para mover.")
            return
        i = sel[0]
        if i == len(self.playlist_items) - 1:
            messagebox.showinfo("Límite", "Esta canción ya está en la última posición.")
            return
        j = i + 1
        self.playlist_items[i], self.playlist_items[j] = self.playlist_items[j], self.playlist_items[i]
        self.undo_stack.append({"action": "move_pl", "idx1": i, "idx2": j})
        self.reload_playlist_listbox()
        self.pl_listbox.select_set(j)

    # ==================== REPRODUCCIÓN ====================
    def play_selected_or_resume(self):
        pl_sel = self.pl_listbox.curselection()
        if pl_sel:
            self.playlist_index = pl_sel[0]
            self.play_playlist(start_index=self.playlist_index)
            return
        lib_sel = self.lib_listbox.curselection()
        if lib_sel:
            name = self.lib_files[lib_sel[0]]
            self.play_file(os.path.join(MUSIC_DIR, name), start_at=0.0, from_playlist=False)
            return
        if self.paused_flag and self.current_path:
            self.play_file(self.current_path, start_at=self.play_start_time, from_playlist=self.from_playlist)
            self.paused_flag = False
            self.pause_btn.config(text="Pausar")
            return
        if self.current_path and not self.is_playing:
            self.play_file(self.current_path, start_at=self.play_start_time, from_playlist=self.from_playlist)
            return

    def play_file(self, path, start_at=0.0, from_playlist=False):
        dur = ffprobe_duration(path) or 0.0
        if dur > 0 and start_at >= dur:
            start_at = max(0.0, dur - 0.5)
        self.stop_process()
        self.current_path = path
        self.current_duration = dur
        self.play_start_time = float(start_at)
        self.play_time_offset = time.time()
        self.from_playlist = bool(from_playlist)
        self.paused_flag = False
        self.pause_btn.config(text="Pausar")

        # Inyectar PULSE_PROP para renombrar el stream de audio
        env = os.environ.copy()
        env["PULSE_PROP"] = f"application.name={STREAM_NAME}"

        try:
            self.play_proc = subprocess.Popen(
                [FFPLAY_EXEC, "-nodisp", "-autoexit", "-loglevel", "quiet",
                 "-ss", str(self.play_start_time), path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env
            )
            self.is_playing = True
            self.update_now_label()
            if self.mpris:
                self.mpris.update_metadata()
                self.mpris.emit_properties_changed()
        except FileNotFoundError:
            messagebox.showerror("Error", "No se pudo ejecutar el reproductor (ffplay).")
            self.play_proc = None
            self.is_playing = False

    def stop_process(self):
        if self.play_proc:
            try:
                self.play_proc.terminate()
                try:
                    self.play_proc.wait(timeout=0.4)
                except Exception:
                    self.play_proc.kill()
            except Exception:
                pass
        self.play_proc = None
        self.is_playing = False

    def pause_toggle(self):
        if self.is_playing:
            cur = self.get_playback_time()
            self.stop_process()
            self.play_start_time = min(cur, self.current_duration)
            self.paused_flag = True
            self.pause_btn.config(text="Continuar")
            self.update_now_label()
            if self.mpris:
                self.mpris.emit_properties_changed()
            return
        if self.paused_flag and self.current_path:
            self.play_file(self.current_path, start_at=self.play_start_time, from_playlist=self.from_playlist)
            self.paused_flag = False
            self.pause_btn.config(text="Pausar")
            return
        if not self.is_playing and self.current_path:
            self.play_file(self.current_path, start_at=self.play_start_time, from_playlist=self.from_playlist)

    def stop_action(self):
        if self.is_playing or self.play_proc:
            self.stop_process()
        self.play_start_time = 0.0
        self.paused_flag = False
        self.pause_btn.config(text="Pausar")
        self.update_now_label()
        self.update_time_and_progress(0.0, 0.0)
        if self.mpris:
            self.mpris.emit_properties_changed()

    def get_playback_time(self):
        if not self.current_path:
            return 0.0
        if self.is_playing and self.play_proc:
            elapsed = time.time() - self.play_time_offset
            t = self.play_start_time + elapsed
            if self.current_duration > 0:
                return min(t, self.current_duration)
            return t
        else:
            return min(self.play_start_time, self.current_duration) if self.current_duration > 0 else self.play_start_time

    # ==================== CONTROL DE PLAYLIST ====================
    def play_playlist(self, start_index=0):
        if not self.playlist_items:
            messagebox.showinfo("Playlist", "La playlist está vacía.")
            return
        if start_index < 0 or start_index >= len(self.playlist_items):
            start_index = 0
        self.playlist_index = start_index
        name = self.playlist_items[self.playlist_index]
        path = os.path.join(MUSIC_DIR, name)
        if not os.path.exists(path):
            messagebox.showerror("Error", f"No existe: {name}")
            return
        self.play_file(path, start_at=0.0, from_playlist=True)

    def advance_playlist(self):
        if not self.playlist_items:
            self.stop_action()
            return
        if self.shuffle_flag:
            if 0 <= self.playlist_index < len(self.playlist_items):
                self.shuffle_history.append(self.playlist_index)
            if len(self.playlist_items) == 1:
                next_idx = 0
            else:
                choices = list(range(len(self.playlist_items)))
                try:
                    choices.remove(self.playlist_index)
                except Exception:
                    pass
                next_idx = random.choice(choices)
        else:
            next_idx = self.playlist_index + 1
        if not self.shuffle_flag and next_idx >= len(self.playlist_items):
            if self.loop_flag:
                next_idx = 0
            else:
                self.stop_action()
                return
        self.playlist_index = next_idx
        name = self.playlist_items[self.playlist_index]
        path = os.path.join(MUSIC_DIR, name)
        if os.path.exists(path):
            self.play_file(path, start_at=0.0, from_playlist=True)
        else:
            try:
                del self.playlist_items[self.playlist_index]
            except Exception:
                pass
            self.reload_playlist_listbox()
            self.advance_playlist()

    def prev_playlist(self):
        if not self.playlist_items:
            return
        if self.shuffle_flag and self.shuffle_history:
            idx = self.shuffle_history.pop()
        else:
            idx = self.playlist_index - 1
            if idx < 0:
                if self.loop_flag:
                    idx = len(self.playlist_items) - 1
                else:
                    idx = 0
        self.playlist_index = idx
        name = self.playlist_items[self.playlist_index]
        path = os.path.join(MUSIC_DIR, name)
        if os.path.exists(path):
            self.play_file(path, start_at=0.0, from_playlist=True)

    # ==================== SIGUIENTE / ANTERIOR ====================
    def next_track(self):
        if self.from_playlist and self.playlist_items:
            self.advance_playlist()
            return
        lib_items = self.lib_files
        if not lib_items:
            return
        curname = os.path.basename(self.current_path) if self.current_path else None
        if self.shuffle_flag:
            if curname in lib_items:
                try:
                    self.shuffle_history.append(lib_items.index(curname))
                except Exception:
                    pass
            if len(lib_items) == 1:
                idx = 0
            else:
                choices = list(range(len(lib_items)))
                if curname in lib_items:
                    try:
                        choices.remove(lib_items.index(curname))
                    except Exception:
                        pass
                idx = random.choice(choices)
            name = lib_items[idx]
            self.play_file(os.path.join(MUSIC_DIR, name), start_at=0.0, from_playlist=False)
            return
        if curname and curname in lib_items:
            idx = lib_items.index(curname) + 1
        else:
            sel = self.lib_listbox.curselection()
            if sel:
                idx = sel[0] + 1
            else:
                idx = 0
        if idx >= len(lib_items):
            if self.loop_flag:
                idx = 0
            else:
                self.stop_action()
                return
        name = lib_items[idx]
        self.play_file(os.path.join(MUSIC_DIR, name), start_at=0.0, from_playlist=False)

    def prev_track(self):
        if self.from_playlist and self.playlist_items:
            self.prev_playlist()
            return
        lib_items = self.lib_files
        if not lib_items:
            return
        curname = os.path.basename(self.current_path) if self.current_path else None
        if self.shuffle_flag:
            if self.shuffle_history:
                idx = self.shuffle_history.pop()
            else:
                if len(lib_items) == 1:
                    idx = 0
                else:
                    choices = list(range(len(lib_items)))
                    if curname in lib_items:
                        try:
                            choices.remove(lib_items.index(curname))
                        except Exception:
                            pass
                    idx = random.choice(choices)
            name = lib_items[idx]
            self.play_file(os.path.join(MUSIC_DIR, name), start_at=0.0, from_playlist=False)
            return
        if curname and curname in lib_items:
            idx = lib_items.index(curname) - 1
        else:
            sel = self.lib_listbox.curselection()
            if sel:
                idx = sel[0] - 1
            else:
                idx = len(lib_items) - 1 if self.loop_flag else 0
        if idx < 0:
            if self.loop_flag:
                idx = len(lib_items) - 1
            else:
                idx = 0
        name = lib_items[idx]
        self.play_file(os.path.join(MUSIC_DIR, name), start_at=0.0, from_playlist=False)

    # ==================== PROGRESO ====================
    def on_progress_drag(self, value):
        try:
            v = float(value)
        except Exception:
            v = 0.0
        dur = max(1.0, self.current_duration)
        self.time_lbl.config(text=f"{self.format_time(v)} / {self.format_time(dur)}")

    def on_progress_release(self, event):
        if not self.current_path:
            self.progress.set(0)
            return
        val = self.progress.get()
        if val < 0: val = 0
        if val > self.current_duration: val = self.current_duration
        self.play_start_time = float(val)
        if self.is_playing:
            self.play_file(self.current_path, start_at=self.play_start_time, from_playlist=self.from_playlist)
        else:
            self.update_time_and_progress(self.play_start_time, self.current_duration)

    def format_time(self, sec):
        sec = max(0, int(sec))
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    # ==================== POLLING ====================
    def poll_playback(self):
        try:
            if self.is_playing and self.play_proc:
                cur = self.get_playback_time()
                self.update_time_and_progress(cur, self.current_duration)
                if self.play_proc.poll() is not None:
                    self.handle_playback_end()
            else:
                if self.current_path:
                    cur = self.get_playback_time()
                    self.update_time_and_progress(cur, self.current_duration)
        except Exception:
            pass
        self.root.after(POLL_INTERVAL_MS, self.poll_playback)

    def handle_playback_end(self):
        if self.loop_flag:
            self.play_file(self.current_path, start_at=0.0, from_playlist=self.from_playlist)
            return
        if self.from_playlist:
            name = os.path.basename(self.current_path) if self.current_path else None
            if name and name in self.playlist_items:
                if 0 <= self.playlist_index < len(self.playlist_items) and self.playlist_items[self.playlist_index] == name:
                    self.advance_playlist()
                    return
            self.stop_action()
        else:
            self.next_track()

    def update_time_and_progress(self, cur, dur):
        if dur <= 0:
            self.progress.config(to=1)
            self.progress.set(0)
            self.time_lbl.config(text="00:00 / 00:00")
            return
        try:
            self.progress.config(to=max(1, int(dur)))
            pos = min(int(cur), int(dur))
            self.progress.set(pos)
        except Exception:
            pass
        cur_disp = min(cur, dur) if dur > 0 else cur
        self.time_lbl.config(text=f"{self.format_time(cur_disp)} / {self.format_time(dur)}")

    def update_now_label(self):
        if not self.current_path:
            self.now_lbl.config(text="Ninguna canción seleccionada")
            return
        base = os.path.basename(self.current_path)
        base_no_ext = os.path.splitext(base)[0]
        if self.is_playing:
            state = "Reproduciendo"
        elif self.paused_flag:
            state = "Pausado"
        else:
            state = "Detenido"
        text = f"{state}: {base_no_ext}"
        if self.playlist_items and base in self.playlist_items:
            try:
                idx = self.playlist_items.index(base) + 1
                text += f"  ({idx}/{len(self.playlist_items)})"
            except Exception:
                pass
        self.now_lbl.config(text=text)

    # ==================== TOGGLES ====================
    def toggle_loop(self):
        self.loop_flag = not self.loop_flag
        self.loop_btn.config(text=f"Bucle: {'ON' if self.loop_flag else 'OFF'}")
        if self.mpris:
            self.mpris.emit_properties_changed()

    def toggle_shuffle(self):
        self.shuffle_flag = not self.shuffle_flag
        self.shuffle_history = []
        self.shuffle_btn.config(text=f"Aleatorio: {'ON' if self.shuffle_flag else 'OFF'}")
        if self.mpris:
            self.mpris.emit_properties_changed()

    def on_close(self):
        if self.playlist_name:
            try:
                path = os.path.join(PLAYLIST_DIR, self.playlist_name + ".txt")
                with open(path, "w", encoding="utf-8") as f:
                    for it in self.playlist_items:
                        f.write(it + "\n")
            except Exception:
                pass
        try:
            if self.play_proc:
                self.play_proc.terminate()
                try:
                    self.play_proc.wait(timeout=1)
                except Exception:
                    self.play_proc.kill()
        except Exception:
            pass
        self.root.destroy()

# ==================== ARRANQUE ====================
def start_glib_loop():
    if MPRIS_AVAILABLE:
        try:
            loop = GLib.MainLoop()
            debug("Bucle GLib iniciado.")
            loop.run()
        except Exception as e:
            debug(f"Error en el bucle GLib: {e}")

if __name__ == "__main__":
    debug("Entrando en __main__")
    try:
        if MPRIS_AVAILABLE:
            threading.Thread(target=start_glib_loop, daemon=True).start()
            debug("Hilo GLib lanzado.")
    except Exception as e:
        debug(f"Error al lanzar hilo GLib: {e}")

    debug("Creando ventana Tk...")
    root = tk.Tk(className="monojo_music_main")
    debug("Ventana Tk creada.")
    app = MonojoMusicApp(root)
    debug("App instanciada.")

    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            if os.path.isfile(path):
                dest = os.path.join(MUSIC_DIR, os.path.basename(path))
                if not os.path.exists(dest):
                    shutil.copy2(path, MUSIC_DIR)
        app.refresh_library()
        first = os.path.basename(sys.argv[1])
        full = os.path.join(MUSIC_DIR, first)
        if os.path.exists(full):
            app.play_file(full)
            debug(f"Reproduciendo archivo pasado por argumento: {full}")

    debug("Iniciando bucle principal de Tk...")
    root.mainloop()
    debug("Bucle principal terminado.")
