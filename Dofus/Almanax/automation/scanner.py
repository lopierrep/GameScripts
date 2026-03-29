"""
Lógica de escaneo de precios en el mercadillo (sin dependencias de UI).
"""
from datetime import date as _date

from core.prices import find_item_prices
from shared.market.item_price_scanner import ScanItem
from shared.market.prices import now_iso


def build_scan_items(data: list, prices: dict, from_date, to_date) -> list:
    """
    Construye ScanItems a partir del historial de Almanax filtrado por fecha.
    Deduplica items; los que ya tienen precio se marcan como frescos.
    Con fresh_seconds=sys.maxsize, los items con precio nunca se re-escanean.
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
        existing  = find_item_prices(prices, name)
        has_price = existing is not None and any(
            existing.get(f"x{s}", 0) > 0 for s in (1, 10, 100, 1000)
        )
        items.append(ScanItem(
            name              = name,
            market            = r.get("market",   "Unknown"),
            category          = r.get("category", "Sin categoría"),
            type              = "ingredient",
            prices_updated_at = now_iso() if has_price else None,
            has_price         = has_price,
        ))
    return items
