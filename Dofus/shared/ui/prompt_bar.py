"""
PromptBar – Popup de confirmación/precio reutilizable para cualquier UI.
========================================================================
Widget Toplevel modal con label, botón y campos de precio opcionales.
Reproduce un sonido del sistema al aparecer para alertar al usuario.
"""

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, HEADER, BASE


class PromptBar:
    """
    Popup modal para pedir confirmación o precios manuales.

    Uso:
        self.prompt = PromptBar(parent)
        self.prompt.show_confirm("Ve al mercadillo X", callback)
        self.prompt.show_price_prompt("Item", False, callback)
        self.prompt.hide()
    """

    def __init__(self, parent, *, font_family: str = None):
        self._parent = parent
        self._font = font_family or FONT
        self._popup: tk.Toplevel | None = None
        self._callback = None
        self._mode = "confirm"
        self._price_entries: dict[str, tk.Entry] = {}

    # ── API pública ──────────────────────────────────────────────────────

    def show_confirm(self, text: str, on_confirm, **_pack_kwargs):
        self._mode = "confirm"
        self._callback = on_confirm
        self._build_popup(text, button_text="CONTINUAR")

    def show_price_prompt(self, name: str, is_selling: bool, on_confirm, **_pack_kwargs):
        kind = "venta" if is_selling else "ingrediente"
        self._mode = "price"
        self._callback = on_confirm
        self._build_popup(
            f"Precios manuales de '{name}' ({kind}):",
            button_text="CONFIRMAR",
            show_prices=True,
        )

    def hide(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None

    # ── Interno ──────────────────────────────────────────────────────────

    def _build_popup(self, text: str, *, button_text: str, show_prices: bool = False):
        self.hide()

        popup = tk.Toplevel(self._parent)
        popup.title("Dofus Hub")
        popup.configure(bg=C["surface"], padx=24, pady=18)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.protocol("WM_DELETE_WINDOW", lambda: None)  # no cerrar con X
        self._popup = popup

        # Label
        tk.Label(
            popup, text=text, bg=C["surface"], fg=C["text"],
            font=(self._font, HEADER, "bold"), anchor="w",
            wraplength=500, justify="left",
        ).pack(pady=(0, 14))

        # Price fields
        if show_prices:
            price_frame = tk.Frame(popup, bg=C["surface"])
            price_frame.pack(pady=(0, 14))
            self._price_entries = {}
            for label, key in (("x1", "unit_price_x1"), ("x10", "unit_price_x10"),
                               ("x100", "unit_price_x100"), ("x1000", "unit_price_x1000")):
                col = tk.Frame(price_frame, bg=C["surface"])
                col.pack(side="left", padx=8)
                tk.Label(col, text=label, bg=C["surface"], fg=C["subtext"],
                         font=(self._font, BASE)).pack()
                e = tk.Entry(col, width=10, bg=C["bg"], fg=C["text"],
                             insertbackground=C["text"], relief="flat",
                             font=(self._font, BASE))
                e.pack()
                self._price_entries[key] = e
            list(self._price_entries.values())[0].focus()

        # Button
        tk.Button(
            popup, text=button_text, bg=C["accent"], fg=C["bg"],
            font=(self._font, HEADER, "bold"), relief="flat",
            padx=20, pady=6, cursor="hand2",
            command=self._on_click,
        ).pack()

        # Centrar sobre la ventana principal
        popup.update_idletasks()
        pw = popup.winfo_width()
        ph = popup.winfo_height()
        root = self._parent.winfo_toplevel()
        rx = root.winfo_x() + (root.winfo_width() - pw) // 2
        ry = root.winfo_y() + (root.winfo_height() - ph) // 2
        popup.geometry(f"+{rx}+{ry}")

        # Sonido de alerta
        popup.bell()

    def _on_click(self):
        cb = self._callback
        if self._mode == "price":
            prices = {}
            for key, entry in self._price_entries.items():
                val = entry.get().strip()
                prices[key] = int(val) if val.isdigit() else 0
            self.hide()
            if cb:
                cb(prices)
        else:
            self.hide()
            if cb:
                cb()
