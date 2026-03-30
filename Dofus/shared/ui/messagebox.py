"""
messagebox – Reemplazo estilizado de tkinter.messagebox.
=========================================================
Popups modales que respetan el tema oscuro de la app.
"""

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, HEADER, BASE

_ICONS = {
    "info":    ("ℹ", C["accent"]),
    "warning": ("⚠", C["yellow"]),
    "error":   ("✖", C["red"]),
}


def _show(parent, title: str, message: str, kind: str = "info"):
    icon_char, icon_color = _ICONS.get(kind, _ICONS["info"])

    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.configure(bg=C["surface"], padx=24, pady=18)
    popup.resizable(False, False)
    popup.attributes("-topmost", True)

    # Icono + mensaje
    row = tk.Frame(popup, bg=C["surface"])
    row.pack(pady=(0, 16))

    tk.Label(
        row, text=icon_char, bg=C["surface"], fg=icon_color,
        font=(FONT, 18),
    ).pack(side="left", padx=(0, 12))

    tk.Label(
        row, text=message, bg=C["surface"], fg=C["text"],
        font=(FONT, BASE), anchor="w",
        wraplength=380, justify="left",
    ).pack(side="left")

    # Botón
    tk.Button(
        popup, text="ACEPTAR", bg=C["accent"], fg=C["bg"],
        font=(FONT, HEADER, "bold"), relief="flat",
        padx=20, pady=4, cursor="hand2",
        command=popup.destroy,
    ).pack()

    # Centrar sobre ventana padre
    popup.update_idletasks()
    pw, ph = popup.winfo_width(), popup.winfo_height()
    top = parent.winfo_toplevel()
    rx = top.winfo_x() + (top.winfo_width() - pw) // 2
    ry = top.winfo_y() + (top.winfo_height() - ph) // 2
    popup.geometry(f"+{rx}+{ry}")

    popup.grab_set()
    popup.wait_window()


def showinfo(title: str, message: str, parent=None):
    _show(parent, title, message, "info")


def showwarning(title: str, message: str, parent=None):
    _show(parent, title, message, "warning")


def showerror(title: str, message: str, parent=None):
    _show(parent, title, message, "error")
