"""
Constantes globales para Crafting.
"""

import os
import sys
from pathlib import Path

_DOFUS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

from shared.market.common import _normalize, _parse_price, SIZES, CACHE_SECONDS  # noqa: F401
from shared.colors import C  # noqa: F401

# ROOT_DIR resuelve correctamente tanto en modo script como .exe (frozen)
if getattr(sys, "frozen", False):
    ROOT_DIR = str(Path(sys.executable).parent)
else:
    ROOT_DIR = str(Path(__file__).resolve().parent.parent)

DATA_DIR         = os.path.join(ROOT_DIR, "data")
CATEGORIES_FILE  = os.path.join(ROOT_DIR, "..", "shared", "market", "categories_by_market.json")
PRICES_FILE      = os.path.join(DATA_DIR, "materials_prices.json")
CREDENTIALS_FILE = os.path.join(ROOT_DIR, "export", "credentials.json")
SETTINGS_FILE    = os.path.join(ROOT_DIR, "config", "user_settings.json")

OMITTED_RECIPES_FILE    = os.path.join(ROOT_DIR, "config", "omitted_recipes.txt")
OMITTED_CATEGORIES_FILE = os.path.join(ROOT_DIR, "config", "omitted_categories.txt")
MANUAL_PRICE_FILE       = os.path.join(ROOT_DIR, "config", "manual_price_items.txt")


DELAY_BETWEEN_ITEMS  = 0.3
DOFUSDB_URL          = "https://api.dofusdb.fr"
UNKNOWN_KEY          = "Sin categoría"

_LOT_NUMS = {"x1": 1, "x10": 10, "x100": 100, "x1000": 1000}

MAX_LOT_PRICE        = 1_500_000  # Precio total máximo por lote de venta
LOT_PROFIT_MARGIN    = 0.05       # Tolerancia de ganancia para preferir lotes de venta más grandes
LOT_STABILITY_MARGIN = 0.25       # Tolerancia para preferir lotes de compra mayores por estabilidad de precio