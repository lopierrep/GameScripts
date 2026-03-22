"""
Dofus 3 - Market Price Tracker
================================
Lee los precios del mercadillo de recursos y los exporta a market_prices.csv.

Uso:
  1. pip install pyautogui pytesseract keyboard Pillow
     Instalar Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
  2. Ejecutar el script. Si no existe calibration.json, se inicia la calibración.
  3. Durante la calibración, posicionar el ratón y pulsar C para capturar.
  4. Pulsar Y en cualquier momento para detener tras el item actual.
"""

import threading
import pyautogui
import pytesseract
import keyboard
import time
import random
import csv
import re
import os
import json
from difflib import SequenceMatcher

from PIL import Image, ImageFilter, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(BASE_DIR, "calibration.json")
ITEMS_FILE       = os.path.join(BASE_DIR, "items.txt")
OUTPUT_CSV       = os.path.join(BASE_DIR, "market_prices.csv")


DELAY_AFTER_CLICK   = 0.15
DELAY_AFTER_SEARCH  = 1.0
DELAY_BETWEEN_ITEMS = 0.3

pyautogui.FAILSAFE = True
stop_requested = False
CAL = None


def on_key_press(event):
    global stop_requested
    if event.name == "y":
        stop_requested = True
        print("[INFO] Stop requested — will finish current item then exit.")


# ── Mouse ──────────────────────────────────────────────────────────────────────

def smooth_move(x, y, steps=4):
    x0, y0 = pyautogui.position()
    for i in range(1, steps + 1):
        t = i / steps
        pyautogui.moveTo(
            x0 + (x - x0) * t + random.randint(-2, 2),
            y0 + (y - y0) * t + random.randint(-2, 2),
        )
        time.sleep(0.002)
    pyautogui.moveTo(x, y)


def click_at(pos, delay=DELAY_AFTER_CLICK):
    smooth_move(*pos)
    pyautogui.click()
    time.sleep(delay + random.uniform(0, 0.05))


# ── OCR ────────────────────────────────────────────────────────────────────────

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    w, h = image.size
    image = image.crop((int(w * 0.14), 0, int(w * 0.72), h))
    image = image.convert("L")
    w2, h2 = image.size
    image = image.resize((w2 * 4, h2 * 4), Image.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(3.0)
    image = image.filter(ImageFilter.SHARPEN)
    image = image.point(lambda p: 255 if p < 160 else 0)
    return image


def ocr_all_prices() -> dict:
    img = pyautogui.screenshot(region=CAL["price_region_all"])
    processed = preprocess_for_ocr(img)
    raw = pytesseract.image_to_string(processed, config="--psm 6")

    prices = {"price_10": "N/A", "price_100": "N/A", "price_1000": "N/A"}
    qty_key = {"10": "price_10", "100": "price_100", "1000": "price_1000"}

    for line in raw.splitlines():
        tokens = re.findall(r"\d+(?:[.,]\d+)*", line)
        if len(tokens) < 2:
            continue
        qty = re.sub(r"[.,]", "", tokens[0])
        if qty not in qty_key:
            continue
        price = re.sub(r"[.,]", "", tokens[1])
        prices[qty_key[qty]] = price

    return prices


# ── Search ─────────────────────────────────────────────────────────────────────

def search_item(name: str):
    click_at(CAL["search_box"])
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    for char in name:
        keyboard.write(char)
        time.sleep(random.uniform(0.02, 0.05))
    time.sleep(DELAY_AFTER_SEARCH + random.uniform(0, 0.1))


def find_exact_result(name: str) -> tuple | None:
    """Captura la región de nombres de resultados y devuelve la (x, y) del item exacto."""
    region = CAL["results_names_region"]
    img = pyautogui.screenshot(region=region)
    img_gray = img.convert("L")
    iw, ih = img_gray.size
    img_gray = img_gray.crop((int(iw * 0.10), 0, iw, ih))  # eliminar iconos
    w, h = img_gray.size
    img_gray = img_gray.resize((w * 3, h * 3), Image.LANCZOS)
    img_gray = img_gray.point(lambda p: 255 if p < 160 else 0)
    raw = pytesseract.image_to_string(img_gray, config="--psm 4 --oem 1")

    all_lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not all_lines:
        return None

    def name_score(line: str) -> float:
        clean = re.sub(r"[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]", " ", line).strip()
        if not clean:
            return 0.0
        clean_nospace = clean.replace(" ", "")
        name_l = name.lower()

        def scored(text):
            ratio = SequenceMatcher(None, name_l, text.lower()).ratio()
            penalty = max(0.0, 1.0 - 0.1 * abs(len(text) - len(name)))
            return ratio * penalty

        return max(scored(clean), scored(clean_nospace))

    scored_lines = [(name_score(l), i, l) for i, l in enumerate(all_lines)]

    best_score, best_orig_idx, _ = max(scored_lines, key=lambda x: x[0])

    if best_score < 0.6:
        return None

    # Rank = número de líneas con dígitos antes de la línea del nombre encontrado.
    rank = sum(1 for i, l in enumerate(all_lines) if i < best_orig_idx and re.search(r"\d", l))

    click_y = CAL["first_result_y"] + rank * CAL["result_row_height"]
    return (CAL["results_click_x"], click_y)


def read_prices(name: str, retries: int = 5) -> dict:
    for attempt in range(1, retries + 1):
        pos = find_exact_result(name)
        if pos is None:
            print(f"  [reintento {attempt}/{retries}] item no encontrado en resultados…", end=" ", flush=True)
            time.sleep(0.5)
            continue
        click_at(pos, delay=DELAY_AFTER_CLICK + 0.2)
        prices = ocr_all_prices()
        if any(v != "N/A" for v in prices.values()):
            return prices
        print(f"  [reintento {attempt}/{retries}] precios no detectados…", end=" ", flush=True)
        time.sleep(0.5)
    return prices


# ── CSV ────────────────────────────────────────────────────────────────────────

def init_csv():
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["item", "price_x10", "price_x100", "price_x1000"])
    print(f"[INFO] Output: {OUTPUT_CSV}")


def append_row(row: dict):
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([row["item"], row["price_10"], row["price_100"], row["price_1000"]])


# ── Calibración ────────────────────────────────────────────────────────────────

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
    price_region_all     = calibrate_region("Región de precios (todas las filas x10/x100/x1000)")
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


# ── Main ───────────────────────────────────────────────────────────────────────

def load_items() -> list[str]:
    if not os.path.exists(ITEMS_FILE):
        raise FileNotFoundError(f"No se encontró: {ITEMS_FILE}")
    items = [l.strip() for l in open(ITEMS_FILE, encoding="utf-8") if l.strip() and not l.startswith("#")]
    if not items:
        raise ValueError("El archivo de items está vacío.")
    return items


def run():
    keyboard.on_press(on_key_press)
    items = load_items()
    init_csv()

    print(f"[INFO] {len(items)} items. Pulsa Y para detener.\n")
    for i in range(3, 0, -1):
        print(f"  Empezando en {i}…", end="\r")
        time.sleep(1)
    print("  Empezando ahora!      ")

    count = 0
    for idx, item in enumerate(items, 1):
        if stop_requested:
            break

        prices = None
        print(f"[{idx}/{len(items)}] {item} …", end=" ", flush=True)
        try:
            search_item(item)
            prices = read_prices(item)
            append_row({"item": item, **prices})
            count += 1
            print(f"x10={prices['price_10']:>8}  x100={prices['price_100']:>8}  x1000={prices['price_1000']:>8}")
        except Exception as e:
            print(f"ERROR — {e}")
            append_row({"item": item, "price_10": "ERROR", "price_100": "ERROR", "price_1000": "ERROR"})
        finally:
            if prices and any(v != "N/A" for v in prices.values()):
                time.sleep(0.1)
                keyboard.press_and_release("esc")
                time.sleep(0.15)

        time.sleep(DELAY_BETWEEN_ITEMS + random.uniform(0, 0.15))

    print(f"\n[DONE] {count} items guardados en: {OUTPUT_CSV}")


if __name__ == "__main__":
    if not os.path.exists(CALIBRATION_FILE):
        print("[INFO] No se encontró calibration.json — iniciando calibración.")
        calibrate()
    with open(CALIBRATION_FILE, encoding="utf-8") as f:
        _cal = json.load(f)
    CAL = {k: (tuple(v) if isinstance(v, list) else v) for k, v in _cal.items()}
    run()
