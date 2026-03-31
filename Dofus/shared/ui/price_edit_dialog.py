"""
PriceEditDialog – Popup para editar precios de una receta y/o sus ingredientes.
"""

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, HEADER, BASE, SMALL

_LOT_SIZES = {"x1": 1, "x10": 10, "x100": 100, "x1000": 1000}


class PriceEditDialog:
    """
    Popup Toplevel para editar precios de múltiples ítems.

    items: list[{
        "label": str,
        "name":  str,
        "kind":  "selling" | "ingredient",
        "prices": {"1": unit, "10": unit, "100": unit, "1000": unit}   # ingredient
                 | {"x1": unit, "x10": unit, ...}                       # selling
    }]
    on_confirm: callable(dict[name, {"unit_price_x1": lot, ..., "_kind": kind}])
    """

    def __init__(self, parent, *, title: str, items: list, on_confirm):
        self._on_confirm = on_confirm
        self._items      = items
        self._entries: list[dict[str, tk.Entry]] = []

        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=C["surface"], padx=20, pady=16)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        self._win = win

        # ── Scrollable content ────────────────────────────────────────
        outer = tk.Frame(win, bg=C["surface"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=C["surface"], highlightthickness=0,
                           width=480, height=min(60 + len(items) * 74, 460))
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=C["surface"])
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _on_configure(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        content.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        win.bind("<MouseWheel>",
                 lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ── Item sections ─────────────────────────────────────────────
        for item in items:
            self._build_item_section(content, item)

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = tk.Frame(win, bg=C["surface"])
        btn_frame.pack(pady=(10, 0))

        tk.Button(
            btn_frame, text="CONFIRMAR",
            bg=C["accent"], fg=C["bg"],
            font=(FONT, HEADER, "bold"), relief="flat",
            padx=16, pady=5, cursor="hand2",
            command=self._confirm,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="CANCELAR",
            bg=C["bg2"], fg=C["subtext"],
            font=(FONT, BASE), relief="flat",
            padx=12, pady=5, cursor="hand2",
            command=win.destroy,
        ).pack(side="left")

        # ── Center over parent ────────────────────────────────────────
        win.update_idletasks()
        root = parent.winfo_toplevel()
        pw, ph = win.winfo_width(), win.winfo_height()
        rx = root.winfo_x() + (root.winfo_width()  - pw) // 2
        ry = root.winfo_y() + (root.winfo_height() - ph) // 2
        win.geometry(f"+{rx}+{ry}")
        win.bell()

    def _build_item_section(self, parent: tk.Frame, item: dict):
        kind   = item["kind"]
        label  = item["label"]
        prices = item.get("prices", {})

        section = tk.Frame(parent, bg=C["surface"], pady=6)
        section.pack(fill="x", padx=8)

        # Separador + label
        tk.Frame(section, bg=C["border"], height=1).pack(fill="x", pady=(0, 6))
        kind_tag = "Venta" if kind == "selling" else "Ingrediente"
        tk.Label(
            section,
            text=f"{label}  [{kind_tag}]",
            bg=C["surface"], fg=C["text"],
            font=(FONT, BASE, "bold"), anchor="w",
        ).pack(anchor="w")

        # Campos de precio
        fields_frame = tk.Frame(section, bg=C["surface"])
        fields_frame.pack(anchor="w", pady=(4, 0))

        item_entries: dict[str, tk.Entry] = {}
        for size_key, lot_num in _LOT_SIZES.items():
            col = tk.Frame(fields_frame, bg=C["surface"])
            col.pack(side="left", padx=(0, 12))

            tk.Label(col, text=size_key, bg=C["surface"], fg=C["subtext"],
                     font=(FONT, SMALL)).pack()

            e = tk.Entry(col, width=10, bg=C["bg"], fg=C["text"],
                         insertbackground=C["text"], relief="flat",
                         font=(FONT, BASE))
            e.pack()

            # Pre-rellenar con precio de lote (unit * cantidad)
            current = self._get_current_lot_price(prices, size_key, lot_num, kind)
            if current:
                e.insert(0, str(current))

            item_entries[size_key] = e

        self._entries.append({"_name": item["name"], "_kind": kind, **item_entries})

    def _get_current_lot_price(self, prices: dict, size_key: str, lot_num: int, kind: str) -> int | None:
        """Convierte unit price almacenado a lot price para mostrar en el campo."""
        if kind == "selling":
            # prices: {"x1": unit, "x10": unit, ...}
            unit = prices.get(size_key, 0)
        else:
            # prices: {"1": unit, "10": unit, ...} (formato raw_market_prices)
            unit = prices.get(str(lot_num), 0)
        if unit:
            return unit * lot_num
        return None

    def _confirm(self):
        result: dict[str, dict] = {}
        for item_entries in self._entries:
            name = item_entries["_name"]
            kind = item_entries["_kind"]
            prices = {"_kind": kind}
            for size_key in _LOT_SIZES:
                val = item_entries[size_key].get().strip().replace(".", "").replace(",", "")
                prices[f"unit_price_{size_key}"] = int(val) if val.isdigit() else 0
            result[name] = prices
        self._win.destroy()
        if self._on_confirm:
            self._on_confirm(result)
