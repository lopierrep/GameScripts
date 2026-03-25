"""
Crafting - Orquestador principal
=================================
Actualiza precios de venta e ingredientes para una profesión completa
o para una receta única, agrupa las búsquedas por mercadillo y exporta
los resultados a Google Sheets.

Uso directo (sin UI):
  python main.py alquimista
  python main.py "Tabla de fresno"   # receta única por nombre
"""

import json
import os
import sys

import keyboard

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.config import (
    DATA_DIR,
    UNKNOWN_KEY,
    find_recipe_file,
)
from core.prices import (
    build_item_lookup,
    ensure_catalogued,
    get_market_for_category,
    load_markets,
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

stop_requested = False


def _on_key_press(event):
    global stop_requested
    if event.name == "y":
        stop_requested = True


# ── Actualizar profesión completa ─────────────────────────────────────────────

def update_profession(profession: str, limit: int | None = None):
    global stop_requested
    stop_requested = False

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
    keyboard.on_press(_on_key_press)

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    craftable_results = all_recipe_results()
    ensure_catalogued(all_ingredients, markets, item_lookup, craftable_results)

    # Determinar mercadillo de cada resultado
    result_market: dict[str, str] = {}
    for r in recipes:
        name        = r["result"]
        category    = r.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            result_market[name] = market_name
        else:
            print(f"  ? {name} → {category} [sin mercadillo, ignorado]")

    # Agrupar por mercadillo
    market_groups: dict[str, dict] = {}
    for name in all_results:
        if name in result_market:
            m = result_market[name]
            market_groups.setdefault(m, {"results": [], "ingredients": []})
            market_groups[m]["results"].append(name)
    for name in all_ingredients:
        if name in item_lookup:
            m = item_lookup[name]
            market_groups.setdefault(m, {"results": [], "ingredients": []})
            if name not in market_groups[m]["ingredients"]:
                market_groups[m]["ingredients"].append(name)

    # Añadir subrecetas al batch de venta
    sub_results = all_ingredients & set(craftable.keys())
    for sub_name in sub_results:
        sub_recipe  = craftable.get(sub_name, {})
        category    = sub_recipe.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            market_groups.setdefault(market_name, {"results": [], "ingredients": []})
            if sub_name not in market_groups[market_name]["results"]:
                market_groups[market_name]["results"].append(sub_name)

    result_file_map   = build_result_file_map()
    stop_flag         = [False]
    all_missing_results: list[str] = []

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
            )
            all_missing_results.extend(r for r in miss_r if r in all_results)
            if (miss_r or miss_i) and not stop_flag[0]:
                total = len(miss_r) + len(miss_i)
                print(f"\n[AVISO] {total} items sin precio en {market_name} (no se reintentará).")
            if stop_flag[0]:
                break

    # Calcular costos de subrecetas primero
    if sub_results:
        for sub_file in sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            save_crafting_costs(sub_file)

    # Calcular costos de crafteo
    with open(recipe_file, encoding="utf-8") as f:
        recipes = json.load(f)
    if limit is not None:
        recipes = recipes[:limit]

    still_missing = save_crafting_costs(recipe_file, recipes)

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


# ── Actualizar receta única ───────────────────────────────────────────────────

def update_single_recipe(result_name: str):
    global stop_requested
    stop_requested = False

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
    keyboard.on_press(_on_key_press)

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    craftable_results = all_recipe_results()
    ensure_catalogued(all_ingredients, markets, item_lookup, craftable_results)

    # Agrupar resultado e ingredientes por mercadillo
    result_market = get_market_for_category(recipe.get("category", UNKNOWN_KEY), markets)
    market_groups: dict[str, dict] = {}

    if result_market:
        market_groups.setdefault(result_market, {"results": [], "ingredients": []})
        market_groups[result_market]["results"].append(result_name)
    else:
        print(f"  ? {result_name} → {recipe.get('category')} [sin mercadillo, ignorado]")

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

    result_file_map = build_result_file_map()
    stop_flag       = [False]

    for market_name, group in market_groups.items():
        if stop_flag[0]:
            break
        miss_r, miss_i = search_market_batch(
            market_name,
            sorted(group["results"]),
            sorted(group["ingredients"]),
            recipe_file, markets, item_lookup,
            result_file_map, stop_flag,
        )

    # Calcular costos de subrecetas primero
    if sub_results:
        for sub_file in sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            save_crafting_costs(sub_file)

    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)
    target = [r for r in all_recipes if r.get("result") == result_name]
    still_missing = save_crafting_costs(recipe_file, target)

    print(f"\n[DONE] '{result_name}' actualizado.")
    if still_missing:
        print(f"[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")

    print("\nExportando a Google Sheets …")
    export_profession(profession)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(DATA_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        print("Uso: python main.py <profesion> [limite]")
        print(f"  Profesiones: {', '.join(available)}")
        return

    arg   = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # Si coincide con un archivo de recetas → actualizar profesión
    if find_recipe_file(arg):
        update_profession(arg, limit)
    else:
        # Intentar como nombre de receta única
        update_single_recipe(arg)


if __name__ == "__main__":
    main()
