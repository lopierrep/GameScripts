"""
Persistencia de precios y cálculo de lotes óptimos.

Formato de data/item_prices.json:
  { "Mercadillo": { "Categoría": { "Nombre item": {"x1": int, "x10": int, "x100": int, "x1000": int} } } }

Los valores son el precio TOTAL del lote:
  x1=395   → comprar 1 ítem cuesta 395 k
  x10=2552 → comprar un lote de 10 cuesta 2552 k  (255 k/u)
"""
import json
import math
from dataclasses import dataclass

from config.config import PRICES_FILE, LOTS, GUIJ_COST


# ── Persistencia ──────────────────────────────────────────────────────────────

def _is_old_format(raw: dict) -> bool:
    """Detecta el formato plano antiguo {item: {x1: int, ...}}."""
    if not raw:
        return False
    first = next(iter(raw.values()))
    return isinstance(first, dict) and "x1" in first


def load_prices() -> dict:
    if not PRICES_FILE.exists():
        return {}
    with open(PRICES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if _is_old_format(raw):
        return {}
    return raw


def save_prices(prices: dict):
    PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


def find_item_prices(prices: dict, item_name: str) -> dict | None:
    """Busca los precios de un item en la estructura anidada."""
    for market in prices.values():
        if not isinstance(market, dict):
            continue
        for category in market.values():
            if not isinstance(category, dict):
                continue
            if item_name in category:
                return category[item_name]
    return None


def add_item_prices(prices: dict, market: str, category: str, item: str, entry: dict):
    """Inserta o actualiza los precios de un item en la estructura anidada."""
    prices.setdefault(market, {}).setdefault(category, {})[item] = entry


def remove_item_prices(prices: dict, item_name: str) -> bool:
    """Elimina un item de la estructura anidada. Devuelve True si se eliminó."""
    for market in prices.values():
        if not isinstance(market, dict):
            continue
        for category in market.values():
            if not isinstance(category, dict):
                continue
            if item_name in category:
                del category[item_name]
                return True
    return False


# ── Cálculo de coste óptimo ───────────────────────────────────────────────────

def _available(price_dict: dict) -> dict:
    """Filtra los tamaños de lote con precio > 0."""
    return {s: p for s in LOTS if (p := price_dict.get(f"x{s}", 0)) > 0}


def _lot_strategy(qty_needed: int, available: dict) -> tuple[float, list[tuple[int, int]]]:
    """
    Estrategia greedy de lotes: para cada tamaño como "unidad mínima", rellena
    con lotes más grandes y redondea hacia arriba con ese lote.
    Devuelve (coste_mínimo, plan_de_lotes).
    """
    best_cost = float("inf")
    best_plan: list[tuple[int, int]] = []

    for min_size in sorted(available):
        remaining = qty_needed
        cost = 0
        plan: list[tuple[int, int]] = []
        for size in sorted(available, reverse=True):
            if size < min_size:
                continue
            lot_price = available[size]
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                if n > 0:
                    cost += n * lot_price
                    plan.append((size, n))
                remaining = 0
            else:
                n = remaining // size
                if n > 0:
                    cost += n * lot_price
                    plan.append((size, n))
                remaining -= n * size
        if cost < best_cost:
            best_cost = cost
            best_plan = plan

    return best_cost, best_plan


def optimal_cost(qty_needed: int, price_dict: dict) -> int:
    """Calcula el coste mínimo para comprar al menos qty_needed ítems."""
    av = _available(price_dict)
    if not av or qty_needed <= 0:
        return 0
    cost, _ = _lot_strategy(qty_needed, av)
    return int(cost) if cost != float("inf") else 0


def get_lot_plan(qty_needed: int, price_dict: dict) -> list[tuple[int, int]]:
    """Devuelve la combinación óptima de lotes como [(tamaño, n_lotes), ...]."""
    av = _available(price_dict)
    if not av or qty_needed <= 0:
        return []
    _, plan = _lot_strategy(qty_needed, av)
    return plan


# ── Guijarros ─────────────────────────────────────────────────────────────────

@dataclass
class GuijarroResult:
    code:  str
    ratio: float   # kamas por almanich


def best_guijarro(alm: int, guij_prices: dict[str, int]) -> GuijarroResult | None:
    """
    Devuelve el guijarro más rentable dado un número de almanichas.

    guij_prices: {"T": precio_kamas, "L": precio_kamas, "S": precio_kamas}
    Devuelve None si ningún guijarro tiene precio > 0.
    """
    best_ratio = 0.0
    best_code  = None

    for code, cost in GUIJ_COST.items():
        price = guij_prices.get(code, 0)
        if price == 0:
            continue
        ratio = price / cost
        if ratio > best_ratio:
            best_ratio = ratio
            best_code  = code

    if best_code is None:
        return None

    return GuijarroResult(
        code  = best_code,
        ratio = best_ratio,
    )