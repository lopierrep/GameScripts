"""
Dofus 3 - Actualizador de una receta específica
================================================
Busca y actualiza los precios de venta e ingredientes de una única receta,
luego recalcula su costo de crafteo y exporta la profesión a Google Sheets.

Uso:
  python update_single_recipe.py "Tabla de fresno"
"""

import json
import os
import sys
import time

import keyboard

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Helpers.SearchAndSave import search_item_prices as sip
from Helpers.SearchAndSave import save_recipe_selling_prices as srsp
from Helpers.SearchAndSave import save_recipe_crafting_prices as srp
from Helpers.Exporting.export_to_sheets import export_profession
from update_profession_recipes import (
    load_markets,
    build_item_lookup,
    ensure_catalogued,
    search_and_save_ingredient,
    save_ingredient_price,
    get_market_for_category,
    _load_all_craftable_recipes,
    expand_sub_ingredients,
    _sub_recipe_files,
    _load_manual_price_items,
    _ask_manual_prices,
    _price_found,
    DELAY_BETWEEN_ITEMS,
    UNKNOWN_KEY,
    RECIPES_DIR,
)

stop_requested = False


def on_key_press(event):
    global stop_requested
    if event.name == "y":
        stop_requested = True


def find_recipe(result_name: str) -> tuple[dict | None, str | None]:
    """Devuelve (recipe_dict, recipe_file_path) para el resultado dado."""
    for fname in os.listdir(RECIPES_DIR):
        if not fname.startswith("recipes_") or not fname.endswith(".json"):
            continue
        path = os.path.join(RECIPES_DIR, fname)
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("result") == result_name:
                    return r, path
    return None, None


def profession_from_file(path: str) -> str:
    fname = os.path.basename(path)
    return fname[len("recipes_"):-len(".json")]


def run(result_name: str):
    recipe, recipe_file = find_recipe(result_name)
    if not recipe:
        print(f"[ERROR] No se encontró ninguna receta con resultado '{result_name}'.")
        return

    profession = profession_from_file(recipe_file)
    print(f"[INFO] Receta encontrada en: {os.path.basename(recipe_file)}\n")

    ingredients = {ing["name"] for ing in recipe.get("ingredients", [])}
    craftable   = _load_all_craftable_recipes()
    all_ingredients = expand_sub_ingredients(ingredients, craftable)

    sip.load_calibration()
    keyboard.on_press(on_key_press)

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    ensure_catalogued(all_ingredients, markets, item_lookup)

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

    # Añadir subrecetas al batch de búsqueda de precios de venta
    sub_results = all_ingredients & set(craftable.keys())
    for sub_name in sub_results:
        sub_recipe  = craftable.get(sub_name, {})
        category    = sub_recipe.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            market_groups.setdefault(market_name, {"results": [], "ingredients": []})
            if sub_name not in market_groups[market_name]["results"]:
                market_groups[market_name]["results"].append(sub_name)

    total_items = sum(len(g["results"]) + len(g["ingredients"]) for g in market_groups.values())
    print(f"[INFO] {total_items} items en {len(market_groups)} mercadillo(s). Pulsa Y para detener.\n")
    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)
    print("  Empezando ahora!      ")

    manual_items = _load_manual_price_items()

    for market_name, group in market_groups.items():
        if stop_requested:
            break
        results          = sorted(group["results"])
        auto_ingredients = sorted(n for n in group["ingredients"] if n not in manual_items)
        manual_ingreds   = sorted(n for n in group["ingredients"] if n in manual_items)
        total            = len(results) + len(auto_ingredients)

        if total:
            print(f"\n── {market_name} ({total} items) ──")
            input(f"  Ve al mercadillo de {market_name} y pulsa ENTER para continuar…")
            print()

        idx = 0
        for name in results:
            if stop_requested:
                break
            idx += 1
            print(f"[{idx}/{total}] [venta] {name} …", end=" ", flush=True)
            prices = {}
            try:
                _, target_file = find_recipe(name)
                prices = srsp.search_and_save_selling(target_file or recipe_file, name)
            except Exception as e:
                print(f"ERROR — {e}")
            if not prices.get("_skipped"):
                keyboard.press_and_release("esc")
                time.sleep(0.15)
            time.sleep(DELAY_BETWEEN_ITEMS)

        for name in auto_ingredients:
            if stop_requested:
                break
            idx += 1
            print(f"[{idx}/{total}] [ingrediente] {name} …", end=" ", flush=True)
            prices = {}
            try:
                prices = search_and_save_ingredient(name, markets, item_lookup)
            except Exception as e:
                print(f"ERROR — {e}")
            if not prices.get("_skipped"):
                keyboard.press_and_release("esc")
                time.sleep(0.15)
            time.sleep(DELAY_BETWEEN_ITEMS)

        for name in manual_ingreds:
            print(f"\n[MANUAL] {name}")
            prices = _ask_manual_prices(name)
            try:
                save_ingredient_price(name, prices, markets, item_lookup)
            except Exception as e:
                print(f"ERROR al guardar — {e}")

    # Calcular costos de subrecetas primero
    if sub_results:
        for sub_file in _sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            srp.save_crafting_costs(sub_file)

    # Calcular costo de crafteo de esta receta
    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)
    target = [r for r in all_recipes if r.get("result") == result_name]
    still_missing = srp.save_crafting_costs(recipe_file, target)

    print(f"\n[DONE] '{result_name}' actualizado.")
    if still_missing:
        print(f"[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")

    print("\nExportando a Google Sheets …")
    export_profession(profession)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python update_single_recipe.py <nombre_resultado>")
        print('  Ejemplo: python update_single_recipe.py "Tabla de fresno"')
        sys.exit(1)

    run(sys.argv[1])
