"""
Constantes y configuración compartida del proyecto Almanax.
"""
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR         = Path(__file__).resolve().parent.parent   # Almanax/
PRICES_FILE      = ROOT_DIR.parent / "shared" / "data" / "materials_prices.json"
CATEGORIES_FILE  = ROOT_DIR.parent / "shared" / "market" / "categories_by_market.json"
ALMANAX_FILE     = ROOT_DIR / "data" / "almanax.json"
SETTINGS_FILE    = ROOT_DIR / "config" / "user_settings.json"

# ── API ───────────────────────────────────────────────────────────────────────
API_BASE       = "https://api.dofusdu.de/dofus3/v1/es/almanax"
ITEMS_API_BASE = "https://api.dofusdu.de/dofus3/v1/es/items"
USER_AGENT     = "AlmanaxTracker/1.0"
API_TIMEOUT         = 60   # timeout para fetch_almanax
API_TIMEOUT_RESOLVE = 10   # timeout para resolve_subtype / fetch_category

# ── Mercadillo ────────────────────────────────────────────────────────────────
LOTS = (1, 10, 100, 1000)

MARKET_NAMES = {
    "resources":   "Recursos",
    "equipment":   "Equipamiento",
    "consumables": "Consumibles",
}

# ── Lógica ────────────────────────────────────────────────────────────────────
MIN_HIGH_PROFIT = 500            # kamas de ganancia para considerar "alta rentabilidad"
SERVER_TIMEZONE = "Europe/Paris"  # zona horaria del servidor Dofus

# ── Guijarros (coste en almanichas y nombre) ──────────────────────────────────
GUIJ_COST = {"T": 3,  "L": 15, "S": 75}

# ── Automatización ────────────────────────────────────────────────────────────
STOP_HOTKEY       = "s"
SCAN_DELAY        = 0.3   # segundos entre ítems al escanear
SCAN_COUNTDOWN    = 3     # cuenta atrás antes de cada mercadillo (escaneo)
BUY_COUNTDOWN     = 5     # cuenta atrás antes de cada mercadillo (compra)
BUY_DELAY_CONFIRM = 0.4   # delay tras click en confirmar compra
BUY_DELAY_LOT     = 0.25  # delay tras click en lote
BUY_DELAY_BETWEEN = 1.0   # espera entre compras del mismo lote
BUY_DELAY_ESC     = 0.3   # delay tras ESC al terminar un ítem
BUY_CLICK_RESULT  = 0.4   # delay tras click en resultado de búsqueda

# ── UI defaults ───────────────────────────────────────────────────────────────
WINDOW_SIZE       = (1150, 720)
WINDOW_MINSIZE    = (800, 500)
DEFAULT_DAYS      = 29     # rango de días por defecto (desde hoy)
DEFAULT_PJS       = "15"
DEFAULT_ALM       = "4"
DEFAULT_GUIJ_PRICES = {"T": "3600", "L": "18000", "S": "90000"}

# ── Paleta de colores ─────────────────────────────────────────────────────────
from shared.colors import C  # noqa: E402