"""
Persistencia de precios y cálculo de lotes óptimos.

Formato de data/item_prices.json:
  { "Nombre item": {"x1": int, "x10": int, "x100": int, "x1000": int} }

Los valores son el precio TOTAL del lote:
  x1=395   → comprar 1 ítem cuesta 395 k
  x10=2552 → comprar un lote de 10 cuesta 2552 k  (255 k/u)
"""
import json
import math
from dataclasses import dataclass

from .models import PRICES_FILE, LOTS, GUIJ_COST


# ── Persistencia ──────────────────────────────────────────────────────────────

def _normalize_entry(v) -> dict:
    """Compatibilidad hacia atrás: convierte entradas antiguas (int) al formato dict."""
    if isinstance(v, int):
        return {"x1": v, "x10": 0, "x100": 0, "x1000": 0}
    return v


def load_prices() -> dict:
    if PRICES_FILE.exists():
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: _normalize_entry(v) for k, v in raw.items()}
    return {}


def save_prices(prices: dict):
    PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


# ── Cálculo de coste óptimo ───────────────────────────────────────────────────

def optimal_cost(qty_needed: int, price_dict: dict) -> int:
    """
    Calcula el coste mínimo para comprar al menos qty_needed ítems.

    Estrategia: para cada tamaño de lote como "unidad mínima", rellena
    con lotes más grandes (greedy) y redondea hacia arriba con ese lote.
    Toma el mínimo de todas las estrategias.
    """
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return 0

    best = float("inf")
    for min_size in sorted(available):
        remaining = qty_needed
        cost = 0
        for size in sorted(available, reverse=True):
            if size < min_size:
                continue
            lot_price = available[size]
            if size == min_size:
                n = math.ceil(remaining / size) if remaining > 0 else 0
                cost += n * lot_price
                remaining = 0
            else:
                n = remaining // size
                cost += n * lot_price
                remaining -= n * size
        best = min(best, cost)

    return int(best) if best != float("inf") else 0


def get_lot_plan(qty_needed: int, price_dict: dict) -> list[tuple[int, int]]:
    """
    Devuelve la combinación óptima de lotes como [(tamaño, n_lotes), ...].
    Misma estrategia que optimal_cost pero retorna el plan en vez del coste.
    """
    available = {s: price_dict.get(f"x{s}", 0) for s in LOTS}
    available = {s: p for s, p in available.items() if p > 0}
    if not available or qty_needed <= 0:
        return []

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

    return best_plan


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