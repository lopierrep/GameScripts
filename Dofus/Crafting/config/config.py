"""
Constantes globales para Crafting.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_DOFUS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

from shared.market.common import _normalize, _parse_price, SIZES, CACHE_SECONDS  # noqa: F401

# ROOT_DIR resuelve correctamente tanto en modo script como .exe (frozen)
if getattr(sys, "frozen", False):
    ROOT_DIR = str(Path(sys.executable).parent)
else:
    ROOT_DIR = str(Path(__file__).resolve().parent.parent)

DATA_DIR         = os.path.join(ROOT_DIR, "data")
CATEGORIES_FILE  = os.path.join(ROOT_DIR, "..", "shared", "market", "categories_by_market.json")
PRICES_FILE      = os.path.join(DATA_DIR, "materials_prices.json")
CREDENTIALS_FILE = os.path.join(ROOT_DIR, "export", "credentials.json")

OMITTED_ITEMS_FILE      = os.path.join(ROOT_DIR, "config", "omitted_items.txt")
OMITTED_CATEGORIES_FILE = os.path.join(ROOT_DIR, "config", "omitted_categories.txt")
MANUAL_PRICE_FILE       = os.path.join(ROOT_DIR, "config", "manual_price_items.txt")

DELAY_BETWEEN_ITEMS = 0.3
DOFUSDB_URL         = "https://api.dofusdb.fr"
UNKNOWN_KEY         = "Sin categoría"


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


def _load_manual_price_items() -> set[str]:
    if not os.path.exists(MANUAL_PRICE_FILE):
        return set()
    with open(MANUAL_PRICE_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def find_recipe_file(profession: str) -> str | None:
    norm = _normalize(profession)
    for fname in os.listdir(DATA_DIR):
        if fname.startswith("recipes_") and fname.endswith(".json"):
            prof_part = fname[len("recipes_"):-len(".json")]
            if _normalize(prof_part) == norm:
                return os.path.join(DATA_DIR, fname)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
