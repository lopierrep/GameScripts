"""
Almanax – Orquestador
=====================
Conecta la UI con los módulos de core/, market/ y calibration/.
"""

import sys
import json
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import date
from pathlib import Path
import urllib.error

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR.parent))

from config.config import C, LOTS, SETTINGS_FILE, CATEGORIES_FILE, STOP_HOTKEY
from core.prices import load_prices, save_prices, optimal_cost, get_lot_plan, best_guijarro, find_item_prices
from core.api    import fetch_almanax, parse_entry, save_almanax, load_almanax, resolve_subtype
from core.table  import today_fr
from shared.market.common import fetch_category, get_market_for_category, load_categories
from calibration.calibration_config import load_calibration as _load_almanax_cal
from ui.ui import AlmanaxUI

# ── Módulo de mercadillo (opcional) ───────────────────────────────────────────
try:
    import shared.market.search_item_prices as _sip
    from shared.market.search_item_prices import (
        search_item       as _search_item,
        read_prices       as _read_prices,
        find_exact_result as _find_exact_result,
        click_at          as _click_at,
    )
    from shared.market.common import _parse_price
    MARKET_AVAILABLE = True
except Exception:
    MARKET_AVAILABLE = False


def _init_calibration() -> dict | None:
    try:
        cal = _load_almanax_cal()
        if MARKET_AVAILABLE:
            _sip.CAL = cal
        return cal
    except Exception:
        return None


def _load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _press_esc():
    import keyboard as _kb
    _kb.press_and_release("esc")


# ── Orquestador ───────────────────────────────────────────────────────────────

class AlmanaxApp:

    def __init__(self, root: tk.Tk):
        self.root    = root
        self.prices  = load_prices()
        self.data:   list[dict] = []
        self.buy_cal = _init_calibration()

        self._worker       = None
        self._scan_worker  = None
        self._scan_stop    = threading.Event()
        self._buy_stop     = threading.Event()
        self._market_event = threading.Event()
        self._market_ok    = False
        self._sort_col     = "fecha"
        self._sort_reverse = False

        settings = _load_settings()
        self.ui = AlmanaxUI(root, callbacks={
            "scan":         self._start_scan,
            "stop_scan":    self._stop_scan,
            "calibrate":    self._calibrate_buy_start,
            "buy_all":      self._buy_all_profitable,
            "stop_buy":     self._stop_buy,
            "select":       self._on_item_selected,
            "refresh":      self._refresh_table,
            "toggle_sort":  self._toggle_sort,
            "sync":         self._sync,
        }, market_available=MARKET_AVAILABLE, settings=settings)

        root.protocol("WM_DELETE_WINDOW", self._on_close)

        cached  = load_almanax()
        today   = today_fr()
        year_end = date(today.year, 12, 31)
        if cached and date.fromisoformat(cached[0]["date"]).year == today.year:
            self.data = cached
            root.after(100, self._refresh_table)
            last_cached = date.fromisoformat(max(e["date"] for e in cached))
            if last_cached < year_end:
                root.after(200, self._start_fetch)
            else:
                root.after(100, lambda: self.ui.set_status("Listo", C["dim"]))
        else:
            root.after(200, self._start_fetch)
        root.after(200, lambda: self.ui.set_calibrated(self.buy_cal is not None))
        root.after(50, lambda: root.attributes("-alpha", 1))

    def _on_close(self):
        _save_settings(self.ui.get_settings())
        self.root.destroy()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _sync(self):
        t = threading.Thread(target=self._run_sync, daemon=True)
        t.start()

    def _run_sync(self):
        try:
            self.root.after(0, self.ui.set_status, "Sincronizando…", C["accent"])
            from shared.sync.sheets import sync_data
            warnings = sync_data()
            for w in warnings:
                print(f"[AVISO] {w}")
            self.prices = load_prices()
            self.root.after(0, self._refresh_table)
            self.root.after(0, self.ui.set_status, "✓ Sincronizado", C["green"])
        except Exception as e:
            self.root.after(0, self.ui.set_status, f"Error sync: {e}", C["red"])

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def _start_fetch(self):
        if self._worker and self._worker.is_alive():
            return
        self.ui.set_status("Cargando desde la API…", C["yellow"])
        self._worker = threading.Thread(target=self._fetch_thread, daemon=True)
        self._worker.start()

    def _fetch_thread(self):
        try:
            today      = today_fr()
            year_end   = date(today.year, 12, 31)
            if self.data:
                from datetime import timedelta
                last = date.fromisoformat(max(e["date"] for e in self.data))
                year_start = last + timedelta(days=1)
            else:
                year_start = date(today.year, 1, 1)
            if year_start > year_end:
                return
            raw        = fetch_almanax(year_start, year_end)

            def _progress(msg):
                self.root.after(0, self.ui.set_status, msg, C["yellow"])

            categories     = load_categories(str(CATEGORIES_FILE))
            subtype_cache  = {}
            category_cache = {}
            processed      = list(self.data)
            total          = len(raw)

            for i, e in enumerate(raw, 1):
                item_name = e["tribute"]["item"]["name"]
                ankama_id = e["tribute"]["item"]["ankama_id"]
                _progress(f"Procesando {i}/{total}: {item_name}…")

                if ankama_id not in subtype_cache:
                    subtype_cache[ankama_id] = resolve_subtype(ankama_id)
                if item_name not in category_cache:
                    cat    = fetch_category(item_name)
                    market = get_market_for_category(cat, categories) or "Unknown"
                    category_cache[item_name] = {"market": market, "category": cat}

                entry = parse_entry(e, subtype_cache[ankama_id])
                entry.update(category_cache[item_name])
                processed.append(entry)
                save_almanax(processed)

            # Reintentar items sin categoría
            failed = [e for e in processed if e.get("category") == "Sin categoría"]
            if failed:
                unique_failed = list(dict.fromkeys(e["item"] for e in failed))
                total_failed  = len(unique_failed)
                for i, item_name in enumerate(unique_failed, 1):
                    _progress(f"Reintentando {i}/{total_failed}: {item_name}…")
                    cat    = fetch_category(item_name)
                    market = get_market_for_category(cat, categories) or "Unknown"
                    if cat != "Sin categoría":
                        for e in processed:
                            if e["item"] == item_name:
                                e["market"]   = market
                                e["category"] = cat
                        save_almanax(processed)

            self.root.after(0, self._on_data, processed)
        except urllib.error.URLError as e:
            self.root.after(0, self._on_error, f"Sin conexión: {e.reason}")
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_data(self, processed: list):
        self.data = processed
        self.ui.set_status(f"✓ {len(self.data)} días cargados", C["green"])
        self._refresh_table()

    def _on_error(self, msg: str):
        self.ui.set_status(f"Error: {msg}", C["red"])

    def _ui_progress(self, msg: str):
        self.root.after(0, self.ui.set_status, msg, C["yellow"])

    # ── Cálculo ───────────────────────────────────────────────────────────────

    def _guijarro_kamas_total(self, pjs: int) -> int:
        alm         = self.ui.alm()
        guij_prices = self.ui.guij_prices()
        result      = best_guijarro(alm * pjs, guij_prices)

        if result is None or alm == 0:
            self.ui.update_best_guijarro("")
            return 0

        label = f"▶ G{result.code}  {result.ratio:,.0f}k/alm"
        self.ui.update_best_guijarro(label)
        return round(result.ratio * alm * pjs)

    def _recompute(self):
        pjs    = self.ui.pjs()
        guij_k = self._guijarro_kamas_total(pjs)

        for r in self.data:
            pd        = find_item_prices(self.prices, r["item"])
            qty_total = r["qty"] * pjs

            has_price = pd and any(pd.get(f"x{s}", 0) > 0 for s in LOTS)
            if has_price:
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
            r["guijarros"]  = guij_k
            r["profit"]     = (r["kamas"] * pjs + r["guijarros"] - cost) if has_price else None

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _filtered_rows(self) -> list[dict]:
        from_date, to_date = self.ui.date_range()
        rows = [r for r in self.data
                if from_date <= date.fromisoformat(r["date"]) <= to_date]
        return self._sort(rows)

    def _refresh_table(self):
        self._recompute()
        rows      = self._filtered_rows()
        today_str = today_fr().isoformat()
        pjs       = self.ui.pjs()
        self.ui.refresh_table(rows, today_str, pjs)
        self._update_totals(rows)

    def _update_totals(self, rows: list[dict]):
        profitable = [r for r in rows if r.get("profit") is not None and r["profit"] > 0]
        if not profitable:
            self.ui.clear_totals()
            return
        invertido = sum(r["cost"]               for r in profitable)
        ganado    = sum(r["profit"] + r["cost"] for r in profitable)
        neto      = sum(r["profit"]             for r in profitable)
        with_losses = [r for r in rows if r.get("profit") is not None]
        neto_all  = sum(r["profit"]             for r in with_losses)
        self.ui.update_totals(len(profitable), invertido, ganado, neto, neto_all)

    def _sort(self, rows: list[dict]) -> list[dict]:
        col, rev = self._sort_col, self._sort_reverse
        sentinel = (-999_999_999 if rev else 999_999_999)
        pjs      = self.ui.pjs()

        key_map = {
            "ganancia":    lambda r: r["profit"] if r["profit"] is not None else sentinel,
            "kamas":       lambda r: r["kamas"],
            "cant":        lambda r: r["qty"],
            "por_cuenta":  lambda r: r["qty"] * 5,
            "comprar":     lambda r: r["qty"] * pjs,
            "coste":       lambda r: r["cost"],
            "kamas_total": lambda r: r["kamas"] * pjs,
            "guijarros":   lambda r: r.get("guijarros", 0),
            "precio_unit": lambda r: r["price"],
            "fecha":       lambda r: r["date"],
            "dia":         lambda r: r["date"],
            "item":        lambda r: r["item"].lower(),
            "bonus":       lambda r: r["bonus"].lower(),
        }
        return sorted(rows, key=key_map.get(col, lambda _: 0), reverse=rev)

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col     = col
            self._sort_reverse = True
        self._refresh_table()

    # ── Precios ───────────────────────────────────────────────────────────────

    def _on_item_selected(self, item_name: str):
        pass

    def _full_item_name(self, display: str) -> str:
        clean = display.rstrip("…")
        for r in self.data:
            if r["item"].startswith(clean):
                return r["item"]
        return display

    # ── Escaneo ───────────────────────────────────────────────────────────────

    def _start_scan(self):
        if not self.data:
            self.ui.set_status("Primero carga los días del Almanax.", C["yellow"])
            return
        if self._scan_worker and self._scan_worker.is_alive():
            return
        self._scan_stop.clear()
        self._buy_stop.clear()
        self.ui.set_scan_busy(True)
        self._scan_worker = threading.Thread(target=self._scan_thread, daemon=True)
        self._scan_worker.start()

    def _stop_scan(self):
        self._scan_stop.set()

    def _stop_buy(self):
        self._buy_stop.set()

    def _scan_thread(self):
        import sys
        import keyboard as _kb
        from automation.scanner import build_scan_items
        from shared.market.item_price_scanner import scan_prices
        from config.config import SCAN_DELAY, SCAN_COUNTDOWN

        _kb.add_hotkey(STOP_HOTKEY, self._scan_stop.set)
        try:
            from_date, to_date = self.ui.date_range()
            items = build_scan_items(self.data, self.prices, from_date, to_date)

            scan_prices(
                items            = items,
                press_esc        = _press_esc,
                is_stopped       = self._scan_stop.is_set,
                on_progress      = self._ui_progress,
                on_market_switch = self._ask_market_switch,
                init_cal         = _init_calibration,
                delay            = SCAN_DELAY,
                countdown        = SCAN_COUNTDOWN,
                fresh_seconds    = sys.maxsize,
            )
        finally:
            self.prices = load_prices()
            try:
                _kb.remove_hotkey(STOP_HOTKEY)
            except Exception:
                pass
            self.root.after(0, self._scan_done)

    def _scan_done(self):
        self.ui.set_scan_busy(False)
        self._refresh_table()

    # ── Calibración ───────────────────────────────────────────────────────────

    def _calibrate_buy_start(self):
        from shared.calibration import CalibrationWindow
        from calibration.calibration_config import CALIBRATION_POINTS, CALIBRATION_FILE, transform
        CalibrationWindow(
            self.root,
            CALIBRATION_POINTS,
            CALIBRATION_FILE,
            on_done=self._on_calibration_done,
            transform=transform,
        )

    def _on_calibration_done(self):
        self.buy_cal = _init_calibration()
        self.ui.set_calibrated(self.buy_cal is not None)
        self.ui.set_status("✓ Calibración guardada", C["green"])

    # ── Compra automática ─────────────────────────────────────────────────────

    def _buy_all_profitable(self):
        if not MARKET_AVAILABLE:
            return
        if not self.buy_cal:
            messagebox.showwarning("Calibración", "Primero calibra la compra (⚙ Cal.compra).")
            return

        pjs               = self.ui.pjs()
        from_date, to_date = self.ui.date_range()

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
            self.ui.set_status("No hay ítems rentables con precio guardado.", C["yellow"])
            return

        all_items = [(n, p) for lst in groups.values() for n, p in lst]

        self.ui.set_buy_busy(True)
        self._buy_stop.clear()
        self._scan_stop.clear()
        threading.Thread(target=self._buy_all_thread, args=(groups,), daemon=True).start()

    def _buy_all_thread(self, groups: dict):
        from automation.buyer import AutoBuyer

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
            on_progress      = self._ui_progress,
            on_market_switch = self._ask_market_switch,
        )
        self.root.after(0, self._buy_all_done, failed)

    def _buy_all_done(self, failed: list[str]):
        self.ui.set_buy_busy(False)
        if failed:
            self.ui.set_status(f"✓ Compra completada — {len(failed)} fallidos", C["yellow"])
        else:
            self.ui.set_status("✓ Todos los rentables comprados", C["green"])

    # ── Sincronización de diálogos con hilos ─────────────────────────────────

    def _ask_market_switch(self, market_name: str, count: int) -> bool:
        self._market_event.clear()
        self._market_ok = False
        self.root.after(0, self._show_market_dialog, market_name, count)
        while not self._market_event.wait(timeout=0.2):
            if self._scan_stop.is_set() or self._buy_stop.is_set():
                self.root.after(0, self.ui.hide_prompt)
                return False
        return self._market_ok

    def _show_market_dialog(self, market_name: str, count: int):
        self.ui.show_confirm(
            f"Abre el mercadillo de {market_name} ({count} items) y pulsa CONTINUAR",
            self._on_market_confirm,
        )

    def _on_market_confirm(self):
        self._market_ok = True
        self._market_event.set()


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-alpha", 0)
    AlmanaxApp(root)
    root.mainloop()
