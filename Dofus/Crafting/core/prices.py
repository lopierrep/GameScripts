"""
Gestión de precios de materiales e ingredientes.
Carga/guardado de materials_prices.json, caché de frescura y cálculo de costos de crafteo.
"""

import json
import math
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
    _load_omitted_recipes,
    _normalize,
    _now_iso,
    _parse_price,
    net_sell_price,
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
        for category in market["data"].values():
            for name in category:
                lookup[name] = market_name
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
        name in category
        for market in markets.values()
        for category in market["data"].values()
    )


# ── Caché de frescura ─────────────────────────────────────────────────────────

def _ingredient_is_fresh(name: str, markets: dict, item_lookup: dict) -> bool:
    market_name = item_lookup.get(name)
    if not market_name:
        return False
    for category in markets[market_name]["data"].values():
        if name in category:
            ts = category[name].get("last_updated")
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
    for category in market["data"].values():
        if name in category:
            p1    = _parse_price(prices, "1")
            p10   = round(_parse_price(prices, "10")   / 10)   if _parse_price(prices, "10")   > 0 else 0
            p100  = round(_parse_price(prices, "100")  / 100)  if _parse_price(prices, "100")  > 0 else 0
            p1000 = round(_parse_price(prices, "1000") / 1000) if _parse_price(prices, "1000") > 0 else 0
            entry = category[name]
            entry["x1"]    = p1
            entry["x10"]   = p10
            entry["x100"]  = p100
            entry["x1000"] = p1000
            if any(v > 0 for v in (p1, p10, p100, p1000)):
                entry["last_updated"] = _now_iso()
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
        market["data"].setdefault(category, {})
        if name not in market["data"][category]:
            market["data"][category][name] = {"x1": 0, "x10": 0, "x100": 0, "x1000": 0}
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
        for category in data.values():
            for name, pd in category.items():
                pack_prices[name] = {size: pd.get(size, 0) for size in SIZES}

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


def load_raw_market_prices() -> tuple[dict, dict]:
    """
    Lee PRICES_FILE y devuelve (raw_market_prices, ing_last_updated).
    raw_market_prices : {name: {"1": price, ...}} — solo precios > 0
    ing_last_updated  : {name: iso_str}
    """
    raw_market_prices: dict = {}
    ing_last_updated: dict  = {}
    try:
        if os.path.exists(PRICES_FILE):
            with open(PRICES_FILE, encoding="utf-8") as f:
                prices_raw = json.load(f)
            for market_data in prices_raw.values():
                for category in market_data.values():
                    for name, pd in category.items():
                        if not isinstance(pd, dict):
                            continue
                        lot_prices = {
                            size: int(p)
                            for size in ("1", "10", "100", "1000")
                            if (p := pd.get(f"x{size}", 0)) and int(p) > 0
                        }
                        if lot_prices:
                            raw_market_prices[name] = lot_prices
                        if pd.get("last_updated"):
                            ing_last_updated[name] = pd["last_updated"]
    except Exception:
        pass
    return raw_market_prices, ing_last_updated


def best_unit_price(prices: dict, pack_size: str) -> float:
    """Precio unitario mínimo entre el lote dado y sus adyacentes."""
    idx = SIZES.index(pack_size)
    candidates = SIZES[max(0, idx - 1):idx + 2]
    values = [prices[s] for s in candidates if prices.get(s, 0) > 0]
    return min(values) if values else 0


_LOT_NUMS = {"x1": 1, "x10": 10, "x100": 100, "x1000": 1000}


def cheapest_lot(prices: dict, qty: int) -> str | None:
    """Devuelve el tamaño de lote ('x1','x10','x100','x1000') que minimiza el costo total
    para adquirir `qty` unidades. None si no hay precios disponibles."""
    if qty <= 0:
        return None
    best_lot = None
    best_eff = 0.0
    for size, lot_num in _LOT_NUMS.items():
        p = prices.get(size, 0)
        if not p or p <= 0:
            continue
        eff_unit = math.ceil(qty / lot_num) * lot_num * p / qty
        if best_eff == 0.0 or eff_unit < best_eff:
            best_eff = eff_unit
            best_lot = size
    return best_lot


def cheapest_unit_price(prices: dict, qty: int) -> float:
    """
    Precio unitario efectivo más barato para adquirir `qty` unidades.

    Considera todos los tamaños de lote disponibles y elige el que minimiza
    el costo total real (incluyendo unidades sobrantes del último pack).
    Por ejemplo: necesitar 200u con x100 a 45u → compras 2 packs = 9000u → 45u/u.
                 necesitar 150u con x100 a 45u → compras 2 packs = 9000u → 60u/u efectivo.
    """
    if qty <= 0:
        return 0.0
    best_eff = 0.0
    for size, lot_num in _LOT_NUMS.items():
        p = prices.get(size, 0)
        if not p or p <= 0:
            continue
        packs      = math.ceil(qty / lot_num)
        total_cost = packs * lot_num * p
        eff_unit   = total_cost / qty
        if best_eff == 0.0 or eff_unit < best_eff:
            best_eff = eff_unit
    return best_eff


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
    exceptions = _load_omitted_recipes()

    for recipe in recipes:
        if recipe.get("result") in exceptions:
            continue

        def calc_cost(pack_size: str) -> tuple[float, bool]:
            lot_num = _LOT_NUMS[pack_size]
            cost = 0.0
            known = True
            for ing in recipe.get("ingredients", []):
                ing_name  = ing["name"]
                ing_qty   = ing["quantity"]
                total_qty = ing_qty * lot_num
                ing_p = cheapest_unit_price(pack_prices.get(ing_name, {}), total_qty)
                if ing_p == 0:
                    ing_costs = crafted_costs.get(ing_name)
                    if ing_costs:
                        ing_p = cheapest_unit_price(ing_costs, total_qty)
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


# ── Pre-cómputo de datos de display ───────────────────────────────────────────

def _enrich_recipe(recipe: dict, pack_prices: dict, craftable_map: dict):
    """Calcula y agrega profit_x* y display al dict de receta (in-place)."""
    _MAX = 1_500_000

    for size in SIZES:
        s = recipe.get(f"unit_selling_price_{size}", 0) or 0
        if s * _LOT_NUMS[size] > _MAX:
            # Mayor al limite establecido: precio de venta, costo de crafteo y profit ignorados para este lote
            recipe[f"unit_selling_price_{size}"] = 0
            recipe[f"unit_crafting_cost_{size}"] = 0
            recipe[f"profit_{size}"] = 0
        elif s == 0:
            # Sin precio de venta para este lote: el costo de crafteo y profit no son relevantes
            recipe[f"unit_crafting_cost_{size}"] = 0
            recipe[f"profit_{size}"] = 0
        else:
            c = recipe.get(f"unit_crafting_cost_{size}", 0) or 0
            recipe[f"profit_{size}"] = round(net_sell_price(s) - c) if c > 0 else 0

    # Determinar mejor lote con tolerancia por defecto (5%)
    valid_profits = {s: recipe[f"profit_{s}"] for s in SIZES if recipe.get(f"profit_{s}", 0) != 0}
    best_size = None
    if valid_profits:
        max_profit = max(valid_profits.values())
        threshold  = max_profit - abs(max_profit) * 0.05
        for size in reversed(SIZES):
            if valid_profits.get(size, float("-inf")) >= threshold:
                best_size = size
                break
    recipe["best_lot"] = best_size or ""

    # Datos de display de ingredientes solo para el mejor lote
    lot_num = _LOT_NUMS.get(best_size, 1)
    for ing in recipe.get("ingredients", []):
        ing_name  = ing["name"]
        ing_qty   = ing["quantity"]
        total_qty = ing_qty * lot_num

        unit_price = cheapest_unit_price(pack_prices.get(ing_name, {}), total_qty) or None
        buy_lot    = cheapest_lot(pack_prices.get(ing_name, {}), total_qty)

        ing_recipe   = craftable_map.get(ing_name)
        buy_or_craft = None
        if ing_recipe:
            craft_cost = cheapest_unit_price(
                {s: ing_recipe.get(f"unit_crafting_cost_{s}", 0) for s in SIZES}, total_qty)
            s_sell = cheapest_unit_price(
                {s: ing_recipe.get(f"unit_selling_price_{s}", 0) for s in SIZES}, total_qty)
            if craft_cost > 0 or s_sell > 0:
                buy_or_craft = "Craft" if craft_cost > 0 and (s_sell == 0 or craft_cost <= s_sell) else "Buy"
            if buy_or_craft == "Craft" and craft_cost > 0:
                unit_price = craft_cost
            elif unit_price is None and craft_cost > 0:
                unit_price = craft_cost
                buy_or_craft = "Craft"

        ing["unit_price"]   = round(unit_price) if unit_price else None
        ing["buy_lot"]      = buy_lot or "—"
        ing["buy_or_craft"] = buy_or_craft
        ing["total"]        = round(unit_price * ing_qty * lot_num) if unit_price else None
        ing.pop("display", None)  # eliminar estructura vieja si existía

    recipe.pop("display", None)  # eliminar campo antiguo si existía

    # Mover selling_last_updated al final del dict
    ts = recipe.pop("selling_last_updated", None)
    if ts is not None:
        recipe["selling_last_updated"] = ts


def compute_and_save_display_data(
    recipe_file: str,
    pack_prices: dict,
    craftable_map: dict,
    recipes_filter=None,
):
    """
    Calcula y guarda profit_x* y display para cada receta en recipe_file.
    Debe llamarse DESPUÉS de save_crafting_costs (los costos deben estar guardados).
    """
    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    if recipes_filter:
        subset_results = {r["result"] for r in recipes_filter(all_recipes)}
    else:
        subset_results = None

    for recipe in all_recipes:
        if subset_results and recipe.get("result") not in subset_results:
            continue
        _enrich_recipe(recipe, pack_prices, craftable_map)

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(all_recipes, f, ensure_ascii=False, indent=2)


# ── Construcción de filas para la UI ──────────────────────────────────────────

def build_table_rows(
    recipes: list,
    craftable_map: dict,
    raw_market_prices: dict,
    ing_last_updated: dict,
    tolerance: float = 0.05,
) -> list:
    """
    Construye las filas de la tabla UI leyendo datos pre-calculados del JSON.
    No realiza cálculos de precios: solo selecciona el mejor lote con tolerancia
    y enriquece con lot_prices / last_updated desde los precios de mercado.
    """
    rows = []

    for r in recipes:
        # Selección del mejor lote usando profits pre-calculados + tolerancia
        valid_profits = {s: r.get(f"profit_{s}", 0) for s in SIZES if r.get(f"profit_{s}", 0) != 0}

        best_size = best_lot = best_craft = best_sell = best_profit = best_profit_total = None
        if valid_profits:
            max_profit = max(valid_profits.values())
            threshold  = max_profit - abs(max_profit) * tolerance
            for size in reversed(SIZES):
                if valid_profits.get(size, float("-inf")) >= threshold:
                    best_size         = size
                    best_lot          = size
                    best_craft        = r.get(f"unit_crafting_cost_{size}")
                    best_sell         = r.get(f"unit_selling_price_{size}")
                    best_profit       = valid_profits[size]
                    best_profit_total = round(best_profit * int(size[1:]))
                    break

        lot_num     = int(best_size[1:]) if best_size else 1
        craft_total = best_craft * lot_num if best_craft else None
        sell_total  = best_sell  * lot_num if best_sell  else None
        ingredients = []
        for ing in r.get("ingredients", []):
            ing_name     = ing["name"]
            buy_or_craft = ing.get("buy_or_craft")

            # Sub-ingredientes desde el craftable_map (datos ya enriquecidos)
            sub_ingredients = []
            if buy_or_craft == "Craft":
                for sub_ing in craftable_map.get(ing_name, {}).get("ingredients", []):
                    sub_name = sub_ing["name"]
                    sub_ingredients.append({
                        "name":            sub_name,
                        "quantity":        sub_ing["quantity"],
                        "sell_size":       lot_num,
                        "unit_price":      sub_ing.get("unit_price"),
                        "buy_lot":         sub_ing.get("buy_lot", "—"),
                        "buy_or_craft":    sub_ing.get("buy_or_craft"),
                        "total":           sub_ing.get("total"),
                        "lot_prices":      raw_market_prices.get(sub_name, {}),
                        "last_updated":    ing_last_updated.get(sub_name, ""),
                        "sub_ingredients": [],
                    })

            ingredients.append({
                "name":            ing_name,
                "quantity":        ing["quantity"],
                "sell_size":       lot_num,
                "unit_price":      ing.get("unit_price"),
                "buy_lot":         ing.get("buy_lot", "—"),
                "buy_or_craft":    buy_or_craft,
                "total":           ing.get("total"),
                "lot_prices":      raw_market_prices.get(ing_name, {}),
                "last_updated":    ing_last_updated.get(ing_name, ""),
                "sub_ingredients": sub_ingredients,
            })

        rows.append({
            "result":       r.get("result", ""),
            "level":        r.get("level", ""),
            "best_lot":     best_lot or "—",
            "craft_cost":   craft_total,
            "sell_price":   sell_total,
            "profit":       best_profit,
            "profit_total": best_profit_total,
            "updated":      r.get("selling_last_updated", ""),
            "ingredients":  ingredients,
        })

    return rows
