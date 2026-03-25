"""
Gestión de precios de materiales e ingredientes.
Carga/guardado de materials_prices.json, caché de frescura y cálculo de costos de crafteo.
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

from config.config import (
    CACHE_SECONDS,
    CATEGORIES_FILE,
    DATA_DIR,
    DOFUSDB_URL,
    PRICES_FILE,
    SIZES,
    UNKNOWN_KEY,
    _load_omitted_items,
    _normalize,
    _now_iso,
    _parse_price,
)


# ── Mercadillos ────────────────────────────────────────────────────────────────

def load_markets() -> dict[str, dict]:
    """Carga categories_by_market.json y materials_prices.json en una estructura combinada."""
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        all_categories = json.load(f)
    all_prices = {}
    if os.path.exists(PRICES_FILE):
        with open(PRICES_FILE, encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            all_prices = json.loads(content)
    markets = {}
    for folder, categories in all_categories.items():
        markets[folder] = {
            "categories": set(categories),
            "data": all_prices.get(folder, {}),
        }
    return markets


def build_item_lookup(markets: dict) -> dict[str, str]:
    """Devuelve {item_name: market_name} para todos los items en materials_prices.json."""
    lookup = {}
    for market_name, market in markets.items():
        for items in market["data"].values():
            for item in items:
                lookup[item["name"]] = market_name
    return lookup


def get_market_for_category(category: str, markets: dict) -> str | None:
    for market_name, market in markets.items():
        if category in market["categories"]:
            return market_name
    return None


def save_markets(markets: dict):
    all_prices = {name: dict(sorted(market["data"].items())) for name, market in markets.items()}
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(all_prices, f, ensure_ascii=False, indent=2)


def find_item_in_markets(name: str, markets: dict) -> bool:
    return any(
        any(i["name"] == name for i in items)
        for market in markets.values()
        for items in market["data"].values()
    )


# ── Caché de frescura ─────────────────────────────────────────────────────────

def _ingredient_is_fresh(name: str, markets: dict, item_lookup: dict) -> bool:
    market_name = item_lookup.get(name)
    if not market_name:
        return False
    for items in markets[market_name]["data"].values():
        for item in items:
            if item["name"] == name:
                ts = item.get("last_updated")
                if not ts:
                    return False
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
                return age < CACHE_SECONDS
    return False


# ── API dofusdb ────────────────────────────────────────────────────────────────

def fetch_category(item_name: str) -> str:
    try:
        resp = requests.get(
            f"{DOFUSDB_URL}/items",
            params={"name.es": item_name, "$limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return UNKNOWN_KEY
        type_obj = data[0].get("type", {})
        name_obj = type_obj.get("name", {})
        return name_obj.get("es", name_obj.get("en", UNKNOWN_KEY))
    except Exception:
        return UNKNOWN_KEY


# ── Guardado de precios de ingredientes ───────────────────────────────────────

def save_ingredient_price(name: str, prices: dict, markets: dict, item_lookup: dict):
    market_name = item_lookup.get(name)
    if not market_name:
        return
    market = markets[market_name]
    for items in market["data"].values():
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
    save_markets(markets)
    p = prices
    print(f"[OK] x1={p.get('unit_price_x1','N/A')}  x10={p.get('unit_price_x10','N/A')}  x100={p.get('unit_price_x100','N/A')}  x1000={p.get('unit_price_x1000','N/A')}")


# ── Catalogación de items nuevos ───────────────────────────────────────────────

def ensure_catalogued(names: set[str], markets: dict, item_lookup: dict, craftable_results: set[str]):
    """Añade a materials_prices.json los ingredientes nuevos, consultando su categoría en dofusdb."""
    uncatalogued = [
        name for name in names
        if name not in craftable_results and not find_item_in_markets(name, markets)
    ]
    if not uncatalogued:
        return

    print(f"\nConsultando categorías para {len(uncatalogued)} items nuevos…")
    for name in uncatalogued:
        category    = fetch_category(name)
        market_name = get_market_for_category(category, markets)
        if not market_name:
            print(f"  ? {name} → {category} [sin mercadillo, ignorado]")
            time.sleep(0.15)
            continue
        market = markets[market_name]
        market["data"].setdefault(category, [])
        if name not in [i["name"] for i in market["data"][category]]:
            market["data"][category].append({
                "name": name,
                "unit_price_x1": 0, "unit_price_x10": 0,
                "unit_price_x100": 0, "unit_price_x1000": 0,
            })
            market["data"][category].sort(key=lambda x: x["name"])
            item_lookup[name] = market_name
        save_markets(markets)
        print(f"  + {name} → {category} [{market_name}]")
        time.sleep(0.15)


# ── Cálculo de costos de crafteo ──────────────────────────────────────────────

def _load_file(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_pack_prices() -> dict[str, dict]:
    """Devuelve {nombre: {x1, x10, x100, x1000}} con precio UNITARIO por pack."""
    pack_prices = {}

    # Precios de todos los mercadillos
    all_markets_data = _load_file(PRICES_FILE) if os.path.exists(PRICES_FILE) else {}
    for data in all_markets_data.values():
        for items in data.values():
            for item in items:
                name = item["name"].strip()
                pack_prices[name] = {
                    size: item.get(f"unit_price_{size}", 0)
                    for size in SIZES
                }

    # Craftables usados como ingredientes: min(crafting_cost, selling_price)
    for fname in os.listdir(DATA_DIR):
        if not fname.startswith("recipes_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(DATA_DIR, fname), encoding="utf-8") as f:
            for recipe in json.load(f):
                name = recipe.get("result", "").strip()
                if not name:
                    continue
                costs = {size: recipe.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}
                sells = {size: recipe.get(f"unit_selling_price_{size}", 0) for size in SIZES}
                merged = {}
                for size in SIZES:
                    c, s = costs.get(size, 0), sells.get(size, 0)
                    if c > 0 and s > 0:
                        merged[size] = min(c, s)
                    else:
                        merged[size] = c or s
                if any(v > 0 for v in merged.values()):
                    pack_prices[name] = merged

    return pack_prices


def best_unit_price(prices: dict, pack_size: str) -> float:
    """Precio unitario mínimo entre el lote dado y sus adyacentes."""
    idx = SIZES.index(pack_size)
    candidates = SIZES[max(0, idx - 1):idx + 2]
    values = [prices[s] for s in candidates if prices.get(s, 0) > 0]
    return min(values) if values else 0


def calculate_crafting_costs(recipes: list, pack_prices: dict) -> tuple[list, set]:
    """
    Calcula unit_crafting_cost_x* para cada receta.
    Devuelve (recipes_actualizadas, ingredientes_sin_precio).
    """
    crafted_costs: dict[str, dict] = {
        r["result"]: {size: r.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}
        for r in recipes
        if any(r.get(f"unit_crafting_cost_{size}", 0) > 0 for size in SIZES)
    }

    still_missing: set[str] = set()
    exceptions = _load_omitted_items()

    for recipe in recipes:
        if recipe.get("result") in exceptions:
            continue

        def calc_cost(pack_size: str) -> tuple[float, bool]:
            cost = 0.0
            known = True
            for ing in recipe.get("ingredients", []):
                ing_name = ing["name"]
                ing_qty  = ing["quantity"]
                ing_p = best_unit_price(pack_prices.get(ing_name, {}), pack_size)
                if ing_p == 0:
                    ing_costs = crafted_costs.get(ing_name)
                    if ing_costs:
                        ing_p = best_unit_price(ing_costs, pack_size)
                if ing_p == 0:
                    known = False
                    if not any(pack_prices.get(ing_name, {}).get(s, 0) > 0 for s in SIZES):
                        still_missing.add(ing_name)
                    continue
                cost += ing_p * ing_qty
            return cost, known

        for size in SIZES:
            cost, known = calc_cost(size)
            recipe[f"unit_crafting_cost_{size}"] = round(cost) if known else 0

        crafted_costs[recipe["result"]] = {size: recipe.get(f"unit_crafting_cost_{size}", 0) for size in SIZES}

        # Timestamp solo cuando hay precio de venta Y costo de crafteo
        has_sell  = any(recipe.get(f"unit_selling_price_{s}", 0) > 0 for s in SIZES)
        has_craft = any(recipe.get(f"unit_crafting_cost_{s}", 0) > 0 for s in SIZES)
        if has_sell and has_craft:
            recipe["selling_last_updated"] = datetime.now(timezone.utc).isoformat()

    return recipes, still_missing


def save_crafting_costs(recipe_file: str, recipes: list | None = None) -> set[str]:
    """Calcula y guarda los costos de crafteo en recipe_file. Devuelve ingredientes sin precio."""
    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    subset = recipes if recipes is not None else all_recipes

    pack_prices = load_all_pack_prices()
    updated_subset, still_missing = calculate_crafting_costs(subset, pack_prices)

    if recipes is not None:
        updated_by_result = {r["result"]: r for r in updated_subset}
        for r in all_recipes:
            if r["result"] in updated_by_result:
                r.update(updated_by_result[r["result"]])
    else:
        all_recipes = updated_subset

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(all_recipes, f, ensure_ascii=False, indent=2)

    return still_missing
