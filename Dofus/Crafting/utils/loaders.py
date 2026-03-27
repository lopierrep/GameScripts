"""
Funciones de carga de archivos de configuración y datos del proyecto.
"""

import json
import os

from config.config import (
    DATA_DIR,
    MANUAL_PRICE_FILE,
    OMITTED_CATEGORIES_FILE,
    OMITTED_RECIPES_FILE,
    SETTINGS_FILE,
    _normalize,
)


def _load_omitted_recipes() -> set[str]:
    if not os.path.exists(OMITTED_RECIPES_FILE):
        return set()
    with open(OMITTED_RECIPES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _load_omitted_categories() -> set[str]:
    if not os.path.exists(OMITTED_CATEGORIES_FILE):
        return set()
    with open(OMITTED_CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _load_manual_price_items() -> set[str]:
    if not os.path.exists(MANUAL_PRICE_FILE):
        return set()
    with open(MANUAL_PRICE_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def get_recipe_files() -> list[str]:
    """Devuelve las rutas absolutas de todos los archivos recipes_*.json en DATA_DIR."""
    if not os.path.isdir(DATA_DIR):
        return []
    return [
        os.path.join(DATA_DIR, f)
        for f in sorted(os.listdir(DATA_DIR))
        if f.startswith("recipes_") and f.endswith(".json")
    ]


def list_professions() -> list[str]:
    """Devuelve los nombres de profesión disponibles en DATA_DIR, ordenados."""
    return [
        os.path.basename(p)[len("recipes_"):-len(".json")]
        for p in get_recipe_files()
    ]


def find_recipe_file(profession: str) -> str | None:
    norm = _normalize(profession)
    for fname in os.listdir(DATA_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            prof_part = fname[len("recipes_"):-len(".json")]
            if _normalize(prof_part) == norm:
                return os.path.join(DATA_DIR, fname)
    return None


def load_user_settings() -> dict:
    """Carga la configuración de usuario desde user_settings.json."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_settings(settings: dict):
    """Guarda la configuración de usuario en user_settings.json."""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
