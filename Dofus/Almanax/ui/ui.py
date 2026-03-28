"""
Almanax – Capa de presentación (AlmanaxUI)
==========================================
Construye y actualiza todos los widgets de la ventana.
No contiene lógica de negocio ni llamadas a módulos externos.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta

from config.config import C, LOTS
from core.table import day_label, profit_tag, today_fr


class AlmanaxUI:
    """
    Construye la UI y expone métodos para leer inputs y actualizar outputs.
    Recibe un dict de callbacks que el orquestador (main.py) implementa.

    Callbacks esperados:
        scan         ()             → escanear precios en el mercadillo
        stop_scan    ()             → detener escaneo
        calibrate    ()             → calibrar posiciones de compra
        buy_all      ()             → comprar todos los rentables
        select       (item_name)    → fila seleccionada en la tabla
        save_price   ()             → guardar precio del ítem seleccionado
        delete_price ()             → borrar precio del ítem seleccionado
        refresh      ()             → recalcular y repintar la tabla
        toggle_sort  (col)          → cambiar columna/dirección de ordenación
    """

    def __init__(self, root: tk.Tk, callbacks: dict, market_available: bool, settings: dict = None):
        self.root              = root
        self._cb               = callbacks
        self._market_available = market_available
        self._settings         = settings or {}

        self._setup_window()
        self._build_ui()

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Almanax")
        self.root.geometry("1150x720+40+40")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(800, 500)

    # ── Construcción de widgets ───────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_table()
        self._build_totalsbar()
        self._build_bottombar()
        self._apply_styles()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["bg"], pady=8)
        bar.pack(fill="x", padx=12)

        tk.Label(bar, text="Almanax", bg=C["bg"], fg=C["accent"],
                 font=("Consolas", 15, "bold")).pack(side="left")

        self._build_date_range(bar)
        self._build_char_controls(bar)
        self._build_action_buttons(bar)

        self.status_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["dim"],
                                   font=("Consolas", 9))
        self.status_lbl.pack(side="left", padx=8)

    def _build_date_range(self, bar: tk.Frame):
        today = today_fr()
        for label, attr, default in [
            ("  Desde:", "from_var", today.isoformat()),
            ("  Hasta:", "to_var",   (today + timedelta(days=29)).isoformat()),
        ]:
            tk.Label(bar, text=label, bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(8 if "Desde" in label else 4, 4))
            # "Desde" siempre arranca con hoy; "Hasta" se restaura de settings
            initial = today.isoformat() if attr == "from_var" else self._settings.get(attr, default)
            var = tk.StringVar(value=initial)
            setattr(self, attr, var)
            e = tk.Entry(bar, textvariable=var, width=11,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._cb["refresh"]())

    def _build_char_controls(self, bar: tk.Frame):
        tk.Label(bar, text="  Pjs:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.pjs_var = tk.StringVar(value=self._settings.get("pjs", "15"))
        e = tk.Entry(bar, textvariable=self.pjs_var, width=4,
                     bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                     insertbackground=C["text"], relief="flat")
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._cb["refresh"]())

        tk.Label(bar, text="  Alm/pj:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.alm_var = tk.StringVar(value=self._settings.get("alm", "4"))
        e = tk.Entry(bar, textvariable=self.alm_var, width=4,
                     bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                     insertbackground=C["text"], relief="flat")
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._cb["refresh"]())

        self.guij_vars: dict[str, tk.StringVar] = {}
        guij_defaults = {"T": "3600", "L": "18000", "S": "90000"}
        for code, default in guij_defaults.items():
            tk.Label(bar, text=f"  G{code}:", bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(4, 2))
            v = tk.StringVar(value=self._settings.get(f"guij_{code}", default))
            self.guij_vars[code] = v
            e = tk.Entry(bar, textvariable=v, width=7,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._cb["refresh"]())

        self.best_guij_lbl = tk.Label(bar, text="", bg=C["bg"],
                                      fg=C["green"], font=("Consolas", 9))
        self.best_guij_lbl.pack(side="left", padx=(6, 0))

    def _build_action_buttons(self, bar: tk.Frame):
        mk = "normal" if self._market_available else "disabled"

        self.scan_btn = tk.Button(
            bar, text="⟳  Actualizar", bg=C["orange"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=mk, command=self._cb["scan"])
        self.scan_btn.pack(side="left", padx=(4, 0))

        self.buy_all_btn = tk.Button(
            bar, text="🛒✓ Rentables", bg=C["green"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=mk, command=self._cb["buy_all"])
        self.buy_all_btn.pack(side="left", padx=(4, 0))

    def _build_table(self):
        frame = tk.Frame(self.root, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("dia", "fecha", "item", "ganancia", "cant", "por_cuenta", "comprar",
                "precio_unit", "coste", "kamas", "kamas_total", "guijarros")
        self.tree = ttk.Treeview(frame, columns=cols,
                                  show="headings", selectmode="browse")

        col_defs = [
            ("dia",         "Día",            55,  "center"),
            ("fecha",       "Fecha",          95,  "center"),
            ("item",        "Item requerido", 230, "w"),
            ("ganancia",    "Ganancia",       100,  "center"),
            ("cant",        "x1 pj",          48,  "center"),
            ("por_cuenta",  "x5 pj/cuenta",   70,  "center"),
            ("comprar",     "Comprar",         72,  "center"),
            ("precio_unit", "Precio unit.",   105,  "center"),
            ("coste",       "Coste total",     95,  "center"),
            ("kamas",       "Kamas/pj",        85,  "center"),
            ("kamas_total", "Kamas totales",   95,  "center"),
            ("guijarros",   "Guijarros",       85,  "center"),
        ]
        for col, label, w, anchor in col_defs:
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._cb["toggle_sort"](c))
            self.tree.column(col, width=w, minwidth=40, anchor=anchor)

        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<ButtonRelease-1>",  self._on_row_click)

    def _build_totalsbar(self):
        bar = tk.Frame(self.root, bg=C["bg"], pady=4)
        bar.pack(fill="x", padx=12)

        for text, attr, fg in [
            ("Días rentables:", "total_days_lbl",      C["green"]),
            ("Invertido:",      "total_cost_lbl",      C["red"]),
            ("Ganado:",         "total_profit_lbl",    C["green"]),
            ("Beneficio neto:", "total_net_lbl",       C["accent"]),
            ("Con pérdidas:",   "total_net_all_lbl",   C["accent"]),
        ]:
            tk.Label(bar, text=text, bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 9)).pack(side="left", padx=(4 if attr == "total_days_lbl" else 0, 2))
            lbl = tk.Label(bar, text="—", bg=C["bg"], fg=fg,
                           font=("Consolas", 9, "bold"))
            lbl.pack(side="left", padx=(0, 14 if attr != "total_net_all_lbl" else 0))
            setattr(self, attr, lbl)


    def _build_bottombar(self):
        bar = tk.Frame(self.root, bg=C["surface"], pady=7)
        bar.pack(fill="x", padx=12, pady=(4, 8))

        tk.Label(bar, text="Seleccionado:", bg=C["surface"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=8)
        self.sel_lbl = tk.Label(bar, text="—", bg=C["surface"],
                                fg=C["text"], font=("Consolas", 10, "bold"),
                                width=28, anchor="w")
        self.sel_lbl.pack(side="left")

        self.lot_vars:    dict[int, tk.StringVar] = {}
        self.lot_entries: dict[int, tk.Entry]     = {}
        for size in LOTS:
            tk.Label(bar, text=f"x{size}:", bg=C["surface"], fg=C["dim"],
                     font=("Consolas", 9)).pack(side="left", padx=(10, 2))
            var = tk.StringVar()
            entry = tk.Entry(bar, textvariable=var, width=9,
                             bg=C["bg"], fg=C["text"], font=("Consolas", 9),
                             insertbackground=C["text"], relief="flat")
            entry.pack(side="left")
            entry.bind("<Return>", lambda _: self._cb["save_price"]())
            self.lot_vars[size]    = var
            self.lot_entries[size] = entry

        tk.Button(bar, text="Guardar  [↵]", bg=C["green"], fg=C["bg"],
                  font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=2,
                  cursor="hand2", command=self._cb["save_price"]
                  ).pack(side="left", padx=(10, 4))

        tk.Button(bar, text="Borrar", bg=C["surface"], fg=C["red"],
                  font=("Consolas", 9), relief="flat", padx=6, pady=2,
                  cursor="hand2", command=self._cb["delete_price"]
                  ).pack(side="left")

        self.cal_btn = tk.Button(bar, text="⚙ Calibrar Clicks", bg=C["bg"], fg=C["dim"],
                                 font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=2,
                                 cursor="hand2",
                                 state="normal" if self._market_available else "disabled",
                                 command=self._cb["calibrate"])
        self.cal_btn.pack(side="right", padx=(0, 8))

        legend = tk.Frame(bar, bg=C["surface"])
        legend.pack(side="right", padx=12)
        for color, label in [
            (C["green"],  "Rentable"),
            (C["yellow"], "Bajo margen"),
            (C["red"],    "Pérdida"),
            (C["dim"],    "Sin precio"),
        ]:
            tk.Label(legend, text="■ ", bg=C["surface"], fg=color,
                     font=("Consolas", 11)).pack(side="left")
            tk.Label(legend, text=label + "   ", bg=C["surface"], fg=C["dim"],
                     font=("Consolas", 8)).pack(side="left")

    def set_calibrated(self, calibrated: bool):
        """Actualiza el aspecto del botón según si hay datos de calibración."""
        if calibrated:
            self.cal_btn.config(bg=C["bg"], fg=C["dim"])
        else:
            self.cal_btn.config(bg=C["orange"], fg=C["bg"])

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=C["surface"], foreground=C["text"],
                        fieldbackground=C["surface"], rowheight=22,
                        font=("Consolas", 9))
        style.configure("Treeview.Heading",
                        background=C["bg"], foreground=C["accent"],
                        font=("Consolas", 9, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", C["bg"])])
        style.configure("TScrollbar", background=C["surface"],
                        troughcolor=C["bg"], bordercolor=C["bg"],
                        arrowcolor=C["dim"])
        self.tree.tag_configure("alta",       foreground=C["green"])
        self.tree.tag_configure("media",      foreground=C["yellow"])
        self.tree.tag_configure("perdida",    foreground=C["red"])
        self.tree.tag_configure("sin_precio", foreground=C["dim"])
        self.tree.tag_configure("hoy",        background=C["today"])

    # ── Eventos internos ──────────────────────────────────────────────────────

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item_name = self.tree.set(sel[0], "item")
        self._cb["select"](item_name)

    def _show_copy_toast(self, name: str):
        toast = tk.Label(
            self.root, text=f"✓ Copiado: {name}",
            bg=C["accent"], fg=C["bg"],
            font=("Segoe UI", 9, "bold"), padx=12, pady=6,
            relief="flat",
        )
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-16)
        self.root.after(1800, toast.destroy)

    def _on_row_click(self, _event):
        """Copia el nombre del ítem al portapapeles y muestra notificación."""
        sel = self.tree.selection()
        if not sel:
            return
        item_name = self.tree.set(sel[0], "item")
        self.root.clipboard_clear()
        self.root.clipboard_append(item_name)
        self._show_copy_toast(item_name)

    # ── Getters de inputs ─────────────────────────────────────────────────────

    def date_range(self) -> tuple[date, date]:
        try:
            from_date = date.fromisoformat(self.from_var.get())
        except ValueError:
            from_date = date.min
        try:
            to_date = date.fromisoformat(self.to_var.get())
        except ValueError:
            to_date = date.max
        return from_date, to_date

    def pjs(self) -> int:
        try:
            return max(1, int(self.pjs_var.get()))
        except ValueError:
            return 1

    def alm(self) -> int:
        try:
            return max(0, int(self.alm_var.get()))
        except ValueError:
            return 0

    def guij_prices(self) -> dict[str, int]:
        result = {}
        for code, var in self.guij_vars.items():
            try:
                result[code] = max(0, int(var.get().replace(".", "").replace(",", "")))
            except ValueError:
                result[code] = 0
        return result

    def selected_item_label(self) -> str:
        return self.sel_lbl.cget("text")

    def lot_values(self) -> dict[int, int]:
        result = {}
        for size in LOTS:
            raw = self.lot_vars[size].get().replace(",", "").replace(".", "").strip()
            result[size] = int(raw) if raw.isdigit() else None
        return result

    # ── Setters / actualizaciones de UI ──────────────────────────────────────

    def set_status(self, text: str, fg: str = C["dim"]):
        self.status_lbl.config(text=text, fg=fg)

    def set_scan_busy(self, busy: bool):
        if busy:
            self.scan_btn.config(text="■  Detener", bg=C["red"], command=self._cb["stop_scan"])
        else:
            self.scan_btn.config(text="⟳  Actualizar", bg=C["orange"], command=self._cb["scan"])

    def set_buy_busy(self, busy: bool):
        if busy:
            self.buy_all_btn.config(text="■  Detener", bg=C["red"], command=self._cb["stop_buy"])
        else:
            self.buy_all_btn.config(text="🛒✓ Rentables", bg=C["green"], command=self._cb["buy_all"])

    def set_date_range(self, from_str: str, to_str: str):
        self.from_var.set(from_str)
        self.to_var.set(to_str)

    def set_selected_label(self, text: str):
        self.sel_lbl.config(text=text)

    def set_lot_values(self, pd: dict):
        for size in LOTS:
            v = pd.get(f"x{size}", 0)
            self.lot_vars[size].set(str(v) if v else "")

    def clear_lot_values(self):
        for size in LOTS:
            self.lot_vars[size].set("")

    def focus_lot_entry(self):
        self.lot_entries[1].focus_set()
        self.lot_entries[1].select_range(0, "end")

    def update_best_guijarro(self, text: str):
        self.best_guij_lbl.config(text=text)

    def update_totals(self, n: int, invertido: int, ganado: int, neto: int, neto_all: int):
        self.total_days_lbl.config(text=str(n))
        self.total_cost_lbl.config(text=f"{invertido:,} k")
        self.total_profit_lbl.config(text=f"{ganado:,} k")
        self.total_net_lbl.config(text=f"{neto:+,} k",
                                  fg=C["green"] if neto >= 0 else C["red"])
        self.total_net_all_lbl.config(text=f"{neto_all:+,} k",
                                      fg=C["green"] if neto_all >= 0 else C["red"])

    def clear_totals(self):
        for lbl in (self.total_days_lbl, self.total_cost_lbl,
                    self.total_profit_lbl, self.total_net_lbl, self.total_net_all_lbl):
            lbl.config(text="—")

    def refresh_table(self, rows: list[dict], today_str: str, pjs: int):
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            tag  = profit_tag(r["profit"])
            tags = (tag, "hoy") if r["date"] == today_str else (tag,)
            self.tree.insert("", "end", iid=r["date"], tags=tags, values=(
                day_label(date.fromisoformat(r["date"])),
                r["date"], r["item"],
                f"{r['profit']:+,}" if r["profit"] is not None else "—",
                r["qty"], f"{r['qty'] * 5:,}",
                f"{r['qty'] * pjs:,}",
                f"{r['price']:,}" if r["price"] else "—",
                f"{r['cost']:,}"  if r["cost"]  else "—",
                f"{r['kamas']:,}",
                f"{r['kamas'] * pjs:,}",
                f"{r['guijarros']:,}",
            ))

    def get_settings(self) -> dict:
        s = {
            "to_var":   self.to_var.get(),
            "pjs":      self.pjs_var.get(),
            "alm":      self.alm_var.get(),
        }
        for code, var in self.guij_vars.items():
            s[f"guij_{code}"] = var.get()
        return s

