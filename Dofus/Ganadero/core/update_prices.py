"""
Actualización de precios de carburantes desde el mercado.
Escanea precios de compra vía OCR y recalcula costos de crafteo.
"""

import json
import time
from pathlib import Path

import keyboard

from shared.market.common import SIZES
from shared.market.prices import (
    LOT_NUMS,
    build_item_lookup,
    cheapest_unit_price,
    is_price_fresh,
    load_materials,
    now_iso,
    save_ingredient_price,
    save_selling_price,
)
from shared.market.scanner import MarketScanner
from shared.market.search_item_prices import (
    read_prices,
    search_item,
    set_calibration,
)

# ── Rutas ────────────────────��────────────────────────────────���───────────────
_ROOT = Path(__file__).resolve().parent.parent           # Ganadero/
_DOFUS = _ROOT.parent                                    # Dofus/
RECIPES_FILE     = _DOFUS / "shared" / "data" / "recipes_ganadero.json"
PRICES_FILE      = _DOFUS / "shared" / "data" / "materials_prices.json"
CALIBRATION_FILE = _DOFUS / "Crafting" / "calibration" / "calibration_data.json"

DELAY_BETWEEN_ITEMS = 0.3


# ── I/O recetas ──────���───────────────────────────────────────────────────────

def _load_recipes() -> list:
    with open(RECIPES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_recipes(recipes: list):
    with open(RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)


def _load_calibration() -> dict:
    if not CALIBRATION_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró calibración en {CALIBRATION_FILE}.\n"
            "Calibra el mercadillo desde Crafting primero."
        )
    with open(CALIBRATION_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (tuple(v) if isinstance(v, list) else v) for k, v in raw.items()}


# ── Frescura (wrappers sobre shared) ───��─────────────────────────────────────

def _is_selling_fresh(recipe: dict) -> bool:
    return is_price_fresh(recipe.get("prices_updated_at"))


def _is_ingredient_fresh(name: str, materials: dict, lookup: dict) -> bool:
    val = lookup.get(name)
    if not val:
        return False
    market_name, category_name = val
    entry = materials.get(market_name, {}).get(category_name, {}).get(name, {})
    return is_price_fresh(entry.get("prices_updated_at"))


# ── Agrupación por mercado ────────���──────────────────────────────────────────

def _collect_items_to_scan(
    recipes: list, materials: dict, lookup: dict,
) -> tuple[dict[str, list[str]], set[str]]:
    """
    Agrupa ítems por mercado. Devuelve (items_by_market, carburante_names).
    Omite ítems frescos (actualizados hace menos de 2h).
    """
    carburantes = [r for r in recipes if r.get("category") == "Carburante de cercados"]
    carburante_names = {r["result"] for r in carburantes}

    creatures_items = [
        r["result"] for r in carburantes if not _is_selling_fresh(r)
    ]

    ingredient_by_market: dict[str, list[str]] = {}
    seen = set()
    for r in carburantes:
        for ing in r.get("ingredients", []):
            ing_name = ing["name"]
            if ing_name in seen:
                continue
            seen.add(ing_name)
            if _is_ingredient_fresh(ing_name, materials, lookup):
                continue
            val = lookup.get(ing_name)
            if not val:
                continue
            ingredient_by_market.setdefault(val[0], []).append(ing_name)

    items_by_market: dict[str, list[str]] = {}
    if creatures_items:
        items_by_market["Creatures"] = sorted(creatures_items)
    for market in sorted(ingredient_by_market):
        items_by_market.setdefault(market, []).extend(sorted(ingredient_by_market[market]))

    return items_by_market, carburante_names


# ── Recálculo de costos de crafteo ──────��────────────────────────────────────

def _recalculate_crafting_costs():
    """Recalcula unit_crafting_cost_x* para todos los carburantes."""
    all_recipes = _load_recipes()
    materials = load_materials(PRICES_FILE)

    pack_prices: dict[str, dict] = {}
    for market_data in materials.values():
        for category in market_data.values():
            for name, pd in category.items():
                if isinstance(pd, dict):
                    pack_prices[name] = {s: pd.get(s, 0) for s in SIZES}

    for recipe in all_recipes:
        if recipe.get("category") != "Carburante de cercados":
            continue
        ingredients = recipe.get("ingredients", [])
        if not ingredients:
            continue

        for size in SIZES:
            lot_num = LOT_NUMS[size]
            cost = 0.0
            known = True
            for ing in ingredients:
                total_qty = ing["quantity"] * lot_num
                unit_p = cheapest_unit_price(
                    pack_prices.get(ing["name"], {}), total_qty,
                )
                if unit_p == 0:
                    known = False
                    break
                cost += unit_p * ing["quantity"]
            recipe[f"unit_crafting_cost_{size}"] = round(cost) if known else 0

        recipe.pop("prices_updated_at", None)
        recipe["prices_updated_at"] = now_iso()

    _save_recipes(all_recipes)


# ��─ Orquestación principal ───────────────────────────────────────────────────

MARKET_NAMES = {
    "Creatures":   "Criaturas",
    "Resources":   "Recursos",
    "Consumables": "Consumibles",
    "Equipment":   "Equipamiento",
    "Runes":       "Runas",
    "Souls":       "Almas",
}


def run_update(
    is_stopped:       callable,
    on_progress:      callable,
    on_market_switch: callable,
) -> dict:
    """
    Actualiza precios de carburantes desde el mercado.

    Args:
        is_stopped:       fn() → bool — True para cancelar
        on_progress:      fn(msg) — actualizar progreso en UI
        on_market_switch: fn(market_name, n_items) → bool — False cancela

    Returns:
        {"scanned": int, "skipped": int}
    """
    on_progress("Cargando calibración��")
    cal = _load_calibration()
    set_calibration(cal)

    on_progress("Cargando datos…")
    recipes = _load_recipes()
    materials = load_materials(PRICES_FILE)
    lookup = build_item_lookup(materials)

    items_by_market, carburante_names = _collect_items_to_scan(
        recipes, materials, lookup,
    )

    if not items_by_market:
        on_progress("Todos los precios están actualizados (< 2h).")
        return {"scanned": 0, "skipped": 0}

    total = sum(len(v) for v in items_by_market.values())
    on_progress(f"{total} ítems por escanear…")

    def process_item(name: str) -> dict:
        search_item(name)
        prices = read_prices(name, stop_flag=is_stopped)
        if name in carburante_names:
            save_selling_price(RECIPES_FILE, name, prices)
        else:
            save_ingredient_price(name, prices, materials, lookup, PRICES_FILE)
        return prices

    def _press_esc():
        keyboard.press_and_release("esc")
        time.sleep(0.15)

    scanner = MarketScanner(
        press_esc=_press_esc, delay=DELAY_BETWEEN_ITEMS, countdown=3,
    )
    results = scanner.scan(
        items_by_market=items_by_market,
        is_stopped=is_stopped,
        on_progress=on_progress,
        on_market_switch=on_market_switch,
        process_item=process_item,
    )

    if is_stopped():
        on_progress("Detenido. Recalculando costos con datos parciales…")
    else:
        on_progress("Recalculando costos de crafteo…")

    _recalculate_crafting_costs()

    scanned = sum(1 for r in results.values() if not r.get("_skipped"))
    skipped = sum(1 for r in results.values() if r.get("_skipped"))
    return {"scanned": scanned, "skipped": skipped}
