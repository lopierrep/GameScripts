"""
Búsqueda de precios en el mercadillo, agrupada por tipo.
"""

import time

import keyboard

from config.config import DELAY_BETWEEN_ITEMS
from utils.loaders import _load_manual_price_items
from utils.market import _is_selling_fresh
from core.prices import _ingredient_is_fresh, save_ingredient_price
from core.recipes import find_recipe as _find_recipe, save_selling_price, search_and_save_selling
from shared.market.search_item_prices import search_item, read_prices
from shared.market.scanner import MarketScanner


# ── Helpers de precio manual ──────────────────────────────────────────────────

def _price_found(prices: dict) -> bool:
    return any(v not in ("N/A", "", "0", 0) for k, v in prices.items() if k != "_skipped")


def ask_manual_prices(name: str) -> dict:
    """Pide al usuario los precios unitarios de un item manualmente."""
    print(f"\n[MANUAL] Ingresa los precios unitarios de '{name}':")
    def _read(label: str) -> int:
        while True:
            val = input(f"  {label}: ").strip()
            if val.isdigit():
                return int(val)
            print("  Ingresa un número entero.")
    return {
        "unit_price_x1":    _read("Precio x1"),
        "unit_price_x10":   _read("Precio unitario x10 (precio_lote / 10)"),
        "unit_price_x100":  _read("Precio unitario x100 (precio_lote / 100)"),
        "unit_price_x1000": _read("Precio unitario x1000 (precio_lote / 1000)"),
    }


def ask_manual_selling_prices(name: str) -> dict:
    """Pide al usuario los precios de venta de lote de un item manualmente."""
    print(f"\n[MANUAL VENTA] Ingresa los precios de lote de '{name}':")
    def _read(label: str) -> int:
        while True:
            val = input(f"  {label}: ").strip()
            if val.isdigit():
                return int(val)
            print("  Ingresa un número entero.")
    return {
        "unit_price_x1":    _read("Precio lote x1"),
        "unit_price_x10":   _read("Precio lote x10"),
        "unit_price_x100":  _read("Precio lote x100"),
        "unit_price_x1000": _read("Precio lote x1000"),
    }


# ── Búsqueda de ingredientes ──────────────────────────────────────────────────

def search_and_save_ingredient(name: str, markets: dict, item_lookup: dict, stop_flag: list = None) -> dict:
    if _ingredient_is_fresh(name, markets, item_lookup):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        market_name, category_name = item_lookup[name]
        pd = markets[market_name]["data"][category_name][name]
        return {**{f"unit_price_x{s}": pd.get(f"x{s}", 0) for s in ("1", "10", "100", "1000")}, "_skipped": True}
    search_item(name)
    prices = read_prices(name, stop_flag=stop_flag)
    save_ingredient_price(name, prices, markets, item_lookup)
    return prices


# ── Búsqueda por lote de mercadillo ──────────────────────────────────────────

def search_market_batch(
    market_name: str,
    results: list[str],
    ingredients: list[str],
    recipe_file: str,
    markets: dict,
    item_lookup: dict,
    result_file_map: dict[str, str] | None = None,
    stop_flag: list[bool] | None = None,
    on_confirm=None,
    manual_price_fn=None,
    on_item_done=None,
) -> tuple[list[str], list[str]]:
    """Busca precios de results e ingredients en el mercadillo indicado.
    stop_flag  : lista de un bool mutable [False] para detención.
    on_confirm : fn(market_name) — bloquea hasta que el usuario confirme estar en el mercadillo.
                 Si es None usa input() como fallback.
    manual_price_fn : fn(name, is_selling) -> dict|None — precios manuales.
                      Si es None usa input() como fallback.
    Devuelve (missing_results, missing_ingredients)."""

    manual_items       = _load_manual_price_items()
    auto_results       = [n for n in results     if n not in manual_items]
    manual_results     = [n for n in results     if n in manual_items]
    auto_ingredients   = [n for n in ingredients if n not in manual_items]
    manual_ingredients = [n for n in ingredients if n in manual_items]

    missing_results     = []
    missing_ingredients = []

    auto_items = auto_results + auto_ingredients

    if auto_items:
        is_stopped   = lambda: bool(stop_flag and stop_flag[0])
        results_set  = set(auto_results)

        def _process(name: str) -> dict:
            if name in results_set:
                target_file = (result_file_map or {}).get(name, recipe_file)
                result = search_and_save_selling(target_file, name, stop_flag=stop_flag)
            else:
                result = search_and_save_ingredient(name, markets, item_lookup, stop_flag=stop_flag)
            if on_item_done:
                on_item_done()
            return result

        def _press_esc():
            keyboard.press_and_release("esc")
            time.sleep(0.15)

        def _market_switch(name: str, n: int) -> bool:
            print(f"\n── {name} ({n} items) ──")
            if on_confirm:
                on_confirm(name)
            else:
                input(f"  Ve al mercadillo de {name} y pulsa ENTER para continuar…")
            print()
            return True

        scanner = MarketScanner(press_esc=_press_esc, delay=DELAY_BETWEEN_ITEMS, countdown=0)
        scan_results = scanner.scan(
            items_by_market  = {market_name: auto_items},
            is_stopped       = is_stopped,
            on_progress      = print,
            on_market_switch = _market_switch,
            process_item     = _process,
        )

        for name in auto_results:
            if name not in scan_results or not _price_found(scan_results[name]):
                missing_results.append(name)
        for name in auto_ingredients:
            if name not in scan_results or not _price_found(scan_results[name]):
                missing_ingredients.append(name)

    # Items con precio manual
    for name in manual_ingredients:
        if _ingredient_is_fresh(name, markets, item_lookup):
            print(f"[SKIP] {name} — actualizado hace menos de 1h")
            continue
        print(f"\n[MANUAL] {name}")
        if manual_price_fn:
            prices = manual_price_fn(name, False)
            if prices is None:
                missing_ingredients.append(name)
                continue
        else:
            prices = ask_manual_prices(name)
        try:
            save_ingredient_price(name, prices, markets, item_lookup)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_ingredients.append(name)

    for name in manual_results:
        target_file = (result_file_map or {}).get(name, recipe_file)
        recipe_data, _ = _find_recipe(name)
        if recipe_data and _is_selling_fresh(recipe_data):
            print(f"[SKIP] {name} — actualizado hace menos de 1h")
            continue
        if manual_price_fn:
            prices = manual_price_fn(name, True)
            if prices is None:
                missing_results.append(name)
                continue
        else:
            prices = ask_manual_selling_prices(name)
        try:
            save_selling_price(target_file, name, prices)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_results.append(name)

    return missing_results, missing_ingredients
