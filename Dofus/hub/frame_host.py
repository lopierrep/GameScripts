"""
FrameHost — shim que permite usar un tk.Frame como si fuera tk.Tk.

Los orquestadores de cada app almacenan self._root y llaman métodos propios
de tk.Tk (title, geometry, minsize, etc.). Este shim intercepta esas llamadas:
- after() / update_idletasks() → heredados de tk.Misc, funcionan nativamente
- title()                      → redirige al tk.Tk real del hub
- geometry / minsize / resizable / withdraw / deiconify / protocol → no-op
- attributes("-topmost", ...)  → suprimido (el hub controla la ventana)
"""

import tkinter as tk
from shared.ui.colors import C


class FrameHost(tk.Frame):
    def __init__(self, parent: tk.Frame, real_root: tk.Tk):
        super().__init__(parent, bg=C["bg"])
        self._real_root = real_root

    # ── Window manager — proxy al root real ──────────────────────────────────

    def title(self, s=None):
        if s is not None:
            self._real_root.title(s)
        return self._real_root.title()

    # ── Window manager — suprimidos (el hub gestiona la ventana) ─────────────

    def geometry(self, spec=None):
        pass

    def minsize(self, w=None, h=None):
        pass

    def resizable(self, w=None, h=None):
        pass

    def withdraw(self):
        pass

    def deiconify(self):
        pass

    def protocol(self, name=None, func=None):
        pass

    def attributes(self, *args, **kw):
        # Suprimir -topmost cuando está embebido en el hub
        if args and str(args[0]) == "-topmost":
            return
        self._real_root.attributes(*args, **kw)
