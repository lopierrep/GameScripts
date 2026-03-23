"""
Dofus 3 - Guardado de precios de venta de recetas
==================================================
Busca el precio de venta de un item resultado de receta en el mercadillo
y lo guarda como selling_price_x1/x10/x100/x1000 en su archivo de recetas.

Uso:
    python save_recipe_selling_prices.py leñador
    python save_recipe_selling_prices.py zapatero 5
"""

import glob
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timezone

from . import search_item_prices as sip
from .search_item_prices import search_item, read_prices

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR     = os.path.join(BASE_DIR, "..", "..", "Recipes")
OMITTED_ITEMS_FILE         = os.path.join(BASE_DIR, "omitted_items.txt")
OMITTED_CATEGORIES_FILE = os.path.join(BASE_DIR, "omitted_categories.txt")


def _load_omitted_items() -> set[str]:
    if not os.path.exists(OMITTED_ITEMS_FILE):
        return set()
    with open(OMITTED_ITEMS_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _load_omitted_categories() -> set[str]:
    if not os.path.exists(OMITTED_CATEGORIES_FILE):
        return set()
    with open(OMITTED_CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


CACHE_SECONDS = 3600  # 1 hora


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_fresh(recipe: dict) -> bool:
    ts = recipe.get("selling_last_updated")
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return age < CACHE_SECONDS


def _normalize(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and raw.isdigit() else 0


def find_recipe_file(profession: str) -> str | None:
    norm = _normalize(profession)
    for fname in os.listdir(RECIPES_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            prof_part = fname[len("recipes_"):-len(".json")]
            if _normalize(prof_part) == norm:
                return os.path.join(RECIPES_DIR, fname)
    return None


def _sanitize_unit_prices(prices: list[int]) -> list[int]:
    """
    Si hay 3+ precios no-cero y alguno supera 1.5x el mínimo, se considera
    outlier y se reemplaza por el promedio de los precios normales.
    Con menos de 3 precios no hace nada.
    """
    non_zero = [(i, p) for i, p in enumerate(prices) if p > 0]
    if len(non_zero) < 3:
        return prices

    min_price = min(p for _, p in non_zero)
    threshold = 1.5 * min_price

    normal  = [(i, p) for i, p in non_zero if p <= threshold]
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
    x1   = _parse_price(prices, "1")
    x10  = _parse_price(prices, "10")
    x100 = _parse_price(prices, "100")
    x1000= _parse_price(prices, "1000")

    with open(recipe_file, encoding="utf-8") as f:
        data = json.load(f)

    # Convertir a precio UNITARIO al guardar (dividir por tamaño del lote)
    u1    = x1
    u10   = round(x10   / 10)   if x10   > 0 else u1
    u100  = round(x100  / 100)  if x100  > 0 else u10
    u1000 = round(x1000 / 1000) if x1000 > 0 else u100

    u1, u10, u100, u1000 = _sanitize_unit_prices([u1, u10, u100, u1000])

    for recipe in data:
        if recipe.get("result") == name:
            recipe["unit_selling_price_x1"]    = u1
            recipe["unit_selling_price_x10"]   = u10
            recipe["unit_selling_price_x100"]  = u100
            recipe["unit_selling_price_x1000"] = u1000
            recipe.pop("selling_last_updated", None)  # se fija al terminar el cálculo de crafteo

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name} → x1={x1}  x10={x10}  x100={x100}  x1000={x1000}")


def _find_recipe(recipe_file: str, name: str) -> dict | None:
    with open(recipe_file, encoding="utf-8") as f:
        data = json.load(f)
    return next((r for r in data if r.get("result") == name), None)


def search_and_save_selling(recipe_file: str, name: str) -> dict:
    """Busca el precio de venta de un item y lo guarda en su receta.
    Si el precio fue actualizado hace menos de 1h, o está en omitted_items.txt, lo omite."""
    if name in _load_omitted_items():
        print(f"[SKIP] {name} — en lista de excepciones")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}
    recipe = _find_recipe(recipe_file, name)
    if recipe and recipe.get("category") in _load_omitted_categories():
        print(f"[SKIP] {name} — categoría omitida ({recipe.get('category')})")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}
    if recipe and _is_fresh(recipe):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        return {
            "unit_price_x1":    recipe.get("unit_selling_price_x1", 0),
            "unit_price_x10":   recipe.get("unit_selling_price_x10", 0),
            "unit_price_x100":  recipe.get("unit_selling_price_x100", 0),
            "unit_price_x1000": recipe.get("unit_selling_price_x1000", 0),
            "_skipped":         True,
        }
    search_item(name)
    prices = read_prices(name)
    save_selling_price(recipe_file, name, prices)
    return prices


def update_profession_selling_prices(profession: str, limit: int | None = None):
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

    results = sorted({r["result"] for r in recipes})
    print(f"[INFO] {len(results)} items a buscar en: {os.path.basename(recipe_file)}\n")

    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)
    print("  Empezando ahora!      ")

    for idx, name in enumerate(results, 1):
        print(f"[{idx}/{len(results)}] {name} …", end=" ", flush=True)
        try:
            search_and_save_selling(recipe_file, name)
        except Exception as e:
            print(f"ERROR — {e}")
        finally:
            import keyboard as kb
            kb.press_and_release("esc")
            time.sleep(0.15)
        time.sleep(0.3)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        available = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(RECIPES_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        print("Uso: python save_recipe_selling_prices.py <profesion> [limite]")
        print(f"  Profesiones disponibles: {', '.join(available)}")
        sys.exit(1)

    profession = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    sip.load_calibration()
    update_profession_selling_prices(profession, limit)
