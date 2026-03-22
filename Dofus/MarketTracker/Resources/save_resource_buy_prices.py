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

import helpers.search_item_prices as sip
from helpers.search_item_prices import search_item, read_prices

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ITEMS_FILE = os.path.join(BASE_DIR, "resources_prices.json")


def _parse_price(prices: dict, pack: str) -> int:
    raw = prices.get(f"unit_price_x{pack}", "N/A")
    return int(raw) if raw not in ("N/A", "ERROR", "") and raw.isdigit() else 0


def save_resource_price(name: str, prices: dict):
    """Guarda los precios de pack de un recurso en resources_prices.json."""
    with open(ITEMS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for items in data.values():
        for item in items:
            if item["name"] == name:
                item["unit_price_x1"]    = _parse_price(prices, "1")
                item["unit_price_x10"]   = _parse_price(prices, "10")
                item["unit_price_x100"]  = _parse_price(prices, "100")
                item["unit_price_x1000"] = _parse_price(prices, "1000")
                break

    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name} → x1={prices['unit_price_x1']}  x10={prices['unit_price_x10']}  x100={prices['unit_price_x100']}  x1000={prices['unit_price_x1000']}")


def search_and_save(name: str) -> dict:
    """Busca el precio de un recurso en el mercado y lo guarda en resources_prices.json."""
    search_item(name)
    prices = read_prices(name)
    save_resource_price(name, prices)
    return prices


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sip.load_calibration()

    name = "Artefacto pandawushu"
    # name = "Zafiro"
    print(f"Buscando: {name} …")
    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)

    search_and_save(name)
