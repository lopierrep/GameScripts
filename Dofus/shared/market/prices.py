"""
Gestión compartida de precios de mercado.
Parseo de precios OCR, frescura, I/O de materials_prices.json,
guardado de precios de venta e ingredientes, y cálculo de lote óptimo.

Usado por Crafting, Ganadero y Almanax.
"""

import json
import math
from datetime import datetime, timezone

from shared.market.common import _parse_price, CACHE_SECONDS, LOT_STABILITY_MARGIN, SIZES

LOT_NUMS = {"x1": 1, "x10": 10, "x100": 100, "x1000": 1000}


# ── Helpers ───────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_price_fresh(ts: str | None, cache_seconds: int = CACHE_SECONDS) -> bool:
    """Devuelve True si el timestamp tiene menos de cache_seconds de antigüedad."""
    if not ts:
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
        return age < cache_seconds
    except Exception:
        return False


def sanitize_unit_prices(prices: list[int]) -> list[int]:
    """Si hay 3+ precios no-cero y alguno supera 1.5x el mínimo, reemplaza outliers."""
    non_zero = [(i, p) for i, p in enumerate(prices) if p > 0]
    if len(non_zero) < 3:
        return prices
    min_price = min(p for _, p in non_zero)
    threshold = 1.5 * min_price
    normal   = [(i, p) for i, p in non_zero if p <= threshold]
    outliers = [(i, p) for i, p in non_zero if p > threshold]
    if not outliers or not normal:
        return prices
    avg_normal = round(sum(p for _, p in normal) / len(normal))
    result = prices[:]
    for i, _ in outliers:
        result[i] = avg_normal
    return result


# ── OCR → Precios unitarios ──────────────────────────────────────────────────

def parse_selling_prices(ocr_prices: dict) -> dict[str, int]:
    """Convierte precios OCR (precios de lote) a precios unitarios de venta.
    Cadena de fallback: si x10=0 → usa x1, si x100=0 → usa x10, etc.
    Aplica sanitización de outliers."""
    x1    = _parse_price(ocr_prices, "1")
    x10   = _parse_price(ocr_prices, "10")
    x100  = _parse_price(ocr_prices, "100")
    x1000 = _parse_price(ocr_prices, "1000")

    u1    = x1
    u10   = round(x10   / 10)   if x10   > 0 else u1
    u100  = round(x100  / 100)  if x100  > 0 else u10
    u1000 = round(x1000 / 1000) if x1000 > 0 else u100

    u1, u10, u100, u1000 = sanitize_unit_prices([u1, u10, u100, u1000])
    return {"x1": u1, "x10": u10, "x100": u100, "x1000": u1000}


def parse_ingredient_prices(ocr_prices: dict) -> dict[str, int]:
    """Convierte precios OCR (precios de lote) a precios unitarios de ingredientes.
    Sin cadena de fallback: si un lote no tiene precio, queda en 0."""
    p1      = _parse_price(ocr_prices, "1")
    raw10   = _parse_price(ocr_prices, "10")
    raw100  = _parse_price(ocr_prices, "100")
    raw1000 = _parse_price(ocr_prices, "1000")
    return {
        "x1":    p1,
        "x10":   round(raw10   / 10)   if raw10   > 0 else 0,
        "x100":  round(raw100  / 100)  if raw100  > 0 else 0,
        "x1000": round(raw1000 / 1000) if raw1000 > 0 else 0,
    }


# ── I/O materials_prices.json ────────────────────────────────────────────────

def load_materials(prices_file) -> dict:
    """Carga materials_prices.json y devuelve el dict crudo."""
    with open(prices_file, encoding="utf-8") as f:
        return json.load(f)


def save_materials(materials: dict, prices_file):
    """Guarda materials_prices.json ordenando categorías por mercado."""
    sorted_data = {k: dict(sorted(v.items())) for k, v in materials.items()}
    with open(prices_file, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)


def build_item_lookup(materials: dict) -> dict[str, tuple[str, str]]:
    """Construye {item_name: (market_name, category_name)} desde materials_prices."""
    lookup = {}
    for market_name, market_data in materials.items():
        for category_name, items in market_data.items():
            for name in items:
                lookup[name] = (market_name, category_name)
    return lookup


# ── Guardado de precios ──────────────────────────────────────────────────────

def save_ingredient_price(
    name: str, ocr_prices: dict, materials: dict, lookup: dict, prices_file,
):
    """Parsea precios OCR de ingredientes y guarda en materials_prices.json."""
    val = lookup.get(name)
    if not val:
        return
    market_name, category_name = val
    entry = materials.get(market_name, {}).get(category_name, {}).get(name)
    if entry is None:
        return

    unit_prices = parse_ingredient_prices(ocr_prices)
    for size in SIZES:
        entry[size] = unit_prices[size]
    if any(v > 0 for v in unit_prices.values()):
        entry["prices_updated_at"] = now_iso()
    save_materials(materials, prices_file)


def save_selling_price(recipe_file, name: str, ocr_prices: dict):
    """Parsea precios OCR de venta y guarda en archivo de recetas.
    Solo actualiza valores no-cero (preserva precios existentes si OCR falla)."""
    unit_prices = parse_selling_prices(ocr_prices)

    with open(recipe_file, encoding="utf-8") as f:
        recipes = json.load(f)

    for recipe in recipes:
        if recipe.get("result") == name:
            for size in SIZES:
                if unit_prices[size] > 0:
                    recipe[f"unit_selling_price_{size}"] = unit_prices[size]
            recipe.pop("prices_updated_at", None)
            recipe["prices_updated_at"] = now_iso()
            break

    with open(recipe_file, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)


# ── Precio óptimo ─────────────────────────────────────────────────────────────

def cheapest_lot(prices: dict, qty: int) -> str | None:
    """Devuelve el tamaño de lote ('x1','x10','x100','x1000') que minimiza el costo total
    para adquirir `qty` unidades. None si no hay precios disponibles.

    Cuando qty >= lot_num (sin desperdicio), aplica LOT_STABILITY_MARGIN: un lote mayor
    gana si su precio no supera al lote x1 en más de ese margen, priorizando estabilidad
    de mercado sobre la diferencia mínima de precio."""
    if qty <= 0:
        return None
    best_lot = None
    best_eff = 0.0
    for size, lot_num in LOT_NUMS.items():
        p = prices.get(size, 0)
        if not p or p <= 0:
            continue
        packs    = math.ceil(qty / lot_num)
        eff_unit = packs * lot_num * p / qty
        if lot_num > 1 and qty >= lot_num and (qty % lot_num == 0):
            eff_unit /= (1 + LOT_STABILITY_MARGIN)
        if best_eff == 0.0 or eff_unit < best_eff:
            best_eff = eff_unit
            best_lot = size
    return best_lot


def cheapest_unit_price(prices: dict, qty: int) -> float:
    """Precio unitario efectivo real del lote óptimo para adquirir `qty` unidades.

    Delega la selección del lote a cheapest_lot (que aplica LOT_STABILITY_MARGIN
    para comparar), pero devuelve el costo real sin el margen de estabilidad."""
    best_size = cheapest_lot(prices, qty)
    if best_size is None:
        return 0.0
    lot_num = LOT_NUMS[best_size]
    p = prices.get(best_size, 0)
    if not p:
        return 0.0
    packs = math.ceil(qty / lot_num)
    return packs * lot_num * p / qty
