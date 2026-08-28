#!/usr/bin/env python3

# Monojo Music — Tkinter + ffplay/ffprobe + MPRIS2
# Requisitos: ffplay, ffprobe, python3-dbus, python3-gi

# Monojo Music 2.3: tema oscuro y claro porque quiero escuchar música de noche
# Licencia: GPL v3
# Proyecto: Monojo Project
# Autor: David Baña Szymaniak
# Copyright (C) 2026 David Baña Szymaniak

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
DEBUG_ENABLED = True

DEBUG_LOG = "/tmp/monojo_music_debug.log"
def debug(msg):
    if DEBUG_ENABLED:
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
THEME_POLL_INTERVAL_MS = 2000   # Comprobación periódica del tema del sistema

# ------------------- Detectar ffplay -------------------
FFPLAY_PATH = shutil.which("ffplay")
if not FFPLAY_PATH:
    debug("ERROR: ffplay no encontrado en el sistema.")
    sys.exit(1)

FFPLAY_EXEC = FFPLAY_PATH

STREAM_NAME = "Monojo Music"

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
                artist = "Biblioteca"
                if self.app.from_playlist and self.app.playlist_name:
                    artist = self.app.playlist_name
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

# ---------------- Utilidades de tema ----------------
DARK_THEME = {
    'bg': '#2e2e2e',
    'fg': '#ffffff',
    'selectbg': '#ffcc00',     # Amarillo
    'selectfg': '#000000',
    'entrybg': '#1e1e1e',
    'entryfg': '#ffffff',
    'textbg': '#1e1e1e',
    'textfg': '#ffffff',
    'scalebg': '#2e2e2e',
    'scalefg': '#ffffff',
    'troughcolor': '#555555',
    'buttonbg': '#3c3c3c',
    'buttonfg': '#ffffff',
    'buttonactivebg': '#4a4a4a',
    'buttonactivefg': '#ffffff',
    'highlightbackground': '#555555',
}

LIGHT_THEME = {
    'bg': '#d9d9d9',           # color por defecto de Tk
    'fg': '#000000',
    'selectbg': '#ffcc00',     # Amarillo en selección también en claro
    'selectfg': '#000000',
    'entrybg': '#ffffff',
    'entryfg': '#000000',
    'textbg': '#ffffff',
    'textfg': '#000000',
    'scalebg': '#d9d9d9',
    'scalefg': '#000000',
    'troughcolor': '#d9d9d9',
    'buttonbg': '#d9d9d9',
    'buttonfg': '#000000',
    'buttonactivebg': '#ececec',
    'buttonactivefg': '#000000',
    'highlightbackground': '#a0a0a0',
}

def _detect_kde_theme():
    """Detecta el tema en KDE Plasma usando kreadconfig o kdeglobals."""
    for kread in ('kreadconfig5', 'kreadconfig6'):
        if shutil.which(kread):
            try:
                result = subprocess.run(
                    [kread, '--file', 'kdeglobals', '--group', 'General', '--key', 'ColorScheme'],
                    capture_output=True, text=True, timeout=2
                )
                scheme = result.stdout.strip()
                debug(f"KDE ColorScheme ({kread}): {scheme}")
                if scheme:
                    if 'dark' in scheme.lower():
                        return 'dark'
                    else:
                        return 'light'
            except Exception as e:
                debug(f"Error con {kread}: {e}")

    kdeglobals = Path.home() / ".config" / "kdeglobals"
    if kdeglobals.exists():
        try:
            content = kdeglobals.read_text()
            for line in content.splitlines():
                if line.strip().startswith("ColorScheme="):
                    scheme = line.split("=", 1)[1].strip()
                    debug(f"KDE ColorScheme (kdeglobals): {scheme}")
                    if 'dark' in scheme.lower():
                        return 'dark'
                    else:
                        return 'light'
        except Exception as e:
            debug(f"Error leyendo kdeglobals: {e}")

    return None

def _detect_gnome_theme():
    """Detecta el tema en GNOME usando gsettings."""
    try:
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
            capture_output=True, text=True, timeout=2
        )
        out = result.stdout.strip().lower()
        debug(f"GNOME color-scheme: {out}")
        if 'dark' in out:
            return 'dark'
        elif 'light' in out:
            return 'light'
    except Exception as e:
        debug(f"Error con gsettings color-scheme: {e}")

    try:
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
            capture_output=True, text=True, timeout=2
        )
        out = result.stdout.strip().lower()
        debug(f"GNOME gtk-theme: {out}")
        if 'dark' in out:
            return 'dark'
        elif 'light' in out:
            return 'light'
    except Exception as e:
        debug(f"Error con gsettings gtk-theme: {e}")

    return None

def detect_system_theme():
    """Devuelve 'dark' o 'light' según el entorno de escritorio."""
    debug("Detectando tema del sistema...")
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    session = os.environ.get('DESKTOP_SESSION', '').lower()
    debug(f"XDG_CURRENT_DESKTOP: {desktop}, DESKTOP_SESSION: {session}")

    if 'kde' in desktop or 'plasma' in session:
        result = _detect_kde_theme()
        if result:
            return result

    if 'gnome' in desktop or 'unity' in desktop or 'cinnamon' in desktop:
        result = _detect_gnome_theme()
        if result:
            return result

    result = _detect_kde_theme()
    if result:
        return result
    result = _detect_gnome_theme()
    if result:
        return result

    theme_env = os.environ.get('GTK_THEME', '')
    if theme_env:
        debug(f"GTK_THEME: {theme_env}")
        if 'dark' in theme_env.lower():
            return 'dark'
        elif 'light' in theme_env.lower():
            return 'light'

    debug("Sin información fiable, asumiendo claro")
    return 'light'

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

        # Ventanas informativas
        self.guide_window = None
        self.credits_window = None

        # Tema
        self.current_theme = detect_system_theme()
        self.open_toplevels = []

        # Construir interfaz
        self.build_ui()
        self.apply_theme_to_widget(self.root)

        # Asegurar que la raíz quede correctamente coloreada
        if self.current_theme == 'dark':
            self.root.configure(bg=DARK_THEME['bg'],
                                highlightbackground=DARK_THEME['bg'],
                                highlightcolor=DARK_THEME['bg'])

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Inicializar datos
        self.refresh_library()
        self.reload_playlist_listbox()
        self.root.after(POLL_INTERVAL_MS, self.poll_playback)
        self.root.after(THEME_POLL_INTERVAL_MS, self.poll_theme_changes)

        if self.lib_files:
            self.lib_listbox.selection_set(0)
            self.lib_listbox.activate(0)
            self.lib_listbox.see(0)
            self.lib_listbox.focus_set()

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

    # --------------- Funciones de tema ---------------
    def apply_theme_to_widget(self, widget):
        """Aplica el tema actual (claro u oscuro) a un widget y sus hijos."""
        colors = DARK_THEME if self.current_theme == 'dark' else LIGHT_THEME
        cls = widget.winfo_class()
        try:
            if cls in ('Frame', 'Labelframe', 'Toplevel', 'Tk'):
                widget.configure(bg=colors['bg'])
                widget.configure(highlightbackground=colors['bg'], highlightcolor=colors['bg'])
                if cls != 'Labelframe':
                    widget.configure(bd=0)
            elif cls == 'Label':
                widget.configure(bg=colors['bg'], fg=colors['fg'])
                widget.configure(highlightbackground=colors['bg'], highlightcolor=colors['bg'])
            elif cls == 'Listbox':
                widget.configure(
                    bg=colors['entrybg'], fg=colors['entryfg'],
                    selectbackground=colors['selectbg'], selectforeground=colors['selectfg'],
                    highlightbackground=colors['highlightbackground'],
                    highlightcolor=colors['highlightbackground'],
                    highlightthickness=1 if self.current_theme == 'light' else 0,
                    relief='solid' if self.current_theme == 'light' else 'flat'
                )
            elif cls == 'Scale':
                widget.configure(
                    bg=colors['scalebg'], fg=colors['scalefg'],
                    troughcolor=colors['troughcolor'],
                    highlightbackground=colors['highlightbackground'],
                    highlightcolor=colors['highlightbackground'],
                    highlightthickness=1 if self.current_theme == 'light' else 0
                )
            elif cls in ('Text', 'Entry'):
                widget.configure(
                    bg=colors['textbg'], fg=colors['textfg'],
                    insertbackground=colors['fg'],
                    selectbackground=colors['selectbg'], selectforeground=colors['selectfg'],
                    highlightbackground=colors['highlightbackground'],
                    highlightcolor=colors['highlightbackground'],
                    highlightthickness=1 if self.current_theme == 'light' else 0
                )
            elif cls == 'Button':
                widget.configure(
                    bg=colors['buttonbg'], fg=colors['buttonfg'],
                    activebackground=colors['buttonactivebg'],
                    activeforeground=colors['buttonactivefg'],
                    highlightbackground=colors['highlightbackground'],
                    highlightcolor=colors['highlightbackground'],
                    highlightthickness=1 if self.current_theme == 'light' else 0,
                    relief='raised' if self.current_theme == 'light' else 'flat'
                )
            elif cls in ('Checkbutton', 'Radiobutton'):
                widget.configure(
                    bg=colors['bg'], fg=colors['fg'],
                    activebackground=colors['bg'],
                    activeforeground=colors['fg'],
                    selectcolor=colors['entrybg'],
                    highlightbackground=colors['bg'],
                    highlightcolor=colors['bg']
                )
        except tk.TclError as e:
            debug(f"Error aplicando tema a {cls}: {e}")

        for child in widget.winfo_children():
            self.apply_theme_to_widget(child)

    def apply_theme_to_all(self):
        """Aplica el tema a la ventana principal y a todas las emergentes."""
        # Primero, asegurar que la raíz tiene el color correcto
        if self.current_theme == 'dark':
            self.root.configure(bg=DARK_THEME['bg'],
                                highlightbackground=DARK_THEME['bg'],
                                highlightcolor=DARK_THEME['bg'])
        else:
            self.root.configure(bg=LIGHT_THEME['bg'],
                                highlightbackground=LIGHT_THEME['bg'],
                                highlightcolor=LIGHT_THEME['bg'])
        # Luego, aplicar a todos los widgets (incluida la raíz)
        for widget in [self.root] + self.open_toplevels[:]:
            if widget.winfo_exists():
                self.apply_theme_to_widget(widget)
        # Forzar actualización visual
        self.root.update_idletasks()
        self.root.update()

    def poll_theme_changes(self):
        new_theme = detect_system_theme()
        if new_theme != self.current_theme:
            debug(f"Cambio de tema detectado: {self.current_theme} -> {new_theme}")
            self.current_theme = new_theme
            self.apply_theme_to_all()
        self.root.after(THEME_POLL_INTERVAL_MS, self.poll_theme_changes)

    # --------------- Ventana informativa sin botón OK ---------------
    def _info(self, title, message):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.resizable(False, False)

        tk.Label(dlg, text=message, wraplength=450, justify="left",
                 font=("TkDefaultFont", 12), padx=20, pady=20).pack()

        dlg.wait_visibility()
        dlg.grab_set()

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.bind("<q>", lambda e: dlg.destroy())
        dlg.bind("<Q>", lambda e: dlg.destroy())
        dlg.bind("<Return>", lambda e: dlg.destroy())

        dlg.focus_set()
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")

        self.apply_theme_to_widget(dlg)
        self.open_toplevels.append(dlg)
        dlg.bind("<Destroy>", lambda e: self.open_toplevels.remove(dlg) if dlg in self.open_toplevels else None)

    # ==================== Ventanas de ayuda (toggle) ====================
    def toggle_guide(self):
        if self.guide_window and self.guide_window.winfo_exists():
            self.guide_window.destroy()
            self.guide_window = None
            return
        self._show_guide_window()

    def toggle_credits(self):
        if self.credits_window and self.credits_window.winfo_exists():
            self.credits_window.destroy()
            self.credits_window = None
            return
        self._show_credits_window()

    def _show_guide_window(self):
        guia_texto = (
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
            "• Tecla V: Reproducir toda la playlist activa\n"
            "• Tecla P: Nueva playlist\n"
            "• Tecla O: Cargar playlist (Enter para seleccionar)\n"
            "• Tecla L: Activar/desactivar bucle\n"
            "• Tecla S: Activar/desactivar modo aleatorio\n"
            "• Control derecho: Créditos\n"
            "• Tecla ?: Mostrar esta ayuda\n\n"
            "Pulsa ? de nuevo, Escape o Q para cerrar."
        )

        dlg = tk.Toplevel(self.root)
        dlg.title("Guía de Controles")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("560x550")
        dlg.resizable(False, False)

        text_widget = tk.Text(dlg, wrap="word", font=("TkDefaultFont", 10), padx=10, pady=10)
        text_widget.insert("1.0", guia_texto)
        text_widget.config(state="disabled")
        text_widget.pack(fill="both", expand=True, padx=12, pady=12)

        def _on_mousewheel(event):
            text_widget.yview_scroll(int(-1*(event.delta/120)), "units")
        text_widget.bind("<MouseWheel>", _on_mousewheel)
        text_widget.bind("<Button-4>", lambda e: text_widget.yview_scroll(-1, "units"))
        text_widget.bind("<Button-5>", lambda e: text_widget.yview_scroll(1, "units"))

        dlg.bind("<question>", lambda e: self._close_guide(dlg))
        dlg.bind("<Escape>", lambda e: self._close_guide(dlg))
        dlg.bind("<q>", lambda e: self._close_guide(dlg))
        dlg.bind("<Q>", lambda e: self._close_guide(dlg))
        dlg.protocol("WM_DELETE_WINDOW", lambda: self._close_guide(dlg))
        self.guide_window = dlg
        dlg.focus_set()

        self.apply_theme_to_widget(dlg)
        self.open_toplevels.append(dlg)
        dlg.bind("<Destroy>", lambda e: self.open_toplevels.remove(dlg) if dlg in self.open_toplevels else None)

    def _close_guide(self, dlg):
        if self.guide_window == dlg:
            dlg.destroy()
            self.guide_window = None

    def _show_credits_window(self):
        creditos = (
            "Monojo Music 2.3\n\n"
            "Desarrollado por David Baña Szymaniak\n"
            "Monojo Project\n\n"
            "Licencia GPL v3 o posterior\n\n"
            "Usa ffplay como backend."
            )
        dlg = tk.Toplevel(self.root)
        dlg.title("Créditos")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        tk.Label(dlg, text=creditos, wraplength=400, justify="left", padx=20, pady=20).pack()
        dlg.bind("<Control_R>", lambda e: self._close_credits(dlg))
        dlg.bind("<Escape>", lambda e: self._close_credits(dlg))
        dlg.bind("<q>", lambda e: self._close_credits(dlg))
        dlg.bind("<Q>", lambda e: self._close_credits(dlg))
        dlg.protocol("WM_DELETE_WINDOW", lambda: self._close_credits(dlg))
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")
        self.credits_window = dlg
        dlg.focus_set()

        self.apply_theme_to_widget(dlg)
        self.open_toplevels.append(dlg)
        dlg.bind("<Destroy>", lambda e: self.open_toplevels.remove(dlg) if dlg in self.open_toplevels else None)

    def _close_credits(self, dlg):
        if self.credits_window == dlg:
            dlg.destroy()
            self.credits_window = None

    # ==================== INTERFAZ GRÁFICA ====================
    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=6, pady=6)
        tk.Button(top, text="Nueva Playlist", command=self.new_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Guardar Playlist", command=self.save_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Cargar Playlist", command=self.choose_and_load_playlist).pack(side="left", padx=4)
        tk.Button(top, text="Créditos", command=self.toggle_credits).pack(side="right", padx=4)
        tk.Button(top, text="Atajos de teclado", command=self.toggle_guide).pack(side="right", padx=4)

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

    # ==================== MÉTODOS DE TECLADO Y ACCIONES ====================
    def on_key_press(self, event):
        try:
            if event.widget.winfo_class() in ("Entry", "Text", "Spinbox"):
                return
        except Exception:
            pass
        is_ctrl = (event.state & 0x0004) != 0
        sym = event.keysym
        char = event.char.lower() if event.char else ""

        if char == 'p':
            self.new_playlist()
            return
        if char == 'o':
            self.choose_and_load_playlist()
            return
        if char == 'l':
            self.toggle_loop()
            return
        if char == 's':
            self.toggle_shuffle()
            return
        if sym == "Control_R":
            self.toggle_credits()
            return
        if char == '?':
            self.toggle_guide()
            return

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
                self._info("Error", f"No se pudo revertir el renombrado:\n{e}")

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
                self._info("Error", f"No se pudo copiar: {p}")
        if added:
            self.refresh_library()
            if self.lib_files:
                self.lib_listbox.selection_set(0)
                self.lib_listbox.activate(0)
                self.lib_listbox.see(0)
                self.lib_listbox.focus_set()

    def delete_music(self):
        sel = list(self.lib_listbox.curselection())
        if not sel:
            self._info("Eliminar MP3", "Selecciona archivos en la biblioteca para eliminar.")
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
                self._info("Error", f"No se pudo borrar: {n}")
        self.undo_stack.clear()
        self.refresh_library()
        self.playlist_items = [x for x in self.playlist_items if x not in names]
        self.reload_playlist_listbox()
        if self.lib_files:
            self.lib_listbox.selection_set(0)
            self.lib_listbox.activate(0)
            self.lib_listbox.see(0)
            self.lib_listbox.focus_set()

    def rename_music(self):
        sel = self.lib_listbox.curselection()
        if not sel:
            self._info("Renombrar", "Selecciona una canción en la biblioteca para renombrar.")
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
            self._info("Atención", f"Ya existe una canción con el nombre '{new_base}'. No se hará nada.")
            return
        try:
            os.rename(old_path, new_path)
        except Exception as e:
            self._info("Error", f"No se pudo renombrar el archivo:\n{e}")
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
        self._info("Playlist", f"Playlist '{name}' creada (vacía).")

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
            self._info("Guardado", f"Playlist guardada: {path}")
        except Exception as e:
            self._info("Error", f"No se pudo guardar playlist:\n{e}")

    def choose_and_load_playlist(self):
        files = [f for f in os.listdir(PLAYLIST_DIR) if f.endswith(".txt")]
        if not files:
            self.new_playlist()
            return

        top = tk.Toplevel(self.root)
        top.title("Seleccionar Playlist")
        top.geometry("300x400")
        top.transient(self.root)
        top.grab_set()

        tk.Label(top, text="Selecciona una playlist para cargar:").pack(pady=10)

        listbox = tk.Listbox(top, selectmode="single", exportselection=False)
        listbox.pack(fill="both", expand=True, padx=15, pady=5)

        for f in files:
            listbox.insert(tk.END, f[:-4])

        if listbox.size() > 0:
            listbox.selection_set(0)
            listbox.activate(0)
            listbox.focus_set()

        def move_selection(delta):
            cur = listbox.curselection()
            if not cur:
                new_idx = 0
            else:
                new_idx = cur[0] + delta
            if 0 <= new_idx < listbox.size():
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(new_idx)
                listbox.activate(new_idx)
                listbox.see(new_idx)
            return "break"

        listbox.bind("<Up>", lambda e: move_selection(-1))
        listbox.bind("<Down>", lambda e: move_selection(1))

        def on_load():
            sel = listbox.curselection()
            if not sel:
                return
            choice = listbox.get(sel[0])
            top.destroy()
            self.root.after(50, lambda: self._load_playlist_file(choice))

        listbox.bind("<Double-Button-1>", lambda e: on_load())
        listbox.bind("<Return>", lambda e: on_load())
        top.bind("<Escape>", lambda e: top.destroy())
        top.bind("<q>", lambda e: top.destroy())
        top.bind("<Q>", lambda e: top.destroy())

        self.apply_theme_to_widget(top)
        self.open_toplevels.append(top)
        top.bind("<Destroy>", lambda e: self.open_toplevels.remove(top) if top in self.open_toplevels else None)

    def _load_playlist_file(self, choice):
        path = os.path.join(PLAYLIST_DIR, choice + ".txt")
        if not os.path.exists(path):
            self._info("Error", "No existe esa playlist.")
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
        self._info("Cargada", f"Playlist '{choice}' cargada con {len(loaded)} canciones.")

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
        if not self.playlist_name:
            self._info("Sin Playlist", "No hay ninguna playlist abierta. Crea o carga una playlist primero.")
            return
        sel = list(self.lib_listbox.curselection())
        if not sel:
            self._info("Sin selección", "Selecciona una canción en la Biblioteca para añadir a Playlist.")
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
            self._info("Sin Playlist", "No hay ninguna playlist abierta.")
            return
        sel = self.pl_listbox.curselection()
        if not sel:
            self._info("Sin selección", "Selecciona una canción en la Playlist para mover.")
            return
        i = sel[0]
        if i == 0:
            self._info("Límite", "Esta canción ya está en la primera posición.")
            return
        j = i - 1
        self.playlist_items[i], self.playlist_items[j] = self.playlist_items[j], self.playlist_items[i]
        self.undo_stack.append({"action": "move_pl", "idx1": i, "idx2": j})
        self.reload_playlist_listbox()
        self.pl_listbox.select_set(j)

    def move_in_playlist_down(self):
        if not self.playlist_items:
            self._info("Sin Playlist", "No hay ninguna playlist abierta.")
            return
        sel = self.pl_listbox.curselection()
        if not sel:
            self._info("Sin selección", "Selecciona una canción en la Playlist para mover.")
            return
        i = sel[0]
        if i == len(self.playlist_items) - 1:
            self._info("Límite", "Esta canción ya está en la última posición.")
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
            self._info("Error", "No se pudo ejecutar el reproductor (ffplay).")
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

    def play_playlist(self, start_index=0):
        if not self.playlist_items:
            self._info("Playlist", "La playlist está vacía.")
            return
        if start_index < 0 or start_index >= len(self.playlist_items):
            start_index = 0
        self.playlist_index = start_index
        name = self.playlist_items[self.playlist_index]
        path = os.path.join(MUSIC_DIR, name)
        if not os.path.exists(path):
            self._info("Error", f"No existe: {name}")
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
        # Detener reproducción y cerrar procesos
        try:
            if self.play_proc:
                self.play_proc.terminate()
                try:
                    self.play_proc.wait(timeout=1)
                except Exception:
                    self.play_proc.kill()
        except Exception:
            pass
        # Guardar playlist actual
        if self.playlist_name:
            try:
                path = os.path.join(PLAYLIST_DIR, self.playlist_name + ".txt")
                with open(path, "w", encoding="utf-8") as f:
                    for it in self.playlist_items:
                        f.write(it + "\n")
            except Exception:
                pass
        # Cerrar todas las ventanas hijas
        for toplevel in self.open_toplevels[:]:
            try:
                if toplevel.winfo_exists():
                    toplevel.destroy()
            except Exception:
                pass
        self.root.destroy()

# ==================== ARRANQUE ====================
def start_glib_loop():
    if MPRIS_AVAILABLE:
        try:
            loop = GLib.MainLoop()
            loop.run()
        except Exception as e:
            debug(f"Error en el bucle GLib: {e}")

if __name__ == "__main__":
    debug("Entrando en __main__")
    try:
        if MPRIS_AVAILABLE:
            threading.Thread(target=start_glib_loop, daemon=True).start()
        root = tk.Tk(className="monojo_music_main")
        app = MonojoMusicApp(root)
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
        root.mainloop()
    except Exception as e:
        debug(f"ERROR FATAL: {e}")
        import traceback
        debug(traceback.format_exc())
        sys.exit(1)
