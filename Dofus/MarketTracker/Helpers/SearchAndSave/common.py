"""
Utilidades comunes de MarketTracker.
Las utilidades compartidas con otros proyectos viven en shared/market/common.py.
"""

import os
import sys as _sys
from datetime import datetime, timezone
from pathlib import Path as _Path

import sys as _sys_path
_DOFUS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _DOFUS_DIR not in _sys_path.path:
    _sys_path.path.insert(0, _DOFUS_DIR)

from shared.market.common import _normalize, _parse_price, SIZES, CACHE_SECONDS  # noqa: F401

# Cuando corre como .exe compilado, ROOT_DIR es la carpeta del ejecutable.
if getattr(_sys, "frozen", False):
    ROOT_DIR = str(_Path(_sys.executable).parent)
    BASE_DIR = str(_Path(_sys.executable).parent / "Helpers" / "SearchAndSave")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = str(_Path(BASE_DIR).parent.parent)

OMITTED_ITEMS_FILE      = os.path.join(BASE_DIR, "omitted_items.txt")
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


def find_recipe_file(profession: str, recipes_dir: str) -> str | None:
    norm = _normalize(profession)
    for fname in os.listdir(recipes_dir):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            prof_part = fname[len("recipes_"):-len(".json")]
            if _normalize(prof_part) == norm:
                return os.path.join(recipes_dir, fname)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()