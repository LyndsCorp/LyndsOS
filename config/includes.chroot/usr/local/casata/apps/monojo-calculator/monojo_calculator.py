#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import os

ICON_PATH = "/usr/share/icons/hicolor/512x512/apps/monojo-naranja.png"

class Calculator(tk.Tk):
    def __init__(self):
        super().__init__(className="monojo_calculator_main")

        self.title("Monojo Calculator")
        self.geometry("360x520")
        self.resizable(False, False)

        try:
            icon = tk.PhotoImage(file=ICON_PATH)
            self.iconphoto(False, icon)
        except:
            pass

        self.expression = ""
        self.create_widgets()

        # Activar teclado
        self.bind_all("<Key>", self.key_input)

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== PANTALLA (ocupa toda la parte superior) ==========
        self.display = tk.Label(
            main_frame,
            text="",
            font=("Arial", 36), # Fuente más grande para rellenar el nuevo espacio
            anchor="e",
            relief="sunken",
            bg="white",
            height=2 # Altura ajustada
        )
        self.display.grid(row=0, column=0, columnspan=5, rowspan=2,
                          padx=5, pady=(5, 15), sticky="nsew")

        # ========== IMAGEN (encima del botón de Ayuda) ==========
        try:
            img_original = tk.PhotoImage(file=ICON_PATH)
            self.img = img_original.subsample(
                max(1, img_original.width() // 90),
                max(1, img_original.height() // 90)
            )
        except:
            self.img = None

        img_label = ttk.Label(main_frame, image=self.img if self.img else None)
        # Ocupa las filas 2 y 3 en la columna 0
        img_label.grid(row=2, column=0, rowspan=2, padx=5, pady=5, sticky="s")

        # ========== BOTÓN DE AYUDA (justo encima de C) ==========
        help_btn = tk.Button(
            main_frame,
            text="Controles\nteclado", # Salto de línea para no ensanchar demasiado la columna
            font=("Arial", 9),
            command=self.show_help
        )
        # Se sitúa en la fila 4, columna 0
        help_btn.grid(row=4, column=0, padx=5, pady=5, sticky="nsew")

        # ========== BOTONERA ==========
        botones = [
            ["", "7", "8", "9", "÷"],  # Fila 2
            ["", "4", "5", "6", "×"],  # Fila 3
            ["", "1", "2", "3", "-"],  # Fila 4
            ["C", ".", "0", "^", "+"]  # Fila 5
        ]

        for i, fila in enumerate(botones, start=2):
            for j, txt in enumerate(fila):
                if txt == "":
                    continue
                tk.Button(
                    main_frame,
                    text=txt,
                    font=("Arial", 18),
                    bg="#e6e6e6",
                    activebackground="#cccccc",
                    command=lambda t=txt: self.on_button(t)
                ).grid(row=i, column=j, padx=4, pady=4, sticky="nsew")

        # "=" gigante
        eq_button = tk.Button(
            main_frame,
            text="=",
            font=("Arial", 22),
            bg="#4CAF50",
            fg="white",
            command=lambda: self.on_button("=")
        )
        eq_button.grid(row=6, column=0, columnspan=5,
                       padx=4, pady=4, sticky="nsew")

        # Ajustes de tamaño (5 columnas en total)
        for col in range(5):
            main_frame.columnconfigure(col, weight=1)
        for row in range(2, 7):
            main_frame.rowconfigure(row, weight=1)

    # ========== TECLADO ==========
    def key_input(self, event):
        key = event.keysym
        char = event.char

        # Reset si hay error
        if self.expression == "Error":
            self.expression = ""

        if char.isdigit():
            self.on_button(char)
            return
        if char == ".":
            self.on_button(".")
            return
        if char == "+":
            self.on_button("+")
            return
        if char == "-":
            self.on_button("-")
            return
        if key == "X":
            self.on_button("×")
            return
        if key == "colon":
            self.on_button("÷")
            return
        if char in "()":
            self.on_button(char)
            return
        if key in ("BackSpace", "Delete"):
            self.expression = self.expression[:-1]
            self.update_display()
            return
        if char == "=" or key == "Return":
            self.calculate()
            return

    # ========== LÓGICA ==========
    def on_button(self, char):
        if self.expression == "Error":
            self.expression = ""

        if char == "C":
            self.clear()
        elif char == "=":
            self.calculate()
        else:
            self.expression += str(char)
            self.update_display()

    def update_display(self):
        self.display.config(text=self.expression)

    def clear(self):
        self.expression = ""
        self.update_display()

    def calculate(self):
        expr = (
            self.expression
            .replace("×", "*")
            .replace("÷", "/")
            .replace("^", "**")
        )

        try:
            result = str(eval(expr))
            self.expression = result
        except:
            self.expression = "Error"

        self.update_display()

    # ========== AYUDA ==========
    def show_help(self):
        msg = (
            "➤ CONTROLES DEL TECLADO\n\n"
            "• Números → escribir normalmente\n"
            "• . → punto decimal\n"
            "• + → sumar\n"
            "• - → restar\n"
            "• Shift + X → multiplicar (×)\n"
            "• Shift + . (:) → dividir (÷)\n"
            "• Shift + 8 → (\n"
            "• Shift + 9 → )\n"
            "• Backspace / Delete → borrar último\n"
            "• = o Enter → calcular\n"
        )
        messagebox.showinfo("Controles del teclado", msg)

if __name__ == "__main__":
    app = Calculator()
    app.mainloop()
