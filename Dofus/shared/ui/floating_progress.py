"""
FloatingProgress – Widget compacto always-on-top para operaciones largas.
=========================================================================
Minimiza el hub y muestra un widget flotante con progreso + botón detener.
Al terminar, restaura el hub.
"""

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, BASE


class FloatingProgress:

    def __init__(self, app_root):
        self._app_root = app_root
        self._hub_root = app_root.winfo_toplevel()
        self._is_hub = (self._hub_root is not app_root)
        self._popup: tk.Toplevel | None = None
        self._status_var: tk.StringVar | None = None

    # ── API pública ──────────────────────────────────────────────────────

    def show(self, on_stop):
        """Minimiza el hub y muestra el widget flotante."""
        if self._popup:
            return

        if self._is_hub:
            self._hub_root.iconify()

        popup = tk.Toplevel()
        popup.title("Dofus")
        popup.configure(bg=C["surface"])
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.protocol("WM_DELETE_WINDOW", on_stop)
        self._popup = popup

        self._status_var = tk.StringVar(value="Iniciando…")

        tk.Label(
            popup, textvariable=self._status_var,
            bg=C["surface"], fg=C["text"],
            font=(FONT, BASE), anchor="w",
            width=45, wraplength=380,
        ).pack(padx=16, pady=(12, 8))

        tk.Button(
            popup, text="■ DETENER",
            bg=C["red"], fg=C["bg"],
            font=(FONT, BASE, "bold"),
            relief="flat", padx=16, pady=4,
            cursor="hand2", command=on_stop,
        ).pack(padx=16, pady=(0, 12), fill="x")

        # Esquina superior derecha
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        sx = popup.winfo_screenwidth()
        popup.geometry(f"+{sx - pw - 20}+{20}")

    def update(self, text):
        """Actualiza el texto de progreso."""
        if self._status_var:
            self._status_var.set(text)

    def hide(self):
        """Cierra el widget y restaura el hub."""
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._status_var = None

        if self._is_hub:
            self._hub_root.deiconify()
            topmost = getattr(self._hub_root, '_topmost', True)
            self._hub_root.attributes("-topmost", topmost)
