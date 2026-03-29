"""
Scanner unificado de precios de mercadillo.
Gestiona: agrupación por mercadillo, frescura, items ignorados,
items manuales, missing file, persistencia batch y mensajes de progreso.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from shared.market.common import SIZES
from shared.market.prices import (
    is_price_fresh,
    load_materials,
    now_iso,
    parse_ingredient_prices,
    parse_selling_prices,
    save_materials,
)
from shared.market.scanner import MarketScanner
from shared.market.search_item_prices import read_prices, search_item

_SHARED      = Path(__file__).resolve().parent.parent   # shared/
MISSING_FILE = _SHARED / "data" / "missing_scan.json"
_PRICES_FILE = str(_SHARED / "data" / "materials_prices.json")


@dataclass
class ScanItem:
    name:               str
    market:             str
    category:           str
    type:               str   # "result" | "ingredient"
    prices_updated_at:  str | None = None
    has_price:          bool = False
    recipe_file:        str | None = None   # solo para type="result"


def _price_found(r: dict) -> bool:
    """True si el dict tiene algún precio válido, o si fue skipped (item fresco)."""
    if r.get("_skipped"):
        return True
    return any(v not in ("N/A", "", "0", 0) for k, v in r.items() if k != "_skipped")


# ── Batch save ───────────────────────────────────────────────────────────────

def _save_ingredients(accumulated: dict):
    """Guarda todos los precios de ingredientes en materials_prices.json de una vez."""
    if not accumulated:
        return
    materials = load_materials(_PRICES_FILE)
    for name, info in accumulated.items():
        market   = info["market"]
        category = info["category"]
        prices   = info["prices"]
        entry = materials.get(market, {}).get(category, {}).get(name)
        if entry is None:
            continue
        for size in SIZES:
            entry[size] = prices[size]
        if any(v > 0 for v in prices.values()):
            entry["prices_updated_at"] = now_iso()
    save_materials(materials, _PRICES_FILE)


def _save_results(accumulated: dict):
    """Guarda todos los precios de venta agrupados por recipe_file de una vez."""
    if not accumulated:
        return
    # Agrupar por archivo
    by_file: dict[str, list] = {}
    for name, info in accumulated.items():
        f = info["recipe_file"]
        if f:
            by_file.setdefault(f, []).append((name, info["prices"], info.get("exceeded", set())))

    for recipe_file, entries in by_file.items():
        with open(recipe_file, encoding="utf-8") as f:
            recipes = json.load(f)

        updated_names = {name for name, _, _ in entries}
        entry_map = {name: (prices, exceeded) for name, prices, exceeded in entries}

        for recipe in recipes:
            result = recipe.get("result")
            if result not in updated_names:
                continue
            prices, exceeded = entry_map[result]
            for size in SIZES:
                if prices[size] > 0:
                    recipe[f"unit_selling_price_{size}"] = prices[size]
            for size in exceeded:
                recipe[f"unit_crafting_cost_{size}"] = 0
            recipe.pop("prices_updated_at", None)

        with open(recipe_file, "w", encoding="utf-8") as f:
            json.dump(recipes, f, ensure_ascii=False, indent=2)


# ── Scanner principal ────────────────────────────────────────────────────────

def scan_prices(
    items:               list,
    press_esc:           Callable,
    is_stopped:          Callable,
    on_progress:         Callable,
    on_market_switch:    Callable,
    *,
    init_cal:            Callable | None = None,
    delay:               float = 0.3,
    countdown:           int   = 3,
    fresh_seconds:       int   = 7200,
    ignored_items:       set | None = None,
    ignored_categories:  set | None = None,
    manual_items:        set | None = None,
    on_manual_item:      Callable | None = None,
    on_item_done:        Callable | None = None,
    filter_selling:      Callable | None = None,
) -> dict:
    """
    Escanea precios de una lista de ScanItem en el mercadillo.

    El scanner gestiona todo el ciclo: búsqueda OCR, parseo, acumulación
    en memoria y guardado batch al final.

    filter_selling: fn(unit_prices) -> (filtered, exceeded_sizes) opcional.
                    Crafting pasa filter_lot_prices para filtrar lotes caros.

    Returns:
        {item_name: parsed_prices_dict}
    """
    # 1. Filtrar ignorados
    active = [
        item for item in items
        if (ignored_items is None or item.name not in ignored_items)
        and (ignored_categories is None or item.category not in ignored_categories)
    ]

    # 2. Filtrar frescos: solo saltarse si tiene precio Y el timestamp es reciente
    to_scan = [
        item for item in active
        if not (item.has_price and is_price_fresh(item.prices_updated_at, fresh_seconds))
    ]

    # 3. Separar auto/manual
    manual_set  = set(manual_items or [])
    auto_list   = [item for item in to_scan if item.name not in manual_set]
    manual_list = [item for item in to_scan if item.name in manual_set]

    # 4. Agrupar por mercadillo (preserva orden de inserción)
    groups: dict = {}
    for item in auto_list:
        groups.setdefault(item.market, {"auto": [], "manual": []})["auto"].append(item)
    for item in manual_list:
        groups.setdefault(item.market, {"auto": [], "manual": []})["manual"].append(item)

    if init_cal:
        init_cal()

    results: dict            = {}   # {name: parsed_prices}
    missing: dict            = {}
    acc_ingredients: dict    = {}   # {name: {market, category, prices}}
    acc_results: dict        = {}   # {name: {recipe_file, prices, exceeded}}

    name_to_item: dict = {item.name: item for item in auto_list}
    base_scanner = MarketScanner(press_esc=press_esc, delay=delay, countdown=countdown)

    def _parse_and_accumulate(item: ScanItem, raw: dict):
        """Parsea precios OCR y acumula en el dict correspondiente."""
        if item.type == "ingredient":
            parsed = parse_ingredient_prices(raw)
            acc_ingredients[item.name] = {
                "market": item.market, "category": item.category, "prices": parsed,
            }
        else:
            parsed = parse_selling_prices(raw)
            exceeded = set()
            if filter_selling:
                parsed, exceeded = filter_selling(parsed)
            acc_results[item.name] = {
                "recipe_file": item.recipe_file, "prices": parsed, "exceeded": exceeded,
            }
        return parsed

    try:
        # 5. Loop por mercadillo
        for market_name, group in groups.items():
            if is_stopped():
                break
            auto   = group["auto"]
            manual = group["manual"]

            if not on_market_switch(market_name, len(auto) + len(manual)):
                break

            # 5a. Items automáticos vía base scanner (countdown integrado)
            if auto and not is_stopped():
                def _process(name: str, _lookup=name_to_item) -> dict:
                    item = _lookup[name]
                    search_item(name)
                    raw = read_prices(name, stop_flag=is_stopped)
                    parsed = _parse_and_accumulate(item, raw)
                    if not _price_found(parsed):
                        raise ValueError("sin precios")
                    results[name] = parsed
                    if on_item_done:
                        on_item_done()
                    return parsed

                base_scanner.scan(
                    items_by_market  = {market_name: [item.name for item in auto]},
                    is_stopped       = is_stopped,
                    on_progress      = on_progress,
                    on_market_switch = lambda *_: True,
                    process_item     = _process,
                )

            # 5b. Items manuales
            for idx, item in enumerate(manual, 1):
                if is_stopped():
                    break
                raw = on_manual_item(item, idx, len(manual)) if on_manual_item else None
                if raw is not None:
                    parsed = _parse_and_accumulate(item, raw)
                    results[item.name] = parsed
                else:
                    missing.setdefault(market_name, {}).setdefault(item.category, []).append(item.name)
                if on_item_done:
                    on_item_done()

    finally:
        # 6. BATCH SAVE — siempre guardar datos parciales
        _save_ingredients(acc_ingredients)
        _save_results(acc_results)

    # 7. Registrar auto items sin precio en missing
    for item in auto_list:
        if item.name not in results or not _price_found(results[item.name]):
            missing.setdefault(item.market, {}).setdefault(item.category, []).append(item.name)

    # 8. Escribir missing file
    MISSING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MISSING_FILE, "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)

    # 9. Mensaje final de resumen
    n_total   = len(auto_list) + len(manual_list)
    n_ok      = sum(1 for r in results.values() if _price_found(r))
    n_missing = sum(len(v) for cats in missing.values() for v in cats.values())
    if n_missing:
        on_progress(f"✓ {n_ok}/{n_total} precios actualizados, {n_missing} sin precio")
    else:
        on_progress(f"✓ {n_ok}/{n_total} precios actualizados")

    return results
