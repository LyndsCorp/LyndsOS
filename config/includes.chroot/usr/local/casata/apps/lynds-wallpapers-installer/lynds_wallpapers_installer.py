#!/bin/python3
import tkinter as tk
from tkinter import ttk
import threading
import os
import shutil
import zipfile
import tempfile
import urllib.request
import json
import io
import uuid
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw

# --- Configuración del Sistema Operativo ---
GITHUB_USER = "Monojo-Project"
GITHUB_REPO = "Lynds-Wallpapers"
INSTALL_BASE = os.path.expanduser("~/.local/share/wallpapers")
CACHE_BASE = os.path.expanduser("~/.cache/lynds-wallpapers")

# Endpoints de la API de GitHub
API_BRANCHES = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/branches"
API_CONTENTS = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents?ref={{branch}}"
API_COMMITS  = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/commits?per_page=4"
ZIP_URL = "https://github.com/{user}/{repo}/archive/refs/heads/{branch}.zip"
RAW_RECOMENDACIONES = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/Recomendaciones"
RAW_NOVEDADES = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/Novedades"

# Rutas de cache para Recomendaciones y Novedades
CACHE_RECOMENDACIONES = os.path.expanduser("~/.cache/lynds-wallpapers/Recomendaciones")
CACHE_NOVEDADES = os.path.expanduser("~/.cache/lynds-wallpapers/Novedades")

class LyndsExecutive(tk.Tk):
    def __init__(self):
        super().__init__(className="lynds_wallpapers_main")
        self.title("Lynds Wallpapers")
        self.geometry("1100x780")
        self.configure(bg="#0a0c0a")

        try:
            icon_img = tk.PhotoImage(file="/usr/share/icons/hicolor/256x256/apps/lynds-wallpapers.png")
            self.iconphoto(False, icon_img)
        except Exception:
            pass

        self.offline_mode = False
        try:
            urllib.request.urlopen("https://api.github.com", timeout=2)
        except Exception:
            self.offline_mode = True

        self.selected_branch = None
        self.selected_files = set()
        self.preview_img = None
        self.current_session_id = None
        self.all_branches = []
        self.thumb_btns = {}
        self.is_downloading = False

        # Nuevos atributos para selección por rango
        self.image_order = []        # Lista ordenada de nombres de imágenes
        self.last_selected = None    # Último archivo seleccionado (para shift)

        # Caché en RAM de la Sesión
        self.session_raw = {}
        self.session_thumbs = {}

        self.c_bg       = "#0a0c0a"
        self.c_side     = "#0f110f"
        self.c_neon     = "#22c55e"
        self.c_neon_dim = "#155e27"
        self.c_text     = "#e2e8f0"
        self.c_btn      = "#142618"
        self.c_alert    = "#ef4444"
        self.c_alert_bg = "#271414"

        # ── SIDEBAR ────────────────────────────────────────────────────────────
        self.sidebar = tk.Frame(self, bg=self.c_side, width=300,
                                highlightbackground=self.c_neon_dim, highlightthickness=1)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        if self.offline_mode:
            tk.Label(self.sidebar, text="⚠ MODO OFFLINE ⚠\nCaché y Archivos Locales", bg=self.c_alert_bg, fg=self.c_alert,
                     font=("Courier", 10, "bold")).pack(pady=(15, 0), fill="x", padx=15)

        tk.Label(self.sidebar, text="⚡ PAQUETES DISPONIBLES ⚡", bg=self.c_side, fg=self.c_neon,
                 font=("Courier", 11, "bold")).pack(pady=(18 if not self.offline_mode else 10, 6), fill="x", padx=15)

        self.search_var = tk.StringVar()
        # El trace se conecta después de que scroll_frame exista

        search_frame = tk.Frame(self.sidebar, bg="#050705",
                                highlightbackground=self.c_neon_dim, highlightthickness=1)
        search_frame.pack(fill="x", padx=15, pady=(0, 12))

        tk.Label(search_frame, text=" 🔍 ", bg="#050705", fg=self.c_neon,
                 font=("Courier", 10)).pack(side="left")

        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                     bg="#050705", fg=self.c_text,
                                     insertbackground=self.c_neon,
                                     font=("Courier", 11), relief="flat", bd=0)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self.search_entry.insert(0, "Buscar paquete...")
        self.search_entry.bind("<FocusIn>",
            lambda e: self.search_entry.delete(0, tk.END)
            if self.search_var.get() == "Buscar paquete..." else None)

        self.package_outer_frame = tk.Frame(self.sidebar, bg=self.c_side)
        self.package_outer_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.package_canvas = tk.Canvas(self.package_outer_frame, bg=self.c_side, bd=0, highlightthickness=0)
        self.v_scrollbar = tk.Scrollbar(self.package_outer_frame, orient="vertical", command=self.package_canvas.yview,
                                        bg=self.c_neon, troughcolor="#050705", activebackground=self.c_neon)

        self.scroll_frame = tk.Frame(self.package_canvas, bg=self.c_side)
        # Se ha eliminado el bind <Configure> que interfería

        self.package_canvas_window = self.package_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.package_canvas.configure(yscrollcommand=self.v_scrollbar.set)
        self.package_canvas.bind('<Configure>', lambda e: self.package_canvas.itemconfig(self.package_canvas_window, width=e.width))

        self.package_canvas.pack(side="left", fill="both", expand=True)
        self.v_scrollbar.pack(side="right", fill="y")

        self.package_canvas.bind("<MouseWheel>", self._on_vertical_mousewheel)
        self.package_canvas.bind("<Button-4>", self._on_vertical_mousewheel)
        self.package_canvas.bind("<Button-5>", self._on_vertical_mousewheel)

        # Ahora sí, conectamos el trace
        self.search_var.trace_add("write", self.filter_branches)

        self.rec_frame = tk.Frame(self.sidebar, bg=self.c_side)
        self.rec_frame.pack(fill="x", side="bottom", padx=10, pady=(0, 15))

        tk.Label(self.rec_frame, text="🔥 RECOMENDADOS", bg=self.c_side,
                 fg=self.c_neon, font=("Courier", 10, "bold"),
                 anchor="w").pack(fill="x", padx=5, pady=(0, 4))

        self.rec_list_frame = tk.Frame(self.rec_frame, bg=self.c_side)
        self.rec_list_frame.pack(fill="x")

        self.news_frame = tk.Frame(self.sidebar, bg=self.c_side)
        self.news_frame.pack(fill="x", side="bottom", padx=10, pady=(5, 5))

        tk.Label(self.news_frame, text="📢 NOVEDADES", bg=self.c_side,
                 fg=self.c_neon, font=("Courier", 10, "bold"),
                 anchor="w").pack(fill="x", padx=5, pady=(0, 4))

        self.lbl_news_box = tk.Label(self.news_frame, text="Iniciando...",
                                     bg="#050705", fg="#a1a1aa", font=("Courier", 9),
                                     justify="left", anchor="w", padx=10, pady=6,
                                     highlightbackground="#1e293b", highlightthickness=1)
        self.lbl_news_box.pack(fill="x")

        # ── ÁREA PRINCIPAL ─────────────────────────────────────────────────────
        self.main_area = tk.Frame(self, bg=self.c_bg)
        self.main_area.pack(side="right", expand=True, fill="both", padx=20, pady=16)

        # ── TOP FRAME CON TÍTULO Y BOTÓN LIMPIAR CACHÉ ──
        self.top_frame = tk.Frame(self.main_area, bg=self.c_bg)
        self.top_frame.pack(fill="x", pady=(0, 8))

        self.lbl_title_top = tk.Label(self.top_frame, text="Fondos de pantalla libres",
                 fg=self.c_neon_dim, bg=self.c_bg, font=("Courier", 9, "bold"))
        self.lbl_title_top.pack(anchor="nw", side="left", expand=True)

        self.btn_clear_cache = tk.Button(self.top_frame, text="🗑️ LIMPIAR CACHÉ",
                                         bg=self.c_alert_bg, fg=self.c_alert,
                                         font=("Courier", 8, "bold"),
                                         activebackground=self.c_alert, activeforeground="white",
                                         command=self.clear_cache, relief="flat", padx=10, pady=4)
        self.btn_clear_cache.pack(anchor="ne", side="right")

        self.title_label = tk.Label(self.main_area, text="SELECCIONA UN PAQUETE",
                                    fg=self.c_neon, bg=self.c_bg, font=("Courier", 13, "bold"))
        self.title_label.pack(pady=(2, 8))

        self.preview_neon_border = tk.Frame(self.main_area, bg=self.c_bg,
                                            highlightbackground=self.c_neon_dim, highlightthickness=2)
        self.preview_neon_border.pack(fill="none", anchor="center")

        self.preview_frame = tk.Frame(self.preview_neon_border, bg="#050705", width=640, height=360)
        self.preview_frame.pack_propagate(False)
        self.preview_frame.pack()

        self.preview_label = tk.Label(self.preview_frame, text="[ SELECCIONA UN PAQUETE PARA PREVISUALIZAR ]",
                                      fg=self.c_neon, bg="#050705", font=("Courier", 11))
        self.preview_label.pack(expand=True, fill="both")

        tk.Label(self.main_area, text="▼ IMÁGENES DEL PAQUETE ▼",
                 fg=self.c_neon, bg=self.c_bg, font=("Courier", 9, "bold")).pack(pady=(12, 2))

        self.thumbs_outer_frame = tk.Frame(self.main_area, bg=self.c_side, height=135,
                                           highlightbackground="#1e293b", highlightthickness=1)
        self.thumbs_outer_frame.pack(fill="x", padx=0, pady=2)
        self.thumbs_outer_frame.pack_propagate(False)

        self.thumb_canvas = tk.Canvas(self.thumbs_outer_frame, bg=self.c_side, bd=0, highlightthickness=0, height=105)
        self.h_scrollbar = tk.Scrollbar(self.thumbs_outer_frame, orient="horizontal", command=self.thumb_canvas.xview,
                                        bg=self.c_side, troughcolor="#050705", activebackground=self.c_neon)

        self.thumbs_frame = tk.Frame(self.thumb_canvas, bg=self.c_side)
        self.thumbs_frame.bind("<Configure>", lambda e: self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all")))

        self.thumb_canvas_window = self.thumb_canvas.create_window((0, 0), window=self.thumbs_frame, anchor="nw")
        self.thumb_canvas.configure(xscrollcommand=self.h_scrollbar.set)

        self.thumb_canvas.pack(side="top", fill="x", expand=True)
        self.h_scrollbar.pack(side="bottom", fill="x")

        self.thumb_canvas.bind("<MouseWheel>", self._on_horizontal_mousewheel)
        self.thumb_canvas.bind("<Button-4>", self._on_horizontal_mousewheel)
        self.thumb_canvas.bind("<Button-5>", self._on_horizontal_mousewheel)
        self.thumbs_outer_frame.bind("<MouseWheel>", self._on_horizontal_mousewheel)
        self.thumbs_outer_frame.bind("<Button-4>", self._on_horizontal_mousewheel)
        self.thumbs_outer_frame.bind("<Button-5>", self._on_horizontal_mousewheel)

        self.control_frame = tk.Frame(self.main_area, bg=self.c_bg)
        self.control_frame.pack(pady=12, fill="x")

        for col in range(4): self.control_frame.grid_columnconfigure(col, weight=1)

        self.btn_install = tk.Button(
            self.control_frame, text="⚡ INSTALAR PACK COMPLETO",
            bg=self.c_btn, fg=self.c_neon, activebackground=self.c_neon, activeforeground=self.c_bg,
            font=("Courier", 10, "bold"), height=2, command=self.install_package, state="disabled", relief="flat")
        self.btn_install.grid(row=0, column=0, padx=4, sticky="ew")

        self.btn_install_selected = tk.Button(
            self.control_frame, text="🖼️ GUARDAR SELECCIÓN",
            bg=self.c_btn, fg=self.c_neon, activebackground=self.c_neon, activeforeground=self.c_bg,
            font=("Courier", 10, "bold"), height=2, command=self.install_selected_images, state="disabled", relief="flat")
        self.btn_install_selected.grid(row=0, column=1, padx=4, sticky="ew")

        self.btn_uninstall_selected = tk.Button(
            self.control_frame, text="🗑️ ELIMINAR SELECCIÓN",
            bg=self.c_alert_bg, fg=self.c_alert, activebackground=self.c_alert, activeforeground="white",
            font=("Courier", 10, "bold"), height=2, command=self.uninstall_selected_images, state="disabled", relief="flat")
        self.btn_uninstall_selected.grid(row=0, column=2, padx=4, sticky="ew")

        self.btn_uninstall = tk.Button(
            self.control_frame, text="❌ ELIMINAR PACK",
            bg=self.c_alert_bg, fg=self.c_alert, activebackground=self.c_alert, activeforeground="white",
            font=("Courier", 10, "bold"), height=2, command=self.uninstall_package, state="disabled", relief="flat")
        self.btn_uninstall.grid(row=0, column=3, padx=4, sticky="ew")

        # ── BARRA DE PROGRESO (oculta por defecto) ──
        self.progress_frame = tk.Frame(self.main_area, bg=self.c_bg)
        self.progress_frame.pack(fill="x", pady=8)

        self.progress_label = tk.Label(self.progress_frame, text="",
                                       fg=self.c_neon, bg=self.c_bg, font=("Courier", 9, "bold"))
        self.progress_label.pack(anchor="w", padx=2)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate',
                                            length=400, style="Custom.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", padx=2, pady=(4, 0))

        # Estilo personalizado para la barra de progreso
        style = ttk.Style()
        style.configure("Custom.Horizontal.TProgressbar",
                       background="#22c55e", troughcolor="#050705", bordercolor="#155e27")

        self.progress_frame.pack_forget()  # Ocultar inicialmente

        self.status_label = tk.Label(self.main_area, text="Lynds Wallpapers",
                                     fg=self.c_neon, bg=self.c_bg, font=("Courier", 10, "bold"))
        self.status_label.pack(side="bottom", fill="x", pady=4)

        self.refresh_data()

    # ── MÉTODOS DE SCROLL ──────────────────────────────────────────────────────
    def _on_vertical_mousewheel(self, event):
        if event.num == 4: self.package_canvas.yview_scroll(-1, "units")
        elif event.num == 5: self.package_canvas.yview_scroll(1, "units")
        else: self.package_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_horizontal_mousewheel(self, event):
        """Desplazamiento horizontal para la galería de miniaturas."""
        if event.num == 4:          # Linux scroll up
            delta = -1
        elif event.num == 5:        # Linux scroll down
            delta = 1
        else:                       # Windows / macOS
            delta = -1 * (event.delta / 120) if event.delta else 0
        self.thumb_canvas.xview_scroll(int(delta), "units")

    # ── LIMPIAR CACHÉ ──────────────────────────────────────────────────────────
    def clear_cache(self):
        """Elimina todos los archivos de caché"""
        try:
            if os.path.exists(CACHE_BASE):
                shutil.rmtree(CACHE_BASE)
                os.makedirs(CACHE_BASE, exist_ok=True)

            # Limpiar caché en RAM
            self.session_raw.clear()
            self.session_thumbs.clear()

            self.status_label.config(text="✅ CACHÉ LIMPIADO CORRECTAMENTE")
            self.btn_clear_cache.config(relief="flat")
        except Exception as e:
            self.status_label.config(text=f"❌ ERROR AL LIMPIAR CACHÉ: {e}")

    # ── SINCRO Y GESTIÓN DE STRINGS ────────────────────────────────────────────
    def refresh_data(self):
        if self.offline_mode:
            self.lbl_news_box.config(text="• Modo Offline\n• Funciones limitadas", fg=self.c_alert)
            tk.Label(self.rec_list_frame, text="No disponible offline", fg=self.c_alert, bg=self.c_side, font=("Courier", 9, "italic")).pack(fill="x", padx=5)

            # Intentar cargar desde caché en modo offline
            try:
                if os.path.exists(CACHE_NOVEDADES):
                    with open(CACHE_NOVEDADES, 'r', encoding='utf-8') as f:
                        text = f.read()
                    self.lbl_news_box.config(text=text, fg="#a1a1aa")
            except Exception:
                pass

            try:
                if os.path.exists(CACHE_RECOMENDACIONES):
                    with open(CACHE_RECOMENDACIONES, 'r', encoding='utf-8') as f:
                        lines = [l.strip() for l in f.read().split("\n") if l.strip()]

                    for w in self.rec_list_frame.winfo_children():
                        w.destroy()

                    for item in lines:
                        clean = item.replace("-", " ")
                        tk.Button(self.rec_list_frame, text=f"🔥 {clean.upper()}",
                                  bg="#050705", fg=self.c_neon, font=("Courier", 10, "bold"), anchor="w", padx=12, pady=4,
                                  activebackground=self.c_neon, activeforeground=self.c_bg, relief="flat",
                                  command=lambda name=item: self.select_branch(name)).pack(fill="x", padx=5, pady=2)
            except Exception:
                pass
        else:
            threading.Thread(target=self._fetch_recommendations_thread, daemon=True).start()
            threading.Thread(target=self._fetch_news_thread, daemon=True).start()
        threading.Thread(target=self._fetch_branches_thread, daemon=True).start()

    def _fetch_news_thread(self):
        try:
            req = urllib.request.Request(RAW_NOVEDADES, headers={"User-Agent": "Lynds-Exec"})
            with urllib.request.urlopen(req) as res:
                text = res.read().decode('utf-8')

                # Guardar en caché
                os.makedirs(os.path.dirname(CACHE_NOVEDADES), exist_ok=True)
                with open(CACHE_NOVEDADES, 'w', encoding='utf-8') as f:
                    f.write(text)

                self.after(0, lambda: self.lbl_news_box.config(text=text, fg=self.c_neon))
        except Exception:
            # Intentar cargar desde caché si hay error de conexión
            try:
                if os.path.exists(CACHE_NOVEDADES):
                    with open(CACHE_NOVEDADES, 'r', encoding='utf-8') as f:
                        text = f.read()
                    self.after(0, lambda: self.lbl_news_box.config(text=text, fg="#a1a1aa"))
            except Exception:
                pass

    def filter_branches(self, *args):
        query = self.search_var.get().lower().strip()
        if not query or query == "buscar paquete...": filtered = self.all_branches
        else: filtered = [b for b in self.all_branches if query in b.lower() or query in b.replace("-", " ").lower()]
        self._render_list(filtered)

    def _fetch_branches_thread(self):
        if self.offline_mode:
            local_branches = set()
            if os.path.exists(INSTALL_BASE):
                local_branches.update([d for d in os.listdir(INSTALL_BASE) if os.path.isdir(os.path.join(INSTALL_BASE, d)) and d != "Individual"])
            if os.path.exists(CACHE_BASE):
                local_branches.update([d for d in os.listdir(CACHE_BASE) if os.path.isdir(os.path.join(CACHE_BASE, d))])
            self.all_branches = list(local_branches)
            self.after(0, lambda: self._render_list(self.all_branches))
            return

        try:
            req = urllib.request.Request(API_BRANCHES, headers={"User-Agent": "Lynds-Exec"})
            with urllib.request.urlopen(req) as res:
                self.all_branches = [b['name'] for b in json.loads(res.read().decode()) if b['name'] not in ["main", "master"]]
                self.after(0, lambda: self._render_list(self.all_branches))
        except Exception as e:
            print(f"Error listando ramas: {e}")

    def _render_list(self, branches):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        if not branches:
            tk.Label(self.scroll_frame, text="Sin resultados" if not self.offline_mode else "Ningún paquete local",
                     fg=self.c_alert, bg=self.c_side, font=("Courier", 10, "italic")).pack(pady=10)
            self._update_scroll_region()
            return
        for b in sorted(branches):
            clean = b.replace("-", " ")
            btn = tk.Button(self.scroll_frame, text=f"• {clean}",
                      bg=self.c_btn, fg=self.c_text, font=("Courier", 11, "bold"), anchor="w", padx=15, pady=6,
                      activebackground=self.c_neon, activeforeground=self.c_bg, relief="flat",
                      command=lambda name=b: self.select_branch(name))
            btn.pack(fill="x", padx=8, pady=3)
            # Bindings para scroll sobre los botones (Windows y Linux)
            btn.bind("<MouseWheel>", self._on_vertical_mousewheel)
            btn.bind("<Button-4>", self._on_vertical_mousewheel)
            btn.bind("<Button-5>", self._on_vertical_mousewheel)

        # Forzamos actualización de scroll con un pequeño retardo
        self.after(10, self._update_scroll_region)

    def _update_scroll_region(self):
        """Ajusta la altura de la ventana del canvas y la región de scroll."""
        self.package_canvas.update_idletasks()
        self.package_canvas.itemconfig(self.package_canvas_window,
                                       height=self.scroll_frame.winfo_reqheight())
        self.package_canvas.configure(scrollregion=self.package_canvas.bbox("all"))
        self.package_canvas.yview_moveto(0)

    def _fetch_recommendations_thread(self):
        try:
            req = urllib.request.Request(RAW_RECOMENDACIONES, headers={"User-Agent": "Lynds-Exec"})
            with urllib.request.urlopen(req) as res:
                text = res.read().decode('utf-8')
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                # Guardar en caché
                os.makedirs(os.path.dirname(CACHE_RECOMENDACIONES), exist_ok=True)
                with open(CACHE_RECOMENDACIONES, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))

                self.after(0, lambda: self._render_recommendations(lines))
        except Exception:
            # Intentar cargar desde caché si hay error de conexión
            try:
                if os.path.exists(CACHE_RECOMENDACIONES):
                    with open(CACHE_RECOMENDACIONES, 'r', encoding='utf-8') as f:
                        lines = [l.strip() for l in f.read().split("\n") if l.strip()]
                    self.after(0, lambda: self._render_recommendations(lines))
                else:
                    self.after(0, lambda: self._render_recommendations(["Sin-Vida", "Cosmos-Legendario"]))
            except Exception:
                self.after(0, lambda: self._render_recommendations(["Sin-Vida", "Cosmos-Legendario"]))

    def _render_recommendations(self, lines):
        for w in self.rec_list_frame.winfo_children(): w.destroy()
        for item in lines:
            clean = item.replace("-", " ")
            tk.Button(self.rec_list_frame, text=f"🔥 {clean.upper()}",
                      bg="#050705", fg=self.c_neon, font=("Courier", 10, "bold"), anchor="w", padx=12, pady=4,
                      activebackground=self.c_neon, activeforeground=self.c_bg, relief="flat",
                      command=lambda name=item: self.select_branch(name)).pack(fill="x", padx=5, pady=2)

    # ── CARGA DE GALERÍA Y CACHÉ EN RAM ────────────────────────────────────
    def select_branch(self, branch):
        self.current_session_id = str(uuid.uuid4())
        self.selected_branch = branch
        clean = branch.replace("-", " ")
        self.title_label.config(text=f"PACK: {clean.upper()}")

        if self.offline_mode: self.btn_install.config(state="disabled", text="❌ SIN CONEXIÓN")
        else: self.btn_install.config(state="normal", text="⚡ INSTALAR PACK COMPLETO")

        self.btn_install_selected.config(state="disabled", text="🖼️ GUARDAR SELECCIÓN")
        self.btn_uninstall_selected.config(state="disabled", text="🗑️ ELIMINAR SELECCIÓN")
        self._update_uninstall_button_status(branch)

        for w in self.thumbs_frame.winfo_children(): w.destroy()
        self.thumb_canvas.xview_moveto(0)

        self.selected_files.clear()
        self.image_order.clear()
        self.last_selected = None
        self.preview_img = None
        self.thumb_btns.clear()

        self.preview_label.config(image="", text="⚙️ Procesando imágenes...")
        threading.Thread(target=self._load_branch_gallery_thread, args=(branch, self.current_session_id), daemon=True).start()

    def _render_single_from_ram(self, file_name, session_id, branch):
        if self.current_session_id != session_id: return
        thumb_img = self.session_thumbs[branch][file_name]
        self._create_thumb_button(branch, file_name, thumb_img)
        if self.preview_img is None:
            # Selección simple al cargar la primera miniatura
            self.handle_thumb_click(file_name, 'single')
        if self.preview_label.cget("text") == "⚙️ Procesando imágenes...":
            self.preview_label.config(text="")

    def _invalidate_branch_cache(self, branch):
        if branch in self.session_thumbs: del self.session_thumbs[branch]
        if branch in self.session_raw: del self.session_raw[branch]

    def _update_uninstall_button_status(self, branch):
        dest = os.path.join(INSTALL_BASE, branch)
        if os.path.exists(dest):
            self.btn_uninstall.config(state="normal", text="❌ ELIMINAR PACK", bg="#451a1a")
        else:
            self.btn_uninstall.config(state="disabled", text="NO INSTALADO", bg=self.c_alert_bg)

    def _load_branch_gallery_thread(self, branch, session_id):
        branch_cache_dir = os.path.join(CACHE_BASE, branch)
        os.makedirs(branch_cache_dir, exist_ok=True)
        image_files = []

        if self.offline_mode:
            found_files = set()
            if os.path.exists(branch_cache_dir):
                for f in os.listdir(branch_cache_dir):
                    if f.startswith('thumb_'):
                        try: os.remove(os.path.join(branch_cache_dir, f))
                        except Exception: pass
                        continue

                    if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                        found_files.add(f)

            installed_dir = os.path.join(INSTALL_BASE, branch)
            if os.path.exists(installed_dir):
                for f in os.listdir(installed_dir):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                        found_files.add(f)

            for f in found_files:
                image_files.append({"name": f})

            if not image_files:
                self.after(0, lambda: self.preview_label.config(text="[ NO HAY DATOS EN CACHÉ PARA ESTE PACK ]") if self.current_session_id == session_id else None)
                return
        else:
            url = API_CONTENTS.format(branch=branch)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Lynds-Exec"})
                with urllib.request.urlopen(req) as res:
                    files_list = json.loads(res.read().decode())
                image_files = [f for f in files_list if f.get("type") == "file" and f.get("name", "").lower().endswith(('.png', '.jpg', '.jpeg'))]
            except Exception as e:
                if self.current_session_id == session_id: self.after(0, lambda: self.preview_label.config(text=f"[ ERROR AL CARGAR LA GALERÍA ]: {e}"))
                return

        for img_meta in image_files:
            if self.current_session_id != session_id: return
            file_name = img_meta.get("name")
            cache_file = os.path.join(branch_cache_dir, file_name)

            if branch in self.session_thumbs and file_name in self.session_thumbs[branch]:
                if self.current_session_id == session_id:
                    self.after(0, lambda f=file_name, s=session_id, b=branch: self._render_single_from_ram(f, s, b))
                continue

            raw_bytes = None
            from_cache = False

            if self.offline_mode:
                installed_file = os.path.join(INSTALL_BASE, branch, file_name)
                if os.path.exists(installed_file):
                    with open(installed_file, "rb") as f: raw_bytes = f.read()
                    from_cache = False
                elif os.path.exists(cache_file):
                    with open(cache_file, "rb") as f: raw_bytes = f.read()
                    from_cache = True
            else:
                download_url = img_meta.get("download_url")
                try:
                    req_img = urllib.request.Request(download_url, headers={"User-Agent": "Lynds-Exec"})
                    with urllib.request.urlopen(req_img) as response:
                        raw_bytes = response.read()

                    if not os.path.exists(cache_file):
                        # --- GENERACIÓN DE CACHÉ EN ALTA CALIDAD PARA PREVIEW (640x360) ---
                        pil_img = Image.open(io.BytesIO(raw_bytes))
                        pil_img.thumbnail((640, 360), Image.Resampling.LANCZOS)

                        img_byte_arr = io.BytesIO()
                        pil_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=85)
                        cached_bytes = img_byte_arr.getvalue()

                        with open(cache_file, "wb") as f:
                            f.write(cached_bytes)
                except Exception as e:
                    print(f"Error descargando {file_name}: {e}")

            if raw_bytes and self.current_session_id == session_id:
                self.after(0, lambda f=file_name, r=raw_bytes, s=session_id, c=from_cache, b=branch: self._add_thumbnail_to_ui(f, r, s, c, b))

    def _add_thumbnail_to_ui(self, file_name, raw_bytes, session_id, from_cache, branch):
        if self.current_session_id != session_id: return

        try:
            if branch not in self.session_raw: self.session_raw[branch] = {}
            if branch not in self.session_thumbs: self.session_thumbs[branch] = {}

            self.session_raw[branch][file_name] = raw_bytes
            pil_img = Image.open(io.BytesIO(raw_bytes))

            # --- CREACIÓN DE LA MINIATURA PARA EL BOTÓN (Siempre a 110x65) ---
            pil_img.thumbnail((110, 65), Image.Resampling.LANCZOS)

            is_installed = os.path.exists(os.path.join(INSTALL_BASE, branch, file_name)) or \
                           os.path.exists(os.path.join(INSTALL_BASE, "Individual", file_name))

            if is_installed:
                draw = ImageDraw.Draw(pil_img)
                w, h = pil_img.size
                draw.ellipse((w-18, h-18, w-4, h-4), fill="#22c55e", outline="#050705")
                draw.line([(w-14, h-11), (w-12, h-8), (w-7, h-14)], fill="#0a0c0a", width=2)

            thumb_img = ImageTk.PhotoImage(pil_img)
            self.session_thumbs[branch][file_name] = thumb_img

            self._create_thumb_button(branch, file_name, thumb_img)

            # Si es la primera miniatura, seleccionarla automáticamente
            if self.preview_img is None:
                self.handle_thumb_click(file_name, 'single')
        except Exception as e:
            print(f"Error en miniatura {file_name}: {e}")

    def _create_thumb_button(self, branch, file_name, thumb_img):
        btn = tk.Button(self.thumbs_frame, image=thumb_img,
                        bg=self.c_side, activebackground=self.c_neon, relief="flat", bd=0,
                        highlightbackground=self.c_neon_dim, highlightthickness=1)

        # Asignar eventos de selección
        btn.bind("<Button-1>", lambda e, f=file_name: self.handle_thumb_click(f, 'single'))
        btn.bind("<Shift-Button-1>", lambda e, f=file_name: self.handle_thumb_click(f, 'range'))
        btn.bind("<Control-Button-1>", lambda e, f=file_name: self.handle_thumb_click(f, 'toggle'))

        # Scroll horizontal
        btn.bind("<MouseWheel>", self._on_horizontal_mousewheel)
        btn.bind("<Button-4>", self._on_horizontal_mousewheel)
        btn.bind("<Button-5>", self._on_horizontal_mousewheel)

        btn.pack(side="left", padx=5, pady=3)
        self.thumb_btns[file_name] = btn

        # Guardar orden de imágenes
        if file_name not in self.image_order:
            self.image_order.append(file_name)

        # Asegurar que el contenedor también capture el scroll
        self.thumbs_outer_frame.bind("<MouseWheel>", self._on_horizontal_mousewheel)
        self.thumbs_outer_frame.bind("<Button-4>", self._on_horizontal_mousewheel)
        self.thumbs_outer_frame.bind("<Button-5>", self._on_horizontal_mousewheel)

        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

        if self.preview_label.cget("text") == "⚙️ Procesando imágenes...":
            self.preview_label.config(text="")

    def handle_thumb_click(self, file_name, mode):
        """Maneja la selección de miniaturas según el modo:
        - 'single': selecciona solo esta imagen
        - 'toggle': añade/elimina esta imagen de la selección
        - 'range': selecciona un rango desde la última seleccionada hasta esta
        """
        if mode == 'single':
            self.selected_files = {file_name}
            self.last_selected = file_name
        elif mode == 'toggle':
            if file_name in self.selected_files:
                self.selected_files.remove(file_name)
            else:
                self.selected_files.add(file_name)
            self.last_selected = file_name
        elif mode == 'range':
            if self.last_selected is None:
                # Si no hay última selección, seleccionar solo esta
                self.selected_files = {file_name}
            else:
                try:
                    idx1 = self.image_order.index(self.last_selected)
                    idx2 = self.image_order.index(file_name)
                    start = min(idx1, idx2)
                    end = max(idx1, idx2)
                    self.selected_files = set(self.image_order[start:end+1])
                except ValueError:
                    # Si algo falla, seleccionar solo esta
                    self.selected_files = {file_name}
            self.last_selected = file_name

        # Actualizar interfaz de selección
        self.update_selection_ui()

        # Mostrar la última imagen seleccionada (la del clic actual)
        if self.selected_files:
            # Para vista previa, mostramos la imagen que se acaba de clickar (file_name)
            self.display_full_preview(file_name)
        else:
            self.preview_label.config(image="", text="[ SELECCIÓN VACÍA ]")
            self.btn_install_selected.config(state="disabled", text="🖼️ GUARDAR SELECCIÓN")
            self.btn_uninstall_selected.config(state="disabled", text="🗑️ ELIMINAR SELECCIÓN")

    def update_selection_ui(self):
        """Actualiza el aspecto visual de los botones y los estados de los botones de acción."""
        # Resaltar botones seleccionados
        for fname, btn in self.thumb_btns.items():
            if fname in self.selected_files:
                btn.config(bg=self.c_neon, highlightbackground=self.c_neon)
            else:
                btn.config(bg=self.c_side, highlightbackground=self.c_neon_dim)

        # Actualizar botones de acción
        count = len(self.selected_files)
        if count > 0:
            if self.offline_mode:
                self.btn_install_selected.config(state="disabled", text=f"❌ OFFLINE ({count})")
            else:
                self.btn_install_selected.config(state="normal", text=f"🖼️ GUARDAR SELECCIÓN ({count})")
            self.btn_uninstall_selected.config(state="normal", text=f"🗑️ ELIMINAR SELECCIÓN ({count})")
        else:
            self.btn_install_selected.config(state="disabled", text="🖼️ GUARDAR SELECCIÓN")
            self.btn_uninstall_selected.config(state="disabled", text="🗑️ ELIMINAR SELECCIÓN")

    def display_full_preview(self, file_name):
        try:
            branch = self.selected_branch
            raw_bytes = self.session_raw.get(branch, {}).get(file_name)
            if not raw_bytes: return

            pil_img = Image.open(io.BytesIO(raw_bytes))
            w, h = pil_img.size

            target_w, target_h = 640, 360
            ratio = min(target_w / w, target_h / h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)

            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.preview_img = ImageTk.PhotoImage(pil_img)

            self.preview_label.config(image=self.preview_img, text="")
            self.preview_neon_border.config(highlightbackground=self.c_neon)

            nombre_original_sin_ext, _ = os.path.splitext(file_name)

            if self.offline_mode and w <= 640:
                self.status_label.config(text=f"Viendo caché de previsualización: {nombre_original_sin_ext} (Offline)")
            elif self.offline_mode:
                self.status_label.config(text=f"Viendo local HD: {nombre_original_sin_ext} (Offline)")
            else:
                self.status_label.config(text=f"Viendo: {nombre_original_sin_ext} ({w}x{h} px)")
        except Exception as e:
            self.preview_label.config(text=f"[ ERROR AL CARGAR IMAGEN ]: {e}")

    # ── OPERACIONES EN DISCO ───────────────────────────────────────────────────
    def install_selected_images(self):
        branch = self.selected_branch
        if not branch or not self.selected_files or self.offline_mode: return
        try:
            dest_dir = os.path.join(INSTALL_BASE, "Individual")
            os.makedirs(dest_dir, exist_ok=True)
            count = 0
            for file_name in self.selected_files:
                raw_bytes = self.session_raw.get(branch, {}).get(file_name)
                if raw_bytes:
                    with open(os.path.join(dest_dir, file_name), "wb") as f: f.write(raw_bytes)
                    count += 1
            self.status_label.config(text=f"ÉXITO: {count} imagen(es) guardada(s) en Carpeta Individual.")

            self._invalidate_branch_cache(branch)
            self.select_branch(branch)
        except Exception as e:
            self.status_label.config(text=f"ERROR AL GUARDAR IMÁGENES: {e}")

    def uninstall_selected_images(self):
        branch = self.selected_branch
        if not branch or not self.selected_files: return
        count = 0
        for file_name in self.selected_files:
            for path in [os.path.join(INSTALL_BASE, branch, file_name), os.path.join(INSTALL_BASE, "Individual", file_name)]:
                if os.path.exists(path):
                    os.remove(path)
                    count += 1
        self.status_label.config(text=f"ELIMINADAS: {count} imagen(es) del disco.")
        branch_dir = os.path.join(INSTALL_BASE, branch)
        if os.path.exists(branch_dir) and not os.listdir(branch_dir):
            shutil.rmtree(branch_dir)

        self._update_uninstall_button_status(branch)
        self._invalidate_branch_cache(branch)
        self.select_branch(branch)

    def install_package(self):
        branch = self.selected_branch
        if not branch or self.offline_mode: return
        clean = branch.replace("-", " ")
        self.status_label.config(text=f"Descargando pack: {clean.upper()}...")
        self.is_downloading = True
        self.show_progress_bar()
        threading.Thread(target=self._download_task, args=(branch,), daemon=True).start()

    def show_progress_bar(self):
        """Muestra la barra de progreso"""
        self.progress_frame.pack(fill="x", pady=8)
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Descargando... 0%")

    def hide_progress_bar(self):
        """Oculta la barra de progreso"""
        self.progress_frame.pack_forget()

    def update_progress(self, value, max_value):
        """Actualiza el progreso de la descarga"""
        if max_value > 0:
            percentage = int((value / max_value) * 100)
            self.progress_bar['value'] = percentage
            self.progress_label.config(text=f"Descargando... {percentage}%")
            self.update_idletasks()

    def _download_task(self, branch):
        url = ZIP_URL.format(user=GITHUB_USER, repo=GITHUB_REPO, branch=branch)
        dest = os.path.join(INSTALL_BASE, branch)
        try:
            os.makedirs(INSTALL_BASE, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = os.path.join(tmp, "pack.zip")
                req = urllib.request.Request(url, headers={"User-Agent": "Lynds-Exec"})

                # Descargar con barra de progreso
                with urllib.request.urlopen(req) as response:
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunk_size = 8192

                    with open(zip_path, 'wb') as out:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            out.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                self.after(0, lambda d=downloaded, t=total_size: self.update_progress(d, t))

                # Extraer zip
                self.after(0, lambda: self.progress_label.config(text="Extrayendo archivos... 100%"))

                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(tmp)
                    if os.path.exists(dest): shutil.rmtree(dest)
                    extracted = os.path.join(tmp, f"{GITHUB_REPO}-{branch}")
                    if os.path.exists(extracted): shutil.move(extracted, dest)
                    else:
                        dirs = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
                        if dirs: shutil.move(os.path.join(tmp, dirs[0]), dest)

            self.after(0, lambda: self._on_install_complete(branch))
        except Exception as e:
            self.after(0, lambda: self.status_label.config(text=f"ERROR EN DESCARGA: {e}"))
            self.after(0, self.hide_progress_bar)
        finally:
            self.is_downloading = False

    def _on_install_complete(self, branch):
        clean = branch.replace("-", " ")
        self.hide_progress_bar()
        self.status_label.config(text=f"ÉXITO: Pack '{clean.upper()}' instalado.")
        if self.selected_branch == branch:
            self._update_uninstall_button_status(branch)
            self._invalidate_branch_cache(branch)
            self.select_branch(branch)

    def uninstall_package(self):
        branch = self.selected_branch
        if not branch: return
        dest = os.path.join(INSTALL_BASE, branch)
        clean = branch.replace("-", " ")
        if os.path.exists(dest):
            try:
                shutil.rmtree(dest)
                self.status_label.config(text=f"ELIMINADO: Pack '{clean.upper()}' borrado del disco.")
                self._update_uninstall_button_status(branch)
                self._invalidate_branch_cache(branch)
                self.select_branch(branch)
            except Exception as e:
                self.status_label.config(text=f"ERROR AL ELIMINAR: {e}")
        else:
            self.status_label.config(text="El pack no está instalado.")


if __name__ == "__main__":
    app = LyndsExecutive()
    app.mainloop()
