"""
Dofus 3 - Generador de raw_ingredients.json
============================================
Extrae todos los ingredientes que NO son a su vez resultado de una receta,
consulta su categoría en dofusdb.fr y guarda el resultado agrupado
en raw_ingredients.json.

Formato de salida:
  { "Categoria": [ {"name": "...", "price_x1": 0, "price_x10": 0, "price_x100": 0, "price_x1000": 0}, ... ], ... }

Si el archivo de salida ya existe, los items ya catalogados se saltan.

Uso:
  python build_raw_ingredients.py
"""

import json
import os
import glob
import time

import requests

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR     = os.path.join(BASE_DIR, "..", "LifeSkillsRecipes")
OUT_FILE        = os.path.join(BASE_DIR, "resources_prices.json")
OTHER_FILE      = os.path.join(BASE_DIR, "..", "other_ingredients_prices.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "resources_categories.txt")
BASE_URL        = "https://api.dofusdb.fr"
LANG            = "es"
UNKNOWN_KEY     = "Sin categoría"
DELAY           = 0.15


def load_allowed_categories() -> set[str]:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def purge_recipe_results(resources: dict, other: dict, recipe_results: set[str]) -> int:
    """Elimina de resources y other cualquier item que ahora sea resultado de una receta."""
    removed = 0
    for data in (resources, other):
        for cat in list(data.keys()):
            before = len(data[cat])
            data[cat] = [i for i in data[cat] if i["name"] not in recipe_results]
            removed += before - len(data[cat])
            if not data[cat]:
                del data[cat]
    return removed


def _load_file(path: str) -> dict[str, list[dict]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    migrated = {}
    for cat, items in data.items():
        migrated[cat] = []
        for item in items:
            if isinstance(item, str):
                migrated[cat].append({"name": item, "price_x1": 0, "price_x10": 0, "price_x100": 0, "price_x1000": 0})
            else:
                item.pop("price", None)
                item.pop("price_pack", None)
                item.setdefault("price_x1", 0)
                item.setdefault("price_x10", 0)
                item.setdefault("price_x100", 0)
                item.setdefault("price_x1000", 0)
                migrated[cat].append(item)
    return migrated


def load_output() -> tuple[dict, dict]:
    return _load_file(OUT_FILE), _load_file(OTHER_FILE)


def save_output(resources: dict[str, list[dict]], other: dict[str, list[dict]]):
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(resources.items())), f, ensure_ascii=False, indent=2)
    with open(OTHER_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(other.items())), f, ensure_ascii=False, indent=2)


def already_catalogued(name: str, resources: dict, other: dict) -> bool:
    for data in (resources, other):
        if any(any(i["name"] == name for i in items) for items in data.values()):
            return True
    return False


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


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    allowed = load_allowed_categories()
    print(f"  {len(allowed)} categorías permitidas en resources_prices.json.\n")

    print("Recopilando ingredientes base (sin receta propia)...")
    raw, recipe_results = collect_raw_ingredients()
    print(f"  {len(raw)} ingredientes base encontrados.\n")

    resources, other = load_output()

    print("Limpiando items que ahora son resultado de una receta...")
    removed = purge_recipe_results(resources, other, recipe_results)
    if removed:
        print(f"  {removed} item(s) eliminado(s).\n")
        save_output(resources, other)
    else:
        print("  Ninguno.\n")

    already_done = sum(len(v) for v in resources.values()) + sum(len(v) for v in other.values())
    print(f"  {already_done} items ya catalogados (se saltaran).\n")

    pending = [n for n in raw if not already_catalogued(n, resources, other)]
    print(f"  {len(pending)} items por consultar.\n")

    for i, name in enumerate(pending, 1):
        category = fetch_category(name)
        target = resources if category in allowed else other
        target.setdefault(category, [])
        names_in_cat = [x["name"] for x in target[category]]
        if name not in names_in_cat:
            target[category].append({"name": name, "price_x1": 0, "price_x10": 0, "price_x100": 0, "price_x1000": 0})
            target[category].sort(key=lambda x: x["name"])

        dest = "resources_prices" if category in allowed else "other_ingredients"
        line = f"  [{i:>4}/{len(pending)}] {name:<45} -> {category} [{dest}]"
        print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

        if i % 10 == 0 or i == len(pending):
            save_output(resources, other)

        time.sleep(DELAY)

    save_output(resources, other)
    total_res   = sum(len(v) for v in resources.values())
    total_other = sum(len(v) for v in other.values())
    print(f"\n[DONE] {total_res} items en resources_prices.json, {total_other} en other_ingredients_prices.json")


if __name__ == "__main__":
    main()
