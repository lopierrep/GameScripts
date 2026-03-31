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

        # Toggle always-on-top
        self._pin_btn = tk.Button(
            self,
            text="📌",
            bg=C["bg2"], fg=C["dim"],
            font=(FONT, BASE),
            relief="flat", bd=0,
            padx=12, pady=0,
            cursor="hand2",
            activebackground=C["accent_bg"],
            activeforeground=C["accent"],
            command=self._toggle_topmost,
        )
        self._pin_btn.pack(side="right", fill="y", padx=(0, 8))
        self._tooltip: tk.Toplevel | None = None
        self._pin_btn.bind("<Enter>", self._show_tooltip)
        self._pin_btn.bind("<Leave>", self._hide_tooltip)

    def _show_tooltip(self, event):
        topmost = getattr(self, '_root', None) and getattr(self._root, '_topmost', False)
        text = "Siempre visible (activado)" if topmost else "Siempre visible (desactivado)"
        self._tooltip = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.configure(bg=C["border"])
        tk.Label(
            tw, text=text, bg=C["surface"], fg=C["text"],
            font=(FONT, SMALL), padx=8, pady=4,
        ).pack()
        tw.update_idletasks()
        x = event.x_root - tw.winfo_reqwidth() // 2
        y = event.y_root + 20
        tw.geometry(f"+{x}+{y}")

    def _hide_tooltip(self, _event=None):
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def set_root(self, root: tk.Tk):
        self._root = root

    def _toggle_topmost(self):
        if not hasattr(self, '_root'):
            return
        current = getattr(self._root, '_topmost', False)
        new_val = not current
        self._root._topmost = new_val
        self._root.attributes("-topmost", new_val)
        self._pin_btn.config(fg=C["accent"] if new_val else C["dim"])

    def set_active(self, key: str):
        if self._active and self._active in self._buttons:
            self._buttons[self._active].config(bg=C["bg2"], fg=C["subtext"])
        self._active = key
        if key and key in self._buttons:
            self._buttons[key].config(bg=C["accent_bg"], fg=C["accent"])
