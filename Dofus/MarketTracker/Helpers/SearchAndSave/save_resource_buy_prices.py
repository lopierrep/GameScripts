"""
Dofus 3 - Guardado de precios de recursos
==========================================
Busca el precio de un recurso en el mercadillo y lo guarda en resources_prices.json.

Uso:
    python save_resource_buy_prices.py
"""

import json
import os
import time
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_item_prices as sip
from search_item_prices import search_item, read_prices

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ITEMS_FILE      = os.path.join(BASE_DIR, "..", "..", "Markets", "Resources", "materials_prices.json")
OMITTED_ITEMS_FILE         = os.path.join(BASE_DIR, "omitted_items.txt")
OMITTED_CATEGORIES_FILE = os.path.join(BASE_DIR, "omitted_categories.txt")


def _load_omitted_items() -> set[str]:
    if not os.path.exists(OMITTED_ITEMS_FILE):
        return set()
    with open(OMITTED_ITEMS_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _load_omitted_categories() -> set[str]:
    if not os.path.exists(OMITTED_CATEGORIES_FILE):
        return set()
    with open(OMITTED_CATEGORIES_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and raw.isdigit() else 0


CACHE_SECONDS = 3600  # 1 hora


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_fresh(item: dict) -> bool:
    ts = item.get("last_updated")
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    return age < CACHE_SECONDS


def save_resource_price(name: str, prices: dict):
    """Guarda los precios de pack de un recurso en resources_prices.json."""
    with open(ITEMS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for items in data.values():
        for item in items:
            if item["name"] == name:
                p1    = _parse_price(prices, "1")
                p10   = round(_parse_price(prices, "10")   / 10)   if _parse_price(prices, "10")   > 0 else 0
                p100  = round(_parse_price(prices, "100")  / 100)  if _parse_price(prices, "100")  > 0 else 0
                p1000 = round(_parse_price(prices, "1000") / 1000) if _parse_price(prices, "1000") > 0 else 0
                item["unit_price_x1"]    = p1
                item["unit_price_x10"]   = p10
                item["unit_price_x100"]  = p100
                item["unit_price_x1000"] = p1000
                if any(v > 0 for v in (p1, p10, p100, p1000)):
                    item["last_updated"] = _now_iso()
                break

    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name} → x1={prices['unit_price_x1']}  x10={prices['unit_price_x10']}  x100={prices['unit_price_x100']}  x1000={prices['unit_price_x1000']}")


def _find_item(name: str) -> tuple[dict, str] | tuple[None, None]:
    with open(ITEMS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for category, items in data.items():
        for item in items:
            if item["name"] == name:
                return item, category
    return None, None


def search_and_save(name: str) -> dict:
    """Busca el precio de un recurso en el mercado y lo guarda en resources_prices.json.
    Si el precio fue actualizado hace menos de 1h, o está en exceptions/omitted_categories, lo omite."""
    if name in _load_omitted_items():
        print(f"[SKIP] {name} — en lista de excepciones")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}
    item, category = _find_item(name)
    if category in _load_omitted_categories():
        print(f"[SKIP] {name} — categoría omitida ({category})")
        return {"unit_price_x1": 0, "unit_price_x10": 0, "unit_price_x100": 0, "unit_price_x1000": 0, "_skipped": True}
    if item and _is_fresh(item):
        print(f"[SKIP] {name} — actualizado hace menos de 1h")
        return {
            "unit_price_x1":    item.get("unit_price_x1", 0),
            "unit_price_x10":   item.get("unit_price_x10", 0),
            "unit_price_x100":  item.get("unit_price_x100", 0),
            "unit_price_x1000": item.get("unit_price_x1000", 0),
            "_skipped":         True,
        }
    search_item(name)
    prices = read_prices(name)
    save_resource_price(name, prices)
    return prices


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sip.load_calibration()

    # name = "Artefacto pandawushu"
    name = "Malta"
    # name = "Zafiro"
    print(f"Buscando: {name} …")
    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)

    search_and_save(name)
