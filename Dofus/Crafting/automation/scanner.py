"""
Búsqueda de precios en el mercadillo, agrupada por tipo.
"""

import time

import keyboard

from config.config import DELAY_BETWEEN_ITEMS, _load_manual_price_items
from core.prices import _ingredient_is_fresh, save_ingredient_price
from core.recipes import search_and_save_selling
from shared.market.search_item_prices import search_item, read_prices


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

def search_and_save_ingredient(name: str, markets: dict, item_lookup: dict) -> dict:
    if _ingredient_is_fresh(name, markets, item_lookup):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        market_name = item_lookup.get(name)
        for items in markets[market_name]["data"].values():
            for item in items:
                if item["name"] == name:
                    return {**{f"unit_price_x{s}": item.get(f"unit_price_x{s}", 0) for s in ("1", "10", "100", "1000")}, "_skipped": True}
    search_item(name)
    prices = read_prices(name)
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
) -> tuple[list[str], list[str]]:
    """Busca precios de results e ingredients en el mercadillo indicado.
    stop_flag es una lista de un bool mutable [False] para permitir detención.
    Devuelve (missing_results, missing_ingredients)."""

    def is_stopped() -> bool:
        return stop_flag is not None and stop_flag[0]

    manual_items       = _load_manual_price_items()
    auto_results       = [n for n in results     if n not in manual_items]
    manual_results     = [n for n in results     if n in manual_items]
    auto_ingredients   = [n for n in ingredients if n not in manual_items]
    manual_ingredients = [n for n in ingredients if n in manual_items]

    total = len(auto_results) + len(auto_ingredients)
    missing_results     = []
    missing_ingredients = []

    if total:
        print(f"\n── {market_name} ({total} items) ──")
        input(f"  Ve al mercadillo de {market_name} y pulsa ENTER para continuar…")
        print()

    idx = 0
    for name in auto_results:
        if is_stopped():
            missing_results.extend(auto_results[idx:])
            return missing_results, missing_ingredients + manual_ingredients
        idx += 1
        print(f"[{idx}/{total}] [venta] {name} …", end=" ", flush=True)
        prices = {}
        target_file = (result_file_map or {}).get(name, recipe_file)
        try:
            prices = search_and_save_selling(target_file, name)
            if not _price_found(prices):
                missing_results.append(name)
        except Exception as e:
            print(f"ERROR — {e}")
            missing_results.append(name)
        if not prices.get("_skipped"):
            keyboard.press_and_release("esc")
            time.sleep(0.15)
        time.sleep(DELAY_BETWEEN_ITEMS)

    for name in auto_ingredients:
        if is_stopped():
            missing_ingredients.extend(auto_ingredients[idx - len(results):])
            return missing_results, missing_ingredients + manual_ingredients
        idx += 1
        print(f"[{idx}/{total}] [ingrediente] {name} …", end=" ", flush=True)
        prices = {}
        try:
            prices = search_and_save_ingredient(name, markets, item_lookup)
            if not _price_found(prices):
                missing_ingredients.append(name)
        except Exception as e:
            print(f"ERROR — {e}")
            missing_ingredients.append(name)
        if not prices.get("_skipped"):
            keyboard.press_and_release("esc")
            time.sleep(0.15)
        time.sleep(DELAY_BETWEEN_ITEMS)

    # Items con precio manual
    for name in manual_ingredients:
        if _ingredient_is_fresh(name, markets, item_lookup):
            print(f"[SKIP] {name} — actualizado hace menos de 1h")
            continue
        print(f"\n[MANUAL] {name}")
        prices = ask_manual_prices(name)
        try:
            save_ingredient_price(name, prices, markets, item_lookup)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_ingredients.append(name)

    from core.recipes import find_recipe as _find_recipe
    from core.recipes import _selling_is_fresh
    for name in manual_results:
        target_file = (result_file_map or {}).get(name, recipe_file)
        recipe_data, _ = _find_recipe(name)
        if recipe_data and _selling_is_fresh(recipe_data):
            print(f"[SKIP] {name} — actualizado hace menos de 1h")
            continue
        prices = ask_manual_selling_prices(name)
        try:
            from core.recipes import save_selling_price
            save_selling_price(target_file, name, prices)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_results.append(name)

    return missing_results, missing_ingredients
