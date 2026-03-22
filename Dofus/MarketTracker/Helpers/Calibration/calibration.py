"""
Dofus 3 - Calibración del mercadillo
=====================================
Guarda y carga calibration.json con las posiciones y regiones necesarias
para que los scripts de búsqueda funcionen correctamente.

Uso standalone:
  python calibration.py   → lanza calibración interactiva y guarda el JSON
"""

import json
import os
import threading
import time

import keyboard
import pyautogui

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(BASE_DIR, "calibration.json")


# ── Captura interactiva ────────────────────────────────────────────────────────

def capture_point(label: str) -> list:
    print(f"\n  >> {label}")
    print("     Mueve el ratón al elemento y pulsa C para capturar.", flush=True)
    done = False
    def _tick():
        while not done:
            print(f"     Posición actual: {pyautogui.position()}    ", end="\r", flush=True)
            time.sleep(0.1)
    threading.Thread(target=_tick, daemon=True).start()
    keyboard.wait("c")
    done = True
    pos = pyautogui.position()
    print(f"     Capturado: {pos}                    ")
    return list(pos)


def calibrate_region(label: str) -> list:
    print(f"\n  >> {label}")
    print("     Esquina SUPERIOR-IZQUIERDA → pulsa C.", flush=True)
    tl = capture_point("")
    print("     Esquina INFERIOR-DERECHA → pulsa C.", flush=True)
    br = capture_point("")
    region = [tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]]
    print(f"     Región: {region}")
    return region


def calibrate():
    print("\n=== MODO CALIBRACIÓN ===\n")
    search_box           = capture_point("Barra de búsqueda del mercadillo")
    results_names_region = calibrate_region("Región de nombres de resultados (columna de nombres, todas las filas visibles)")
    first_result         = capture_point("Centro del PRIMER resultado de la lista")
    second_result        = capture_point("Centro del SEGUNDO resultado de la lista")
    price_region_all     = calibrate_region("Región de precios (todas las filas x1/x10/x100/x1000)")
    data = {
        "search_box":           search_box,
        "results_names_region": results_names_region,
        "first_result_y":       first_result[1],
        "result_row_height":    second_result[1] - first_result[1],
        "results_click_x":      first_result[0],
        "price_region_all":     price_region_all,
    }
    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\n[OK] Calibración guardada en: {CALIBRATION_FILE}")


def load_calibration() -> dict:
    """Carga calibration.json y lo devuelve. Si no existe, lanza la calibración primero."""
    if not os.path.exists(CALIBRATION_FILE):
        print("[INFO] No se encontró calibration.json — iniciando calibración.")
        calibrate()
    with open(CALIBRATION_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (tuple(v) if isinstance(v, list) else v) for k, v in raw.items()}


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    calibrate()
