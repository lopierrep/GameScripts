from pathlib import Path

from Almanax.config.config import LOTS
from shared.automation.calibration import load_calibration as _load
from shared.calibration.calibration_config import (
    CALIBRATION_FILE as SCANNER_CALIBRATION_FILE,
    CALIBRATION_POINTS as SCANNER_CALIBRATION_POINTS,
    load_calibration as load_scanner_calibration,
)

BUY_CALIBRATION_FILE = str(Path(__file__).resolve().parent / "calibration_data.json")

BUY_CALIBRATION_POINTS = [
    ("lot_x1",   "Botón de lote x1",                                    "point"),
    ("lot_x10",  "Botón de lote x10",                                   "point"),
    ("lot_x100", "Botón de lote x100",                                  "point"),
    ("lot_x1000","Botón de lote x1000",                                 "point"),
    (None, "Haz clic en un lote para que aparezca el botón de compra",  "info"),
    ("buy_btn",  "Botón de COMPRAR (confirmar)",                        "point"),
]


def transform_buy(data: dict) -> dict:
    data["lot_buttons"] = {
        str(s): data.pop(f"lot_x{s}") for s in LOTS
    }
    return data


def load_buy_calibration() -> dict | None:
    raw = _load(BUY_CALIBRATION_FILE)
    if raw is None:
        return None
    result = {}
    for k, v in raw.items():
        if k == "lot_buttons":
            result[k] = {s: tuple(p) for s, p in v.items()}
        elif isinstance(v, list):
            result[k] = tuple(v)
        else:
            result[k] = v
    buy_result = {k: result[k] for k in ("lot_buttons", "buy_btn") if k in result}
    return buy_result if buy_result else None


def load_calibration() -> dict | None:
    """Combina calibración del escáner (compartida) + calibración de compra (local)."""
    scanner = load_scanner_calibration()
    buy = load_buy_calibration()
    if scanner is None and buy is None:
        return None
    result = {}
    if scanner:
        result.update(scanner)
    if buy:
        result.update(buy)
    return result or None
