"""
Constantes y configuración compartida del proyecto Almanax.
"""
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).resolve().parent.parent   # Almanax/
PRICES_FILE      = ROOT_DIR / "data" / "item_prices.json"
MISSING_FILE     = ROOT_DIR / "data" / "missing_items.json"
CATEGORIES_FILE  = ROOT_DIR.parent / "shared" / "market" / "categories_by_market.json"
ALMANAX_FILE  = ROOT_DIR / "data" / "almanax.json"
SETTINGS_FILE = ROOT_DIR / "config" / "user_settings.json"
API_BASE       = "https://api.dofusdu.de/dofus3/v1/es/almanax"
ITEMS_API_BASE = "https://api.dofusdu.de/dofus3/v1/es/items"

# ── Mercadillo ────────────────────────────────────────────────────────────────
LOTS = (1, 10, 100, 1000)

MARKET_NAMES = {
    "resources":   "Recursos",
    "equipment":   "Equipamiento",
    "consumables": "Consumibles",
}

# ── Guijarros (coste en almanichas y nombre) ──────────────────────────────────
GUIJ_COST = {"T": 3,  "L": 15, "S": 75}

# ── Paleta de colores ─────────────────────────────────────────────────────────
from shared.colors import C  # noqa: E402