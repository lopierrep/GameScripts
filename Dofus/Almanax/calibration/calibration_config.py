from pathlib import Path
from shared.calibration import load_calibration as _load

CALIBRATION_FILE = str(Path(__file__).resolve().parent / "calibration_data.json")


def load_calibration() -> dict | None:
    raw = _load(CALIBRATION_FILE)
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
    return result

CALIBRATION_POINTS = [
    ("search_box",           "Barra de búsqueda del mercadillo",                    "point"),
    ("results_names_region", "Región de nombres de resultados (todas las filas)",    "region"),
    ("_first_result",        "Centro del PRIMER resultado de la lista",              "point"),
    ("_second_result",       "Centro del SEGUNDO resultado de la lista",             "point"),
    ("price_region_all",     "Región de precios (filas x1/x10/x100/x1000)",         "region"),
    (None, "Selecciona un ítem para que aparezcan los botones de lote",             "info"),
    ("lot_x1",               "Botón de lote x1",                                    "point"),
    ("lot_x10",              "Botón de lote x10",                                   "point"),
    ("lot_x100",             "Botón de lote x100",                                  "point"),
    (None, "Haz clic en un lote para que aparezca el botón de compra",              "info"),
    ("buy_btn",              "Botón de COMPRAR (confirmar)",                         "point"),
]


def transform(data: dict) -> dict:
    first = data.pop("_first_result")
    second = data.pop("_second_result")
    data["first_result_y"] = first[1]
    data["result_row_height"] = second[1] - first[1]
    data["results_click_x"] = first[0]
    data["lot_buttons"] = {
        "1":   data.pop("lot_x1"),
        "10":  data.pop("lot_x10"),
        "100": data.pop("lot_x100"),
    }
    return data
