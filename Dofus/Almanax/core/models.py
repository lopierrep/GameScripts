"""
Constantes y configuración compartida del proyecto Almanax.
"""
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).resolve().parent.parent   # Almanax/
PRICES_FILE  = ROOT_DIR / "data" / "item_prices.json"
ALMANAX_FILE = ROOT_DIR / "data" / "almanax.json"
API_BASE    = "https://api.dofusdu.de/dofus3/v1/es/almanax"
MARKET_DIR  = ROOT_DIR.parent / "MarketTracker"

# ── Mercadillo ────────────────────────────────────────────────────────────────
LOTS = (1, 10, 100, 1000)

MARKET_NAMES = {
    "resources":   "Recursos",
    "equipment":   "Equipamiento",
    "consumables": "Consumibles",
}

# ── Guijarros (coste en almanichas y nombre) ──────────────────────────────────
GUIJ_COST = {"T": 3,  "L": 15, "S": 75}
GUIJ_NAME = {"T": "Temporal", "L": "Lunar", "S": "Solar"}

# ── Paleta de colores (tema oscuro compartido con MarketTracker) ───────────────
C = {
    "bg":      "#1e1e2e",
    "surface": "#2a2a3e",
    "accent":  "#89b4fa",
    "green":   "#a6e3a1",
    "red":     "#f38ba8",
    "yellow":  "#f9e2af",
    "text":    "#cdd6f4",
    "dim":     "#6c7086",
    "orange":  "#fab387",
    "today":   "#2d3250",
}