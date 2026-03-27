"""
Gestión de recetas: carga, precios de venta y expansión de subrecetas.
"""

import json
import os

from config.config import (
    CACHE_SECONDS,
    DATA_DIR,
    SIZES,
    _parse_price,
)
from utils.loaders import _load_omitted_categories, _load_omitted_recipes, find_recipe_file, get_recipe_files
from utils.market import _now_iso, filter_lot_prices
from shared.market.search_item_prices import search_item, read_prices
from datetime import datetime, timezone


# ── Carga de recetas ──────────────────────────────────────────────────────────

def load_all_craftable_recipes() -> dict[str, dict]:
    """Devuelve {result_name: recipe_dict} para todas las recetas de todas las profesiones."""
    craftable = {}
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                craftable[r["result"]] = r
    return craftable


def all_recipe_results() -> set[str]:
    results = set()
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                results.add(r["result"])
    return results


def build_result_file_map() -> dict[str, str]:
    """Devuelve {result_name: recipe_file_path} para todas las recetas."""
    result_map = {}
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                result_map[r["result"]] = path
    return result_map


def find_recipe(result_name: str) -> tuple[dict | None, str | None]:
    """Devuelve (recipe_dict, recipe_file_path) para el resultado dado."""
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("result") == result_name:
                    return r, path
    return None, None


def profession_from_file(path: str) -> str:
    fname = os.path.basename(path)
    return fname[len("recipes_"):-len(".json")]


def sub_recipe_files(sub_results: set[str], main_recipe_file: str) -> list[str]:
    """Archivos de receta que contienen subrecetas usadas como ingredientes, excluyendo el principal."""
    main_abs = os.path.abspath(main_recipe_file)
    files = []
    for path in get_recipe_files():
        if os.path.abspath(path) == main_abs:
            continue
        with open(path, encoding="utf-8") as f:
            if any(r.get("result") in sub_results for r in json.load(f)):
                files.append(path)
    return files


# ── Expansión de subrecetas ───────────────────────────────────────────────────

def _is_selling_fresh(recipe: dict) -> bool:
    ts = recipe.get("selling_last_updated")
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return age < CACHE_SECONDS


def expand_sub_ingredients(ingredients: set[str], craftable: dict[str, dict]) -> set[str]:
    """Añade recursivamente los ingredientes de subrecetas que no están actualizadas."""
    expanded = set(ingredients)
    queue    = list(ingredients)
    visited  = set()

    while queue:
        name = queue.pop()
        if name in visited:
            continue
        visited.add(name)
        recipe = craftable.get(name)
        if recipe and not _is_selling_fresh(recipe):
            for ing in recipe.get("ingredients", []):
                sub = ing["name"]
                expanded.add(sub)
                if sub not in visited:
                    queue.append(sub)

    return expanded


# ── Precios de venta ──────────────────────────────────────────────────────────

def _sanitize_unit_prices(prices: list[int]) -> list[int]:
    """Si hay 3+ precios no-cero y alguno supera 1.5x el mínimo, reemplaza outliers por el promedio."""
    non_zero = [(i, p) for i, p in enumerate(prices) if p > 0]
    if len(non_zero) < 3:
        return prices

    min_price = min(p for _, p in non_zero)
    threshold = 1.5 * min_price

    normal   = [(i, p) for i, p in non_zero if p <= threshold]
    outliers = [(i, p) for i, p in non_zero if p > threshold]

    if not outliers or not normal:
        return prices

    avg_normal = round(sum(p for _, p in normal) / len(normal))
    result = prices[:]
    for i, _ in outliers:
        result[i] = avg_normal
    return result


def save_selling_price(recipe_file: str, name: str, prices: dict):
    """Guarda los precios de venta de un resultado de receta en su archivo JSON."""
    x1    = _parse_price(prices, "1")
    x10   = _parse_price(prices, "10")
    x100  = _parse_price(prices, "100")
    x1000 = _parse_price(prices, "1000")

    with open(recipe_file, encoding="utf-8") as f:
        data = json.load(f)

    u1    = x1
    u10   = round(x10   / 10)   if x10   > 0 else u1
    u100  = round(x100  / 100)  if x100  > 0 else u10
    u1000 = round(x1000 / 1000) if x1000 > 0 else u100

    u1, u10, u100, u1000 = _sanitize_unit_prices([u1, u10, u100, u1000])

    filtered, exceeded = filter_lot_prices({"x1": u1, "x10": u10, "x100": u100, "x1000": u1000})

    for recipe in data:
        if recipe.get("result") == name:
            recipe["unit_selling_price_x1"]    = filtered["x1"]
            recipe["unit_selling_price_x10"]   = filtered["x10"]
            recipe["unit_selling_price_x100"]  = filtered["x100"]
            recipe["unit_selling_price_x1000"] = filtered["x1000"]
            for size in exceeded:
                recipe[f"unit_crafting_cost_{size}"] = 0
            recipe.pop("selling_last_updated", None)

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name} → x1={x1}  x10={x10}  x100={x100}  x1000={x1000}")


def search_and_save_selling(recipe_file: str, name: str, stop_flag: list = None) -> dict:
    """Busca el precio de venta de un item y lo guarda. Omite si está en exclusiones o es fresco."""
    if name in _load_omitted_recipes():
        print(f"[SKIP] {name} — en lista de excepciones")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}

    recipe, _ = find_recipe(name)
    if recipe and recipe.get("category") in _load_omitted_categories():
        print(f"[SKIP] {name} — categoría omitida ({recipe.get('category')})")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}
    if recipe and _is_selling_fresh(recipe):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        return {
            "unit_price_x1":    recipe.get("unit_selling_price_x1", 0),
            "unit_price_x10":   recipe.get("unit_selling_price_x10", 0),
            "unit_price_x100":  recipe.get("unit_selling_price_x100", 0),
            "unit_price_x1000": recipe.get("unit_selling_price_x1000", 0),
            "_skipped":         True,
        }
    search_item(name)
    prices = read_prices(name, stop_flag=stop_flag)
    save_selling_price(recipe_file, name, prices)
    return prices
