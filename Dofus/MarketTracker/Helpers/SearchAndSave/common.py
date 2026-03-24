"""
Utilidades comunes compartidas por los módulos de búsqueda y guardado.
"""

import os
import sys as _sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path as _Path

# Cuando corre como .exe compilado, ROOT_DIR es la carpeta del ejecutable.
if getattr(_sys, "frozen", False):
    ROOT_DIR = str(_Path(_sys.executable).parent)
    BASE_DIR = str(_Path(_sys.executable).parent / "Helpers" / "SearchAndSave")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = str(_Path(BASE_DIR).parent.parent)

OMITTED_ITEMS_FILE      = os.path.join(BASE_DIR, "omitted_items.txt")
OMITTED_CATEGORIES_FILE = os.path.join(BASE_DIR, "omitted_categories.txt")

CACHE_SECONDS = 3600
SIZES = ["x1", "x10", "x100", "x1000"]


def _normalize(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and str(raw).isdigit() else 0


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