"""
Analiza cuál es el carburante más eficiente (recarga/precio) para cada tope de indicador.
Considera tanto precio de compra en mercado como costo de crafteo.
"""

import json
import math
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent          # Ganadero/
DATA_DIR = ROOT_DIR / "data"
RECIPES_FILE = ROOT_DIR.parent / "Crafting" / "data" / "recipes_ganadero.json"

with open(DATA_DIR / "game_data.json", encoding="utf-8") as _f:
    _GD = json.load(_f)

INDICADORES = [i["nombre"] for i in _GD["cercado"]["indicadores"]]
TOPES = [r["max"] for r in _GD["cercado"]["rangos_consumo"]]
MONTURAS_POR_CERCADO = _GD["cercado"]["capacidad_monturas"]
TAMANIO_MAP = {t["nivel_resto"]: (t["nombre"], t["recarga"])
               for t in _GD["carburantes"]["tamanios"]}

_TOPES_POR_NIVEL = _GD["carburantes"]["topes_por_nivel"]

COSTOS_DRAGOPAVO = {}
for _ind in _GD["cercado"]["indicadores"]:
    if "estadistica" in _ind:
        COSTOS_DRAGOPAVO[_ind["nombre"]] = (
            _GD["dragopavo"]["estadisticas"][_ind["estadistica"]]["max"])
    elif _ind.get("efecto") == "xp":
        COSTOS_DRAGOPAVO[_ind["nombre"]] = _GD["dragopavo"]["xp_para_nivel_maximo"]

LOTES = ["x10", "x100"]

# Umbral: si el costo total supera este valor, se marca como caro
UMBRAL_COSTO_TOTAL = 10000


def _tope_de_nivel(level):
    for t in _TOPES_POR_NIVEL:
        if t["nivel_min"] <= level <= t["nivel_max"]:
            return t["tope_indicador"]
    return None


def _get_indicador(nombre):
    for ind in INDICADORES:
        if ind in nombre.lower():
            return ind
    return None


def cargar_carburantes():
    """Lee directamente de recipes_ganadero.json (fuente actualizada)."""
    with open(RECIPES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for r in data:
        if r.get("category") != "Carburante de cercados":
            continue
        bl = r["level"] % 50 if r["level"] % 50 != 0 else 50
        tam, cantidad = TAMANIO_MAP.get(bl, ("?", 0))
        result.append({
            "id": r["id"],
            "nombre": r["result"],
            "level": r["level"],
            "indicador": _get_indicador(r["result"]),
            "tamanio": tam,
            "cantidad_recarga": cantidad,
            "tope_indicador": _tope_de_nivel(r["level"]),
            "precio_compra_x1":  r.get("unit_selling_price_x1"),
            "precio_compra_x10": r.get("unit_selling_price_x10"),
            "precio_compra_x100": r.get("unit_selling_price_x100"),
            "costo_crafteo_x1":  r.get("unit_crafting_cost_x1"),
            "costo_crafteo_x10": r.get("unit_crafting_cost_x10"),
            "costo_crafteo_x100": r.get("unit_crafting_cost_x100"),
        })
    return result


def mejor_por_modo(carburante, modo, tope):
    """Devuelve el mejor lote para un modo, considerando costo total con ceil."""
    recarga = carburante["cantidad_recarga"]
    campo = "precio_compra" if modo == "compra" else "costo_crafteo"
    uds = math.ceil(tope / recarga)
    mejor = None
    for lote in LOTES:
        precio = carburante.get(f"{campo}_{lote}")
        if precio and precio > 0:
            costo_total = uds * precio
            if mejor is None or costo_total < mejor["costo_total"]:
                mejor = {
                    "lote": lote,
                    "precio_unitario": precio,
                    "uds": uds,
                    "costo_total": costo_total,
                    "k_por_1000rec": round(precio * 1000 / recarga)
                }
    return mejor


def analizar():
    carburantes = cargar_carburantes()
    resultado = {}

    tope_anterior = 0
    for tope in TOPES:
        tramo = tope - tope_anterior
        resultado[str(tope)] = {}
        grupo_tope = [c for c in carburantes if c["tope_indicador"] >= tope]

        for indicador in INDICADORES:
            grupo = [c for c in grupo_tope if c["indicador"] == indicador]
            if not grupo:
                continue

            ranking = []
            for c in grupo:
                mejor_compra  = mejor_por_modo(c, "compra", tramo)
                mejor_crafteo = mejor_por_modo(c, "crafteo", tramo)

                # El mejor global entre compra y crafteo (por costo total)
                opciones = [o for o in [mejor_compra, mejor_crafteo] if o]
                if not opciones:
                    continue
                global_mejor = min(opciones, key=lambda x: x["costo_total"])
                modo_ganador = "compra" if global_mejor is mejor_compra else "crafteo"

                ranking.append({
                    "id": c["id"],
                    "nombre": c["nombre"],
                    "level": c["level"],
                    "tamanio": c["tamanio"],
                    "cantidad_recarga": c["cantidad_recarga"],
                    "mejor_modo": modo_ganador,
                    "mejor_lote": global_mejor["lote"],
                    "precio_unitario": global_mejor["precio_unitario"],
                    "uds": global_mejor["uds"],
                    "costo_total": global_mejor["costo_total"],
                    "k_por_1000rec": global_mejor["k_por_1000rec"],
                    "caro": global_mejor["costo_total"] > UMBRAL_COSTO_TOTAL,
                    "compra": mejor_compra,
                    "crafteo": mejor_crafteo,
                })

            ranking.sort(key=lambda x: x["costo_total"])
            resultado[str(tope)][indicador] = ranking

        tope_anterior = tope

    return resultado


def mejor_carburante_para(indicador, cantidad_total, tope_min=0):
    """Encuentra el carburante más barato para cubrir cantidad_total de un indicador."""
    carburantes = cargar_carburantes()
    grupo = [c for c in carburantes
             if c["indicador"] == indicador and c["tope_indicador"] >= tope_min]

    mejor = None
    for c in grupo:
        mejor_compra  = mejor_por_modo(c, "compra", cantidad_total)
        mejor_crafteo = mejor_por_modo(c, "crafteo", cantidad_total)
        opciones = [o for o in [mejor_compra, mejor_crafteo] if o]
        if not opciones:
            continue
        ganador = min(opciones, key=lambda x: x["costo_total"])
        modo = "compra" if ganador is mejor_compra else "crafteo"

        entry = {
            "nombre": c["nombre"],
            "cantidad_recarga": c["cantidad_recarga"],
            "mejor_modo": modo,
            "mejor_lote": ganador["lote"],
            "precio_unitario": ganador["precio_unitario"],
            "uds": ganador["uds"],
            "costo_total": ganador["costo_total"],
        }
        if mejor is None or entry["costo_total"] < mejor["costo_total"]:
            mejor = entry

    return mejor


