"""
Dofus 3 - Descargador de recetas desde dofusdb.fr
==================================================
Obtiene todas las recetas de todas las profesiones y las guarda en JSON.
Preserva unit_selling_price_x* y unit_crafting_cost_x* existentes.

Uso:
  pip install requests
  python fetch_recipes.py                  # actualiza todas las profesiones
  python fetch_recipes.py --job 24         # solo Minero (por ID)
  python fetch_recipes.py --list           # listar profesiones y sus IDs
"""

import argparse
import json
import os
import sys

import requests

BASE_URL       = "https://api.dofusdb.fr"
LANG           = "es"
OUT_DIR        = os.path.dirname(os.path.abspath(__file__))
CATEGORIES_FILE = os.path.join(OUT_DIR, "lifeskills_categories.txt")


def load_categories() -> set[str]:
    """Lee lifeskills_categories.txt y devuelve los nombres en minúsculas."""
    if not os.path.exists(CATEGORIES_FILE):
        return set()
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


# ── API ─────────────────────────────────────────────────────────────────────

def get_jobs() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/jobs", params={"$limit": 100}, timeout=10)
    resp.raise_for_status()
    jobs = resp.json()["data"]
    # ordenar por nombre en español
    return sorted(jobs, key=lambda j: j["name"].get(LANG, j["name"]["en"]))


def get_recipes(job_id: int) -> list[dict]:
    recipes = []
    skip = 0
    limit = 50

    while True:
        resp = requests.get(
            f"{BASE_URL}/recipes",
            params={"jobId": job_id, "$limit": limit, "$skip": skip},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        recipes.extend(data["data"])
        skip += limit
        if skip >= data["total"]:
            break

    return recipes


# ── Parseo ──────────────────────────────────────────────────────────────────

def parse_recipe(r: dict) -> dict:
    """Simplifica una receta al formato útil para el proyecto."""
    quantities = r.get("quantities", [])
    ingredients = []
    for i, ing in enumerate(r.get("ingredients", [])):
        name = ing.get("name", "?")
        if isinstance(name, dict):
            name = name.get(LANG, name.get("en", "?"))
        qty = quantities[i] if i < len(quantities) else ing.get("quantity", 1)
        ingredients.append({"name": name, "quantity": qty})

    return {
        "id":                         r.get("resultId"),
        "result":                     r["resultName"].get(LANG, r["resultName"]["en"]),
        "level":                      r.get("resultLevel"),
        "ingredients":                ingredients,
        "unit_selling_price_x1":      0,
        "unit_selling_price_x10":     0,
        "unit_selling_price_x100":    0,
        "unit_selling_price_x1000":   0,
        "unit_crafting_cost_x1":      0,
        "unit_crafting_cost_x10":     0,
        "unit_crafting_cost_x100":    0,
        "unit_crafting_cost_x1000":   0,
    }


# ── Guardado ────────────────────────────────────────────────────────────────

SELLING_FIELDS = (
    "unit_selling_price_x1", "unit_selling_price_x10",
    "unit_selling_price_x100", "unit_selling_price_x1000",
)
CRAFTING_FIELDS = (
    "unit_crafting_cost_x1", "unit_crafting_cost_x10",
    "unit_crafting_cost_x100", "unit_crafting_cost_x1000",
)


def _ingredients_changed(old: list[dict], new: list[dict]) -> bool:
    normalize = lambda ings: sorted((i["name"], i["quantity"]) for i in ings)
    return normalize(old) != normalize(new)


def save(job_name: str, recipes: list[dict]):
    safe_name = job_name.lower().replace(" ", "_")
    path = os.path.join(OUT_DIR, f"recipes_{safe_name}.json")

    existing: dict[int, dict] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for rec in json.load(f):
                existing[rec["id"]] = rec

    parsed = []
    added = changed = skipped = 0
    for r in recipes:
        rec = parse_recipe(r)
        old = existing.get(rec["id"])

        if old is None:
            # Receta nueva: añadir tal cual
            parsed.append(rec)
            added += 1
        elif _ingredients_changed(old.get("ingredients", []), rec["ingredients"]):
            # Ingredientes cambiaron: actualizar ingredientes, resetear precios de venta y crafting
            parsed.append(rec)
            changed += 1
        else:
            # Sin cambios: conservar todo
            parsed.append(old)
            skipped += 1

    parsed.sort(key=lambda r: r["level"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(f"  -> {len(parsed)} recetas | +{added} nuevas, {changed} actualizadas, {skipped} sin cambios | {os.path.basename(path)}")
    return path


# ── Modos ───────────────────────────────────────────────────────────────────

def list_jobs(jobs: list[dict]):
    print(f"\n{'ID':>4}  Profesión")
    print("-" * 30)
    for j in jobs:
        name = j["name"].get(LANG, j["name"]["en"])
        print(f"{j['id']:>4}  {name}")
    print()


def fetch_one(jobs: list[dict], job_id: int):
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"[ERROR] No se encontró la profesión con ID {job_id}.")
        sys.exit(1)
    name = job["name"].get(LANG, job["name"]["en"])
    print(f"Descargando recetas de: {name} (id={job_id}) …")
    recipes = get_recipes(job_id)
    save(name, recipes)


def fetch_all(jobs: list[dict]):
    categories = load_categories()
    for job in jobs:
        name = job["name"].get(LANG, job["name"]["en"])
        safe_name = name.lower().replace(" ", "_")
        if categories and safe_name not in categories:
            continue
        print(f"[{job['id']:>2}] {name} …", end=" ", flush=True)
        recipes = get_recipes(job["id"])
        save(name, recipes)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Descarga recetas de dofusdb.fr")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--job",  type=int, metavar="ID", help="ID de la profesión (solo esa)")
    group.add_argument("--list", action="store_true",   help="Listar profesiones disponibles")
    args = parser.parse_args()

    print("Obteniendo lista de profesiones…")
    jobs = get_jobs()

    if args.list:
        list_jobs(jobs)
    elif args.job:
        fetch_one(jobs, args.job)
    else:
        fetch_all(jobs)


if __name__ == "__main__":
    main()
