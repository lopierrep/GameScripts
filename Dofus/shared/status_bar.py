"""Barra de estado compartida para el borde inferior de las UIs."""

import tkinter as tk
from shared.colors import C
from shared.font import FONT as F, SMALL


class StatusBar(tk.Label):
    """Label de estado que se posiciona en el borde inferior de la ventana."""

    def __init__(self, parent: tk.Widget):
        super().__init__(
            parent,
            text="",
            bg=C["bg"],
            fg=C["dim"],
            font=(F, SMALL),
            anchor="w",
            padx=14,
            pady=4,
        )
        self.pack(side="bottom", fill="x")

    def set(self, text: str, color: str = C["dim"]):
        self.config(text=text, fg=color)
