"""
Dofus 3 - Cálculo y guardado de costos de crafteo
==================================================
Calcula unit_crafting_cost_x1/x10/x100/x1000 para cada receta de un archivo
usando los precios de recursos e ingredientes craftables.

Uso:
    python save_recipe_prices.py alquimista
"""

import json
import os
import sys
from datetime import datetime, timezone

from .common import ROOT_DIR, SIZES, _load_omitted_items, find_recipe_file as _find_recipe_file_by_profession

OTHER_JSON  = os.path.join(ROOT_DIR, "other_ingredients_prices.json")
RECIPES_DIR = os.path.join(ROOT_DIR, "Recipes")


# ── Carga de precios ───────────────────────────────────────────────────────────

def _load_file(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_pack_prices() -> dict[str, dict]:
    """Devuelve {nombre: {x1, x10, x100, x1000}} con precio UNITARIO por pack."""
    pack_prices = {}

    # Precios de todos los mercadillos
    markets_dir = os.path.join(ROOT_DIR, "Markets")
    market_files = []
    if os.path.isdir(markets_dir):
        for folder in os.listdir(markets_dir):
            fp = os.path.join(markets_dir, folder, "materials_prices.json")
            if os.path.exists(fp):
                market_files.append(fp)
    for data in [_load_file(fp) for fp in market_files] + [_load_file(OTHER_JSON)]:
        for items in data.values():
            for item in items:
                name = item["name"].strip()
                pack_prices[name] = {
                    size: item.get(f"unit_price_{size}", 0)
                    for size in SIZES
                }

    # Craftables usados como ingredientes: min(crafting_cost, selling_price)
    for fname in os.listdir(RECIPES_DIR):
        if not fname.startswith("recipes_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(RECIPES_DIR, fname), encoding="utf-8") as f:
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


# ── Cálculo de costo ───────────────────────────────────────────────────────────

def best_unit_price(prices: dict, pack_size: str) -> float:
    """Precio unitario mínimo entre el lote dado y sus adyacentes."""
    idx = SIZES.index(pack_size)
    candidates = SIZES[max(0, idx - 1):idx + 2]
    values = [prices[s] for s in candidates if prices.get(s, 0) > 0]
    return min(values) if values else 0


def calculate_crafting_costs(recipes: list, pack_prices: dict) -> tuple[list, set]:
    """
    Calcula unit_crafting_cost_x* para cada receta.
    Devuelve (recipes_actualizadas, ingredientes_sin_precio).
    """
    crafted_costs: dict[str, dict] = {
        r["result"]: {size: r.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}
        for r in recipes
        if any(r.get(f"unit_crafting_cost_{size}", 0) > 0 for size in SIZES)
    }

    still_missing: set[str] = set()
    exceptions = _load_omitted_items()

    for recipe in recipes:
        if recipe.get("result") in exceptions:
            continue
        def calc_cost(pack_size: str) -> tuple[float, bool]:
            cost = 0.0
            known = True
            for ing in recipe.get("ingredients", []):
                ing_name = ing["name"]
                ing_qty  = ing["quantity"]
                ing_p = best_unit_price(pack_prices.get(ing_name, {}), pack_size)
                if ing_p == 0:
                    ing_costs = crafted_costs.get(ing_name)
                    if ing_costs:
                        ing_p = best_unit_price(ing_costs, pack_size)
                if ing_p == 0:
                    known = False
                    still_missing.add(ing_name)
                    continue
                cost += ing_p * ing_qty
            return cost, known

        for size in SIZES:
            cost, known = calc_cost(size)
            recipe[f"unit_crafting_cost_{size}"] = round(cost) if known else 0

        crafted_costs[recipe["result"]] = {size: recipe.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}

        # Timestamp solo cuando hay precio de venta Y costo de crafteo
        has_sell  = any(recipe.get(f"unit_selling_price_{s}", 0) > 0 for s in SIZES)
        has_craft = any(recipe.get(f"unit_crafting_cost_{s}", 0) > 0 for s in SIZES)
        if has_sell and has_craft:
            recipe["selling_last_updated"] = datetime.now(timezone.utc).isoformat()

    return recipes, still_missing


def save_crafting_costs(recipe_file: str, recipes: list | None = None) -> set[str]:
    """Calcula y guarda los costos de crafteo en recipe_file. Devuelve ingredientes sin precio."""
    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    subset = recipes if recipes is not None else all_recipes

    pack_prices = load_all_pack_prices()
    updated_subset, still_missing = calculate_crafting_costs(subset, pack_prices)

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


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        available = sorted(f[len("recipes_"):-len(".json")] for f in os.listdir(RECIPES_DIR) if f.startswith("recipes_") and f.endswith(".json"))
        print("Uso: python save_recipe_prices.py <profesion>")
        print(f"  Profesiones disponibles: {', '.join(available)}")
        sys.exit(1)

    recipe_file = _find_recipe_file_by_profession(sys.argv[1], RECIPES_DIR)
    if not recipe_file:
        print(f"[ERROR] No se encontró receta para '{sys.argv[1]}'.")
        sys.exit(1)

    missing = save_crafting_costs(recipe_file)
    print(f"[DONE] {os.path.basename(recipe_file)} actualizado.")
    if missing:
        print(f"\n[AVISO] {len(missing)} ingredientes sin precio:")
        for name in sorted(missing):
            print(f"  - {name}")