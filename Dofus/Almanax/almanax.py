"""
Almanax Tracker - Dofus
=======================
Muestra los días del Almanax, los ítems requeridos y calcula
la rentabilidad según los precios del mercadillo.

API: https://api.dofusdu.de/dofus3/v1/es/almanax
"""

import json
import math
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from pathlib import Path
import urllib.request
import urllib.error

# ── Constantes ────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).resolve().parent
PRICES_FILE = ROOT_DIR / "item_prices.json"
BUY_CAL_FILE = ROOT_DIR / "buy_calibration.json"
API_BASE    = "https://api.dofusdu.de/dofus3/v1/es/almanax"
MARKET_DIR  = ROOT_DIR.parent / "MarketTracker"
LOTS        = (1, 10, 100, 1000)

# ── Importar módulo de mercadillo (opcional) ──────────────────────────────────
sys.path.insert(0, str(MARKET_DIR))
try:
    from Helpers.SearchAndSave.search_item_prices import (   # type: ignore
        load_calibration  as _load_cal,
        search_item       as _search_item,
        read_prices       as _read_prices,
        find_exact_result as _find_exact_result,
        click_at          as _click_at,
    )
    from Helpers.SearchAndSave.common import _parse_price    # type: ignore
    MARKET_AVAILABLE = True
except Exception:
    MARKET_AVAILABLE = False

# ── Colores ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#1e1e2e",
    "surface": "#2a2a3e",
    "accent":  "#89b4fa",
    "green":   "#a6e3a1",
    "red":     "#f38ba8",
    "yellow":  "#f9e2af",
    "text":    "#cdd6f4",
    "dim":     "#6c7086",
    "orange":  "#fab387",
    "today":   "#2d3250",
}

# ── Precios ───────────────────────────────────────────────────────────────────
# Formato: { "Nombre": {"x1": int, "x10": int, "x100": int, "x1000": int} }
# Los valores son el precio TOTAL del lote (no unitario).
# Compat. hacia atrás: si el valor es int se trata como precio x1.

def _normalize_entry(v) -> dict:
    if isinstance(v, int):
        return {"x1": v, "x10": 0, "x100": 0, "x1000": 0}
    return v

def load_prices() -> dict:
    if PRICES_FILE.exists():
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: _normalize_entry(v) for k, v in raw.items()}
    return {}

def save_prices(prices: dict):
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

def optimal_cost(qty_needed: int, price_dict: dict) -> int:
    """
    Coste mínimo para comprar al menos qty_needed ítems.
    price_dict valores = precio total del lote (x10: 2552 → lote de 10 cuesta 2552k).
    """
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return 0
    best = float("inf")
    for min_size in sorted(available):
        remaining = qty_needed
        cost = 0
        for size in sorted(available, reverse=True):
            if size < min_size:
                continue
            lp = available[size]
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                cost += n * lp
                remaining = 0
            else:
                n = remaining // size
                cost += n * lp
                remaining -= n * size
        best = min(best, cost)
    return int(best) if best != float("inf") else 0

def get_lot_plan(qty_needed: int, price_dict: dict) -> list:
    """Plan óptimo de compra: [(tamaño_lote, n_lotes), ...]"""
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return []
    best_cost = float("inf")
    best_plan: list = []
    for min_size in sorted(available):
        remaining = qty_needed
        cost = 0
        plan: list = []
        for size in sorted(available, reverse=True):
            if size < min_size:
                continue
            lp = available[size]
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                if n > 0:
                    cost += n * lp
                    plan.append((size, n))
                remaining = 0
            else:
                n = remaining // size
                if n > 0:
                    cost += n * lp
                    plan.append((size, n))
                remaining -= n * size
        if cost < best_cost:
            best_cost = cost
            best_plan = plan
    return best_plan

# ── Calibración de compra ─────────────────────────────────────────────────────

def load_buy_cal() -> dict | None:
    if BUY_CAL_FILE.exists():
        with open(BUY_CAL_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        return {k: (tuple(v) if isinstance(v, list) else
                    {ks: tuple(vs) for ks, vs in v.items()} if isinstance(v, dict) else v)
                for k, v in raw.items()}
    return None

def save_buy_cal(data: dict):
    def serial(v):
        if isinstance(v, tuple):
            return list(v)
        if isinstance(v, dict):
            return {ks: list(vs) if isinstance(vs, tuple) else vs for ks, vs in v.items()}
        return v
    with open(BUY_CAL_FILE, "w", encoding="utf-8") as f:
        json.dump({k: serial(v) for k, v in data.items()}, f, indent=2)

# ── API ───────────────────────────────────────────────────────────────────────

def fetch_almanax(start: date, days: int) -> list:
    end = start + timedelta(days=days - 1)
    url = f"{API_BASE}?range[from]={start.isoformat()}&range[to]={end.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "AlmanaxTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

# ── Aplicación ────────────────────────────────────────────────────────────────

class AlmanaxApp:

    _MARKET_NAMES = {
        "resources":   "Recursos",
        "equipment":   "Equipamiento",
        "consumables": "Consumibles",
    }

    def __init__(self, root: tk.Tk):
        self.root    = root
        self.prices  = load_prices()
        self.data: list[dict] = []
        self.buy_cal = load_buy_cal()

        self._worker       = None
        self._scan_worker  = None
        self._scan_stop    = threading.Event()
        self._market_event = threading.Event()
        self._market_ok    = False
        self._sort_col     = "ganancia"
        self._sort_reverse = True

        self._setup_window()
        self._build_ui()
        self.root.after(200, self._start_fetch)

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Almanax Tracker – Dofus")
        self.root.geometry("1200x740+40+40")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(800, 500)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_table()
        self._build_bottombar()
        self._apply_styles()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["bg"], pady=8)
        bar.pack(fill="x", padx=12)

        tk.Label(bar, text="Almanax Tracker", bg=C["bg"], fg=C["accent"],
                 font=("Consolas", 15, "bold")).pack(side="left")

        for label, attr, w, default in [
            ("  Días:",        "days_var",       5,  "365"),
            ("  Pjs:",         "pjs_var",         4,  "15"),
            ("  Guijarros/pj:","guijarros_var",   7,  "7000"),
        ]:
            tk.Label(bar, text=label, bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(8, 4))
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            e = tk.Entry(bar, textvariable=var, width=w,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._refresh_table())

        self.fetch_btn = tk.Button(
            bar, text="⟳  Cargar", bg=C["accent"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", command=self._start_fetch)
        self.fetch_btn.pack(side="left", padx=(14, 4))

        mk = "normal" if MARKET_AVAILABLE else "disabled"

        self.scan_btn = tk.Button(
            bar, text="$  Mercadillo", bg=C["orange"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=mk, command=self._start_scan)
        self.scan_btn.pack(side="left", padx=(4, 0))

        self.stop_scan_btn = tk.Button(
            bar, text="■  Detener", bg=C["red"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._stop_scan)
        # se muestra solo mientras escanea

        self.cal_buy_btn = tk.Button(
            bar, text="⚙ Cal.", bg=C["surface"], fg=C["dim"],
            font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=4,
            cursor="hand2", state=mk, command=self._calibrate_buy_start)
        self.cal_buy_btn.pack(side="left", padx=(4, 0))

        self.buy_btn = tk.Button(
            bar, text="🛒 Comprar", bg=C["green"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=mk, command=self._buy_selected)
        self.buy_btn.pack(side="left", padx=(4, 0))

        self.status_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["dim"],
                                   font=("Consolas", 9))
        self.status_lbl.pack(side="left", padx=8)

        tk.Label(bar, text="Bonus:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="right", padx=(0, 4))
        self.filter_var = tk.StringVar(value="Todos")
        self.filter_combo = ttk.Combobox(
            bar, textvariable=self.filter_var, width=26,
            state="readonly", font=("Consolas", 9))
        self.filter_combo["values"] = ["Todos"]
        self.filter_combo.pack(side="right", padx=4)
        self.filter_combo.bind("<<ComboboxSelected>>",
                               lambda _: self._refresh_table())

        self.only_profit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            bar, text="Solo rentables", variable=self.only_profit_var,
            bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
            activebackground=C["bg"], activeforeground=C["accent"],
            font=("Consolas", 9), command=self._refresh_table,
        ).pack(side="right", padx=8)

    def _build_table(self):
        frame = tk.Frame(self.root, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("dia", "fecha", "item", "cant", "comprar", "kamas",
                "precio_unit", "coste", "guijarros", "ganancia", "bonus")
        self.tree = ttk.Treeview(frame, columns=cols,
                                  show="headings", selectmode="browse")

        defs = [
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
        for col, label, w, anchor in defs:
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

    def _build_bottombar(self):
        bar = tk.Frame(self.root, bg=C["surface"], pady=7)
        bar.pack(fill="x", padx=12, pady=(4, 8))

        tk.Label(bar, text="Seleccionado:", bg=C["surface"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=8)
        self.sel_lbl = tk.Label(bar, text="—", bg=C["surface"],
                                fg=C["text"], font=("Consolas", 10, "bold"),
                                width=28, anchor="w")
        self.sel_lbl.pack(side="left")

        self.lot_vars:    dict = {}
        self.lot_entries: dict = {}
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

        tk.Button(
            bar, text="Guardar  [↵]", bg=C["green"], fg=C["bg"],
            font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._save_price,
        ).pack(side="left", padx=(10, 4))

        tk.Button(
            bar, text="Borrar", bg=C["surface"], fg=C["red"],
            font=("Consolas", 9), relief="flat", padx=6, pady=2,
            cursor="hand2", command=self._delete_price,
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
            days = max(1, min(365, int(self.days_var.get())))
            raw  = fetch_almanax(date.today(), days=days)
            self.root.after(0, self._on_data, raw)
        except urllib.error.URLError as e:
            self.root.after(0, self._on_error, f"Sin conexión: {e.reason}")
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_data(self, raw: list):
        self.data = [self._parse(e) for e in raw]
        bonus_types = sorted({r["bonus_type"] for r in self.data})
        self.filter_combo["values"] = ["Todos"] + bonus_types
        self.fetch_btn.config(state="normal")
        self.status_lbl.config(text=f"✓ {len(self.data)} días cargados", fg=C["green"])
        self._refresh_table()

    def _on_error(self, msg: str):
        self.status_lbl.config(text=f"Error: {msg}", fg=C["red"])
        self.fetch_btn.config(state="normal")

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _parse(self, entry: dict) -> dict:
        return dict(
            date       = entry["date"],
            item       = entry["tribute"]["item"]["name"],
            qty        = entry["tribute"]["quantity"],
            kamas      = entry["reward_kamas"],
            subtype    = entry["tribute"]["item"].get("subtype", "resources"),
            bonus      = entry["bonus"]["description"],
            bonus_type = entry["bonus"]["type"]["name"],
            price      = 0,
            cost       = 0,
            guijarros  = 0,
            profit     = None,
            price_dict = {},
        )

    def _pjs(self) -> int:
        try:
            return max(1, int(self.pjs_var.get()))
        except ValueError:
            return 1

    def _guijarros_k(self) -> int:
        try:
            return max(0, int(self.guijarros_var.get()))
        except ValueError:
            return 0

    def _recompute(self):
        pjs   = self._pjs()
        guij  = self._guijarros_k()
        for r in self.data:
            pd        = self.prices.get(r["item"])
            qty_total = r["qty"] * pjs
            if pd:
                cost       = optimal_cost(qty_total, pd)
                unit_price = min(
                    (pd[f"x{s}"] / s for s in LOTS if pd.get(f"x{s}", 0) > 0),
                    default=0)
                unit_price = round(unit_price)
            else:
                cost       = 0
                unit_price = 0
            r["price_dict"] = pd or {}
            r["price"]      = unit_price
            r["cost"]       = cost
            r["guijarros"]  = guij * pjs
            r["profit"]     = (r["kamas"] * pjs + r["guijarros"] - cost) if pd else None

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        self._recompute()
        self.tree.delete(*self.tree.get_children())
        today_str   = date.today().isoformat()
        filter_val  = self.filter_var.get()
        only_profit = self.only_profit_var.get()

        rows = list(self.data)
        if filter_val != "Todos":
            rows = [r for r in rows if r["bonus_type"] == filter_val]
        if only_profit:
            rows = [r for r in rows if r["profit"] is not None and r["profit"] > 0]

        rows = self._sort(rows)

        for r in rows:
            day_delta = (date.fromisoformat(r["date"]) - date.today()).days
            day_lbl   = "Hoy" if day_delta == 0 else f"+{day_delta}d"
            pjs       = self._pjs()

            p_str    = f"{r['price']:,}"      if r["price"]  else "—"
            cost_str = f"{r['cost']:,}"       if r["cost"]   else "—"
            guij_str = f"{r['guijarros']:,}"
            gan_str  = f"{r['profit']:+,}"    if r["profit"] is not None else "—"
            bonus_s  = r["bonus"]
            if len(bonus_s) > 65:
                bonus_s = bonus_s[:65] + "…"

            tag = "sin_precio"
            if r["profit"] is not None:
                tag = "alta" if r["profit"] >= 500 else \
                      "media" if r["profit"] >= 0 else "perdida"

            tags = (tag, "hoy") if r["date"] == today_str else (tag,)

            self.tree.insert("", "end", iid=r["date"], tags=tags,
                             values=(day_lbl, r["date"], r["item"],
                                     r["qty"], f"{r['qty'] * pjs:,}",
                                     f"{r['kamas']:,}", p_str,
                                     cost_str, guij_str, gan_str, bonus_s))

    def _sort(self, rows: list) -> list:
        col = self._sort_col
        rev = self._sort_reverse
        def key(r):
            if col == "ganancia":
                return r["profit"] if r["profit"] is not None else \
                       (-999_999_999 if rev else 999_999_999)
            if col == "kamas":      return r["kamas"]
            if col == "cant":       return r["qty"]
            if col == "comprar":    return r["qty"] * self._pjs()
            if col == "coste":      return r["cost"]
            if col == "guijarros":  return r.get("guijarros", 0)
            if col == "precio_unit":return r["price"]
            if col in ("fecha","dia"): return r["date"]
            if col == "item":       return r["item"].lower()
            if col == "bonus":      return r["bonus"].lower()
            return 0
        return sorted(rows, key=key, reverse=rev)

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col     = col
            self._sort_reverse = True
        self._refresh_table()

    # ── Edición de precios manual ──────────────────────────────────────────────

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
            self.status_lbl.config(
                text=f"Precio borrado: {full_name[:30]}", fg=C["yellow"])
            self._refresh_table()

    def _full_item_name(self, display: str) -> str:
        clean = display.rstrip("…")
        for r in self.data:
            if r["item"].startswith(clean):
                return r["item"]
        return display

    # ── Escaneo de precios ────────────────────────────────────────────────────

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
        import time
        import keyboard as _kb

        try:
            _load_cal()
        except Exception as e:
            self.root.after(0, self._scan_done, 0, 0, f"Error calibración: {e}")
            return

        # Agrupar ítems únicos por mercadillo
        groups: dict[str, list[str]] = {}
        seen: set[str] = set()
        for r in self.data:
            key  = r["subtype"]
            item = r["item"]
            if item not in seen:
                seen.add(item)
                groups.setdefault(key, []).append(item)
        for lst in groups.values():
            lst.sort()

        total   = sum(len(v) for v in groups.values())
        updated = 0
        scanned = 0

        for subtype, items in groups.items():
            if self._scan_stop.is_set():
                break
            market = self._MARKET_NAMES.get(subtype, subtype.capitalize())
            if not self._ask_market_switch(market, len(items)):
                break

            for i in range(3, 0, -1):
                if self._scan_stop.is_set():
                    break
                self.root.after(0, self.status_lbl.config,
                                {"text": f"[{market}] Cambia al juego… {i}s",
                                 "fg": C["yellow"]})
                time.sleep(1)

            if self._scan_stop.is_set():
                break

            for item in items:
                if self._scan_stop.is_set():
                    break
                scanned += 1
                self.root.after(0, self.status_lbl.config, {
                    "text": f"[{market}] [{scanned}/{total}] {item[:30]}…",
                    "fg": C["yellow"],
                })
                try:
                    _search_item(item)
                    raw = _read_prices(item)
                    _kb.press_and_release("esc")
                    time.sleep(0.3)
                except Exception:
                    continue

                entry = {f"x{s}": _parse_price(raw, str(s)) for s in LOTS}
                if any(v > 0 for v in entry.values()):
                    self.prices[item] = entry
                    updated += 1
                    save_prices(self.prices)
                    self.root.after(0, self._refresh_table)

        self.root.after(0, self._scan_done, updated, total)

    def _scan_done(self, updated: int, total: int, error: str = ""):
        self.stop_scan_btn.pack_forget()
        self.scan_btn.pack(side="left", padx=(4, 0))
        self.fetch_btn.config(state="normal")
        if error:
            self.status_lbl.config(text=error, fg=C["red"])
        else:
            self.status_lbl.config(
                text=f"✓ Precios actualizados: {updated}/{total} items",
                fg=C["green"])
        self._refresh_table()

    def _ask_market_switch(self, market_name: str, count: int) -> bool:
        self._market_event.clear()
        self._market_ok = False
        self.root.after(0, self._show_market_dialog, market_name, count)
        self._market_event.wait()
        return self._market_ok

    def _show_market_dialog(self, market_name: str, count: int):
        result = messagebox.askokcancel(
            "Cambiar mercadillo",
            f"A continuación se buscarán {count} ítems en:\n\n"
            f"  ➜  Mercadillo de {market_name}\n\n"
            f"Abre ese mercadillo en Dofus y pulsa OK.\n"
            f"Tendrás 3 segundos para cambiar al juego.",
            icon="question",
        )
        self._market_ok = result
        self._market_event.set()

    # ── Calibración de compra ─────────────────────────────────────────────────

    def _calibrate_buy_start(self):
        if not messagebox.askokcancel(
            "Calibrar compra",
            "Abre el mercadillo en Dofus, busca cualquier ítem con\n"
            "filas de lote visibles y pulsa OK.\n\n"
            "Tendrás 3 segundos. Luego mueve el ratón a cada posición\n"
            "y pulsa C para capturar."
        ):
            return
        threading.Thread(target=self._calibrate_buy_thread, daemon=True).start()

    def _calibrate_buy_thread(self):
        import time
        import keyboard as _kb
        import pyautogui as _pag

        def capture(label: str) -> tuple:
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Mueve a: {label}  →  pulsa C",
                             "fg": C["yellow"]})
            _kb.wait("c")
            pos = tuple(_pag.position())
            self.root.after(0, self.status_lbl.config,
                            {"text": f"✓ {label}: {pos}", "fg": C["green"]})
            time.sleep(0.3)
            return pos

        for i in range(3, 0, -1):
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Cambia al juego… {i}s", "fg": C["yellow"]})
            time.sleep(1)

        try:
            rows = {str(s): capture(f"fila x{s}") for s in LOTS}
            confirm = capture("botón Confirmar/Comprar")
            data = {"rows": rows, "confirm": confirm}
            save_buy_cal(data)
            self.buy_cal = load_buy_cal()
            self.root.after(0, self.status_lbl.config,
                            {"text": "✓ Calibración de compra guardada", "fg": C["green"]})
        except Exception as e:
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Error calibración: {e}", "fg": C["red"]})

    # ── Compra automática ─────────────────────────────────────────────────────

    def _buy_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un día en la tabla.")
            return
        if not self.buy_cal:
            messagebox.showwarning(
                "Sin calibración",
                "Primero calibra las posiciones de compra con '⚙ Cal.'.")
            return

        iid = sel[0]
        row = next((r for r in self.data if r["date"] == iid), None)
        if not row or not row.get("price_dict"):
            messagebox.showwarning("Sin precio", "Este ítem no tiene precio guardado.")
            return

        pjs       = self._pjs()
        qty_total = row["qty"] * pjs
        plan      = get_lot_plan(qty_total, row["price_dict"])
        if not plan:
            messagebox.showwarning("Sin plan", "No se puede calcular un plan de compra.")
            return

        plan_str = "  +  ".join(f"{n}× x{s}" for s, n in plan)
        market   = self._MARKET_NAMES.get(row["subtype"], row["subtype"])
        if not messagebox.askokcancel(
            "Confirmar compra",
            f"Ítem:      {row['item']}\n"
            f"Cantidad:  {qty_total} ({row['qty']} × {pjs} pjs)\n"
            f"Plan:      {plan_str}\n\n"
            f"Abre el mercadillo de {market} y pulsa OK.\n"
            f"Tendrás 3 segundos para cambiar al juego."
        ):
            return

        self.buy_btn.config(state="disabled")
        threading.Thread(
            target=self._buy_thread,
            args=(row["item"], plan),
            daemon=True,
        ).start()

    def _buy_thread(self, item: str, plan: list):
        import time
        import keyboard as _kb

        for i in range(3, 0, -1):
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Comprando en {i}s…", "fg": C["yellow"]})
            time.sleep(1)

        try:
            _load_cal()
            _search_item(item)
            pos = _find_exact_result(item)
            if pos is None:
                raise RuntimeError(f"No se encontró '{item}' en resultados")
            _click_at(pos, delay=0.4)

            total_ops = sum(n for _, n in plan)
            done = 0
            for lot_size, n_lots in plan:
                row_pos     = self.buy_cal["rows"][str(lot_size)]
                confirm_pos = self.buy_cal["confirm"]
                for _ in range(n_lots):
                    _click_at(row_pos, delay=0.25)
                    _click_at(confirm_pos, delay=0.4)
                    done += 1
                    self.root.after(0, self.status_lbl.config, {
                        "text": f"[{done}/{total_ops}] {item[:30]}…",
                        "fg": C["yellow"],
                    })

            _kb.press_and_release("esc")
            self.root.after(0, self.status_lbl.config,
                            {"text": f"✓ Compra completada: {item[:35]}", "fg": C["green"]})
        except Exception as e:
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Error en compra: {e}", "fg": C["red"]})
        finally:
            self.root.after(0, self.buy_btn.config, {"state": "normal"})


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    AlmanaxApp(root)
    root.mainloop()
