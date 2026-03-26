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

OMITTED_RECIPES_FILE    = os.path.join(ROOT_DIR, "config", "omitted_recipes.txt")
OMITTED_CATEGORIES_FILE = os.path.join(ROOT_DIR, "config", "omitted_categories.txt")
MANUAL_PRICE_FILE       = os.path.join(ROOT_DIR, "config", "manual_price_items.txt")

DELAY_BETWEEN_ITEMS = 0.3
DOFUSDB_URL         = "https://api.dofusdb.fr"
UNKNOWN_KEY         = "Sin categoría"

# ── Impuestos de mercadillo ───────────────────────────────────────────────────
# Impuesto de listing: 2% del precio de venta.
# Coste de modificar precio: 1% del nuevo precio.
# Asumimos 5 bajadas de 10k antes de vender.
#
# Net = (P - 50) - 0.02·P - 0.01·[(P-10)+(P-20)+(P-30)+(P-40)+(P-50)]
#     = (P - 50) - 0.02·P - (0.05·P - 1.5)
#     = 0.93·P - 48.5

def net_sell_price(price: int) -> int:
    """Precio neto real tras impuestos de listing (2%) y 5 bajadas de 10k
    con coste de modificación del 1% cada una.
    Los impuestos se redondean hacia arriba (ceil) ya que las kamas son enteras."""
    import math
    listing_tax = math.ceil(price * 0.02)
    mod_fees    = sum(math.ceil((price - 10 * i) * 0.01) for i in range(1, 6))
    return (price - 50) - listing_tax - mod_fees

from shared.colors import C  # noqa: E402


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


def list_professions() -> list[str]:
    """Devuelve los nombres de profesión disponibles en DATA_DIR, ordenados."""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        f[len("recipes_"):-len(".json")]
        for f in os.listdir(DATA_DIR)
        if f.startswith("recipes_") and f.endswith(".json")
    )


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
