"""
Dofus 3 - Actualizador de precios de recursos
================================
Lee los precios del mercadillo de recursos y actualiza resources_prices.json.

Uso:
  1. pip install pyautogui pytesseract keyboard Pillow
     Instalar Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
  2. Ejecutar el script. Si no existe calibration.json, se inicia la calibración.
  3. Durante la calibración, posicionar el ratón y pulsar C para capturar.
  4. Pulsar Y en cualquier momento para detener tras el item actual.
"""

import json
import os
import random
import time

import keyboard
import pyautogui

import helpers.search_item_prices as sip
from save_resource_buy_prices import search_and_save

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ITEMS_FILE = os.path.join(BASE_DIR, "resources_prices.json")

DELAY_BETWEEN_ITEMS = 0.3

pyautogui.FAILSAFE = True
stop_requested = False


def on_key_press(event):
    global stop_requested
    if event.name == "y":
        stop_requested = True
        print("[INFO] Stop requested — will finish current item then exit.")


# ── Main ───────────────────────────────────────────────────────────────────────

def load_data() -> dict:
    if not os.path.exists(ITEMS_FILE):
        raise FileNotFoundError(f"No se encontró: {ITEMS_FILE}")
    with open(ITEMS_FILE, encoding="utf-8") as f:
        return json.load(f)


def run():
    keyboard.on_press(on_key_press)
    data = load_data()
    all_items = [(cat, item) for cat, items in data.items() for item in items]
    if not all_items:
        raise ValueError("El archivo de items está vacío.")

    print(f"[INFO] {len(all_items)} items. Pulsa Y para detener.\n")
    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)
    print("  Empezando ahora!      ")

    count = 0
    for idx, (_, item) in enumerate(all_items, 1):
        if stop_requested:
            break

        name = item["name"]
        prices = None
        print(f"[{idx}/{len(all_items)}] {name} …", end=" ", flush=True)
        try:
            prices = search_and_save(name)
            count += 1
        except Exception as e:
            print(f"ERROR — {e}")
        finally:
            if prices and any(v != "N/A" for v in prices.values()):
                time.sleep(0.1)
                keyboard.press_and_release("esc")
                time.sleep(0.15)

        time.sleep(DELAY_BETWEEN_ITEMS + random.uniform(0, 0.15))

    print(f"\n[DONE] {count} items actualizados en: {ITEMS_FILE}")


if __name__ == "__main__":
    sip.load_calibration()
    run()
