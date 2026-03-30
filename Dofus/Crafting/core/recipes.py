"""
Gestión de recetas: carga, precios de venta y expansión de subrecetas.
"""

import json
import os

from shared.market.common import _normalize as _normalize_name
from Crafting.utils.loaders import get_recipe_files
from Crafting.utils.market import _is_selling_fresh


# ── Carga de recetas ──────────────────────────────────────────────────────────

def _read_all_recipes() -> list[tuple[dict, str]]:
    """Lee todos los archivos de recetas y devuelve [(recipe_dict, file_path)]."""
    result = []
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                result.append((r, path))
    return result


def load_all_craftable_recipes() -> dict[str, dict]:
    """Devuelve {result_name: recipe_dict} para todas las recetas de todas las profesiones."""
    return {r["result"]: r for r, _ in _read_all_recipes()}


def all_recipe_results() -> set[str]:
    return {r["result"] for r, _ in _read_all_recipes()}


def build_result_file_map() -> dict[str, str]:
    """Devuelve {result_name: recipe_file_path} para todas las recetas."""
    return {r["result"]: path for r, path in _read_all_recipes()}


def find_recipe(result_name: str) -> tuple[dict | None, str | None]:
    """Devuelve (recipe_dict, recipe_file_path) para el resultado dado.
    Ignora tildes, mayúsculas y minúsculas."""
    needle = _normalize_name(result_name)
    for path in get_recipe_files():
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if _normalize_name(r.get("result", "")) == needle:
                    return r, path
    return None, None


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






