"""
Calcula la produccion diaria de stats y la estrategia nocturna optima
segun las horas de juego del jugador.
"""

from core.carburante_efficiency import (
    TOPES, mejor_carburante_para, COSTOS_DRAGOPAVO, MONTURAS_POR_CERCADO,
)

RANGOS_CONSUMO = [
    {"min": 0,     "max": 40_000,  "rate": 1},
    {"min": 40_000, "max": 70_000,  "rate": 2},
    {"min": 70_000, "max": 90_000,  "rate": 3},
    {"min": 90_000, "max": 100_000, "rate": 4},
]

STATS_DIAS = [
    ("XP (nivel 200)", 867_582),
    ("Amor",           20_000),
    ("Resistencia",    20_000),
    ("Madurez",        20_000),
]

INDICADORES_STATS = {
    "pesebre":     867_582,
    "dragonalgas": 20_000,
    "fulminadora": 20_000,
    "abrevadero":  20_000,
}


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
        for nombre, total in STATS_DIAS:
            dias = total / consumo_diario if consumo_diario > 0 else float("inf")
            segundos = total / consumo_diario * 86400 if consumo_diario > 0 else float("inf")
            stats[nombre] = {"total": total, "dias": round(dias, 1), "segundos": segundos}

        # Costo por dragopavo para cada indicador de stats
        costos = {}
        for indicador, total_stat in INDICADORES_STATS.items():
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


if __name__ == "__main__":
    print("=== Ciclo diario (16h juego / 8h offline) ===\n")
    ciclo = calcular_ciclo_diario(16)
    for tope in TOPES:
        d = ciclo[str(tope)]
        print(f"Tope {tope:>7,}: avg {d['tasa_avg']}/s | "
              f"activo {d['consumo_activo']:,} | offline {d['consumo_offline']:,} | "
              f"total {d['consumo_diario']:,}/dia | "
              f"XP {d['stats']['XP (nivel 200)']['dias']}d | "
              f"stat {d['stats']['Amor']['dias']}d")

    print("\n=== Estrategia nocturna (8h offline) ===\n")
    noche = calcular_estrategia_nocturna(8)
    for tope in TOPES:
        n = noche[str(tope)]
        opt = " *OPTIMO*" if n["optimo"] else ""
        print(f"Tope {tope:>7,}: {n['puntos_noche']:,} pts | "
              f"costo {n['costo_llenar']:,} | efic {n['eficiencia']} pts/k{opt}")
