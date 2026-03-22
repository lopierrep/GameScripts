"""
Dofus 3 - Actualizador de precios por profesión
================================================
Recibe una profesión como argumento y actualiza selling_price y crafting_cost
en el archivo recipes_{profesion}.json correspondiente.

Si un ingrediente no tiene precio conocido, lo busca automáticamente en el
mercadillo del juego usando OCR (requiere calibration.json).

Fuentes de precios: resources_prices.json y other_ingredients_prices.json

Uso:
  python update_profession_prices.py alquimista
  python update_profession_prices.py herrero
"""

import json
import os
import sys
import time
import unicodedata

import keyboard
import requests

import helpers.search_item_prices as sip
import save_resource_buy_prices as srs
from save_resource_buy_prices import search_and_save
import helpers.save_recipe_selling_prices as srsp
import helpers.save_recipe_crafting_prices as srp

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MARKET_DIR      = os.path.join(BASE_DIR, "..")

OTHER_JSON      = os.path.join(MARKET_DIR, "other_ingredients_prices.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "resources_categories.txt")
RECIPES_DIR     = os.path.join(MARKET_DIR, "LifeSkillsRecipes")

DELAY_BETWEEN_ITEMS = 0.3
DOFUSDB_URL         = "https://api.dofusdb.fr"
UNKNOWN_KEY         = "Sin categoría"

stop_requested = False


# ── Utilidades ────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def load_allowed_categories() -> set[str]:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ── Carga y guardado de precios ───────────────────────────────────────────────

def _load_price_file(path: str) -> dict[str, list]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)


def find_item_in_data(name: str, data: dict) -> dict | None:
    for items in data.values():
        for item in items:
            if item["name"] == name:
                return item
    return None


def add_item_to_data(name: str, category: str, data: dict):
    for items in data.values():
        if any(i["name"] == name for i in items):
            return
    data.setdefault(category, [])
    data[category].append({"name": name, "unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0})
    data[category].sort(key=lambda x: x["name"])


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


# ── Búsqueda en mercado ───────────────────────────────────────────────────────

def _price_found(prices: dict) -> bool:
    return any(v not in ("N/A", "", "0", 0) for v in prices.values())


def search_prices_in_market(items: list[str], label: str, save_fn) -> list[str]:
    """Busca precios en el mercado. Devuelve los items en los que no se encontró precio."""
    global stop_requested
    missing = []
    if not items:
        return missing
    print(f"\n── {label} ({len(items)} items) ──")
    print("Pulsa Y para detener.\n")

    def on_key(event):
        global stop_requested
        if event.name == "y":
            stop_requested = True
    keyboard.on_press(on_key)

    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)
    print("  Empezando ahora!      ")

    for idx, name in enumerate(items, 1):
        if stop_requested:
            missing.extend(items[idx - 1:])
            break
        print(f"[{idx}/{len(items)}] {name} …", end=" ", flush=True)
        try:
            prices = save_fn(name)
            if not _price_found(prices):
                missing.append(name)
        except Exception as e:
            print(f"ERROR — {e}")
            missing.append(name)
        finally:
            keyboard.press_and_release("esc")
            time.sleep(0.15)
        time.sleep(DELAY_BETWEEN_ITEMS)

    return missing


def _all_recipe_results() -> set[str]:
    results = set()
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            with open(os.path.join(RECIPES_DIR, fname), encoding="utf-8") as f:
                for r in json.load(f):
                    results.add(r["result"])
    return results


def ensure_catalogued(names: set[str]):
    """Añade a los JSONs los items que aún no están catalogados (excluye craftables)."""
    allowed        = load_allowed_categories()
    resources_data = _load_price_file(srs.ITEMS_FILE)
    other_data     = _load_price_file(OTHER_JSON)
    craftable      = _all_recipe_results()

    uncatalogued = [
        name for name in names
        if name not in craftable
        and find_item_in_data(name, resources_data) is None
        and find_item_in_data(name, other_data) is None
    ]
    if not uncatalogued:
        return

    print(f"\nConsultando categorías para {len(uncatalogued)} items nuevos…")
    for name in uncatalogued:
        category = fetch_category(name)
        target = resources_data if category in allowed else other_data
        add_item_to_data(name, category, target)
        print(f"  + {name} → {category}")
        time.sleep(0.15)
    _save_json(srs.ITEMS_FILE, resources_data)
    _save_json(OTHER_JSON, other_data)


# ── Búsqueda de archivo de recetas ────────────────────────────────────────────

def find_recipe_file(profession: str) -> str | None:
    norm = _normalize(profession)
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            prof_part = fname[len("recipes_"):-len(".json")]
            if _normalize(prof_part) == norm:
                return os.path.join(RECIPES_DIR, fname)
    return None


# ── Actualización de recetas ──────────────────────────────────────────────────

def update_profession(profession: str, limit: int | None = None):
    recipe_file = find_recipe_file(profession)
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

    sip.load_calibration()
    ensure_catalogued(all_ingredients)

    # Fase 1: precios de venta de recetas
    print("\n[FASE 1] Buscando precios de venta de recetas…")
    global stop_requested
    stop_requested = False
    missing_recipes = search_prices_in_market(
        sorted(all_results), "precios de venta",
        lambda name: srsp.search_and_save_selling(recipe_file, name)
    )

    # Fase 2: precios de ingredientes (con confirmación)
    input("\nPresiona ENTER para buscar precios de ingredientes…")
    stop_requested = False
    missing_ingredients = search_prices_in_market(
        sorted(all_ingredients), "ingredientes", search_and_save
    )

    # Fase 3: reintentar recetas sin precio (con confirmación, si las hay)
    if missing_recipes:
        print(f"\n[INFO] {len(missing_recipes)} recetas sin precio: {', '.join(missing_recipes)}")
        input("Presiona ENTER para reintentar…")
        stop_requested = False
        search_prices_in_market(
            sorted(missing_recipes), "recetas (reintento)",
            lambda name: srsp.search_and_save_selling(recipe_file, name)
        )

    # Fase 4: reintentar ingredientes sin precio (si los hay)
    if missing_ingredients:
        print(f"\n[INFO] {len(missing_ingredients)} ingredientes sin precio: {', '.join(missing_ingredients)}")
        stop_requested = False
        search_prices_in_market(
            sorted(missing_ingredients), "ingredientes (reintento)", search_and_save
        )

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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(RECIPES_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        print("Uso: python update_profession_prices.py <profesion> [limite]")
        print(f"  Profesiones disponibles: {', '.join(available)}")
        return

    profession = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    update_profession(profession, limit)


if __name__ == "__main__":
    main()
