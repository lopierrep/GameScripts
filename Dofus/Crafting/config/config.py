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
from shared.ui.colors import C  # noqa: F401

# ── Rutas ──────────────────────────────────────────────────────────────
# ROOT_DIR resuelve correctamente tanto en modo script como .exe (frozen)
if getattr(sys, "frozen", False):
    ROOT_DIR = str(Path(sys.executable).parent)
else:
    ROOT_DIR = str(Path(__file__).resolve().parent.parent)

DATA_DIR         = os.path.join(ROOT_DIR, "..", "shared", "data")
CATEGORIES_FILE  = os.path.join(ROOT_DIR, "..", "shared", "market", "categories_by_market.json")
PRICES_FILE      = os.path.join(DATA_DIR, "materials_prices.json")
SETTINGS_FILE    = os.path.join(ROOT_DIR, "config", "user_settings.json")

# ── API / Scraping ─────────────────────────────────────────────────────
DELAY_BETWEEN_ITEMS  = 0.3

# ── Lógica de negocio ─────────────────────────────────────────────────
UNKNOWN_KEY          = "Sin categoría"
from shared.market.prices import LOT_NUMS as _LOT_NUMS  # noqa: F401, compatibilidad interna
MAX_LOT_PRICE        = 1_500_000  # Precio total máximo por lote de venta
LOT_PROFIT_MARGIN    = 0.05       # Tolerancia de ganancia para preferir lotes de venta más grandes
EQUIPMENT_PROFESSIONS = {"escultor", "fabricante", "herrero", "joyero", "manitas", "sastre", "zapatero"}