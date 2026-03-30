"""
Calibración compartida del escáner de precios.
==============================================
Los tres proyectos (Crafting, Almanax, Ganadero) usan el mismo archivo
de calibración para el escáner de mercadillo. Solo hay que calibrar una vez.
"""

from pathlib import Path

from shared.automation.calibration import load_calibration as _load

CALIBRATION_FILE = str(Path(__file__).resolve().parent / "scanner_calibration.json")

CALIBRATION_POINTS = [
    ("search_box",           "Barra de búsqueda del mercadillo",                    "point"),
    ("results_names_region", "Región de nombres de resultados (todas las filas)",    "region"),
    ("_first_result",        "Centro del PRIMER resultado de la lista",              "point"),
    ("_second_result",       "Centro del SEGUNDO resultado de la lista",             "point"),
    ("price_region_all",     "Región de precios (filas x1/x10/x100/x1000)",         "region"),
]


def transform(data: dict) -> dict:
    first = data.pop("_first_result")
    second = data.pop("_second_result")
    data["first_result_y"] = first[1]
    data["result_row_height"] = second[1] - first[1]
    data["results_click_x"] = first[0]
    return data


def load_calibration() -> dict | None:
    raw = _load(CALIBRATION_FILE)
    if raw is None:
        return None
    return {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items()}
