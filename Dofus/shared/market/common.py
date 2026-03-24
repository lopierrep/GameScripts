"""
Utilidades compartidas entre Almanax y MarketTracker.
"""
import unicodedata

SIZES        = ["x1", "x10", "x100", "x1000"]
CACHE_SECONDS = 3600


def _normalize(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and str(raw).isdigit() else 0
