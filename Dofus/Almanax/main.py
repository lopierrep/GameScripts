"""
Almanax - Dofus
===============
Muestra los días del Almanax, los ítems requeridos y calcula
la rentabilidad según el precio del mercadillo.

API: https://api.dofusdu.de/dofus3/v1/es/almanax
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
import urllib.error

# ── Rutas ─────────────────────────────────────────────────────────────────────
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR.parent / "MarketTracker"))

from core.models import C, LOTS, MARKET_DIR
from core.prices import load_prices, save_prices, optimal_cost, get_lot_plan, best_guijarro
from core.api    import fetch_almanax, parse_entry

# ── Importar módulo del mercadillo (opcional) ─────────────────────────────────
try:
    import Helpers.SearchAndSave.search_item_prices as _sip  # type: ignore[import]
    from Helpers.SearchAndSave.search_item_prices import (   # type: ignore[import]
        search_item       as _search_item,
        read_prices       as _read_prices,
        find_exact_result as _find_exact_result,
        click_at          as _click_at,
    )
    from Helpers.SearchAndSave.common import _parse_price    # type: ignore[import]
    MARKET_AVAILABLE = True
except Exception:
    MARKET_AVAILABLE = False

# ── Calibración propia del Almanax ────────────────────────────────────────────
from calibration.calibration import load_calibration as _load_almanax_cal


def _init_calibration() -> dict | None:
    try:
        cal = _load_almanax_cal()
        if MARKET_AVAILABLE:
            _sip.CAL = cal
        return cal
    except Exception:
        return None


def _press_esc():
    import keyboard as _kb
    _kb.press_and_release("esc")


# ── Aplicación ────────────────────────────────────────────────────────────────

class AlmanaxApp:

    def __init__(self, root: tk.Tk):
        self.root   = root
        self.prices = load_prices()
        self.data:  list[dict] = []

        # Hilos y eventos
        self._worker        = None
        self._scan_worker   = None
        self._scan_stop     = threading.Event()
        self._buy_stop      = threading.Event()
        self._market_event  = threading.Event()
        self._market_ok     = False

        # Calibración y estado de UI
        self.buy_cal       = _init_calibration()
        self._sort_col     = "ganancia"
        self._sort_reverse = True
        self._copy_timer   = None

        self._setup_window()
        self._build_ui()
        self.root.after(200, self._start_fetch)

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Almanax")
        self.root.geometry("1150x720+40+40")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(800, 500)

    # ── Construcción de UI ────────────────────────────────────────────────────

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

        self.best_guij_lbl.pack(side="left", padx=(6, 0))

        self.status_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["dim"],
                                   font=("Consolas", 9))
        self.status_lbl.pack(side="left", padx=8)


    def _build_date_range(self, bar: tk.Frame):
        today = date.today()
        for label, attr, default in [
            ("  Desde:", "from_var", today.isoformat()),
            ("  Hasta:", "to_var",   (today + timedelta(days=29)).isoformat()),
        ]:
            tk.Label(bar, text=label, bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(8 if "Desde" in label else 4, 4))
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            e = tk.Entry(bar, textvariable=var, width=11,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._refresh_table())

    def _build_char_controls(self, bar: tk.Frame):
        # Personajes
        tk.Label(bar, text="  Pjs:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.pjs_var = tk.StringVar(value="15")
        e = tk.Entry(bar, textvariable=self.pjs_var, width=4,
                     bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                     insertbackground=C["text"], relief="flat")
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._refresh_table())

        # Almanichas por pj/día
        tk.Label(bar, text="  Alm/pj:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.alm_var = tk.StringVar(value="4")
        e = tk.Entry(bar, textvariable=self.alm_var, width=4,
                     bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                     insertbackground=C["text"], relief="flat")
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._refresh_table())

        # Precios guijarros: GT (Temporal=3alm), GL (Lunar=15alm), GS (Solar=75alm)
        self.guij_vars: dict[str, tk.StringVar] = {}
        for code, default in [("T", "3600"), ("L", "18000"), ("S", "90000")]:
            tk.Label(bar, text=f"  G{code}:", bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(4, 2))
            v = tk.StringVar(value=default)
            self.guij_vars[code] = v
            e = tk.Entry(bar, textvariable=v, width=7,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._refresh_table())

        self.best_guij_lbl = tk.Label(bar, text="", bg=C["bg"],
                                      fg=C["green"], font=("Consolas", 9))

    def _build_action_buttons(self, bar: tk.Frame):
        self.fetch_btn = tk.Button(
            bar, text="⟳  Cargar", bg=C["accent"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", command=self._start_fetch)
        self.fetch_btn.pack(side="left", padx=(14, 4))

        scan_state = "normal" if MARKET_AVAILABLE else "disabled"
        self.scan_btn = tk.Button(
            bar, text="$  Mercadillo", bg=C["orange"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=scan_state, command=self._start_scan)
        self.scan_btn.pack(side="left", padx=(4, 0))

        self.stop_scan_btn = tk.Button(
            bar, text="■  Detener", bg=C["red"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._stop_scan)

        self.cal_buy_btn = tk.Button(
            bar, text="⚙ Cal.compra", bg=C["surface"], fg=C["dim"],
            font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=4,
            cursor="hand2", state="normal" if MARKET_AVAILABLE else "disabled",
            command=self._calibrate_buy_start)
        self.cal_buy_btn.pack(side="left", padx=(4, 0))

        self.buy_all_btn = tk.Button(
            bar, text="🛒✓ Rentables", bg=C["green"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state="normal" if MARKET_AVAILABLE else "disabled",
            command=self._buy_all_profitable)
        self.buy_all_btn.pack(side="left", padx=(4, 0))

    def _build_table(self):
        frame = tk.Frame(self.root, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("dia", "fecha", "item", "cant", "comprar", "kamas",
                "precio_unit", "coste", "guijarros", "ganancia", "bonus")
        self.tree = ttk.Treeview(frame, columns=cols,
                                  show="headings", selectmode="browse")

        col_defs = [
            ("dia",         "Día",            55,  "center"),
            ("fecha",       "Fecha",          95,  "center"),
            ("item",        "Item requerido", 230, "w"),
            ("cant",        "x1 pj",          48,  "center"),
            ("comprar",     "Comprar",         72,  "center"),
            ("kamas",       "Kamas/pj",        85,  "center"),
            ("precio_unit", "Precio unit.",   105,  "center"),
            ("coste",       "Coste total",     95,  "center"),
            ("guijarros",   "Guijarros",       85,  "center"),
            ("ganancia",    "Ganancia",        90,  "center"),
            ("bonus",       "Bonus del día",  280,  "w"),
        ]
        for col, label, w, anchor in col_defs:
            self.tree.heading(col, text=label,
                              command=lambda c=col: self._toggle_sort(c))
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
            ("Días rentables:", "total_days_lbl",   C["green"]),
            ("Invertido:",      "total_cost_lbl",   C["red"]),
            ("Ganado:",         "total_profit_lbl", C["green"]),
            ("Beneficio neto:", "total_net_lbl",    C["accent"]),
        ]:
            tk.Label(bar, text=text, bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 9)).pack(side="left", padx=(4 if attr == "total_days_lbl" else 0, 2))
            lbl = tk.Label(bar, text="—", bg=C["bg"], fg=fg,
                           font=("Consolas", 9, "bold"))
            lbl.pack(side="left", padx=(0, 14 if attr != "total_net_lbl" else 0))
            setattr(self, attr, lbl)

        self.copy_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["accent"],
                                 font=("Consolas", 9))
        self.copy_lbl.pack(side="right", padx=(0, 8))

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
            entry.bind("<Return>", lambda _: self._save_price())
            self.lot_vars[size]    = var
            self.lot_entries[size] = entry

        tk.Button(bar, text="Guardar  [↵]", bg=C["green"], fg=C["bg"],
                  font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=2,
                  cursor="hand2", command=self._save_price
                  ).pack(side="left", padx=(10, 4))

        tk.Button(bar, text="Borrar", bg=C["surface"], fg=C["red"],
                  font=("Consolas", 9), relief="flat", padx=6, pady=2,
                  cursor="hand2", command=self._delete_price
                  ).pack(side="left")

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

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def _start_fetch(self):
        if self._worker and self._worker.is_alive():
            return
        self.fetch_btn.config(state="disabled")
        self.status_lbl.config(text="Cargando desde la API…", fg=C["yellow"])
        self._worker = threading.Thread(target=self._fetch_thread, daemon=True)
        self._worker.start()

    def _fetch_thread(self):
        try:
            start = date.fromisoformat(self.from_var.get())
            end   = date.fromisoformat(self.to_var.get())
            raw   = fetch_almanax(start, end)
            self.root.after(0, self._on_data, raw)
        except urllib.error.URLError as e:
            self.root.after(0, self._on_error, f"Sin conexión: {e.reason}")
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_data(self, raw: list):
        self.data = [parse_entry(e) for e in raw]
        self.fetch_btn.config(state="normal")
        self.status_lbl.config(text=f"✓ {len(self.data)} días cargados", fg=C["green"])
        if self.data:
            self.from_var.set(self.data[0]["date"])
            self.to_var.set(self.data[-1]["date"])
        self._refresh_table()

    def _on_error(self, msg: str):
        self.status_lbl.config(text=f"Error: {msg}", fg=C["red"])
        self.fetch_btn.config(state="normal")

    # ── Cálculo de datos ──────────────────────────────────────────────────────

    def _pjs(self) -> int:
        try:
            return max(1, int(self.pjs_var.get()))
        except ValueError:
            return 1

    def _guijarro_kamas_per_pj(self) -> int:
        """Calcula kamas de guijarros por pj y actualiza el label informativo."""
        try:
            alm = max(0, int(self.alm_var.get()))
        except ValueError:
            alm = 0

        guij_prices = {}
        for code in self.guij_vars:
            try:
                guij_prices[code] = max(0, int(
                    self.guij_vars[code].get().replace(".", "").replace(",", "")))
            except ValueError:
                guij_prices[code] = 0

        result = best_guijarro(alm, guij_prices)
        if result is None or alm == 0:
            self.best_guij_lbl.config(text="")
            return 0

        label = (f"▶ {result.name} "
                 f"({result.n}× {result.kamas // max(result.n, 1):,}k"
                 f" = {result.kamas:,}k/pj  |  {result.ratio:,.0f}k/alm)")
        self.best_guij_lbl.config(text=label)
        return result.kamas

    def _recompute(self):
        """Recalcula precios y ganancias para todos los días cargados."""
        pjs    = self._pjs()
        guij_k = self._guijarro_kamas_per_pj()

        for r in self.data:
            pd        = self.prices.get(r["item"])
            qty_total = r["qty"] * pjs

            if pd:
                cost       = optimal_cost(qty_total, pd)
                unit_price = round(min(
                    pd[f"x{s}"] / s for s in LOTS if pd.get(f"x{s}", 0) > 0
                ))
            else:
                cost       = 0
                unit_price = 0

            r["price_dict"] = pd or {}
            r["price"]      = unit_price
            r["cost"]       = cost
            r["guijarros"]  = guij_k * pjs
            r["profit"]     = (r["kamas"] * pjs + r["guijarros"] - cost) if pd else None

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _date_filter(self) -> tuple[date, date]:
        try:
            from_date = date.fromisoformat(self.from_var.get())
        except ValueError:
            from_date = date.min
        try:
            to_date = date.fromisoformat(self.to_var.get())
        except ValueError:
            to_date = date.max
        return from_date, to_date

    def _filtered_rows(self) -> list[dict]:
        from_date, to_date = self._date_filter()
        rows = [r for r in self.data
                if from_date <= date.fromisoformat(r["date"]) <= to_date]
        return self._sort(rows)

    def _refresh_table(self):
        self._recompute()
        self.tree.delete(*self.tree.get_children())
        today_str = date.today().isoformat()

        for r in self._filtered_rows():
            day_delta = (date.fromisoformat(r["date"]) - date.today()).days
            day_lbl   = "Hoy" if day_delta == 0 else f"+{day_delta}d"
            tag       = self._profit_tag(r["profit"])
            tags      = (tag, "hoy") if r["date"] == today_str else (tag,)
            bonus_short = r["bonus"][:65] + ("…" if len(r["bonus"]) > 65 else "")

            self.tree.insert("", "end", iid=r["date"], tags=tags, values=(
                day_lbl, r["date"], r["item"],
                r["qty"], f"{r['qty'] * self._pjs():,}", f"{r['kamas']:,}",
                f"{r['price']:,}" if r["price"] else "—",
                f"{r['cost']:,}"  if r["cost"]  else "—",
                f"{r['guijarros']:,}",
                f"{r['profit']:+,}" if r["profit"] is not None else "—",
                bonus_short,
            ))

        self._update_totals(self._filtered_rows())

    @staticmethod
    def _profit_tag(profit) -> str:
        if profit is None:  return "sin_precio"
        if profit >= 500:   return "alta"
        if profit >= 0:     return "media"
        return "perdida"

    def _update_totals(self, rows: list[dict]):
        profitable = [r for r in rows if r.get("profit") is not None and r["profit"] > 0]
        n = len(profitable)

        if n == 0:
            for lbl in (self.total_days_lbl, self.total_cost_lbl,
                        self.total_profit_lbl, self.total_net_lbl):
                lbl.config(text="—")
            return

        invertido = sum(r["cost"]               for r in profitable)
        ganado    = sum(r["profit"] + r["cost"] for r in profitable)
        neto      = sum(r["profit"]             for r in profitable)

        self.total_days_lbl.config(text=str(n))
        self.total_cost_lbl.config(text=f"{invertido:,} k")
        self.total_profit_lbl.config(text=f"{ganado:,} k")
        self.total_net_lbl.config(text=f"{neto:+,} k",
                                  fg=C["green"] if neto >= 0 else C["red"])

    # ── Ordenación ────────────────────────────────────────────────────────────

    def _sort(self, rows: list[dict]) -> list[dict]:
        col, rev = self._sort_col, self._sort_reverse
        sentinel = (-999_999_999 if rev else 999_999_999)

        key_map = {
            "ganancia":    lambda r: r["profit"] if r["profit"] is not None else sentinel,
            "kamas":       lambda r: r["kamas"],
            "cant":        lambda r: r["qty"],
            "comprar":     lambda r: r["qty"] * self._pjs(),
            "coste":       lambda r: r["cost"],
            "guijarros":   lambda r: r.get("guijarros", 0),
            "precio_unit": lambda r: r["price"],
            "fecha":       lambda r: r["date"],
            "dia":         lambda r: r["date"],
            "item":        lambda r: r["item"].lower(),
            "bonus":       lambda r: r["bonus"].lower(),
        }
        return sorted(rows, key=key_map.get(col, lambda r: 0), reverse=rev)

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col     = col
            self._sort_reverse = True
        self._refresh_table()

    # ── Selección y edición de precios ────────────────────────────────────────

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item_name = self.tree.set(sel[0], "item")
        self.sel_lbl.config(text=item_name[:35] + ("…" if len(item_name) > 35 else ""))
        pd = self.prices.get(item_name, {})
        for size in LOTS:
            v = pd.get(f"x{size}", 0)
            self.lot_vars[size].set(str(v) if v else "")
        self.lot_entries[1].focus_set()
        self.lot_entries[1].select_range(0, "end")

    def _on_row_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item_name = self.tree.set(sel[0], "item")
        self.root.clipboard_clear()
        self.root.clipboard_append(item_name)
        self.copy_lbl.config(text=f"📋 {item_name[:40]}")
        if self._copy_timer is not None:
            self.root.after_cancel(self._copy_timer)
        self._copy_timer = self.root.after(2000, lambda: self.copy_lbl.config(text=""))

    def _save_price(self):
        item = self.sel_lbl.cget("text")
        if item in ("—", ""):
            return
        full_name = self._full_item_name(item)
        entry = {}
        for size in LOTS:
            raw = self.lot_vars[size].get().replace(",", "").replace(".", "").strip()
            if not raw:
                entry[f"x{size}"] = 0
                continue
            if not raw.isdigit():
                messagebox.showerror("Error", f"Precio x{size}: introduce solo números.")
                return
            entry[f"x{size}"] = int(raw)
        if not any(entry.values()):
            messagebox.showwarning("Sin precios", "Introduce al menos un precio.")
            return
        self.prices[full_name] = entry
        save_prices(self.prices)
        filled = ", ".join(f"x{s}={entry[f'x{s}']:,}" for s in LOTS if entry[f"x{s}"])
        self.status_lbl.config(text=f"✓ {full_name[:25]}: {filled}", fg=C["green"])
        self._refresh_table()

    def _delete_price(self):
        item = self.sel_lbl.cget("text")
        if item in ("—", ""):
            return
        full_name = self._full_item_name(item)
        if full_name in self.prices:
            del self.prices[full_name]
            save_prices(self.prices)
            for size in LOTS:
                self.lot_vars[size].set("")
            self.status_lbl.config(text=f"Precio borrado: {full_name[:30]}", fg=C["yellow"])
            self._refresh_table()

    def _full_item_name(self, display: str) -> str:
        display_clean = display.rstrip("…")
        for r in self.data:
            if r["item"].startswith(display_clean):
                return r["item"]
        return display

    # ── Escaneo de precios en mercadillo ──────────────────────────────────────

    def _start_scan(self):
        if not self.data:
            messagebox.showwarning("Sin datos", "Primero carga los días del Almanax.")
            return
        if self._scan_worker and self._scan_worker.is_alive():
            return
        self._scan_stop.clear()
        self.scan_btn.pack_forget()
        self.stop_scan_btn.pack(side="left", padx=(4, 0))
        self.fetch_btn.config(state="disabled")
        self._scan_worker = threading.Thread(target=self._scan_thread, daemon=True)
        self._scan_worker.start()

    def _stop_scan(self):
        self._scan_stop.set()

    def _scan_thread(self):
        from market.scanner import MarketScanner

        scanner = MarketScanner(
            search_item = _search_item,
            read_prices = _read_prices,
            parse_price = _parse_price,
            init_cal    = _init_calibration,
            press_esc   = _press_esc,
        )

        # Agrupar ítems únicos por tipo de mercadillo
        groups: dict[str, list[str]] = {}
        seen: set[str] = set()
        for r in self.data:
            if r["item"] not in seen:
                seen.add(r["item"])
                groups.setdefault(r["subtype"], []).append(r["item"])
        for items in groups.values():
            items.sort()

        total = sum(len(v) for v in groups.values())

        results = scanner.scan(
            items_by_subtype = groups,
            stop_event       = self._scan_stop,
            on_progress      = lambda msg: self.root.after(
                0, self.status_lbl.config, {"text": msg, "fg": C["yellow"]}),
            on_market_switch = self._ask_market_switch,
        )

        for item, entry in results.items():
            self.prices[item] = entry
        if results:
            save_prices(self.prices)

        updated = len(results)
        self.root.after(0, self._scan_done, updated, total)

    def _scan_done(self, updated: int, total: int, error: str = ""):
        self.stop_scan_btn.pack_forget()
        self.scan_btn.pack(side="left", padx=(4, 0))
        self.fetch_btn.config(state="normal")
        if error:
            self.status_lbl.config(text=error, fg=C["red"])
        else:
            self.status_lbl.config(
                text=f"✓ Precios actualizados: {updated}/{total} items", fg=C["green"])
        self._refresh_table()

    # ── Calibración de compra ─────────────────────────────────────────────────

    def _calibrate_buy_start(self):
        msg = (
            "CALIBRACIÓN DE COMPRA\n\n"
            "Abre el mercadillo en Dofus, busca cualquier ítem que tenga\n"
            "filas de lote visibles (x1, x10, x100, x1000) y pulsa OK.\n\n"
            "Tendrás 3 segundos para cambiar al juego.\n"
            "Luego mueve el ratón a cada posición y pulsa C para capturar."
        )
        if not messagebox.askokcancel("Calibrar compra", msg):
            return
        threading.Thread(target=self._calibrate_buy_thread, daemon=True).start()

    def _calibrate_buy_thread(self):
        self.root.after(0, self.status_lbl.config,
                        {"text": "Sigue las instrucciones en la consola…", "fg": C["yellow"]})
        try:
            from calibration.calibration import calibrate
            calibrate()
            self.buy_cal = _init_calibration()
            self.root.after(0, self.status_lbl.config,
                            {"text": "✓ Calibración guardada", "fg": C["green"]})
        except Exception as e:
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Error calibración: {e}", "fg": C["red"]})

    # ── Compra automática de rentables ────────────────────────────────────────

    def _buy_all_profitable(self):
        if not MARKET_AVAILABLE:
            return
        if not self.buy_cal:
            messagebox.showwarning("Calibración", "Primero calibra la compra (⚙ Cal.compra).")
            return

        pjs = self._pjs()
        from_date, to_date = self._date_filter()

        seen:   set[str]        = set()
        groups: dict[str, list] = {}
        for r in self.data:
            if not (from_date <= date.fromisoformat(r["date"]) <= to_date):
                continue
            if r.get("profit") is None or r["profit"] <= 0:
                continue
            if not r.get("price_dict") or r["item"] in seen:
                continue
            plan = get_lot_plan(r["qty"] * pjs, r["price_dict"])
            if plan:
                seen.add(r["item"])
                groups.setdefault(r["subtype"], []).append((r["item"], plan))

        if not groups:
            messagebox.showinfo("Sin rentables", "No hay ítems rentables con precio guardado.")
            return

        all_items = [(n, p) for lst in groups.values() for n, p in lst]
        resumen = "\n".join(
            f"• {n}  ({'+'.join(f'{c}×x{s}' for s, c in p)})"
            for n, p in all_items)
        if not messagebox.askokcancel(
            "Comprar todos los rentables",
            f"{len(all_items)} ítems rentables:\n\n{resumen}\n\n"
            "El script comprará automáticamente. ¡Tendrás 5 segundos para cambiar al juego!",
        ):
            return

        self.buy_all_btn.config(state="disabled")
        self._buy_stop.clear()
        threading.Thread(
            target=self._buy_all_thread, args=(groups,), daemon=True).start()

    def _buy_all_thread(self, groups: dict):
        from market.buyer import AutoBuyer

        buyer = AutoBuyer(
            search_item       = _search_item,
            find_exact_result = _find_exact_result,
            click_at          = _click_at,
            init_cal          = _init_calibration,
            press_esc         = _press_esc,
        )
        failed = buyer.buy(
            items_by_subtype = groups,
            buy_cal          = self.buy_cal,
            stop_event       = self._buy_stop,
            on_progress      = lambda msg: self.root.after(
                0, self.status_lbl.config, {"text": msg, "fg": C["yellow"]}),
            on_market_switch = self._ask_market_switch,
        )
        self.root.after(0, self._buy_all_done, failed)

    def _buy_all_done(self, failed: list[str]):
        self.buy_all_btn.config(state="normal")
        if failed:
            lista = "\n".join(f"• {n}" for n in failed)
            messagebox.showwarning(
                "Ítems no comprados",
                f"Los siguientes ítems eran rentables pero no se pudieron comprar:\n\n{lista}",
            )
            self.status_lbl.config(
                text=f"✓ Compra completada — {len(failed)} fallidos", fg=C["yellow"])
        else:
            self.status_lbl.config(text="✓ Todos los rentables comprados", fg=C["green"])

    # ── Diálogo de cambio de mercadillo ───────────────────────────────────────

    def _ask_market_switch(self, market_name: str, count: int) -> bool:
        """Muestra el diálogo en el hilo principal y espera la respuesta."""
        self._market_event.clear()
        self._market_ok = False
        self.root.after(0, self._show_market_dialog, market_name, count)
        self._market_event.wait()
        return self._market_ok

    def _show_market_dialog(self, market_name: str, count: int):
        result = messagebox.askokcancel(
            "Cambiar mercadillo",
            f"A continuación se buscarán {count} ítems en el mercadillo de:\n\n"
            f"  ➜  {market_name}\n\n"
            f"Abre ese mercadillo en Dofus y pulsa OK.\n"
            f"Tendrás 3-5 segundos para poner el juego en primer plano.",
            icon="question",
        )
        self._market_ok = result
        self._market_event.set()


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    AlmanaxApp(root)
    root.mainloop()
