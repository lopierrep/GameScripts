"""
Lógica de escaneo de precios en el mercadillo (sin dependencias de UI).
"""
from datetime import date as _date

from Almanax.config.config import LOTS
from Almanax.core.prices import find_item_prices
from shared.market.item_price_scanner import ScanItem


def build_scan_items(data: list, prices: dict, from_date, to_date) -> list:
    """
    Construye ScanItems a partir del historial de Almanax filtrado por fecha.
    Deduplica items y propaga el `prices_updated_at` real del entry, para que
    el scanner aplique freshness (CACHE_SECONDS) sobre datos verdaderos.
    """
    seen: set = set()
    items: list = []
    for r in data:
        if not (from_date <= _date.fromisoformat(r["date"]) <= to_date):
            continue
        name = r["item"]
        if name in seen:
            continue
        seen.add(name)
        existing  = find_item_prices(prices, name) or {}
        has_price = any(existing.get(f"x{s}", 0) > 0 for s in LOTS)
        items.append(ScanItem(
            name              = name,
            market            = r.get("market",   "Unknown"),
            category          = r.get("category", "Sin categoría"),
            type              = "ingredient",
            prices_updated_at = existing.get("prices_updated_at"),
            has_price         = has_price,
        ))
    return items
