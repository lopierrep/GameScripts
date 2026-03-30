"""
Crafting - Orquestador principal
=================================
Conecta la UI con la lógica de negocio.
Entrada: python main.py  →  lanza la interfaz gráfica.
"""

import json
import os
import sys
import threading
import tkinter as tk

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Crafting.config.config import C, DATA_DIR, UNKNOWN_KEY
from Crafting.utils.loaders import _load_omitted_categories, _load_omitted_recipes, find_recipe_file, list_professions, load_user_settings, save_user_settings
from Crafting.core.prices import (
    build_item_lookup,
    build_table_rows,
    compute_and_save_display_data,
    ensure_catalogued,
    get_market_for_category,
    load_all_pack_prices,
    load_markets,
    load_raw_market_prices,
    save_crafting_costs,
)
from Crafting.core.recipes import (
    all_recipe_results,
    build_result_file_map,
    expand_sub_ingredients,
    load_all_craftable_recipes,
    sub_recipe_files,
)
from Crafting.ui.ui import CraftingUI
from shared.ui.floating_progress import FloatingProgress


# ── stdout redirect ────────────────────────────────────────────────────────────

class _StdoutRedirect:
    def __init__(self, callback):
        self._cb = callback

    def write(self, text):
        if text:
            self._cb(text)

    def flush(self):
        pass


# ── Helpers internos ───────────────────────────────────────────────────────────

def _build_market_groups(
    result_items: list,       # [(name, category), ...]
    all_ingredients: set,
    craftable: dict,
    markets: dict,
    item_lookup: dict,
) -> tuple[dict, set]:
    """
    Agrupa resultados e ingredientes por mercadillo.
    Devuelve (market_groups, sub_results).
    """
    market_groups: dict = {}

    for name, category in result_items:
        market_name = get_market_for_category(category, markets)
        if market_name:
            market_groups.setdefault(market_name, {"results": [], "ingredients": []})
            market_groups[market_name]["results"].append(name)
        else:
            print(f"  ? {name} → {category} [sin mercadillo, ignorado]")

    for name in all_ingredients:
        if name in item_lookup:
            m, _ = item_lookup[name]
            market_groups.setdefault(m, {"results": [], "ingredients": []})
            if name not in market_groups[m]["ingredients"]:
                market_groups[m]["ingredients"].append(name)

    sub_results = all_ingredients & set(craftable.keys())
    for sub_name in sub_results:
        sub_recipe  = craftable.get(sub_name, {})
        category    = sub_recipe.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            market_groups.setdefault(market_name, {"results": [], "ingredients": []})
            if sub_name not in market_groups[market_name]["results"]:
                market_groups[market_name]["results"].append(sub_name)

    return market_groups, sub_results


def _finalize_costs(
    sub_results: set,
    recipe_file: str,
    recipe_filter=None,   # callable(all_recipes) -> subset | None para todas
) -> set:
    """
    Calcula costos de subrecetas, guarda costos en recipe_file y
    pre-calcula los datos de display (profit_x*, display) en el JSON.
    Devuelve el conjunto de ingredientes sin precio.
    """
    if sub_results:
        for sub_file in sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            save_crafting_costs(sub_file)

    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    subset = recipe_filter(all_recipes) if recipe_filter else all_recipes
    still_missing = save_crafting_costs(recipe_file, subset)

    # Pre-calcular datos de display con costos ya guardados
    pack_prices   = load_all_pack_prices()
    craftable_map = load_all_craftable_recipes()
    if sub_results:
        for sub_file in sub_recipe_files(sub_results, recipe_file):
            compute_and_save_display_data(sub_file, pack_prices, craftable_map)
    compute_and_save_display_data(recipe_file, pack_prices, craftable_map, recipe_filter)

    return still_missing


# ── Orchestration functions ────────────────────────────────────────────────────

def update_profession(
    profession: str,
    stop_flag: list = None,
    on_confirm=None,
    manual_price_fn=None,
    on_item_done=None,
    filtered: set = None,
    on_progress=None,
):
    if stop_flag is None:
        stop_flag = [False]

    recipe_file = find_recipe_file(profession)
    if not recipe_file:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(DATA_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        print(f"[ERROR] No se encontró receta para '{profession}'.")
        print(f"  Profesiones disponibles: {', '.join(available)}")
        return

    with open(recipe_file, encoding="utf-8") as f:
        recipes = json.load(f)

    omitted_recipes    = _load_omitted_recipes()
    omitted_categories = _load_omitted_categories()
    recipes = [
        r for r in recipes
        if r.get("result") not in omitted_recipes
        and r.get("category", "") not in omitted_categories
    ]

    if filtered:
        recipes = [r for r in recipes if r.get("result") in filtered]
        print(f"[INFO] Filtrado: {len(recipes)} recetas seleccionadas.\n")

    all_results     = {r["result"] for r in recipes}
    all_ingredients = {ing["name"] for r in recipes for ing in r.get("ingredients", [])}

    craftable       = load_all_craftable_recipes()
    all_ingredients = expand_sub_ingredients(all_ingredients, craftable)

    import shared.market.search_item_prices as _sip
    _sip.load_calibration()

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    craftable_results = all_recipe_results()
    ensure_catalogued(all_ingredients, markets, item_lookup, craftable_results)

    result_items = [(r["result"], r.get("category", UNKNOWN_KEY)) for r in recipes]
    market_groups, sub_results = _build_market_groups(
        result_items, all_ingredients, craftable, markets, item_lookup
    )

    result_file_map = build_result_file_map()

    from Crafting.automation.scanner import build_scan_items
    from shared.market.item_price_scanner import scan_prices
    from shared.market.common import CACHE_SECONDS
    from Crafting.config.config import DELAY_BETWEEN_ITEMS
    from Crafting.utils.market import filter_lot_prices
    import keyboard as _keyboard
    import time as _time

    is_stopped  = lambda: bool(stop_flag[0])
    scan_items  = build_scan_items(market_groups, item_lookup, markets, craftable, result_file_map)

    def _on_market_switch(market_name, n):
        print(f"\n── {market_name} ({n} items) ──")
        if on_confirm:
            on_confirm(market_name)
        else:
            input(f"  Ve al mercadillo de {market_name} y pulsa ENTER para continuar…")
        print()
        return not stop_flag[0]

    def _on_manual_item(item, idx, total_manual):
        if not manual_price_fn:
            return None
        return manual_price_fn(item.name, item.type == "result")

    def _press_esc():
        _keyboard.press_and_release("esc")
        _time.sleep(0.15)

    if not stop_flag[0]:
        scan_prices(
            items              = scan_items,
            press_esc          = _press_esc,
            is_stopped         = is_stopped,
            on_progress        = on_progress or print,
            on_market_switch   = _on_market_switch,
            delay              = DELAY_BETWEEN_ITEMS,
            fresh_seconds      = CACHE_SECONDS,
            on_manual_item     = _on_manual_item,
            on_item_done       = on_item_done,
            filter_selling     = filter_lot_prices,
        )

    if stop_flag[0]:
        print("\n[INFO] Detenido por el usuario. No se guardaron cambios.")
        return

    still_missing = _finalize_costs(sub_results, recipe_file)

    print(f"\n[DONE] {os.path.basename(recipe_file)}: {len(recipes)} recetas actualizadas.")
    if still_missing:
        print(f"\n[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")




# ── CraftingApp ────────────────────────────────────────────────────────────────

class CraftingApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self._stop_flag  = [False]
        self._float      = FloatingProgress(self.root)
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self._last_refresh = 0.0

        professions = list_professions()
        prof_counts = {}
        for prof in professions:
            path = find_recipe_file(prof)
            if path:
                try:
                    with open(path, encoding="utf-8") as f:
                        prof_counts[prof] = len(json.load(f))
                except Exception:
                    prof_counts[prof] = 0

        callbacks = {
            "start":     self._start,
            "stop":      self._stop,
            "sync":      self._sync,
            "calibrate": self._calibrate,
        }

        UIClass = CraftingUI
        self.ui = UIClass(root, callbacks, professions, load_user_settings, save_user_settings,
                          prof_counts=prof_counts)

        sys.stdout = _StdoutRedirect(lambda _: None)
        sys.stderr = _StdoutRedirect(lambda _: None)

        self.ui.set_status("Listo", C["dim"])

        # Cargar datos existentes al arrancar
        if professions:
            self.root.after(100, self._load_table, professions[0])

        # Recargar tabla al cambiar de profesión
        self.ui._prof_cb.bind("<<ComboboxSelected>>", self._on_profession_changed, add="+")


    def _on_profession_changed(self, _event=None):
        profession = self.ui.profession()
        if profession:
            self._load_table(profession)

    # ── Callbacks de UI ───────────────────────────────────────────────────────

    def _start(self, target: str, filtered: set = None):
        self._float.show(on_stop=self._stop)
        self._stop_flag[0] = False
        self.root.after(0, self.ui.set_busy, True)
        self.root.after(0, self.ui.set_status, "Iniciando actualización de precios…", C["accent"])

        t = threading.Thread(
            target=self._run_profession, args=(target, filtered), daemon=True
        )
        t.start()

    def _stop(self):
        self._stop_flag[0] = True
        self.root.after(0, self.ui.set_status, "Deteniendo…", C["yellow"])
        # Desbloquear cualquier prompt activo
        self.root.after(0, self.ui.hide_prompt)

    def _sync(self):
        t = threading.Thread(target=self._run_sync, daemon=True)
        t.start()

    def _calibrate(self):
        from shared.automation.calibration import CalibrationWindow
        from Crafting.calibration.calibration_config import CALIBRATION_POINTS, CALIBRATION_FILE, transform
        CalibrationWindow(
            self.root,
            CALIBRATION_POINTS,
            CALIBRATION_FILE,
            on_done=self._on_calibration_done,
            transform=transform,
        )

    def _on_calibration_done(self):
        self.ui.set_status("✓ Calibración guardada", C["green"])

    # ── Workers ───────────────────────────────────────────────────────────────

    def _run_profession(self, profession: str, filtered: set = None):
        import time as _time

        def _on_item_done():
            now = _time.monotonic()
            if now - self._last_refresh >= 2.0:
                self._last_refresh = now
                self.root.after(0, self._load_table, profession)

        def _on_progress(msg: str):
            self.root.after(0, self.ui.set_status, msg, C["accent"])
            self.root.after(0, self._float.update, msg)

        try:
            self.root.after(0, self.ui.set_status, f"Actualizando {profession}…", C["accent"])
            update_profession(
                profession, self._stop_flag, filtered=filtered,
                on_confirm=self._ask_confirm,
                manual_price_fn=self._ask_manual_price,
                on_item_done=_on_item_done,
                on_progress=_on_progress,
            )
            self.root.after(0, self._load_table, profession)
        except Exception as e:
            self.root.after(0, self.ui.set_status, f"Error: {e}", C["red"])
        finally:
            self.root.after(0, self._on_done)


    def _run_sync(self):
        try:
            self.root.after(0, self.ui.set_status, "Sincronizando…", C["accent"])
            from shared.sync.sheets import sync_data
            warnings = sync_data()
            profession = self.ui.profession()
            if profession:
                self.root.after(0, self._load_table, profession)
            self.root.after(0, self.ui.set_status, "✓ Sincronizado", C["green"])
        except Exception as e:
            self.root.after(0, self.ui.set_status, f"Error: {e}", C["red"])

    def _on_done(self):
        self._float.hide()
        self.ui.set_busy(False)
        self.ui.set_status("Listo", C["dim"])
        self.ui.hide_prompt()

    # ── Prompts bloqueantes (llamados desde hilo worker) ──────────────────────

    def _ask_blocking(self, show_fn, *args):
        """
        Bloquea el hilo worker hasta que el usuario confirme un prompt.
        Llama show_fn(*args, on_confirm) en el hilo principal y espera.
        Devuelve el valor que on_confirm reciba (None si no recibe argumentos).
        """
        if self._stop_flag[0]:
            return None
        ev     = threading.Event()
        result = [None]

        def on_confirm(*cb_args):
            result[0] = cb_args[0] if cb_args else None
            ev.set()

        self.root.after(0, show_fn, *args, on_confirm)
        while not ev.wait(timeout=0.2):
            if self._stop_flag[0]:
                self.root.after(0, self.ui.hide_prompt)
                return None
        return result[0]

    def _ask_confirm(self, market_name: str):
        """Bloquea el hilo worker hasta que el usuario confirme estar en el mercadillo."""
        self._ask_blocking(
            self.ui.show_confirm,
            f"Ve al mercadillo de {market_name} y pulsa CONTINUAR cuando estés listo…",
        )

    def _ask_manual_price(self, name: str, is_selling: bool):
        """Bloquea el hilo worker hasta que el usuario introduzca precios manuales."""
        return self._ask_blocking(self.ui.show_price_prompt, name, is_selling)

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _load_table(self, profession: str):
        recipe_file = find_recipe_file(profession)
        if not recipe_file:
            return
        try:
            with open(recipe_file, encoding="utf-8") as f:
                recipes = json.load(f)
        except Exception:
            return

        omitted_recipes    = _load_omitted_recipes()
        omitted_categories = _load_omitted_categories()
        recipes = [
            r for r in recipes
            if r.get("result") not in omitted_recipes
            and r.get("category", "") not in omitted_categories
        ]

        raw_market_prices, ing_updated_at = load_raw_market_prices()
        craftable_map = load_all_craftable_recipes()

        rows = build_table_rows(recipes, craftable_map, raw_market_prices, ing_updated_at)
        self.ui.refresh_table(rows)

    def restore_io(self):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.withdraw()
    app  = CraftingApp(root)
    try:
        root.mainloop()
    finally:
        app.restore_io()


if __name__ == "__main__":
    main()
