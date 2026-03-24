"""
Almanax - Calibración del mercadillo
======================================
Calibra las posiciones necesarias para buscar precios Y comprar ítems
automáticamente. Guarda almanax_calibration.json en la misma carpeta.

Uso:
  python calibration.py
"""

import json
import os
import threading
import time
from pathlib import Path

import keyboard
import pyautogui

CAL_FILE = Path(__file__).parent / "almanax_calibration.json"


# ── Captura interactiva ────────────────────────────────────────────────────────

def _show_cursor():
    done = False
    def _tick():
        while not done:
            print(f"     Posición actual: {pyautogui.position()}    ", end="\r", flush=True)
            time.sleep(0.1)
    t = threading.Thread(target=_tick, daemon=True)
    t.start()
    keyboard.wait("c")
    done = True
    time.sleep(0.05)


def capture_point(label: str) -> list:
    print(f"\n  >> {label}")
    print("     Mueve el ratón al punto y pulsa C para capturar.", flush=True)
    _show_cursor()
    pos = list(pyautogui.position())
    print(f"     Capturado: {pos}                    ")
    return pos


def capture_region(label: str) -> list:
    print(f"\n  >> {label}")
    print("     Esquina SUPERIOR-IZQUIERDA → pulsa C.", flush=True)
    _show_cursor()
    tl = list(pyautogui.position())
    print(f"     TL: {tl}                    ")
    print("     Esquina INFERIOR-DERECHA → pulsa C.", flush=True)
    _show_cursor()
    br = list(pyautogui.position())
    print(f"     BR: {br}                    ")
    region = [tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]]
    print(f"     Región: {region}")
    return region


# ── Calibración completa ───────────────────────────────────────────────────────

def calibrate():
    print("\n=== CALIBRACIÓN ALMANAX ===")
    print("Abre el mercadillo en Dofus antes de continuar.")
    print("Pulsa C en cada paso para capturar.\n")

    # ── Búsqueda y resultados ──────────────────────────────────────────────────
    search_box           = capture_point("Barra de búsqueda del mercadillo")
    results_names_region = capture_region("Región de nombres de resultados (todas las filas visibles)")
    first_result         = capture_point("Centro del PRIMER resultado de la lista")
    second_result        = capture_point("Centro del SEGUNDO resultado de la lista")
    price_region_all     = capture_region("Región de precios (filas x1/x10/x100/x1000)")

    # ── Botones de lote para comprar ──────────────────────────────────────────
    print("\n--- Ahora selecciona un ítem para que aparezcan los botones de lote ---")
    input("     Pulsa ENTER cuando los botones de lote sean visibles...")

    lot_x1   = capture_point("Botón de lote x1")
    lot_x10  = capture_point("Botón de lote x10")
    lot_x100 = capture_point("Botón de lote x100")

    # ── Botón de confirmar compra ──────────────────────────────────────────────
    print("\n--- Ahora haz clic en un lote para que aparezca el botón de compra ---")
    input("     Pulsa ENTER cuando el botón de compra sea visible...")

    buy_btn = capture_point("Botón de COMPRAR (confirmar)")

    data = {
        "search_box":           search_box,
        "results_names_region": results_names_region,
        "first_result_y":       first_result[1],
        "result_row_height":    second_result[1] - first_result[1],
        "results_click_x":      first_result[0],
        "price_region_all":     price_region_all,
        "lot_buttons": {
            "1":   lot_x1,
            "10":  lot_x10,
            "100": lot_x100,
        },
        "buy_btn": buy_btn,
    }

    with open(CAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\n[OK] Calibración guardada en: {CAL_FILE}")
    return data


def load_calibration() -> dict:
    if not CAL_FILE.exists():
        print("[INFO] No se encontró almanax_calibration.json — iniciando calibración.")
        return calibrate()
    with open(CAL_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    # Convertir listas a tuplas excepto lot_buttons y buy_btn (los dejamos como listas)
    result = {}
    for k, v in raw.items():
        if k == "lot_buttons":
            result[k] = {s: tuple(p) for s, p in v.items()}
        elif isinstance(v, list):
            result[k] = tuple(v)
        else:
            result[k] = v
    return result


if __name__ == "__main__":
    calibrate()
