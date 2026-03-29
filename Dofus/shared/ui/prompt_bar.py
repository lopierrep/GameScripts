"""
PromptBar – Barra de confirmación/precio reutilizable para cualquier UI.
========================================================================
Widget tk.Frame con label, botón y campos de precio opcionales.
"""

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, HEADER, BASE


class PromptBar(tk.Frame):
    """
    Barra colapsable para pedir confirmación o precios manuales.

    Uso:
        self.prompt = PromptBar(parent)
        self.prompt.show_confirm("Ve al mercadillo X", callback, fill="x")
        self.prompt.show_price_prompt("Item", False, callback, fill="x")
        self.prompt.hide()
    """

    def __init__(self, parent, *, font_family: str = None):
        super().__init__(parent, bg=C["yellow"], pady=6)
        _font = font_family or FONT
        self._callback = None
        self._mode = "confirm"

        # Label
        self._label = tk.Label(
            self, text="", bg=C["yellow"], fg=C["bg"],
            font=(_font, HEADER, "bold"), anchor="w",
            wraplength=700, justify="left",
        )
        self._label.pack(side="left", padx=14, fill="x", expand=True)

        # Price fields (ocultos por defecto)
        self._price_frame = tk.Frame(self, bg=C["yellow"])
        self._price_entries: dict[str, tk.Entry] = {}
        for label, key in (("x1", "unit_price_x1"), ("x10", "unit_price_x10"),
                           ("x100", "unit_price_x100"), ("x1000", "unit_price_x1000")):
            col = tk.Frame(self._price_frame, bg=C["yellow"])
            col.pack(side="left", padx=6)
            tk.Label(col, text=label, bg=C["yellow"], fg=C["bg"],
                     font=(_font, BASE)).pack()
            e = tk.Entry(col, width=10, bg=C["bg"], fg=C["text"],
                         insertbackground=C["text"], relief="flat",
                         font=(_font, BASE))
            e.pack()
            self._price_entries[key] = e

        # Button
        self._button = tk.Button(
            self, text="CONTINUAR", bg=C["bg"], fg=C["yellow"],
            font=(_font, HEADER, "bold"), relief="flat",
            padx=12, pady=2, cursor="hand2",
            command=self._on_click,
        )
        self._button.pack(side="right", padx=14)

    # ── API pública ──────────────────────────────────────────────────────

    def show_confirm(self, text: str, on_confirm, **pack_kwargs):
        self._mode = "confirm"
        self._callback = on_confirm
        self._label.config(text=text)
        self._price_frame.pack_forget()
        self._button.config(text="CONTINUAR")
        if not self.winfo_manager():
            self.pack(**pack_kwargs)

    def show_price_prompt(self, name: str, is_selling: bool, on_confirm, **pack_kwargs):
        kind = "venta" if is_selling else "ingrediente"
        self._mode = "price"
        self._callback = on_confirm
        self._label.config(text=f"Precios manuales de '{name}' ({kind}):")
        for e in self._price_entries.values():
            e.delete(0, "end")
        self._price_frame.pack(side="left", padx=(0, 10))
        self._button.config(text="CONFIRMAR")
        list(self._price_entries.values())[0].focus()
        if not self.winfo_manager():
            self.pack(**pack_kwargs)

    def hide(self):
        self.pack_forget()

    # ── Interno ──────────────────────────────────────────────────────────

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
