"""
Cálculo de costos de crafteo compartido entre proyectos.
"""

import json
import os
from pathlib import Path

from shared.market.common import SIZES
from shared.market.prices import LOT_NUMS, cheapest_unit_price, now_iso

_SHARED    = Path(__file__).resolve().parent.parent          # shared/
_DATA_DIR  = str(_SHARED / "data")
_PRICES_FILE = str(_SHARED / "data" / "materials_prices.json")


# ── Archivos de recetas ──────────────────────────────────────────────────────

def get_recipe_files() -> list[str]:
    """Devuelve las rutas absolutas de todos los archivos recipes_*.json en shared/data/."""
    if not os.path.isdir(_DATA_DIR):
        return []
    return [
        os.path.join(_DATA_DIR, f)
        for f in sorted(os.listdir(_DATA_DIR))
        if f.startswith("recipes_") and f.endswith(".json")
    ]


# ── Precios de packs ─────────────────────────────────────────────────────────

def load_all_pack_prices() -> dict[str, dict]:
    """Devuelve {nombre: {x1, x10, x100, x1000}} con precio UNITARIO por pack.

    Combina precios de materials_prices.json con min(crafting_cost, selling_price)
    de todas las recetas."""
    pack_prices: dict[str, dict] = {}

    # Precios de todos los mercadillos
    if os.path.exists(_PRICES_FILE):
        with open(_PRICES_FILE, encoding="utf-8") as f:
            all_markets_data = json.load(f)
    else:
        all_markets_data = {}
    for data in all_markets_data.values():
        for category in data.values():
            for name, pd in category.items():
                if isinstance(pd, dict):
                    pack_prices[name] = {size: pd.get(size, 0) for size in SIZES}

    # Craftables usados como ingredientes: min(crafting_cost, selling_price)
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for recipe in json.load(f):
                name = recipe.get("result", "").strip()
                if not name:
                    continue
                costs = {size: recipe.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}
                sells = {size: recipe.get(f"unit_selling_price_{size}", 0) for size in SIZES}
                merged = {}
                for size in SIZES:
                    c, s = costs.get(size, 0), sells.get(size, 0)
                    if c > 0 and s > 0:
                        merged[size] = min(c, s)
                    else:
                        merged[size] = c or s
                if any(v > 0 for v in merged.values()):
                    pack_prices[name] = merged

    return pack_prices


# ── Cálculo de costos de crafteo ─────────────────────────────────────────────

def calculate_crafting_costs(
    recipes:     list,
    pack_prices: dict,
    *,
    crafted_costs: dict | None = None,
    exceptions:    set | None = None,
) -> tuple[list, set]:
    """
    Calcula unit_crafting_cost_x* para cada receta.
    Devuelve (recipes_actualizadas, ingredientes_sin_precio).

    crafted_costs: {result_name: {x1: cost, ...}} para fallback de sub-recetas.
    exceptions:    set de nombres de recetas a ignorar.
    """
    if crafted_costs is None:
        crafted_costs = {
            r["result"]: {size: r.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}
            for r in recipes
            if any(r.get(f"unit_crafting_cost_{size}", 0) > 0 for size in SIZES)
        }

    still_missing: set[str] = set()
    _exceptions = exceptions or set()

    for recipe in recipes:
        if recipe.get("result") in _exceptions:
            continue

        def calc_cost(pack_size: str) -> tuple[float, bool]:
            lot_num = LOT_NUMS[pack_size]
            cost = 0.0
            known = True
            for ing in recipe.get("ingredients", []):
                ing_name  = ing["name"]
                ing_qty   = ing["quantity"]
                total_qty = ing_qty * lot_num
                ing_p = cheapest_unit_price(pack_prices.get(ing_name, {}), total_qty)
                if ing_p == 0:
                    ing_costs = crafted_costs.get(ing_name)
                    if ing_costs:
                        ing_p = cheapest_unit_price(ing_costs, total_qty)
                if ing_p == 0:
                    known = False
                    if not any(pack_prices.get(ing_name, {}).get(s, 0) > 0 for s in SIZES):
                        still_missing.add(ing_name)
                    continue
                cost += ing_p * ing_qty
            return cost, known

        for size in SIZES:
            cost, known = calc_cost(size)
            recipe[f"unit_crafting_cost_{size}"] = round(cost) if known else 0

        crafted_costs[recipe["result"]] = {
            size: recipe.get(f"unit_crafting_cost_{size}", 0) for size in SIZES
        }
        recipe["prices_updated_at"] = now_iso()

    return recipes, still_missing


def save_crafting_costs(
    recipe_file: str,
    recipes: list | None = None,
    *,
    exceptions: set | None = None,
) -> set[str]:
    """Calcula y guarda los costos de crafteo en recipe_file.
    Si recipes es un subset, solo recalcula esas y hace merge en el archivo.
    Devuelve ingredientes sin precio."""
    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    subset = recipes if recipes is not None else all_recipes

    pack_prices = load_all_pack_prices()
    updated_subset, still_missing = calculate_crafting_costs(
        subset, pack_prices, exceptions=exceptions,
    )

    if recipes is not None:
        updated_by_result = {r["result"]: r for r in updated_subset}
        for r in all_recipes:
            if r["result"] in updated_by_result:
                r.update(updated_by_result[r["result"]])
    else:
        all_recipes = updated_subset

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(all_recipes, f, ensure_ascii=False, indent=2)

    return still_missing
