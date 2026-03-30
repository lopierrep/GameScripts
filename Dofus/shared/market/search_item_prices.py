"""
Dofus 3 - Búsqueda de precios en el mercadillo
===============================================
Lee los precios de un item buscándolo por nombre via OCR.
No guarda nada — solo devuelve el dict de precios leídos.

Uso:
    import shared.market.search_item_prices as sip
    sip.load_calibration()
    sip.search_item("Madera de arce")
    prices = sip.read_prices("Madera de arce")
"""

import re
import random
import os
import time

import keyboard
import pyautogui
import pytesseract
from difflib import SequenceMatcher
from PIL import Image

from shared.automation.ocr import preprocess_for_ocr
from shared.market.common import _normalize
from shared.automation.mouse import smooth_move

import shutil as _shutil
pytesseract.pytesseract.tesseract_cmd = (
    _shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


_CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "categories.txt")

def _load_categories() -> set[str]:
    if not os.path.exists(_CATEGORIES_FILE):
        return set()
    with open(_CATEGORIES_FILE, encoding="utf-8") as f:
        return {_normalize(line.strip()) for line in f if line.strip()}

_CATEGORIES: set[str] = set()  # se carga la primera vez que se usa


DELAY_AFTER_CLICK  = 0.15
DELAY_AFTER_SEARCH = 1.0

CAL = None


def set_calibration(cal: dict):
    """Permite al caller inyectar una calibración ya cargada."""
    global CAL
    CAL = cal


def load_calibration():
    """Carga calibración desde el módulo de calibración del proyecto activo.
    Intenta primero calibration.calibration_config (nuevo estilo Crafting/Almanax),
    luego el path legado Helpers.Calibration.calibration."""
    global CAL
    try:
        from calibration.calibration_config import load_calibration as _lc
        CAL = _lc()
    except ImportError:
        try:
            from Helpers.Calibration.calibration import load_calibration as _lc
            CAL = _lc()
        except ImportError:
            raise ImportError(
                "No se encontró módulo de calibración. "
                "Llama a set_calibration(cal) antes de usar search_item_prices."
            )


# ── Mouse ──────────────────────────────────────────────────────────────────────

def click_at(pos, delay=DELAY_AFTER_CLICK):
    smooth_move(*pos)
    pyautogui.click()
    time.sleep(delay + random.uniform(0, 0.05))



def ocr_all_prices() -> dict:
    r = CAL["price_region_all"]
    region = (r[0], r[1] - 20, r[2], r[3] + 10)
    img = pyautogui.screenshot(region=region)
    processed = preprocess_for_ocr(img)
    raw = pytesseract.image_to_string(processed, config="--psm 6 -c tessedit_char_whitelist=0123456789.,")

    prices = {"unit_price_x1": "N/A", "unit_price_x10": "N/A", "unit_price_x100": "N/A", "unit_price_x1000": "N/A"}
    qty_key = {"1": "unit_price_x1", "10": "unit_price_x10", "100": "unit_price_x100", "1000": "unit_price_x1000"}

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
    region = CAL["results_names_region"]
    img = pyautogui.screenshot(region=region)

    scale = 3
    img_gray = img.convert("L")
    w, h = img_gray.size
    img_gray = img_gray.resize((w * scale, h * scale), Image.LANCZOS)
    img_gray = img_gray.point(lambda p: 255 if p < 160 else 0)

    data = pytesseract.image_to_data(
        img_gray, config="--psm 4 --oem 1 -l spa",
        output_type=pytesseract.Output.DICT
    )

    line_map = {}
    for i, text in enumerate(data["text"]):
        if not str(text).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line_map.setdefault(key, {"words": [], "tops": [], "heights": []})
        line_map[key]["words"].append(text)
        line_map[key]["tops"].append(data["top"][i])
        line_map[key]["heights"].append(data["height"][i])

    global _CATEGORIES
    if not _CATEGORIES:
        _CATEGORIES = _load_categories()

    line_list = []
    for key in sorted(line_map.keys()):
        d = line_map[key]
        text = " ".join(w for w in d["words"] if w.strip())
        if not text.strip():
            continue
        text_norm = _normalize(re.sub(r"[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]", " ", text).strip())
        if any(
            abs(len(text_norm) - len(cat)) <= max(2, len(cat) * 0.3)
            and SequenceMatcher(None, text_norm, cat).ratio() >= 0.75
            for cat in _CATEGORIES
        ):
            continue
        avg_top = sum(d["tops"]) / len(d["tops"])
        avg_h   = sum(d["heights"]) / len(d["heights"])
        line_list.append((text, avg_top + avg_h / 2))

    if not line_list:
        return None

    def screen_y(cy_scaled: float) -> int:
        return region[1] + round(cy_scaled / scale)

    def clean_text(t: str) -> str:
        return re.sub(r"[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]", " ", t).strip()

    name_norm = _normalize(name)

    def _is_continuation(line: str) -> bool:
        first_char = line.strip()[0] if line.strip() else ""
        return first_char.islower()

    for i, (text, cy) in enumerate(line_list):
        if _normalize(clean_text(text)) == name_norm:
            next_is_cont = i + 1 < len(line_list) and _is_continuation(line_list[i + 1][0])
            if not next_is_cont:
                return (CAL["results_click_x"], screen_y(cy))

    for i in range(len(line_list) - 1):
        t1, cy1 = line_list[i]
        t2, cy2 = line_list[i + 1]
        if _normalize(clean_text(t1 + " " + t2)) == name_norm:
            return (CAL["results_click_x"], screen_y((cy1 + cy2) / 2))

    def name_score(text: str) -> float:
        clean = clean_text(text)
        if not clean:
            return 0.0
        name_l = name.lower()

        def scored(t):
            ratio = SequenceMatcher(None, name_l, t.lower()).ratio()
            penalty = max(0.0, 1.0 - 0.1 * abs(len(t) - len(name)))
            if name_l in t.lower() and len(t) > len(name) * 1.3:
                penalty *= 0.2
            return ratio * penalty

        return scored(clean)

    candidates = [(name_score(t), cy) for t, cy in line_list]
    for i in range(len(line_list) - 1):
        t1, cy1 = line_list[i]
        t2, cy2 = line_list[i + 1]
        candidates.append((name_score(t1 + " " + t2), (cy1 + cy2) / 2))

    best_score, best_cy = max(candidates, key=lambda x: x[0])
    if best_score < 0.6:
        return None

    return (CAL["results_click_x"], screen_y(best_cy))


def read_prices(name: str, retries: int = 5, stop_flag = None) -> dict:
    """Busca el item en el mercadillo y devuelve sus precios leídos por OCR.
    stop_flag: lista de un bool mutable [False] o callable que retorna bool."""
    def _is_stopped() -> bool:
        if stop_flag is None:
            return False
        elif isinstance(stop_flag, list):
            return bool(stop_flag[0])
        else:  # callable (e.g., event.is_set)
            return bool(stop_flag())
    
    prices = {"unit_price_x1": "N/A", "unit_price_x10": "N/A", "unit_price_x100": "N/A", "unit_price_x1000": "N/A"}
    for attempt in range(1, retries + 1):
        if _is_stopped():
            break
        pos = find_exact_result(name)
        if pos is None:
            print(f"  [reintento {attempt}/{retries}] item no encontrado en resultados…", end=" ", flush=True)
            # Sleep interruptible
            remaining = 0.5
            while remaining > 0 and not _is_stopped():
                sleep_time = min(0.1, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time
            continue
        click_at(pos, delay=DELAY_AFTER_CLICK + 0.2)
        prices = ocr_all_prices()
        if any(v != "N/A" for v in prices.values()):
            return prices
        print(f"  [reintento {attempt}/{retries}] precios no detectados…", end=" ", flush=True)
        # Sleep interruptible
        remaining = 0.5
        while remaining > 0 and not _is_stopped():
            sleep_time = min(0.1, remaining)
            time.sleep(sleep_time)
            remaining -= sleep_time
    return prices
