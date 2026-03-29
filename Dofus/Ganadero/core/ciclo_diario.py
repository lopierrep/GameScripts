"""
Calcula la produccion diaria de stats y la estrategia nocturna optima
segun las horas de juego del jugador.
"""

import json
from pathlib import Path

from core.carburante_efficiency import mejor_carburante_para

_GD_FILE = Path(__file__).resolve().parent.parent / "data" / "game_data.json"
with open(_GD_FILE, encoding="utf-8") as _f:
    _GD = json.load(_f)

_tick_s = _GD["cercado"]["tick_segundos"]
TOPES = [r["max"] for r in _GD["cercado"]["rangos_consumo"]]
MONTURAS_POR_CERCADO = _GD["cercado"]["capacidad_monturas"]
RANGOS_CONSUMO = [{"min": r["min"], "max": r["max"],
                   "rate": r["consumo_por_tick"] // _tick_s}
                  for r in _GD["cercado"]["rangos_consumo"]]

COSTOS_DRAGOPAVO = {}
for _ind in _GD["cercado"]["indicadores"]:
    if "estadistica" in _ind:
        COSTOS_DRAGOPAVO[_ind["nombre"]] = (
            _GD["dragopavo"]["estadisticas"][_ind["estadistica"]]["max"])
    elif _ind.get("efecto") == "xp":
        COSTOS_DRAGOPAVO[_ind["nombre"]] = _GD["dragopavo"]["xp_para_nivel_maximo"]

_xp = _GD["dragopavo"]["xp_para_nivel_maximo"]
STATS_TIEMPO = [("XP (nivel 200)", _xp)]
for _stat, _val in _GD["dragopavo"]["estadisticas"].items():
    STATS_TIEMPO.append((_stat.capitalize(), _val["max"]))


def calcular_drenaje(tope: int, segundos: float) -> float:
    """Puntos consumidos al drenar desde *tope* durante *segundos* segundos."""
    restante = segundos
    consumido = 0.0
    valor = tope

    for bracket in reversed(RANGOS_CONSUMO):
        if valor <= bracket["min"] or restante <= 0:
            continue
        puntos_en_bracket = min(valor, bracket["max"]) - bracket["min"]
        tiempo_bracket = puntos_en_bracket / bracket["rate"]

        if restante >= tiempo_bracket:
            consumido += puntos_en_bracket
            restante -= tiempo_bracket
            valor = bracket["min"]
        else:
            consumido += restante * bracket["rate"]
            restante = 0
            break

    return consumido


def calcular_tiempo_drenaje(tope: int) -> float:
    """Segundos totales para drenar de *tope* a 0."""
    tiempo = 0.0
    valor = tope
    for bracket in reversed(RANGOS_CONSUMO):
        if valor <= bracket["min"]:
            continue
        puntos = min(valor, bracket["max"]) - bracket["min"]
        tiempo += puntos / bracket["rate"]
        valor = bracket["min"]
    return tiempo


def calcular_ciclo_diario(horas_juego: int) -> dict:
    """Produccion diaria de stats para cada tope, dado *horas_juego* h/dia."""
    activo_s = horas_juego * 3600
    offline_s = (24 - horas_juego) * 3600

    # Tasa activa = rate del bracket mas alto de cada tope
    # (el jugador rellena antes de que baje al bracket inferior)
    tasa_por_tope = {r["max"]: r["rate"] for r in RANGOS_CONSUMO}

    resultado = {}
    for tope in TOPES:
        tasa_activa = tasa_por_tope[tope]

        consumo_activo = activo_s * tasa_activa
        consumo_offline = calcular_drenaje(tope, offline_s)
        consumo_diario = consumo_activo + consumo_offline

        stats = {}
        for nombre, total in STATS_TIEMPO:
            dias = total / consumo_diario if consumo_diario > 0 else float("inf")
            segundos = total / consumo_diario * 86400 if consumo_diario > 0 else float("inf")
            stats[nombre] = {"total": total, "dias": round(dias, 1), "segundos": segundos}

        # Costo por dragopavo para cada indicador de stats
        costos = {}
        for indicador, total_stat in COSTOS_DRAGOPAVO.items():
            m = mejor_carburante_para(indicador, round(consumo_diario), tope)
            costo_diario = (m["costo_total"] if m else 0) // MONTURAS_POR_CERCADO
            dias = total_stat / consumo_diario if consumo_diario > 0 else float("inf")
            costos[indicador] = {
                "costo_diario": costo_diario,
                "costo_total": round(costo_diario * dias),
            }

        stats_keys = ["fulminadora", "abrevadero", "dragonalgas"]
        costo_stats = sum(costos[k]["costo_total"] for k in stats_keys)
        costo_xp = costos["pesebre"]["costo_total"]

        resultado[str(tope)] = {
            "tasa_activa": tasa_activa,
            "consumo_activo": round(consumo_activo),
            "consumo_offline": round(consumo_offline),
            "consumo_diario": round(consumo_diario),
            "stats": stats,
            "costos": costos,
            "costo_stats": costo_stats,
            "costo_xp": costo_xp,
            "costo_total": costo_stats + costo_xp,
        }

    return resultado


def calcular_estrategia_nocturna(horas_offline: float) -> dict:
    """Eficiencia de cada tope para cubrir el periodo offline."""
    offline_s = horas_offline * 3600

    resultado = {}
    for tope in TOPES:
        puntos_noche = round(calcular_drenaje(tope, offline_s))
        autonomia_s = calcular_tiempo_drenaje(tope)
        se_vacia = autonomia_s <= offline_s

        # Costo de llenar pesebre (XP) a este tope
        m = mejor_carburante_para("pesebre", tope, tope)
        costo = m["costo_total"] if m else 0
        eficiencia = round(puntos_noche / costo, 2) if costo > 0 else 0

        resultado[str(tope)] = {
            "puntos_noche": puntos_noche,
            "autonomia_s": autonomia_s,
            "se_vacia": se_vacia,
            "costo_llenar": costo,
            "eficiencia": eficiencia,
        }

    # Marcar el optimo (mayor eficiencia)
    mejor_tope = max(resultado, key=lambda t: resultado[t]["eficiencia"])
    for t in resultado:
        resultado[t]["optimo"] = (t == mejor_tope)

    return resultado


