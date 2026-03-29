"""
TabBar — barra de pestañas horizontal en la parte superior del hub.
"""

import tkinter as tk
from shared.ui.colors import C
from shared.ui.font import FONT, BASE, SMALL

APPS = [
    ("crafting",  "⚗",  "Crafting"),
    ("almanax",   "📅", "Almanax"),
    ("ganadero",  "🐴", "Ganadero"),
    ("trolichas", "🏁", "Trolichas"),
]

HEIGHT = 42  # px


class Sidebar(tk.Frame):
    """Barra de pestañas horizontal. Mantiene el nombre 'Sidebar' para no cambiar main.py."""

    def __init__(self, parent, on_select):
        super().__init__(parent, bg=C["bg2"], height=HEIGHT)
        self.pack_propagate(False)
        self._on_select = on_select
        self._buttons = {}
        self._active = None
        self._build()

    def _build(self):
        # Título / logo a la izquierda
        tk.Label(
            self, text="Dofus Hub",
            bg=C["bg2"], fg=C["accent"],
            font=(FONT, BASE, "bold"),
            padx=16,
        ).pack(side="left")

        # Separador vertical
        tk.Frame(self, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)

        for key, icon, label in APPS:
            btn = tk.Button(
                self,
                text=f"{icon}  {label}",
                bg=C["bg2"], fg=C["subtext"],
                font=(FONT, BASE),
                relief="flat", bd=0,
                padx=18, pady=0,
                cursor="hand2",
                activebackground=C["accent_bg"],
                activeforeground=C["accent"],
                command=lambda k=key: self._on_select(k),
            )
            btn.pack(side="left", fill="y")
            self._buttons[key] = btn

    def set_active(self, key: str):
        if self._active and self._active in self._buttons:
            self._buttons[self._active].config(bg=C["bg2"], fg=C["subtext"])
        self._active = key
        if key and key in self._buttons:
            self._buttons[key].config(bg=C["accent_bg"], fg=C["accent"])
