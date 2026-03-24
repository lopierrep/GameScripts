"""
Dofus 3 - Generador de materiales de crafteo por mercadillo
============================================================
Extrae todos los ingredientes que NO son a su vez resultado de una receta,
consulta su categoría en dofusdb.fr y guarda el resultado en
Markets/{Mercadillo}/materials.json según las categorías de cada uno.

Formato de salida (por mercadillo):
  { "Categoria": [ {"name": "...", "unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0}, ... ], ... }

Items cuya categoría no pertenece a ningún mercadillo se guardan en
Markets/uncategorized_materials.json.

Si el archivo ya existe, los items ya catalogados se saltan.

Uso:
  python fetch_crafting_materials.py
"""

import json
import os
import glob
import time

import requests

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR   = os.path.join(BASE_DIR, "..", "Recipes")
MARKETS_DIR   = BASE_DIR
FALLBACK_FILE = os.path.join(MARKETS_DIR, "uncategorized_materials.json")
BASE_URL      = "https://api.dofusdb.fr"
UNKNOWN_KEY   = "Sin categoría"
DELAY         = 0.15


# ── Carga de archivos ─────────────────────────────────────────────────────────

def _load_file(path: str) -> dict[str, list[dict]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return {}
    data = json.loads(content)
    migrated = {}
    for cat, items in data.items():
        migrated[cat] = []
        for item in items:
            if isinstance(item, str):
                migrated[cat].append({"name": item, "unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0})
            else:
                item.pop("price", None)
                item.pop("price_pack", None)
                item.setdefault("unit_price_x1", 0)
                item.setdefault("unit_price_x10", 0)
                item.setdefault("unit_price_x100", 0)
                item.setdefault("unit_price_x1000", 0)
                migrated[cat].append(item)
    return migrated


# ── Carga de mercadillos ──────────────────────────────────────────────────────

def load_markets() -> dict[str, dict]:
    """Carga categorías y datos existentes de cada mercadillo en Markets/."""
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
        markets[folder] = {
            "categories": categories,
            "file": data_file,
            "data": _load_file(data_file),
        }
    return markets


def get_market_for_category(category: str, markets: dict) -> str | None:
    for name, market in markets.items():
        if category in market["categories"]:
            return name
    return None


# ── Lógica de ingredientes ────────────────────────────────────────────────────

def collect_raw_ingredients() -> tuple[list[str], set[str]]:
    results     = set()
    ingredients = set()
    for path in glob.glob(os.path.join(RECIPES_DIR, "recipes_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for recipe in data:
            results.add(recipe["result"])
            for ing in recipe.get("ingredients", []):
                ingredients.add(ing["name"])
    return sorted(ingredients - results), results


def purge_recipe_results(markets: dict, fallback: dict, recipe_results: set[str]) -> int:
    """Elimina de todos los mercadillos cualquier item que ahora sea resultado de una receta."""
    removed = 0
    for market in markets.values():
        data = market["data"]
        for cat in list(data.keys()):
            before = len(data[cat])
            data[cat] = [i for i in data[cat] if i["name"] not in recipe_results]
            removed += before - len(data[cat])
            if not data[cat]:
                del data[cat]
    for cat in list(fallback.keys()):
        before = len(fallback[cat])
        fallback[cat] = [i for i in fallback[cat] if i["name"] not in recipe_results]
        removed += before - len(fallback[cat])
        if not fallback[cat]:
            del fallback[cat]
    return removed


def already_catalogued(name: str, markets: dict, fallback: dict) -> bool:
    for market in markets.values():
        if any(any(i["name"] == name for i in items) for items in market["data"].values()):
            return True
    return any(any(i["name"] == name for i in items) for items in fallback.values())


def fetch_category(item_name: str) -> str:
    try:
        resp = requests.get(
            f"{BASE_URL}/items",
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
    except Exception as e:
        print(f"    [ERROR] {e}")
        return UNKNOWN_KEY


# ── Guardado ──────────────────────────────────────────────────────────────────

def save_all(markets: dict, fallback: dict):
    for market in markets.values():
        with open(market["file"], "w", encoding="utf-8") as f:
            json.dump(dict(sorted(market["data"].items())), f, ensure_ascii=False, indent=2)
    with open(FALLBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(fallback.items())), f, ensure_ascii=False, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    markets  = load_markets()
    fallback = _load_file(FALLBACK_FILE)

    total_cats = sum(len(m["categories"]) for m in markets.values())
    print(f"  {len(markets)} mercadillos cargados ({total_cats} categorías en total).\n")

    print("Recopilando ingredientes base (sin receta propia)...")
    raw, recipe_results = collect_raw_ingredients()
    print(f"  {len(raw)} ingredientes base encontrados.\n")

    print("Limpiando items que ahora son resultado de una receta...")
    removed = purge_recipe_results(markets, fallback, recipe_results)
    if removed:
        print(f"  {removed} item(s) eliminado(s).\n")
        save_all(markets, fallback)
    else:
        print("  Ninguno.\n")

    already_done = (
        sum(len(v) for m in markets.values() for v in m["data"].values())
        + sum(len(v) for v in fallback.values())
    )
    print(f"  {already_done} items ya catalogados (se saltarán).\n")

    pending = [n for n in raw if not already_catalogued(n, markets, fallback)]
    print(f"  {len(pending)} items por consultar.\n")

    for i, name in enumerate(pending, 1):
        category    = fetch_category(name)
        market_name = get_market_for_category(category, markets)

        if market_name:
            target = markets[market_name]["data"]
            dest   = market_name
        else:
            target = fallback
            dest   = "sin_categorizar"

        target.setdefault(category, [])
        if name not in [x["name"] for x in target[category]]:
            target[category].append({"name": name, "unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0})
            target[category].sort(key=lambda x: x["name"])

        line = f"  [{i:>4}/{len(pending)}] {name:<45} -> {category} [{dest}]"
        print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

        if i % 10 == 0 or i == len(pending):
            save_all(markets, fallback)

        time.sleep(DELAY)

    save_all(markets, fallback)

    print()
    for market_name, market in markets.items():
        total = sum(len(v) for v in market["data"].values())
        print(f"  {market_name}: {total} items en materials_prices.json")
    total_fallback = sum(len(v) for v in fallback.values())
    if total_fallback:
        print(f"  Sin categorizar: {total_fallback} items en uncategorized_materials.json")
    print("\n[DONE]")


if __name__ == "__main__":
    main()
