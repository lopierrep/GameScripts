"""
Funciones de carga de archivos de configuración y datos del proyecto.
"""

import json
import os
from functools import lru_cache

from Crafting.config.config import (
    DATA_DIR,
    SETTINGS_FILE,
    _normalize,
)
from shared.market.crafting_costs import get_recipe_files  # noqa: F401
from shared.market.item_price_scanner import (
    load_omitted_items   as _load_omitted_recipes,     # noqa: F401
    load_omitted_categories as _load_omitted_categories, # noqa: F401
)


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
