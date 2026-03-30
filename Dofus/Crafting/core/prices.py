"""
Gestión de precios de materiales e ingredientes.
Carga/guardado de materials_prices.json, caché de frescura y cálculo de costos de crafteo.
"""

import json
import os
import time
from config.config import (
    CATEGORIES_FILE,
    MIN_LOT_ROI,
    PRICES_FILE,
    SIZES,
)
from shared.market.prices import (
    LOT_NUMS as _LOT_NUMS,
    cheapest_lot,
    cheapest_unit_price,
    is_price_fresh,
    parse_ingredient_prices,
)
from shared.market.crafting_costs import (
    calculate_crafting_costs,
    get_recipe_files,
    load_all_pack_prices,
    save_crafting_costs,
)
from utils.market import _now_iso, filter_lot_prices, net_sell_price



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


def build_item_lookup(markets: dict) -> dict[str, tuple[str, str]]:
    """Devuelve {item_name: (market_name, category_name)} para todos los items en materials_prices.json."""
    lookup = {}
    for market_name, market in markets.items():
        for category_name, category in market["data"].items():
            for name in category:
                lookup[name] = (market_name, category_name)
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
    lookup_val = item_lookup.get(name)
    if not lookup_val:
        return False
    market_name, category_name = lookup_val
    category = markets[market_name]["data"].get(category_name, {})
    if name not in category:
        return False
    return is_price_fresh(category[name].get("prices_updated_at"))


# ── API dofusdb ────────────────────────────────────────────────────────────────

from shared.market.common import fetch_category  # noqa: E402


# ── Guardado de precios de ingredientes ───────────────────────────────────────

def save_ingredient_price(name: str, prices: dict, markets: dict, item_lookup: dict):
    lookup_val = item_lookup.get(name)
    if not lookup_val:
        return
    market_name, category_name = lookup_val
    category = markets[market_name]["data"].get(category_name, {})
    if name in category:
        unit_prices = parse_ingredient_prices(prices)
        entry = category[name]
        for size in SIZES:
            entry[size] = unit_prices[size]
        if any(v > 0 for v in unit_prices.values()):
            entry["prices_updated_at"] = _now_iso()
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
            item_lookup[name] = (market_name, category)
        save_markets(markets)
        print(f"  + {name} → {category} [{market_name}]")
        time.sleep(0.15)






def load_raw_market_prices() -> tuple[dict, dict]:
    """
    Lee PRICES_FILE y devuelve (raw_market_prices, ing_updated_at).
    raw_market_prices : {name: {"1": price, ...}} — solo precios > 0
    ing_updated_at  : {name: iso_str}
    """
    raw_market_prices: dict = {}
    ing_updated_at: dict  = {}
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
                        if pd.get("prices_updated_at"):
                            ing_updated_at[name] = pd["prices_updated_at"]
    except Exception:
        pass
    return raw_market_prices, ing_updated_at







# ── Pre-cómputo de datos de display ───────────────────────────────────────────

def _enrich_recipe(recipe: dict, pack_prices: dict, craftable_map: dict, force_x1: bool = False):
    """Calcula y agrega profit_x* y display al dict de receta (in-place)."""
    raw_sells = {size: recipe.get(f"unit_selling_price_{size}", 0) or 0 for size in SIZES}
    filtered_sells, exceeded = filter_lot_prices(raw_sells)
    for size in SIZES:
        s = filtered_sells[size]
        recipe[f"unit_selling_price_{size}"] = s
        if size in exceeded:
            # Mayor al limite establecido: precio de venta, costo de crafteo y profit ignorados para este lote
            recipe[f"unit_crafting_cost_{size}"] = 0
            recipe[f"profit_{size}"] = 0
        elif s == 0:
            # Sin precio de venta para este lote: el costo de crafteo y profit no son relevantes
            recipe[f"unit_crafting_cost_{size}"] = 0
            recipe[f"profit_{size}"] = 0
        else:
            c = recipe.get(f"unit_crafting_cost_{size}", 0) or 0
            if c > 0:
                lot_num    = _LOT_NUMS[size]
                net_total  = net_sell_price(s * lot_num)
                recipe[f"profit_{size}"] = round(net_total / lot_num - c)
            else:
                recipe[f"profit_{size}"] = 0

    # Determinar mejor lote
    if force_x1:
        best_size = "x1" if recipe.get("profit_x1", 0) != 0 else None
    else:
        # Prefiere el lote más grande cuyo ROI (profit/crafting_cost) supere MIN_LOT_ROI
        best_size = None
        for size in reversed(SIZES):
            profit = recipe.get(f"profit_{size}", 0) or 0
            cost   = recipe.get(f"unit_crafting_cost_{size}", 0) or 0
            if cost > 0 and profit / cost >= MIN_LOT_ROI:
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

        # Precio de display: para ingredientes comprados se muestra el precio de mercado
        # real en el lote recomendado. El total es cantidad_receta × precio_unitario.
        if buy_or_craft != "Craft" and buy_lot:
            market_price  = pack_prices.get(ing_name, {}).get(buy_lot) or None
            display_price = market_price
            display_total = round(ing_qty * lot_num * market_price) if market_price else None
        else:
            display_price = round(unit_price) if unit_price else None
            display_total = round(unit_price * ing_qty * lot_num) if unit_price else None

        ing["unit_price"]   = display_price
        ing["buy_lot"]      = buy_lot or "—"
        ing["buy_or_craft"] = buy_or_craft
        ing["total"]        = display_total
    # Mover prices_updated_at al final del dict
    ts = recipe.pop("prices_updated_at", None)
    if ts is not None:
        recipe["prices_updated_at"] = ts


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
    from config.config import EQUIPMENT_PROFESSIONS
    profession = os.path.basename(recipe_file).replace("recipes_", "").replace(".json", "")
    force_x1 = profession in EQUIPMENT_PROFESSIONS

    with open(recipe_file, encoding="utf-8") as f:
        all_recipes = json.load(f)

    target_set = {r["result"] for r in recipes_filter(all_recipes)} if recipes_filter else None

    for recipe in all_recipes:
        if target_set is None or recipe.get("result") in target_set:
            _enrich_recipe(recipe, pack_prices, craftable_map, force_x1=force_x1)

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(all_recipes, f, ensure_ascii=False, indent=2)


# ── Construcción de filas para la UI ──────────────────────────────────────────

def build_table_rows(
    recipes: list,
    craftable_map: dict,
    raw_market_prices: dict,
    ing_updated_at: dict,
) -> list:
    """
    Construye las filas de la tabla UI leyendo datos pre-calculados del JSON.
    No realiza cálculos de precios.
    """
    rows = []

    for r in recipes:
        best_size = r.get("best_lot") or None
        best_lot = best_craft = best_sell = best_profit = best_profit_total = None
        if best_size:
            best_lot          = best_size
            best_craft        = r.get(f"unit_crafting_cost_{best_size}")
            best_sell         = r.get(f"unit_selling_price_{best_size}")
            best_profit       = r.get(f"profit_{best_size}")
            best_profit_total = round(best_profit * _LOT_NUMS[best_size]) if best_profit else None

        lot_num     = _LOT_NUMS.get(best_size, 1)
        craft_total = best_craft * lot_num if best_craft else None
        sell_total  = best_sell  * lot_num if best_sell  else None
        def _display_price_total(name, buy_lot, buy_or_craft, qty, lot_num_recipe):
            """Precio de mercado real y total exacto del lote para ingredientes comprados."""
            if buy_or_craft != "Craft" and buy_lot and buy_lot != "—":
                lot_key  = buy_lot[1:]  # "x100" → "100"
                market_p = raw_market_prices.get(name, {}).get(lot_key)
                if market_p:
                    return market_p, qty * lot_num_recipe * market_p
            return None, None

        ingredients = []
        for ing in r.get("ingredients", []):
            ing_name     = ing["name"]
            buy_or_craft = ing.get("buy_or_craft")
            buy_lot      = ing.get("buy_lot", "—")

            dp, dt = _display_price_total(ing_name, buy_lot, buy_or_craft, ing["quantity"], lot_num)
            unit_price_disp = dp if dp is not None else ing.get("unit_price")
            total_disp      = dt if dt is not None else ing.get("total")

            # Sub-ingredientes desde el craftable_map (datos ya enriquecidos)
            sub_ingredients = []
            if buy_or_craft == "Craft":
                for sub_ing in craftable_map.get(ing_name, {}).get("ingredients", []):
                    sub_name     = sub_ing["name"]
                    sub_buy_lot  = sub_ing.get("buy_lot", "—")
                    sub_boc      = sub_ing.get("buy_or_craft")
                    sdp, sdt = _display_price_total(sub_name, sub_buy_lot, sub_boc, sub_ing["quantity"], lot_num)
                    sub_ingredients.append({
                        "name":              sub_name,
                        "quantity":          sub_ing["quantity"],
                        "sell_size":         lot_num,
                        "unit_price":        sdp if sdp is not None else sub_ing.get("unit_price"),
                        "buy_lot":           sub_buy_lot,
                        "buy_or_craft":      sub_boc,
                        "total":             sdt if sdt is not None else sub_ing.get("total"),
                        "lot_prices":        raw_market_prices.get(sub_name, {}),
                        "prices_updated_at": ing_updated_at.get(sub_name, ""),
                        "sub_ingredients":   [],
                    })

            ingredients.append({
                "name":              ing_name,
                "quantity":          ing["quantity"],
                "sell_size":         lot_num,
                "unit_price":        unit_price_disp,
                "buy_lot":           buy_lot,
                "buy_or_craft":      buy_or_craft,
                "total":             total_disp,
                "lot_prices":        raw_market_prices.get(ing_name, {}),
                "prices_updated_at": ing_updated_at.get(ing_name, ""),
                "sub_ingredients":   sub_ingredients,
            })

        rows.append({
            "result":       r.get("result", ""),
            "level":        r.get("level", ""),
            "best_lot":     best_lot or "—",
            "craft_cost":   craft_total,
            "sell_price":   sell_total,
            "profit":       best_profit,
            "profit_total": best_profit_total,
            "updated":      r.get("prices_updated_at", ""),
            "ingredients":  ingredients,
        })

    return rows
