"""
Dofus 3 - Actualizador de precios por profesión
================================================
Recibe una profesión como argumento y actualiza selling_price y crafting_cost
en el archivo recipes_{profesion}.json correspondiente.

Agrupa los items por mercadillo y pide confirmación al usuario antes de
buscar en cada uno. Repite el proceso para los items sin precio hasta
que todos estén actualizados.

Uso:
  python update_profession_recipes.py alquimista
  python update_profession_recipes.py herrero
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import keyboard
import requests  # usado en ensure_catalogued → fetch_category

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Helpers.SearchAndSave import search_item_prices as sip
from Helpers.SearchAndSave import save_recipe_selling_prices as srsp
from Helpers.SearchAndSave import save_recipe_crafting_prices as srp
from Helpers.Exporting.export_to_sheets import export_profession
from Helpers.SearchAndSave.common import (
    CACHE_SECONDS,
    ROOT_DIR as _ROOT_DIR,
    _normalize,
    _now_iso,
    _parse_price as _parse_price_str,
    find_recipe_file as _find_recipe_file,
)

# ROOT_DIR viene de common.py y maneja correctamente el modo .exe (frozen)
BASE_DIR    = _ROOT_DIR
MARKETS_DIR = os.path.join(_ROOT_DIR, "Markets")
RECIPES_DIR = os.path.join(_ROOT_DIR, "Recipes")

DELAY_BETWEEN_ITEMS = 0.3
DOFUSDB_URL         = "https://api.dofusdb.fr"
UNKNOWN_KEY         = "Sin categoría"

stop_requested = False


def on_key_press(event):
    global stop_requested
    if event.name == "y":
        stop_requested = True


# ── Utilidades ────────────────────────────────────────────────────────────────


MANUAL_PRICE_FILE = os.path.join(BASE_DIR, "Helpers", "SearchAndSave", "manual_price_items.txt")


def _load_manual_price_items() -> set[str]:
    if not os.path.exists(MANUAL_PRICE_FILE):
        return set()
    with open(MANUAL_PRICE_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _ask_manual_prices(name: str) -> dict:
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


def _ask_manual_selling_prices(name: str) -> dict:
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


def _price_found(prices: dict) -> bool:
    return any(v not in ("N/A", "", "0", 0) for k, v in prices.items() if k != "_skipped")


# ── Mercadillos ───────────────────────────────────────────────────────────────

def load_markets() -> dict[str, dict]:
    markets = {}
    for folder in sorted(os.listdir(MARKETS_DIR)):
        folder_path = os.path.join(MARKETS_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        cat_file = os.path.join(folder_path, "categories.txt")
        if not os.path.exists(cat_file):
            continue
        with open(cat_file, encoding="utf-8") as f:
            categories = {line.strip() for line in f if line.strip()}
        data_file = os.path.join(folder_path, "materials_prices.json")
        data = {}
        if os.path.exists(data_file):
            with open(data_file, encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                data = json.loads(content)
        markets[folder] = {
            "categories": categories,
            "file": data_file,
            "data": data,
        }
    return markets


def build_item_lookup(markets: dict) -> dict[str, str]:
    """Devuelve {item_name: market_name} para todos los items en materials_prices.json."""
    lookup = {}
    for market_name, market in markets.items():
        for items in market["data"].values():
            for item in items:
                lookup[item["name"]] = market_name
    return lookup


def get_market_for_category(category: str, markets: dict) -> str | None:
    for market_name, market in markets.items():
        if category in market["categories"]:
            return market_name
    return None


def save_market_file(market: dict):
    with open(market["file"], "w", encoding="utf-8") as f:
        json.dump(dict(sorted(market["data"].items())), f, ensure_ascii=False, indent=2)


# ── dofusdb API ───────────────────────────────────────────────────────────────

def fetch_category(item_name: str) -> str:
    try:
        resp = requests.get(
            f"{DOFUSDB_URL}/items",
            params={"name.es": item_name, "$limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return UNKNOWN_KEY
        type_obj = data[0].get("type", {})
        name_obj = type_obj.get("name", {})
        return name_obj.get("es", name_obj.get("en", UNKNOWN_KEY))
    except Exception:
        return UNKNOWN_KEY


# ── Catalogación ──────────────────────────────────────────────────────────────

def _all_recipe_results() -> set[str]:
    results = set()
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            with open(os.path.join(RECIPES_DIR, fname), encoding="utf-8") as f:
                for r in json.load(f):
                    results.add(r["result"])
    return results


def _load_all_craftable_recipes() -> dict[str, dict]:
    """Devuelve {result_name: recipe_dict} para todas las recetas de todas las profesiones."""
    craftable = {}
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            with open(os.path.join(RECIPES_DIR, fname), encoding="utf-8") as f:
                for r in json.load(f):
                    craftable[r["result"]] = r
    return craftable


def _build_result_file_map() -> dict[str, str]:
    """Devuelve {result_name: recipe_file_path} para todas las recetas."""
    result_map = {}
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            path = os.path.join(RECIPES_DIR, fname)
            with open(path, encoding="utf-8") as f:
                for r in json.load(f):
                    result_map[r["result"]] = path
    return result_map


def _has_crafting_cost(recipe: dict) -> bool:
    return any(recipe.get(f"unit_crafting_cost_{s}", 0) > 0 for s in ("x1", "x10", "x100", "x1000"))


def _recipe_is_fresh(recipe: dict) -> bool:
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
        if recipe and not _recipe_is_fresh(recipe):
            for ing in recipe.get("ingredients", []):
                sub = ing["name"]
                expanded.add(sub)
                if sub not in visited:
                    queue.append(sub)

    return expanded


def find_item_in_markets(name: str, markets: dict) -> bool:
    return any(
        any(i["name"] == name for i in items)
        for market in markets.values()
        for items in market["data"].values()
    )


def ensure_catalogued(names: set[str], markets: dict, item_lookup: dict):
    """Añade a materials_prices.json los ingredientes nuevos, consultando su categoría."""
    craftable    = _all_recipe_results()
    uncatalogued = [
        name for name in names
        if name not in craftable and not find_item_in_markets(name, markets)
    ]
    if not uncatalogued:
        return

    print(f"\nConsultando categorías para {len(uncatalogued)} items nuevos…")
    for name in uncatalogued:
        category    = fetch_category(name)
        market_name = get_market_for_category(category, markets)
        if not market_name:
            print(f"  ? {name} → {category} [sin mercadillo, ignorado]")
            time.sleep(0.15)
            continue
        market = markets[market_name]
        market["data"].setdefault(category, [])
        if name not in [i["name"] for i in market["data"][category]]:
            market["data"][category].append({
                "name": name,
                "unit_price_x1": 0, "unit_price_x10": 0,
                "unit_price_x100": 0, "unit_price_x1000": 0,
            })
            market["data"][category].sort(key=lambda x: x["name"])
            item_lookup[name] = market_name
        save_market_file(market)
        print(f"  + {name} → {category} [{market_name}]")
        time.sleep(0.15)


# ── Guardado de precios de ingredientes ───────────────────────────────────────

def _ingredient_is_fresh(name: str, markets: dict, item_lookup: dict) -> bool:
    market_name = item_lookup.get(name)
    if not market_name:
        return False
    for items in markets[market_name]["data"].values():
        for item in items:
            if item["name"] == name:
                ts = item.get("last_updated")
                if not ts:
                    return False
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
                return age < CACHE_SECONDS
    return False


def save_ingredient_price(name: str, prices: dict, markets: dict, item_lookup: dict):
    market_name = item_lookup.get(name)
    if not market_name:
        return
    market = markets[market_name]
    for items in market["data"].values():
        for item in items:
            if item["name"] == name:
                p1    = _parse_price_str(prices, "1")
                p10   = round(_parse_price_str(prices, "10")   / 10)   if _parse_price_str(prices, "10")   > 0 else 0
                p100  = round(_parse_price_str(prices, "100")  / 100)  if _parse_price_str(prices, "100")  > 0 else 0
                p1000 = round(_parse_price_str(prices, "1000") / 1000) if _parse_price_str(prices, "1000") > 0 else 0
                item["unit_price_x1"]    = p1
                item["unit_price_x10"]   = p10
                item["unit_price_x100"]  = p100
                item["unit_price_x1000"] = p1000
                if any(v > 0 for v in (p1, p10, p100, p1000)):
                    item["last_updated"] = _now_iso()
                break
    save_market_file(market)
    p = prices
    print(f"[OK] x1={p.get('unit_price_x1','N/A')}  x10={p.get('unit_price_x10','N/A')}  x100={p.get('unit_price_x100','N/A')}  x1000={p.get('unit_price_x1000','N/A')}")


def search_and_save_ingredient(name: str, markets: dict, item_lookup: dict) -> dict:
    if _ingredient_is_fresh(name, markets, item_lookup):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        market_name = item_lookup.get(name)
        for items in markets[market_name]["data"].values():
            for item in items:
                if item["name"] == name:
                    return {**{f"unit_price_x{s}": item.get(f"unit_price_x{s}", 0) for s in ("1", "10", "100", "1000")}, "_skipped": True}
    sip.search_item(name)
    prices = sip.read_prices(name)
    save_ingredient_price(name, prices, markets, item_lookup)
    return prices


# ── Búsqueda por mercadillo ───────────────────────────────────────────────────

def search_market_batch(
    market_name: str,
    results: list[str],
    ingredients: list[str],
    recipe_file: str,
    markets: dict,
    item_lookup: dict,
    result_file_map: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Busca precios de results e ingredients en el mercadillo indicado.
    result_file_map permite resolver el archivo correcto para cada resultado (necesario para subrecetas).
    Devuelve (missing_results, missing_ingredients)."""
    global stop_requested

    manual_items = _load_manual_price_items()
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
        if stop_requested:
            missing_results.extend(auto_results[idx:])
            return missing_results, missing_ingredients + manual_ingredients
        idx += 1
        print(f"[{idx}/{total}] [venta] {name} …", end=" ", flush=True)
        prices = {}
        target_file = (result_file_map or {}).get(name, recipe_file)
        try:
            prices = srsp.search_and_save_selling(target_file, name)
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
        if stop_requested:
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

    # Items con precio manual — preguntar al usuario al final del mercadillo
    for name in manual_ingredients:
        if _ingredient_is_fresh(name, markets, item_lookup):
            print(f"[SKIP] {name} — actualizado hace menos de 1h")
            continue
        print(f"\n[MANUAL] {name}")
        prices = _ask_manual_prices(name)
        try:
            save_ingredient_price(name, prices, markets, item_lookup)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_ingredients.append(name)

    # Resultados con precio de venta manual
    for name in manual_results:
        target_file = (result_file_map or {}).get(name, recipe_file)
        prices = _ask_manual_selling_prices(name)
        try:
            srsp.save_selling_price(target_file, name, prices)
        except Exception as e:
            print(f"ERROR al guardar — {e}")
            missing_results.append(name)

    return missing_results, missing_ingredients


# ── Cálculo de subrecetas ─────────────────────────────────────────────────────

def _sub_recipe_files(sub_results: set[str], main_recipe_file: str) -> list[str]:
    """Archivos de receta que contienen subrecetas usadas como ingredientes, excluyendo el principal."""
    files = []
    for fname in sorted(os.listdir(RECIPES_DIR)):
        if not fname.startswith("recipes_") or not fname.endswith(".json"):
            continue
        path = os.path.join(RECIPES_DIR, fname)
        if os.path.abspath(path) == os.path.abspath(main_recipe_file):
            continue
        with open(path, encoding="utf-8") as f:
            if any(r.get("result") in sub_results for r in json.load(f)):
                files.append(path)
    return files


# ── Actualización de recetas ──────────────────────────────────────────────────

def update_profession(profession: str, limit: int | None = None):
    recipe_file = _find_recipe_file(profession, RECIPES_DIR)
    if not recipe_file:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(RECIPES_DIR)
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

    craftable       = _load_all_craftable_recipes()
    all_ingredients = expand_sub_ingredients(all_ingredients, craftable)

    sip.load_calibration()
    keyboard.on_press(on_key_press)

    markets     = load_markets()
    item_lookup = build_item_lookup(markets)

    # Catalogar ingredientes nuevos
    ensure_catalogued(all_ingredients, markets, item_lookup)

    # Determinar mercadillo de cada resultado usando la categoría del JSON de recetas
    result_market: dict[str, str] = {}
    for r in recipes:
        name        = r["result"]
        category    = r.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            result_market[name] = market_name
        else:
            print(f"  ? {name} → {category} [sin mercadillo, ignorado]")

    # Agrupar por mercadillo: {market_name: {results: [], ingredients: []}}
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

    # Buscar precio de venta de subrecetas y añadirlas al batch de búsqueda
    sub_results = all_ingredients & set(craftable.keys())
    for sub_name in sub_results:
        sub_recipe = craftable.get(sub_name, {})
        category   = sub_recipe.get("category", UNKNOWN_KEY)
        market_name = get_market_for_category(category, markets)
        if market_name:
            market_groups.setdefault(market_name, {"results": [], "ingredients": []})
            if sub_name not in market_groups[market_name]["results"]:
                market_groups[market_name]["results"].append(sub_name)

    result_file_map = _build_result_file_map()

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
                market_name,
                results,
                ingredients,
                recipe_file,
                markets,
                item_lookup,
                result_file_map,
            )
            all_missing_results.extend(r for r in miss_r if r in all_results)
            if (miss_r or miss_i) and not stop_requested:
                total = len(miss_r) + len(miss_i)
                print(f"\n[AVISO] {total} items sin precio en {market_name} (no se reintentará).")
            if stop_requested:
                break

    # Calcular costos de subrecetas primero
    if sub_results:
        for sub_file in _sub_recipe_files(sub_results, recipe_file):
            print(f"[INFO] Calculando subrecetas en {os.path.basename(sub_file)} …")
            srp.save_crafting_costs(sub_file)

    # Calcular costos de crafteo
    with open(recipe_file, encoding="utf-8") as f:
        recipes = json.load(f)
    if limit is not None:
        recipes = recipes[:limit]

    still_missing = srp.save_crafting_costs(recipe_file, recipes)

    print(f"\n[DONE] {os.path.basename(recipe_file)}: {len(recipes)} recetas actualizadas.")
    if still_missing:
        print(f"\n[AVISO] {len(still_missing)} ingredientes sin precio:")
        for name in sorted(still_missing):
            print(f"  - {name}")

    missing_file = os.path.join(RECIPES_DIR, "missing_recipes.json")
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(RECIPES_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        print("Uso: python update_profession_recipes.py <profesion> [limite]")
        print(f"  Profesiones disponibles: {', '.join(available)}")
        return

    profession = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    update_profession(profession, limit)


if __name__ == "__main__":
    main()
