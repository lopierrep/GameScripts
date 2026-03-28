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

TOPES = [40000, 70000, 90000, 100000]
INDICADORES = ["aporreadora", "acariciador", "dragonalgas", "fulminadora", "abrevadero", "pesebre"]
LOTES = ["x10", "x100"]

# Umbral: si el costo total supera este valor, se marca como caro
UMBRAL_COSTO_TOTAL = 10000

TAMANIO_MAP = {5: ("minusculo", 1000), 15: ("pequeno", 2000), 25: ("normal", 3000),
               35: ("grande", 4000), 45: ("gigantesco", 5000)}

_INDICADORES_KEYS = ["aporreadora", "acariciador", "dragonalgas", "fulminadora", "abrevadero", "pesebre"]


def _tope_de_nivel(level):
    if 5 <= level <= 45:    return 40000
    if 55 <= level <= 95:   return 70000
    if 105 <= level <= 145: return 90000
    if 155 <= level <= 195: return 100000


def _get_indicador(nombre):
    for ind in _INDICADORES_KEYS:
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


XP_NIVEL_200 = 867582
STAT_MAX = 20000
MONTURAS_POR_CERCADO = 10

COSTOS_DRAGOPAVO = {
    "fulminadora": STAT_MAX,   # resistencia
    "abrevadero":  STAT_MAX,   # madurez
    "dragonalgas": STAT_MAX,   # amor
    "pesebre":     XP_NIVEL_200,
}


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


def calcular_costo_dragopavo():
    """Calcula el costo total para llenar stats y subir a nivel 200, por cada tope."""
    stats_keys = ["fulminadora", "abrevadero", "dragonalgas"]
    resultado = {}

    for tope in TOPES:
        detalle = {}
        for indicador, cantidad in COSTOS_DRAGOPAVO.items():
            detalle[indicador] = mejor_carburante_para(indicador, cantidad, tope)

        costo_stats = sum(
            detalle[i]["costo_total"] for i in stats_keys if detalle.get(i)
        ) // MONTURAS_POR_CERCADO
        costo_xp = (detalle["pesebre"]["costo_total"] if detalle.get("pesebre") else 0) // MONTURAS_POR_CERCADO

        resultado[str(tope)] = {
            "detalle": detalle,
            "costo_stats": costo_stats,
            "costo_xp": costo_xp,
            "costo_total": costo_stats + costo_xp,
        }

    return resultado


def imprimir_resumen(resultado):
    print("=" * 85)
    print("MEJOR CARBURANTE POR TOPE E INDICADOR  (ordenado por costo total para llenar el tope)")
    print(f"Umbral de rentabilidad: {UMBRAL_K_POR_1000REC} k/1000rec  [!] = supera el umbral")
    print("=" * 85)

    for tope, indicadores in resultado.items():
        print(f"\n-- Tope {int(tope):,} --")
        for indicador, ranking in indicadores.items():
            if not ranking:
                continue
            m = ranking[0]
            alerta = " [!]" if m["caro"] else "    "
            print(
                f"  {indicador:<14} -> {m['nombre']:<42} "
                f"[{m['mejor_modo']:<7} {m['mejor_lote']}] "
                f"{m['uds']:>3} uds x {m['precio_unitario']:>6} = {m['costo_total']:>10,} total{alerta}"
            )


def guardar_resultado(resultado):
    out_path = DATA_DIR / "analisis_eficiencia.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\nResultado completo guardado en: {out_path}")


if __name__ == "__main__":
    resultado = analizar()
    imprimir_resumen(resultado)
    guardar_resultado(resultado)
