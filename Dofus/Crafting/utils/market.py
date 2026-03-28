"""
Utilidades de cálculo de mercado: impuestos, filtros de lote y timestamps.
"""

import math
from datetime import datetime, timezone

from config.config import CACHE_SECONDS, MAX_LOT_PRICE, _LOT_NUMS


def net_sell_price(price: int) -> int:
    """Precio neto real tras impuestos de listing (2%) y 5 bajadas de 10k
    con coste de modificación del 1% cada una.
    Los impuestos se redondean hacia arriba (ceil) ya que las kamas son enteras.

    Net = (P - 50) - 0.02·P - 0.01·[(P-10)+(P-20)+(P-30)+(P-40)+(P-50)]
        = 0.93·P - 48.5
    """
    listing_tax = math.ceil(price * 0.02)
    mod_fees    = sum(math.ceil((price - 10 * i) * 0.01) for i in range(1, 6))
    return (price - 50) - listing_tax - mod_fees


def filter_lot_prices(unit_prices: dict[str, int]) -> tuple[dict[str, int], set[str]]:
    """Filtra precios unitarios cuyo total de lote supera MAX_LOT_PRICE.
    Devuelve (precios_filtrados, tamaños_excedidos)."""
    filtered = {}
    exceeded = set()
    for size, lot_num in _LOT_NUMS.items():
        u = unit_prices.get(size, 0) or 0
        if u * lot_num > MAX_LOT_PRICE:
            filtered[size] = 0
            exceeded.add(size)
        else:
            filtered[size] = u
    return filtered, exceeded


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_selling_fresh(recipe: dict) -> bool:
    """Verifica si el precio de venta de una receta fue actualizado en el último CACHE_SECONDS."""
    ts = recipe.get("prices_updated_at")
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return age < CACHE_SECONDS
