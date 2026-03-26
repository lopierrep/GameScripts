"""
Utilidades compartidas entre Almanax y MarketTracker.
"""
import json
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

_DOFUSDB_URL = "https://api.dofusdb.fr"
_UNKNOWN_CAT = "Sin categoría"

SIZES        = ["x1", "x10", "x100", "x1000"]
CACHE_SECONDS = 7200


def _normalize(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and str(raw).isdigit() else 0


def load_categories(categories_file: str) -> dict:
    with open(categories_file, encoding="utf-8") as f:
        return json.load(f)


def get_market_for_category(category: str, categories: dict) -> str | None:
    for market, cats in categories.items():
        if category in cats:
            return market
    return None


def fetch_category(item_name: str) -> str:
    try:
        params = urllib.parse.urlencode({"name.es": item_name, "$limit": 1})
        req = urllib.request.Request(
            f"{_DOFUSDB_URL}/items?{params}",
            headers={"User-Agent": "AlmanaxTracker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data", [])
        if not data:
            return _UNKNOWN_CAT
        name_obj = data[0].get("type", {}).get("name", {})
        return name_obj.get("es", name_obj.get("en", _UNKNOWN_CAT))
    except Exception:
        return _UNKNOWN_CAT
