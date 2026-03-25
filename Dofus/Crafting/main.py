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

from config.config import C, DATA_DIR, UNKNOWN_KEY, find_recipe_file
from core.prices import (
    build_item_lookup,
    build_table_rows,
    ensure_catalogued,
    get_market_for_category,
    load_all_pack_prices,
    load_markets,
    load_raw_market_prices,
    save_crafting_costs,
)
from core.recipes import (
    all_recipe_results,
    build_result_file_map,
    expand_sub_ingredients,
    find_recipe,
    load_all_craftable_recipes,
    profession_from_file,
    sub_recipe_files,
)
from automation.scanner import search_market_batch
from export.export_to_sheets import export_profession
import shared.market.search_item_prices as _sip
from ui.ui import CraftingUI


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
            m = item_lookup[name]
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
    Calcula costos de subrecetas y guarda costos en recipe_file.
    Devuelve el conjunto de ingredientes sin precio.
    """
    if sub_results:
        for sub_file in sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            save_crafting_costs(sub_file)

    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    subset = recipe_filter(all_recipes) if recipe_filter else all_recipes
    return save_crafting_costs(recipe_file, subset)


# ── Orchestration functions ────────────────────────────────────────────────────

def update_profession(
    profession: str,
    limit: int = None,
    stop_flag: list = None,
    on_confirm=None,
    manual_price_fn=None,
    on_item_done=None,
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
    if limit is not None:
        recipes = recipes[:limit]
        print(f"[INFO] Limitado a las primeras {limit} recetas.\n")

    all_results     = {r["result"] for r in recipes}
    all_ingredients = {ing["name"] for r in recipes for ing in r.get("ingredients", [])}

    craftable       = load_all_craftable_recipes()
    all_ingredients = expand_sub_ingredients(all_ingredients, craftable)

    _sip.load_calibration()

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    craftable_results = all_recipe_results()
    ensure_catalogued(all_ingredients, markets, item_lookup, craftable_results)

    result_items = [(r["result"], r.get("category", UNKNOWN_KEY)) for r in recipes]
    market_groups, sub_results = _build_market_groups(
        result_items, all_ingredients, craftable, markets, item_lookup
    )

    result_file_map   = build_result_file_map()
    all_missing_results: list = []

    if not market_groups:
        print("[INFO] No hay items para consultar en ningún mercadillo.")
    else:
        for market_name, group in market_groups.items():
            results     = sorted(group["results"])
            ingredients = sorted(group["ingredients"])
            if not results and not ingredients:
                continue
            miss_r, miss_i = search_market_batch(
                market_name, results, ingredients,
                recipe_file, markets, item_lookup,
                result_file_map, stop_flag,
                on_confirm=on_confirm,
                manual_price_fn=manual_price_fn,
                on_item_done=on_item_done,
            )
            all_missing_results.extend(r for r in miss_r if r in all_results)
            if (miss_r or miss_i) and not stop_flag[0]:
                total = len(miss_r) + len(miss_i)
                print(f"\n[AVISO] {total} items sin precio en {market_name} (no se reintentará).")
            if stop_flag[0]:
                break

    still_missing = _finalize_costs(
        sub_results, recipe_file,
        recipe_filter=lambda rs: rs[:limit] if limit is not None else rs,
    )

    print(f"\n[DONE] {os.path.basename(recipe_file)}: {len(recipes)} recetas actualizadas.")
    if still_missing:
        print(f"\n[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")

    missing_file = os.path.join(DATA_DIR, "missing_recipes.json")
    if os.path.exists(missing_file):
        with open(missing_file, encoding="utf-8") as f:
            content = f.read().strip()
        all_missing = json.loads(content) if content else {}
    else:
        all_missing = {}
    missing_data = sorted(set(all_missing_results))
    all_missing[profession] = missing_data
    with open(missing_file, "w", encoding="utf-8") as f:
        json.dump(all_missing, f, ensure_ascii=False, indent=2)
    if missing_data:
        print(f"\n[INFO] {len(missing_data)} recetas sin precio guardadas en missing_recipes.json")
    else:
        print("\n[INFO] Todas las recetas tienen precio. missing_recipes.json actualizado.")

    print("\nExportando a Google Sheets …")
    export_profession(profession)


def update_single_recipe(
    result_name: str,
    stop_flag: list = None,
    on_confirm=None,
    manual_price_fn=None,
):
    if stop_flag is None:
        stop_flag = [False]

    recipe, recipe_file = find_recipe(result_name)
    if not recipe:
        print(f"[ERROR] No se encontró ninguna receta con resultado '{result_name}'.")
        return

    profession = profession_from_file(recipe_file)
    print(f"[INFO] Receta encontrada en: {os.path.basename(recipe_file)}\n")

    ingredients = {ing["name"] for ing in recipe.get("ingredients", [])}
    craftable   = load_all_craftable_recipes()
    all_ingredients = expand_sub_ingredients(ingredients, craftable)

    _sip.load_calibration()

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    craftable_results = all_recipe_results()
    ensure_catalogued(all_ingredients, markets, item_lookup, craftable_results)

    result_items = [(result_name, recipe.get("category", UNKNOWN_KEY))]
    market_groups, sub_results = _build_market_groups(
        result_items, all_ingredients, craftable, markets, item_lookup
    )

    result_file_map = build_result_file_map()

    for market_name, group in market_groups.items():
        if stop_flag[0]:
            break
        search_market_batch(
            market_name,
            sorted(group["results"]),
            sorted(group["ingredients"]),
            recipe_file, markets, item_lookup,
            result_file_map, stop_flag,
            on_confirm=on_confirm,
            manual_price_fn=manual_price_fn,
        )

    still_missing = _finalize_costs(
        sub_results, recipe_file,
        recipe_filter=lambda rs: [r for r in rs if r.get("result") == result_name],
    )

    print(f"\n[DONE] '{result_name}' actualizado.")
    if still_missing:
        print(f"[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")

    print("\nExportando a Google Sheets …")
    export_profession(profession)


# ── CraftingApp ────────────────────────────────────────────────────────────────

class CraftingApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self._stop_flag  = [False]
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self._last_refresh = 0.0

        professions = self._list_professions()

        callbacks = {
            "start":     self._start,
            "stop":      self._stop,
            "export":    self._export,
            "calibrate": self._calibrate,
        }

        self.ui = CraftingUI(root, callbacks, professions)

        sys.stdout = _StdoutRedirect(self._on_log)
        sys.stderr = _StdoutRedirect(self._on_log)

        # Cargar datos existentes al arrancar
        if professions:
            self.root.after(100, self._load_table, professions[0])

        # Recargar tabla al cambiar de profesión
        self.ui._prof_cb.bind("<<ComboboxSelected>>", self._on_profession_changed)

    def _list_professions(self) -> list:
        if not os.path.isdir(DATA_DIR):
            return []
        return sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(DATA_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )

    def _on_log(self, text: str):
        self.root.after(0, self.ui.log, text)

    def _on_profession_changed(self, _event=None):
        profession = self.ui.profession()
        if profession:
            self._load_table(profession)

    # ── Callbacks de UI ───────────────────────────────────────────────────────

    def _start(self, target: str, limit, mode: str):
        self._stop_flag[0] = False
        self.root.after(0, self.ui.set_busy, True)
        self.root.after(0, self.ui.clear_log)

        if mode == "profesion":
            t = threading.Thread(
                target=self._run_profession, args=(target, limit), daemon=True
            )
        else:
            t = threading.Thread(
                target=self._run_single, args=(target,), daemon=True
            )
        t.start()

    def _stop(self):
        self._stop_flag[0] = True
        self.root.after(0, self.ui.set_status, "Deteniendo…", C["yellow"])
        # Desbloquear cualquier prompt activo
        self.root.after(0, self.ui.hide_prompt)

    def _export(self, profession: str):
        t = threading.Thread(target=self._run_export, args=(profession,), daemon=True)
        t.start()

    def _calibrate(self):
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
        self.ui.log("[OK] Calibración guardada.", "ok")

    # ── Workers ───────────────────────────────────────────────────────────────

    def _run_profession(self, profession: str, limit):
        import time as _time

        def _on_item_done():
            now = _time.monotonic()
            if now - self._last_refresh >= 2.0:
                self._last_refresh = now
                self.root.after(0, self._load_table, profession)

        try:
            self.root.after(0, self.ui.set_status, f"Actualizando {profession}…", C["accent"])
            update_profession(
                profession, limit, self._stop_flag,
                on_confirm=self._ask_confirm,
                manual_price_fn=self._ask_manual_price,
                on_item_done=_on_item_done,
            )
            self.root.after(0, self._load_table, profession)
        except Exception as e:
            self.root.after(0, self.ui.log, f"[ERROR] {e}", "error")
        finally:
            self.root.after(0, self._on_done)

    def _run_single(self, recipe_name: str):
        try:
            self.root.after(0, self.ui.set_status, f"Actualizando '{recipe_name}'…", C["accent"])
            _, rf = find_recipe(recipe_name)
            profession = profession_from_file(rf) if rf else ""
            update_single_recipe(
                recipe_name, self._stop_flag,
                on_confirm=self._ask_confirm,
                manual_price_fn=self._ask_manual_price,
            )
            if profession:
                self.root.after(0, self._load_table, profession)
        except Exception as e:
            self.root.after(0, self.ui.log, f"[ERROR] {e}", "error")
        finally:
            self.root.after(0, self._on_done)

    def _run_export(self, profession: str):
        try:
            self.root.after(0, self.ui.set_status, "Exportando…", C["accent"])
            export_profession(profession)
            self.root.after(0, self.ui.log, "[DONE] Exportado a Google Sheets.", "done")
        except Exception as e:
            self.root.after(0, self.ui.log, f"[ERROR] {e}", "error")
        finally:
            self.root.after(0, self.ui.set_status, "Listo", C["dim"])

    def _on_done(self):
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
        ev.wait()
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

    def _load_table(self, profession: str, tolerance: float = None):
        recipe_file = find_recipe_file(profession)
        if not recipe_file:
            return
        try:
            with open(recipe_file, encoding="utf-8") as f:
                recipes = json.load(f)
        except Exception:
            return

        tol = (tolerance if tolerance is not None else self.ui.tolerance()) / 100

        raw_market_prices, ing_last_updated = load_raw_market_prices()

        pack_prices   = load_all_pack_prices()
        craftable_map = load_all_craftable_recipes()

        rows = build_table_rows(
            recipes, pack_prices, craftable_map,
            raw_market_prices, ing_last_updated, tol,
        )
        self.ui.refresh_table(rows)

    def restore_io(self):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app  = CraftingApp(root)
    try:
        root.mainloop()
    finally:
        app.restore_io()


if __name__ == "__main__":
    main()
