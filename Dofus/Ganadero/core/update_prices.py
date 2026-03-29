"""
Actualización de precios de carburantes desde el mercado.
Escanea precios de compra vía OCR y recalcula costos de crafteo.
"""

import json
import time
from pathlib import Path

import keyboard

from shared.market.common import SIZES
from shared.market.crafting_costs import save_crafting_costs
from shared.market.item_price_scanner import scan_prices, ScanItem
from shared.market.prices import (
    build_item_lookup,
    load_materials,
)
from shared.market.search_item_prices import set_calibration

# ── Rutas ──────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent           # Ganadero/
_DOFUS = _ROOT.parent                                    # Dofus/
RECIPES_FILE     = _DOFUS / "shared" / "data" / "recipes_ganadero.json"
PRICES_FILE      = _DOFUS / "shared" / "data" / "materials_prices.json"
CALIBRATION_FILE = _DOFUS / "Crafting" / "calibration" / "calibration_data.json"

DELAY_BETWEEN_ITEMS = 0.3

MARKET_NAMES = {
    "Creatures":   "Criaturas",
    "Resources":   "Recursos",
    "Consumables": "Consumibles",
    "Equipment":   "Equipamiento",
    "Runes":       "Runas",
    "Souls":       "Almas",
}


# ── I/O recetas ────────────────────────────────────────────────────────────────

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


# ── Construcción de ScanItems ──────────────────────────────────────────────────

def _build_scan_items(recipes: list, materials: dict, lookup: dict) -> list:
    """Construye ScanItems para carburantes y sus ingredientes."""
    carburantes = [r for r in recipes if r.get("category") == "Carburante de cercados"]
    items: list = []

    # Results (carburantes de venta)
    for r in carburantes:
        has_price = any(r.get(f"unit_selling_price_{s}", 0) > 0 for s in SIZES)
        items.append(ScanItem(
            name              = r["result"],
            market            = "Creatures",
            category          = "Carburante de cercados",
            type              = "result",
            prices_updated_at = r.get("prices_updated_at"),
            has_price         = has_price,
            recipe_file       = str(RECIPES_FILE),
        ))

    # Ingredients
    seen: set = set()
    for r in carburantes:
        for ing in r.get("ingredients", []):
            name = ing["name"]
            if name in seen:
                continue
            seen.add(name)
            val = lookup.get(name)
            if not val:
                continue
            market_name, category_name = val
            entry = materials.get(market_name, {}).get(category_name, {}).get(name, {})
            has_price = any(entry.get(s, 0) > 0 for s in SIZES)
            items.append(ScanItem(
                name              = name,
                market            = market_name,
                category          = category_name,
                type              = "ingredient",
                prices_updated_at = entry.get("prices_updated_at"),
                has_price         = has_price,
            ))

    return items


# ── Recálculo de costos de crafteo ─────────────────────────────────────────────

def _recalculate_crafting_costs():
    """Recalcula unit_crafting_cost_x* para todos los carburantes."""
    all_recipes = _load_recipes()
    carburantes = [r for r in all_recipes if r.get("category") == "Carburante de cercados"]
    save_crafting_costs(RECIPES_FILE, carburantes)


# ── Orquestación principal ─────────────────────────────────────────────────────

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
    cal = _load_calibration()
    set_calibration(cal)

    recipes   = _load_recipes()
    materials = load_materials(PRICES_FILE)
    lookup    = build_item_lookup(materials)

    items = _build_scan_items(recipes, materials, lookup)

    def _press_esc():
        keyboard.press_and_release("esc")
        time.sleep(0.15)

    scan_prices(
        items            = items,
        press_esc        = _press_esc,
        is_stopped       = is_stopped,
        on_progress      = on_progress,
        on_market_switch = on_market_switch,
        delay            = DELAY_BETWEEN_ITEMS,
    )

    _recalculate_crafting_costs()
