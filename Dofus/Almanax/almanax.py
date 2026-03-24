"""
Almanax Tracker - Dofus
=======================
Muestra los días del Almanax, los items requeridos y calcula
la rentabilidad según el precio que tú indiques para cada item.

API: https://api.dofusdu.de/dofus3/v1/es/almanax
"""

import json
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
API_BASE    = "https://api.dofusdu.de/dofus3/v1/es/almanax"
MARKET_DIR  = ROOT_DIR.parent / "MarketTracker"

# ── Importar módulo de búsqueda del mercadillo (opcional) ─────────────────────
sys.path.insert(0, str(MARKET_DIR))
try:
    import Helpers.SearchAndSave.search_item_prices as _sip
    from Helpers.SearchAndSave.search_item_prices import (
        search_item        as _search_item,
        read_prices        as _read_prices,
        find_exact_result  as _find_exact_result,
        click_at           as _click_at,
    )
    from Helpers.SearchAndSave.common import _parse_price
    MARKET_AVAILABLE = True
except Exception:
    MARKET_AVAILABLE = False

# ── Calibración propia del Almanax ────────────────────────────────────────────
from calibration import load_calibration as _load_almanax_cal

def _init_calibration() -> dict | None:
    """Carga almanax_calibration.json e inyecta los campos en search_item_prices."""
    try:
        cal = _load_almanax_cal()
        if MARKET_AVAILABLE:
            _sip.CAL = cal          # los helpers usan esta variable global
        return cal
    except Exception:
        return None

def get_lot_plan(qty_needed: int, price_dict: dict) -> list:
    """
    Devuelve la combinación óptima de lotes como [(tamaño, n_lotes), ...].
    Misma lógica que optimal_cost pero retorna el plan en vez del coste.
    """
    import math
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return []

    best_cost = float("inf")
    best_plan = []
    sizes = sorted(available)

    for min_size in sizes:
        remaining = qty_needed
        cost = 0
        plan = []
        for size in sorted(sizes, reverse=True):
            if size < min_size:
                continue
            lot_price = available[size]
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                if n > 0:
                    cost += n * lot_price
                    plan.append((size, n))
                remaining = 0
            else:
                n = remaining // size
                if n > 0:
                    cost += n * lot_price
                    plan.append((size, n))
                remaining -= n * size
        if cost < best_cost:
            best_cost = cost
            best_plan = plan

    return best_plan

# ── Colores (mismo tema que MarketTracker) ────────────────────────────────────
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


# ── Persistencia de precios ───────────────────────────────────────────────────
# Formato: { "Nombre item": {"x1": int, "x10": int, "x100": int, "x1000": int} }
# Compatibilidad hacia atrás: si el valor es un int, se trata como precio x1.

LOTS = (1, 10, 100, 1000)

def _normalize_entry(v) -> dict:
    """Convierte entradas antiguas (int) al nuevo formato dict."""
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
    Calcula el coste mínimo para comprar al menos qty_needed ítems.

    Los valores en price_dict son el precio TOTAL del lote:
      x1=395   → comprar 1 ítem cuesta 395 k
      x10=2552 → comprar un lote de 10 cuesta 2552 k  (255 k/u)
      x100=... → comprar un lote de 100 cuesta ... k

    Estrategia: para cada tamaño de lote como "unidad mínima", rellena
    con lotes más grandes (greedy) y redondea hacia arriba con ese lote.
    Toma el mínimo de todas las estrategias.
    """
    import math
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return 0

    best = float("inf")
    sizes = sorted(available)

    for min_size in sizes:
        remaining = qty_needed
        cost = 0
        for size in sorted(sizes, reverse=True):
            if size < min_size:
                continue
            lot_price = available[size]          # precio total del lote (no unitario)
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                cost += n * lot_price            # n lotes × precio_lote
                remaining = 0
            else:
                n = remaining // size
                cost += n * lot_price            # n lotes × precio_lote
                remaining -= n * size
        best = min(best, cost)

    return int(best) if best != float("inf") else 0


# ── API ───────────────────────────────────────────────────────────────────────

def fetch_almanax(start: date, end: date) -> list:
    url = f"{API_BASE}?range[from]={start.isoformat()}&range[to]={end.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "AlmanaxTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Aplicación ────────────────────────────────────────────────────────────────

class AlmanaxApp:

    def __init__(self, root: tk.Tk):
        self.root    = root
        self.prices  = load_prices()
        self.data    = []          # lista de dicts procesados
        self._worker = None
        self._scan_worker   = None
        self._scan_stop     = threading.Event()
        self._buy_stop      = threading.Event()
        self._market_event  = threading.Event()
        self._market_ok     = False
        self.buy_cal        = _init_calibration()
        self._sort_col     = "ganancia"
        self._sort_reverse = True
        self._copy_timer   = None

        self._setup_window()
        self._build_ui()
        # Carga automática al arrancar
        self.root.after(200, self._start_fetch)

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Almanax")
        self.root.geometry("1150x720+40+40")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(800, 500)

    # ── UI ────────────────────────────────────────────────────────────────────

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

        # Rango de fechas
        today = date.today()
        tk.Label(bar, text="  Desde:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.from_var = tk.StringVar(value=today.isoformat())
        from_entry = tk.Entry(bar, textvariable=self.from_var, width=11,
                              bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                              insertbackground=C["text"], relief="flat")
        from_entry.pack(side="left")
        from_entry.bind("<Return>", lambda _: self._refresh_table())

        tk.Label(bar, text="  Hasta:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(4, 4))
        self.to_var = tk.StringVar(value=(today + timedelta(days=29)).isoformat())
        to_entry = tk.Entry(bar, textvariable=self.to_var, width=11,
                            bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                            insertbackground=C["text"], relief="flat")
        to_entry.pack(side="left")
        to_entry.bind("<Return>", lambda _: self._refresh_table())

        # Personajes
        tk.Label(bar, text="  Pjs:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.pjs_var = tk.StringVar(value="15")
        pjs_entry = tk.Entry(bar, textvariable=self.pjs_var, width=4,
                             bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                             insertbackground=C["text"], relief="flat")
        pjs_entry.pack(side="left")
        pjs_entry.bind("<Return>", lambda _: self._refresh_table())

        # Almanichas por pj/día
        tk.Label(bar, text="  Alm/pj:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4))
        self.alm_var = tk.StringVar(value="4")
        alm_entry = tk.Entry(bar, textvariable=self.alm_var, width=4,
                             bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                             insertbackground=C["text"], relief="flat")
        alm_entry.pack(side="left")
        alm_entry.bind("<Return>", lambda _: self._refresh_table())

        # Precios guijarros (Temporal=3alm, Lunar=15alm, Solar=75alm)
        GUIJ = [("T", 3, "3600"), ("L", 15, "18000"), ("S", 75, "90000")]
        self.guij_vars = {}   # {"T": StringVar, "L": ..., "S": ...}
        for code, cost, default in GUIJ:
            tk.Label(bar, text=f"  G{code}:", bg=C["bg"], fg=C["dim"],
                     font=("Consolas", 10)).pack(side="left", padx=(4, 2))
            v = tk.StringVar(value=default)
            self.guij_vars[code] = v
            e = tk.Entry(bar, textvariable=v, width=7,
                         bg=C["surface"], fg=C["text"], font=("Consolas", 10),
                         insertbackground=C["text"], relief="flat")
            e.pack(side="left")
            e.bind("<Return>", lambda _: self._refresh_table())

        # Label que muestra el mejor guijarro
        self.best_guij_lbl = tk.Label(bar, text="", bg=C["bg"],
                                      fg=C["green"], font=("Consolas", 9))

        # Botón cargar
        self.fetch_btn = tk.Button(
            bar, text="⟳  Cargar", bg=C["accent"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", command=self._start_fetch)
        self.fetch_btn.pack(side="left", padx=(14, 4))

        # Botón buscar precios en mercadillo
        scan_state = "normal" if MARKET_AVAILABLE else "disabled"
        scan_tip   = "Buscar precios" if MARKET_AVAILABLE else "Buscar precios (requiere MarketTracker)"
        self.scan_btn = tk.Button(
            bar, text="$  Mercadillo", bg=C["orange"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state=scan_state, command=self._start_scan)
        self.scan_btn.pack(side="left", padx=(4, 0))
        self.scan_btn_tooltip = scan_tip

        self.stop_scan_btn = tk.Button(
            bar, text="■  Detener", bg=C["red"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._stop_scan)
        # se muestra solo mientras escanea

        # Botón calibrar compra
        self.cal_buy_btn = tk.Button(
            bar, text="⚙ Cal.compra", bg=C["surface"], fg=C["dim"],
            font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=4,
            cursor="hand2", state="normal" if MARKET_AVAILABLE else "disabled",
            command=self._calibrate_buy_start)
        self.cal_buy_btn.pack(side="left", padx=(4, 0))

        # Botón comprar todos los rentables
        self.buy_all_btn = tk.Button(
            bar, text="🛒✓ Rentables", bg=C["green"], fg=C["bg"],
            font=("Consolas", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2", state="normal" if MARKET_AVAILABLE else "disabled",
            command=self._buy_all_profitable)
        self.buy_all_btn.pack(side="left", padx=(4, 0))

        self.best_guij_lbl.pack(side="left", padx=(6, 0))

        # Status
        self.status_lbl = tk.Label(bar, text="", bg=C["bg"], fg=C["dim"],
                                   font=("Consolas", 9))
        self.status_lbl.pack(side="left", padx=8)

        # Solo mostrar rentables
        self.only_profit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            bar, text="Solo rentables", variable=self.only_profit_var,
            bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
            activebackground=C["bg"], activeforeground=C["accent"],
            font=("Consolas", 9), command=self._refresh_table
        ).pack(side="right", padx=8)

    def _build_table(self):
        frame = tk.Frame(self.root, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("dia", "fecha", "item", "cant", "comprar", "kamas",
                "precio_unit", "coste", "guijarros", "ganancia", "bonus")
        self.tree = ttk.Treeview(frame, columns=cols,
                                  show="headings", selectmode="browse")

        defs = [
            ("dia",        "Día",            55,  "center"),
            ("fecha",      "Fecha",          95,  "center"),
            ("item",       "Item requerido", 230, "w"),
            ("cant",       "x1 pj",          48,  "center"),
            ("comprar",    "Comprar",         72,  "center"),
            ("kamas",      "Kamas/pj",        85,  "center"),
            ("precio_unit","Precio unit.",   105, "center"),
            ("coste",      "Coste total",    95,  "center"),
            ("guijarros",  "Guijarros",      85,  "center"),
            ("ganancia",   "Ganancia",       90,  "center"),
            ("bonus",      "Bonus del día",  280, "w"),
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
        self.tree.bind("<ButtonRelease-1>", self._on_row_click)

    def _build_totalsbar(self):
        bar = tk.Frame(self.root, bg=C["bg"], pady=4)
        bar.pack(fill="x", padx=12)

        tk.Label(bar, text="Días rentables:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=(4, 2))
        self.total_days_lbl = tk.Label(bar, text="—", bg=C["bg"], fg=C["green"],
                                       font=("Consolas", 9, "bold"))
        self.total_days_lbl.pack(side="left", padx=(0, 14))

        tk.Label(bar, text="Invertido:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=(0, 2))
        self.total_cost_lbl = tk.Label(bar, text="—", bg=C["bg"], fg=C["red"],
                                       font=("Consolas", 9, "bold"))
        self.total_cost_lbl.pack(side="left", padx=(0, 14))

        tk.Label(bar, text="Ganado:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=(0, 2))
        self.total_profit_lbl = tk.Label(bar, text="—", bg=C["bg"], fg=C["green"],
                                         font=("Consolas", 9, "bold"))
        self.total_profit_lbl.pack(side="left", padx=(0, 14))

        tk.Label(bar, text="Beneficio neto:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 9)).pack(side="left", padx=(0, 2))
        self.total_net_lbl = tk.Label(bar, text="—", bg=C["bg"], fg=C["accent"],
                                      font=("Consolas", 9, "bold"))
        self.total_net_lbl.pack(side="left")

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

        # Campos de precio por lote
        self.lot_vars = {}
        self.lot_entries = {}
        for size in LOTS:
            tk.Label(bar, text=f"x{size}:", bg=C["surface"], fg=C["dim"],
                     font=("Consolas", 9)).pack(side="left", padx=(10, 2))
            var = tk.StringVar()
            entry = tk.Entry(bar, textvariable=var, width=9,
                             bg=C["bg"], fg=C["text"], font=("Consolas", 9),
                             insertbackground=C["text"], relief="flat")
            entry.pack(side="left")
            entry.bind("<Return>", lambda _: self._save_price())
            self.lot_vars[size]   = var
            self.lot_entries[size] = entry

        tk.Button(
            bar, text="Guardar  [↵]", bg=C["green"], fg=C["bg"],
            font=("Consolas", 9, "bold"), relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._save_price
        ).pack(side="left", padx=(10, 4))

        tk.Button(
            bar, text="Borrar", bg=C["surface"], fg=C["red"],
            font=("Consolas", 9), relief="flat", padx=6, pady=2,
            cursor="hand2", command=self._delete_price
        ).pack(side="left")

        # Leyenda
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

        self.tree.tag_configure("alta",      foreground=C["green"])
        self.tree.tag_configure("media",     foreground=C["yellow"])
        self.tree.tag_configure("perdida",   foreground=C["red"])
        self.tree.tag_configure("sin_precio",foreground=C["dim"])
        self.tree.tag_configure("hoy",       background=C["today"])

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
        self.data = [self._parse(e) for e in raw]
        self.fetch_btn.config(state="normal")
        self.status_lbl.config(
            text=f"✓ {len(self.data)} días cargados", fg=C["green"])
        if self.data:
            self.from_var.set(self.data[0]["date"])
            self.to_var.set(self.data[-1]["date"])
        self._refresh_table()

    def _on_error(self, msg: str):
        self.status_lbl.config(text=f"Error: {msg}", fg=C["red"])
        self.fetch_btn.config(state="normal")

    # ── Proceso de datos ──────────────────────────────���─────────────────────���─

    def _parse(self, entry: dict) -> dict:
        item_name  = entry["tribute"]["item"]["name"]
        qty        = entry["tribute"]["quantity"]
        kamas      = entry["reward_kamas"]
        return dict(
            date       = entry["date"],
            item       = item_name,
            qty        = qty,
            kamas      = kamas,
            price      = 0,
            cost       = 0,
            profit     = None,
            guijarros  = 0,
            bonus      = entry["bonus"]["description"],
            bonus_type = entry["bonus"]["type"]["name"],
            subtype    = entry["tribute"]["item"].get("subtype", "resources"),
        )

    def _pjs(self) -> int:
        try:
            return max(1, int(self.pjs_var.get()))
        except ValueError:
            return 1

    # Guijarro costs in almanichas
    _GUIJ_COST = {"T": 3, "L": 15, "S": 75}
    _GUIJ_NAME = {"T": "Temporal", "L": "Lunar", "S": "Solar"}

    def _guijarro_kamas_per_pj(self) -> int:
        """
        Devuelve los kamas ganados por pj gracias a los guijarros.
        Elige el tipo de guijarro que más renta según kamas/almanich.
        Actualiza self.best_guij_lbl con el mejor tipo.
        """
        try:
            alm = max(0, int(self.alm_var.get()))
        except ValueError:
            alm = 0
        if alm == 0:
            self.best_guij_lbl.config(text="")
            return 0

        best_ratio = 0.0
        best_code  = None
        prices     = {}
        for code, cost in self._GUIJ_COST.items():
            try:
                price = max(0, int(self.guij_vars[code].get().replace(".", "").replace(",", "")))
            except ValueError:
                price = 0
            prices[code] = price
            if price == 0:
                continue
            ratio = price / cost   # kamas por almanich
            if ratio > best_ratio:
                best_ratio = ratio
                best_code  = code

        if best_code is None:
            self.best_guij_lbl.config(text="")
            return 0

        cost   = self._GUIJ_COST[best_code]
        price  = prices[best_code]
        n_guij = alm // cost
        kamas  = n_guij * price
        label  = (f"▶ {self._GUIJ_NAME[best_code]} "
                  f"({n_guij}× {price:,}k = {kamas:,}k/pj  |  {best_ratio:,.0f}k/alm)")
        self.best_guij_lbl.config(text=label)
        return kamas

    def _recompute(self):
        """Recalcula precios/ganancias con los precios actuales y el nº de pjs."""
        pjs = self._pjs()
        for r in self.data:
            pd = self.prices.get(r["item"])          # dict o None
            qty_total = r["qty"] * pjs
            if pd:
                cost       = optimal_cost(qty_total, pd)
                # Precio unitario = precio de lote más barato / tamaño de ese lote
                unit_price = min(
                    (pd[f"x{s}"] / s for s in LOTS if pd.get(f"x{s}", 0) > 0),
                    default=0
                )
                unit_price = round(unit_price)
            else:
                cost       = 0
                unit_price = 0
            r["price_dict"] = pd or {}
            r["price"]      = unit_price
            r["cost"]       = cost
            guij_k = self._guijarro_kamas_per_pj()
            r["guijarros"]  = guij_k * pjs
            r["profit"]     = (r["kamas"] * pjs + r["guijarros"] - cost) if pd else None

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        self._recompute()
        self.tree.delete(*self.tree.get_children())
        today_str   = date.today().isoformat()
        only_profit = self.only_profit_var.get()

        try:
            from_date = date.fromisoformat(self.from_var.get())
        except ValueError:
            from_date = date.min
        try:
            to_date = date.fromisoformat(self.to_var.get())
        except ValueError:
            to_date = date.max

        rows = [r for r in self.data
                if from_date <= date.fromisoformat(r["date"]) <= to_date]
        if only_profit:
            rows = [r for r in rows if r["profit"] is not None and r["profit"] > 0]

        rows = self._sort(rows)

        for r in rows:
            day_delta = (date.fromisoformat(r["date"]) - date.today()).days
            day_lbl   = "Hoy" if day_delta == 0 else f"+{day_delta}d"

            p_str    = f"{r['price']:,}" if r["price"] else "—"
            cost_str = f"{r['cost']:,}" if r["cost"] else "—"
            gan_str  = (f"{r['profit']:+,}" if r["profit"] is not None else "—")

            tag = "sin_precio"
            if r["profit"] is not None:
                if r["profit"] >= 500:
                    tag = "alta"
                elif r["profit"] >= 0:
                    tag = "media"
                else:
                    tag = "perdida"

            tags = (tag, "hoy") if r["date"] == today_str else (tag,)

            bonus_short = r["bonus"]
            if len(bonus_short) > 65:
                bonus_short = bonus_short[:65] + "…"

            comprar_str = f"{r['qty'] * self._pjs():,}"

            self.tree.insert("", "end", iid=r["date"], tags=tags,
                             values=(day_lbl, r["date"], r["item"],
                                     r["qty"], comprar_str, f"{r['kamas']:,}",
                                     p_str, cost_str,
                                     f"{r['guijarros']:,}",
                                     gan_str, bonus_short))

        self._update_totals(rows)

    def _update_totals(self, rows: list):
        profitable = [r for r in rows if r.get("profit") is not None and r["profit"] > 0]
        n          = len(profitable)
        invertido  = sum(r["cost"]   for r in profitable)
        ganado     = sum(r["profit"] + r["cost"] for r in profitable)  # ingreso bruto
        neto       = sum(r["profit"] for r in profitable)

        if n == 0:
            for lbl in (self.total_days_lbl, self.total_cost_lbl,
                        self.total_profit_lbl, self.total_net_lbl):
                lbl.config(text="—")
            return

        self.total_days_lbl.config(text=str(n))
        self.total_cost_lbl.config(text=f"{invertido:,} k")
        self.total_profit_lbl.config(text=f"{ganado:,} k")
        self.total_net_lbl.config(text=f"{neto:+,} k",
                                  fg=C["green"] if neto >= 0 else C["red"])

    def _sort(self, rows: list) -> list:
        col = self._sort_col
        rev = self._sort_reverse

        def key(r):
            if col == "ganancia":
                return r["profit"] if r["profit"] is not None else (-999_999_999 if rev else 999_999_999)
            if col == "kamas":   return r["kamas"]
            if col == "cant":    return r["qty"]
            if col == "comprar": return r["qty"] * self._pjs()
            if col == "coste":      return r["cost"]
            if col == "guijarros":  return r.get("guijarros", 0)
            if col == "precio_unit": return r["price"]
            if col == "fecha":   return r["date"]
            if col == "dia":     return r["date"]
            if col == "item":    return r["item"].lower()
            if col == "bonus":   return r["bonus"].lower()
            return 0

        return sorted(rows, key=key, reverse=rev)

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col     = col
            self._sort_reverse = True
        self._refresh_table()

    # ── Selección y edición de precio ─────────────────────────────────────────

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
            self.status_lbl.config(
                text=f"Precio borrado: {full_name[:30]}", fg=C["yellow"])
            self._refresh_table()

    def _full_item_name(self, display: str) -> str:
        """Recupera el nombre completo desde self.data (puede estar truncado)."""
        display_clean = display.rstrip("…")
        for r in self.data:
            if r["item"].startswith(display_clean):
                return r["item"]
        return display

    # ── Búsqueda de precios en mercadillo ─────────────────────────────────────

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

    # Nombres de mercadillo por subtype
    _MARKET_NAMES = {
        "resources":   "Recursos",
        "equipment":   "Equipamiento",
        "consumables": "Consumibles",
    }

    def _scan_thread(self):
        import time

        # Cargar calibración
        try:
            _init_calibration()
        except Exception as e:
            self.root.after(0, self._scan_done, 0, 0,
                            f"Error cargando calibración: {e}")
            return

        # Agrupar ítems únicos por subtype (mercadillo)
        groups: dict[str, list[str]] = {}
        seen = set()
        for r in self.data:
            key = r["subtype"]
            item = r["item"]
            if item not in seen:
                seen.add(item)
                groups.setdefault(key, []).append(item)
        for items in groups.values():
            items.sort()

        total   = sum(len(v) for v in groups.values())
        updated = 0
        scanned = 0

        for subtype, items in groups.items():
            if self._scan_stop.is_set():
                break

            market_name = self._MARKET_NAMES.get(subtype, subtype.capitalize())

            # Pedir al usuario que abra el mercadillo correcto
            ok = self._ask_market_switch(market_name, len(items))
            if not ok or self._scan_stop.is_set():
                break

            # Cuenta atrás de 3 s
            for i in range(3, 0, -1):
                if self._scan_stop.is_set():
                    break
                self.root.after(0, self.status_lbl.config, {
                    "text": f"[{market_name}] Cambia al juego… {i}s",
                    "fg": C["yellow"],
                })
                time.sleep(1)

            if self._scan_stop.is_set():
                break

            # Escanear ítems de este mercadillo
            for item in items:
                if self._scan_stop.is_set():
                    break

                scanned += 1
                self.root.after(0, self.status_lbl.config, {
                    "text": f"[{market_name}] [{scanned}/{total}] {item[:30]}…",
                    "fg": C["yellow"],
                })

                try:
                    _search_item(item)
                    raw = _read_prices(item)
                    import keyboard as _kb
                    _kb.press_and_release("esc")
                    time.sleep(0.3)
                except Exception:
                    continue

                # Guardar los 4 precios
                entry = {f"x{s}": _parse_price(raw, str(s)) for s in LOTS}
                if any(v > 0 for v in entry.values()):
                    self.prices[item] = entry
                    updated += 1
                    save_prices(self.prices)
                    self.root.after(0, self._refresh_table)

        self.root.after(0, self._scan_done, updated, total)

    def _ask_market_switch(self, market_name: str, count: int) -> bool:
        """Muestra un diálogo en el hilo principal y espera la respuesta del usuario."""
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
            f"Tendrás 3 segundos para poner el juego en primer plano.",
            icon="question",
        )
        self._market_ok = result
        self._market_event.set()

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
        t = threading.Thread(target=self._calibrate_buy_thread, daemon=True)
        t.start()

    def _calibrate_buy_thread(self):
        self.root.after(0, self.status_lbl.config,
                        {"text": "Sigue las instrucciones en la consola…", "fg": C["yellow"]})
        try:
            from calibration import calibrate
            calibrate()
            self.buy_cal = _init_calibration()
            self.root.after(0, self.status_lbl.config,
                            {"text": "✓ Calibración guardada", "fg": C["green"]})
        except Exception as e:
            self.root.after(0, self.status_lbl.config,
                            {"text": f"Error calibración: {e}", "fg": C["red"]})

    # ── Compra automática ─────────────────────────────────────────────────────

    # ── Compra masiva de rentables ─────────────────────────────────────────────

    def _buy_all_profitable(self):
        if not MARKET_AVAILABLE:
            return
        if not self.buy_cal:
            messagebox.showwarning("Calibración", "Primero calibra la compra (⚙ Cal.compra).")
            return

        pjs = self._pjs()
        try:
            from_date = date.fromisoformat(self.from_var.get())
            to_date   = date.fromisoformat(self.to_var.get())
        except ValueError:
            from_date, to_date = date.min, date.max

        # Recoger rentables con precio guardado, sin duplicados de ítem, dentro del rango
        seen   = set()
        items  = []
        for r in self.data:
            if not (from_date <= date.fromisoformat(r["date"]) <= to_date):
                continue
            if r.get("profit") is None or r["profit"] <= 0:
                continue
            if not r.get("price_dict"):
                continue
            if r["item"] in seen:
                continue
            seen.add(r["item"])
            plan = get_lot_plan(r["qty"] * pjs, r["price_dict"])
            if plan:
                items.append((r["item"], plan, r.get("subtype", "resources")))

        if not items:
            messagebox.showinfo("Sin rentables", "No hay ítems rentables con precio guardado.")
            return

        resumen = "\n".join(f"• {name}  ({'+'.join(f'{n}×x{s}' for s,n in plan)})"
                            for name, plan, _ in items)
        if not messagebox.askokcancel(
            "Comprar todos los rentables",
            f"{len(items)} ítems rentables:\n\n{resumen}\n\n"
            "El script comprará automáticamente. ¡Tendrás 5 segundos para cambiar al juego!"
        ):
            return

        self.buy_all_btn.config(state="disabled")
        self._buy_stop.clear()
        threading.Thread(target=self._buy_all_thread, args=(items,), daemon=True).start()

    def _buy_all_thread(self, items: list):
        """items: [(nombre, plan, subtype), ...]"""
        import time, keyboard as _kb

        # Registrar tecla Y para parar
        _kb.add_hotkey("y", self._buy_stop.set)

        # Agrupar por mercadillo
        groups: dict[str, list] = {}
        for name, plan, subtype in items:
            groups.setdefault(subtype, []).append((name, plan))

        failed = []   # ítems rentables que no se pudieron comprar

        _init_calibration()

        try:
            for subtype, group in groups.items():
                if self._buy_stop.is_set():
                    failed.extend(name for name, _ in group)
                    continue

                market_name = self._MARKET_NAMES.get(subtype, subtype.capitalize())

                ok = self._ask_market_switch(market_name, len(group))
                if not ok:
                    failed.extend(name for name, _ in group)
                    continue

                for i in range(5, 0, -1):
                    if self._buy_stop.is_set():
                        break
                    self.root.after(0, self.status_lbl.config,
                                    {"text": f"[{market_name}] Cambia al juego… {i}s  (Y para parar)", "fg": C["yellow"]})
                    time.sleep(1)

                for name, plan in group:
                    if self._buy_stop.is_set():
                        failed.append(name)
                        continue
                    try:
                        _search_item(name)
                        pos = _find_exact_result(name)
                        if pos is None:
                            failed.append(name)
                            continue
                        _click_at(pos, delay=0.4)

                        total_ops   = sum(n for _, n in plan)
                        done        = 0
                        for lot_size, n_lots in plan:
                            if self._buy_stop.is_set():
                                break
                            row_pos     = self.buy_cal["lot_buttons"][str(lot_size)]
                            confirm_pos = self.buy_cal["buy_btn"]
                            first_click = True  # cada lote nuevo necesita confirmar la primera vez
                            for _ in range(n_lots):
                                if self._buy_stop.is_set():
                                    break
                                _click_at(row_pos, delay=0.25)
                                if first_click:
                                    _click_at(confirm_pos, delay=0.4)
                                    first_click = False
                                time.sleep(1)
                                done += 1
                                self.root.after(0, self.status_lbl.config, {
                                    "text": f"[{market_name}] {name[:25]}: {done}/{total_ops}…  (Y para parar)",
                                    "fg": C["yellow"],
                                })
                        _kb.press_and_release("esc")
                        time.sleep(0.3)

                    except Exception:
                        failed.append(name)
                        _kb.press_and_release("esc")
                        time.sleep(0.3)
        finally:
            _kb.remove_hotkey("y")

        self.root.after(0, self._buy_all_done, failed)

    def _buy_all_done(self, failed: list):
        self.buy_all_btn.config(state="normal")
        if failed:
            lista = "\n".join(f"• {n}" for n in failed)
            messagebox.showwarning(
                "Ítems no comprados",
                f"Los siguientes ítems eran rentables pero no se pudieron comprar:\n\n{lista}"
            )
            self.status_lbl.config(text=f"✓ Compra completada — {len(failed)} fallidos", fg=C["yellow"])
        else:
            self.status_lbl.config(text="✓ Todos los rentables comprados", fg=C["green"])

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


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    AlmanaxApp(root)
    root.mainloop()
