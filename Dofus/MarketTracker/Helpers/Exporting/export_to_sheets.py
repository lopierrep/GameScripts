"""
Dofus 3 - Exportador de recetas a Google Sheets
================================================
Lee todos los recipes_*.json, calcula rentabilidad y sube cada profesión
a su propia hoja dentro de un Google Spreadsheet.

Requisitos:
  pip install gspread google-auth

Configuración inicial (solo una vez):
  1. Ir a https://console.cloud.google.com
  2. Crear proyecto → habilitar "Google Sheets API"
  3. Crear Service Account → descargar JSON de credenciales
  4. Guardar el JSON como: MarketTracker/credentials.json
  5. Abrir tu Google Sheet → compartirlo con el email del Service Account

Uso:
  python export_to_sheets.py
"""

import glob
import json
import os
import sys
import time

import gspread
from google.oauth2.service_account import Credentials

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from Helpers.SearchAndSave.common import (
    SIZES,
    _load_omitted_items,
    _load_omitted_categories,
)


def _api_call(fn, *args, retries: int = 5, **kwargs):
    """Llama fn(*args, **kwargs) reintentando con backoff exponencial si hay 429."""
    delay = 10
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                print(f"    [RATE LIMIT] Esperando {delay}s …")
                time.sleep(delay)
                delay *= 2
            else:
                raise

# ── Configuración ─────────────────────────────────────────────────────────────

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR      = os.path.join(BASE_DIR, "..", "..", "Recipes")
MARKETS_DIR      = os.path.join(BASE_DIR, "..", "..", "Markets")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# ID del spreadsheet (parte de la URL: /spreadsheets/d/<SPREADSHEET_ID>/edit)
SPREADSHEET_ID  = "1S7B58S_tkt4kx4vopK9fVzP9rMbWybUC3xrWUrqBuT8"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

PROFESSION_ICONS = {
    "Alquimista":  "🧪",
    "Base":        "📦",
    "Campesino":   "🌾",
    "Cazador":     "🏹",
    "Escultor":    "🗿",
    "Fabricante":  "🛡️",
    "Ganadero":    "🐾",
    "Herrero":     "⚒️",
    "Joyero":      "💎",
    "Leñador":     "🪓",
    "Manitas":     "🛠️",
    "Minero":      "⛏️",
    "Pescador":    "🎣",
    "Sastre":      "🧵",
    "Zapatero":    "🥾",
}
LOT_MULT = {"x1": 1, "x10": 10, "x100": 100, "x1000": 1000}

INGREDIENTS_SHEET_NAME = "🧺 Ingredientes"
INGREDIENTS_HEADERS = [
    "Profesión", "Receta", "Nivel",
    "Ingrediente", "Cantidad", "Precio unit", "Costo total", "Fuente",
]

# Columnas de cada hoja
HEADERS = [
    "Receta", "Nivel",
    "Craft U. x1",   "Sell U. x1",   "Profit U. x1",
    "Craft U. x10",  "Sell U. x10",  "Profit U. x10",
    "Craft U. x100", "Sell U. x100", "Profit U. x100",
    "Craft U. x1000","Sell U. x1000","Profit U. x1000",
    "Ingredientes",
]


# ── Lógica de datos ───────────────────────────────────────────────────────────

def profession_from_filename(path: str) -> str:
    """Extrae el nombre de profesión del nombre de archivo (recipes_herrero.json → Herrero ⚒️)."""
    basename = os.path.basename(path)
    name = basename.replace("recipes_", "").replace(".json", "").capitalize()
    icon = PROFESSION_ICONS.get(name, "")
    return f"{name} {icon}" if icon else name


def _load_ingredient_prices() -> dict[str, tuple[int, str | None]]:
    """Devuelve {nombre: (precio_unitario, fuente)} donde fuente es None, 'craft' o 'venta'."""
    prices = {}

    # Precios de materiales de todos los mercadillos (sin fuente)
    for folder in os.listdir(MARKETS_DIR):
        fp = os.path.join(MARKETS_DIR, folder, "materials_prices.json")
        if not os.path.exists(fp):
            continue
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        for items in data.values():
            for item in items:
                vals = [item.get(f"unit_price_{s}", 0) for s in SIZES]
                best = min((v for v in vals if v > 0), default=0)
                if best:
                    prices[item["name"]] = (best, "buy")

    # Subrecetas: min(crafting_cost, selling_price) indicando la fuente
    for fname in os.listdir(RECIPES_DIR):
        if not fname.startswith("recipes_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(RECIPES_DIR, fname), encoding="utf-8") as f:
            for recipe in json.load(f):
                name  = recipe.get("result", "")
                craft = min((recipe.get(f"unit_crafting_cost_{s}", 0) for s in SIZES if recipe.get(f"unit_crafting_cost_{s}", 0) > 0), default=0)
                sell  = min((recipe.get(f"unit_selling_price_{s}",  0) for s in SIZES if recipe.get(f"unit_selling_price_{s}",  0) > 0), default=0)
                if craft > 0 and sell > 0:
                    if craft <= sell:
                        prices[name] = (craft, "craft")
                    else:
                        prices[name] = (sell, "buy")
                elif craft > 0:
                    prices[name] = (craft, "craft")
                elif sell > 0:
                    prices[name] = (sell, "buy")

    return prices


def format_ingredients(ingredients: list, price_lookup: dict) -> str:
    """Convierte lista de ingredientes a string con precio unitario y fuente."""
    parts = []
    for ing in ingredients:
        name        = ing["name"]
        qty         = ing["quantity"]
        entry       = price_lookup.get(name)
        if entry:
            price, source = entry
            label = f"{price:,} {source}" if source else f"{price:,}"
            parts.append(f"{name}({label})x{qty}")
        else:
            parts.append(f"{name} x{qty}")
    return " | ".join(parts)


def calc_margin(ganancia: float, costo: float) -> str:
    if costo and costo > 0:
        return f"{(ganancia / costo * 100):.1f}%"
    return "N/A"


def best_buy_lot(recipe: dict) -> tuple[str, int]:
    """Lote que minimiza el costo de fabricación por unidad (menor no-cero)."""
    options = [(s, recipe.get(f"unit_crafting_cost_{s}", 0)) for s in SIZES]
    valid = [(s, v) for s, v in options if v > 0]
    return min(valid, key=lambda x: x[1]) if valid else ("x1", 0)


def best_sell_lot(recipe: dict) -> tuple[str, int]:
    """Lote que maximiza el precio de venta por unidad (mayor no-cero)."""
    options = [(s, recipe.get(f"unit_selling_price_{s}", 0)) for s in SIZES]
    valid = [(s, v) for s, v in options if v > 0]
    return max(valid, key=lambda x: x[1]) if valid else ("x1", 0)


def _collect_sub_recipes(recipe_name: str, craftable: dict, visited: set | None = None) -> set[str]:
    """Devuelve recursivamente todos los nombres de sub-recetas de una receta."""
    if visited is None:
        visited = set()
    subs = set()
    for ing in craftable.get(recipe_name, []):
        name = ing["name"]
        if name in craftable and name not in visited:
            visited.add(name)
            subs.add(name)
            subs |= _collect_sub_recipes(name, craftable, visited)
    return subs


def load_recipes_by_profession() -> dict[str, list[dict]]:
    """
    Devuelve {profesion: [filas_ordenadas]} donde cada fila es un dict listo para Sheets.
    Solo incluye recetas con precio_venta y costo_fabricacion conocidos (no None, no 0).
    """
    files         = sorted(glob.glob(os.path.join(RECIPES_DIR, "recipes_*.json")))
    result        = {}
    price_lookup  = _load_ingredient_prices()

    exceptions           = _load_omitted_items()
    omitted_categories   = _load_omitted_categories()

    # Lookup de todas las recetas craftables: {result_name: [ingredients]}
    craftable: dict[str, list] = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            for recipe in json.load(f):
                name = recipe.get("result", "")
                if name:
                    craftable[name] = recipe.get("ingredients", [])

    for path in files:
        profession = profession_from_filename(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        for recipe in data:
            if recipe.get("result") in exceptions:
                continue
            if recipe.get("category") in omitted_categories:
                continue
            costos  = [recipe.get(f"unit_crafting_cost_{s}", 0)  for s in SIZES]
            precios = [recipe.get(f"unit_selling_price_{s}", 0) for s in SIZES]

            # Saltar recetas sin ningún dato
            if all(v == 0 for v in costos) and all(v == 0 for v in precios):
                continue

            ganancias = [p - c if c > 0 and p > 0 else 0 for c, p in zip(costos, precios)]

            raw_ings = []
            for ing in recipe.get("ingredients", []):
                entry = price_lookup.get(ing["name"])
                price, source = entry if entry else (0, None)
                raw_ings.append((ing["name"], ing["quantity"], price, source))

            result_name = recipe.get("result", "")
            rows.append({
                "result":            result_name,
                "level":             recipe.get("level", ""),
                "costos":            costos,
                "precios":           precios,
                "ganancias":         ganancias,
                "best_ganancia":     max(ganancias),
                "ingredientes":      format_ingredients(recipe.get("ingredients", []), price_lookup),
                "raw_ingredients":   raw_ings,
                "sub_recipe_names":  sorted(_collect_sub_recipes(result_name, craftable)),
            })

        # Ordenar de más profit a menos (por ganancia absoluta máxima entre lotes)
        rows.sort(key=lambda r: r["best_ganancia"], reverse=True)
        result[profession] = rows

    return result


# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    """Devuelve la hoja con ese título, creándola si no existe."""
    try:
        return _api_call(spreadsheet.worksheet, title)
    except gspread.exceptions.WorksheetNotFound:
        return _api_call(spreadsheet.add_worksheet, title=title, rows=500, cols=len(HEADERS))


def _clear_filter_views(spreadsheet: gspread.Spreadsheet, sheet_id: int):
    """Elimina todas las filter views existentes de una hoja específica."""
    info = spreadsheet.client.request(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}",
        params={"fields": "sheets(properties/sheetId,filterViews/filterViewId)"},
    ).json()
    delete_requests = [
        {"deleteFilterView": {"filterId": fv["filterViewId"]}}
        for sheet in info.get("sheets", [])
        if sheet.get("properties", {}).get("sheetId") == sheet_id
        for fv in sheet.get("filterViews", [])
    ]
    if delete_requests:
        _api_call(spreadsheet.batch_update, {"requests": delete_requests})


def write_ingredients_sheet(
    spreadsheet: gspread.Spreadsheet,
    data: dict[str, list[dict]],
) -> tuple[int, dict[tuple[str, str], tuple[int, int]], dict[tuple[str, str], int]]:
    """
    Escribe la hoja 'Ingredientes' con una fila por ingrediente.
    Devuelve (sheet_id, recipe_row_map, filter_view_map).
    """
    ws = get_or_create_worksheet(spreadsheet, INGREDIENTS_SHEET_NAME)
    _api_call(ws.clear)

    sheet_rows = [INGREDIENTS_HEADERS]
    recipe_row_map: dict[tuple[str, str], tuple[int, int]] = {}
    recipe_order: list[tuple[str, str]] = []

    for profession, rows in sorted(data.items()):
        for recipe in rows:
            first_row = len(sheet_rows) + 1   # fila 1 = encabezado
            for ing_name, ing_qty, ing_price, ing_source in recipe["raw_ingredients"]:
                costo_total = ing_price * ing_qty if ing_price else ""
                sheet_rows.append([
                    profession,
                    recipe["result"],
                    recipe["level"],
                    ing_name,
                    ing_qty,
                    ing_price or "",
                    costo_total,
                    ing_source or "???",
                ])
            last_row = len(sheet_rows)
            key = (profession, recipe["result"])
            recipe_row_map[key] = (first_row, last_row)
            recipe_order.append(key)

    _api_call(ws.update, "A1", sheet_rows, value_input_option="RAW")

    sheet_id = ws.id
    n_data = len(sheet_rows) - 1

    _clear_filter_views(spreadsheet, sheet_id)

    # Lookup rápido: recipe_name → sub_recipe_names
    sub_recipe_lookup: dict[str, list[str]] = {}
    for profession, rows in data.items():
        for recipe in rows:
            sub_recipe_lookup[recipe["result"]] = recipe.get("sub_recipe_names", [])

    all_recipe_names_in_sheet = sorted({name for _, name in recipe_order})

    filter_view_requests = []
    for _, recipe_name in recipe_order:
        sub_names = sub_recipe_lookup.get(recipe_name, [])
        visible = {recipe_name} | set(sub_names)
        hidden  = [n for n in all_recipe_names_in_sheet if n not in visible]

        filter_view_requests.append({
            "addFilterView": {
                "filter": {
                    "title": recipe_name,
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(INGREDIENTS_HEADERS),
                    },
                    "criteria": {
                        "1": {"hiddenValues": hidden},  # columna "Receta" (índice 1, 0-based)
                    },
                }
            }
        })

    requests = [
        # Limpiar todos los bordes antes de aplicar los nuevos
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1000,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(INGREDIENTS_HEADERS),
                },
                "top":             {"style": "NONE"},
                "bottom":          {"style": "NONE"},
                "left":            {"style": "NONE"},
                "right":           {"style": "NONE"},
                "innerHorizontal": {"style": "NONE"},
                "innerVertical":   {"style": "NONE"},
            }
        },
        # Encabezado
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.2, "green": 0.35, "blue": 0.6},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        # Formato numérico en columnas Cantidad, Precio unit, Costo total (D, E, F → índices 4,5,6)
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1,
                          "startColumnIndex": 4, "endColumnIndex": 7},
                "cell": {"userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                }},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        # Fijar primera fila
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Ancho de columnas
        *[
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                              "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": _col_width(sheet_rows, i)},
                    "fields": "pixelSize",
                }
            }
            for i in range(len(INGREDIENTS_HEADERS))
        ],
        # Filtro básico (tabla)
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": len(sheet_rows),
                        "startColumnIndex": 0,
                        "endColumnIndex": len(INGREDIENTS_HEADERS),
                    }
                }
            }
        },
        # Línea gruesa en la última fila de cada receta
        *[
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": last_row - 1,
                        "endRowIndex": last_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(INGREDIENTS_HEADERS),
                    },
                    "bottom": {"style": "SOLID_THICK", "color": {"red": 0.3, "green": 0.3, "blue": 0.3}},
                }
            }
            for _, (_, last_row) in recipe_row_map.items()
        ],
    ]
    all_requests = requests + filter_view_requests
    response = _api_call(ws.spreadsheet.batch_update, {"requests": all_requests})

    # Extraer filter view IDs de la respuesta
    replies = response.get("replies", [])
    fv_replies = replies[len(requests):]
    filter_view_map: dict[tuple[str, str], int] = {}
    for key, reply in zip(recipe_order, fv_replies):
        fv_id = reply.get("addFilterView", {}).get("filter", {}).get("filterViewId")
        if fv_id is not None:
            filter_view_map[key] = fv_id

    print(f"  {INGREDIENTS_SHEET_NAME:<20} {n_data} filas, {len(filter_view_map)} filter views")

    return sheet_id, recipe_row_map, filter_view_map


_RED      = {"red": 0.96, "green": 0.70, "blue": 0.70}
_WHITE    = {"red": 1.00, "green": 1.00, "blue": 1.00}
_YELLOW   = {"red": 1.00, "green": 0.95, "blue": 0.60}
_GREEN_LO = {"red": 0.85, "green": 0.96, "blue": 0.85}
_GREEN_HI = {"red": 0.50, "green": 0.84, "blue": 0.55}

GANANCIA_COLS = (4, 7, 10, 13)   # índices 0-based de las columnas de ganancia


def _lerp_color(a: dict, b: dict, t: float) -> dict:
    return {k: a[k] + (b[k] - a[k]) * t for k in ("red", "green", "blue")}


def _row_ganancia_colors(ganancias: list) -> list[dict]:
    """Devuelve una lista de colores por ranking dentro de la fila."""
    positives = sorted(set(g for g in ganancias if g > 0))
    n = len(positives)
    colors = []
    for value in ganancias:
        if value < 0:
            colors.append(_RED)
        elif value == 0:
            colors.append(_YELLOW)
        elif n == 0:
            colors.append(_WHITE)
        else:
            rank = positives.index(value)          # 0 = menor, n-1 = mayor
            t    = rank / (n - 1) if n > 1 else 1.0
            colors.append(_lerp_color(_GREEN_LO, _GREEN_HI, t))
    return colors


def _ganancia_color_requests(sheet_id: int, rows: list[dict]) -> list[dict]:
    """Un updateCells por columna de ganancia con color calculado por ranking fila a fila."""
    # Calcula los colores una sola vez por fila, solo con los valores de ganancia
    row_colors = [_row_ganancia_colors(r["ganancias"]) for r in rows]

    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": 1 + len(rows),
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "rows": [
                    {"values": [{"userEnteredFormat": {"backgroundColor": row_colors[i][col_offset]}}]}
                    for i in range(len(rows))
                ],
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
        for col_offset, col_idx in enumerate(GANANCIA_COLS)
    ]


def _col_width(sheet_rows: list[list], col_idx: int, px_per_char: int = 7, padding: int = 10) -> int:
    """Estima el ancho en píxeles de una columna basándose en el contenido más largo."""
    max_len = max((len(str(row[col_idx])) for row in sheet_rows if col_idx < len(row)), default=4)
    return max_len * px_per_char + padding


def write_profession_sheet(
    ws: gspread.Worksheet,
    rows: list[dict],
    profession: str = "",
    ing_sheet_id: int | None = None,
    recipe_row_map: dict | None = None,
    filter_view_map: dict | None = None,
):
    """Escribe encabezados + datos en la hoja, borrando el contenido anterior."""
    _api_call(ws.clear)

    sheet_id = ws.id

    sheet_rows = [HEADERS]
    for r in rows:
        lot_cols = []
        for c, p, g in zip(r["costos"], r["precios"], r["ganancias"]):
            lot_cols += [c, p, g]

        if ing_sheet_id is not None and recipe_row_map is not None:
            key = (profession, r["result"])
            fv_id = filter_view_map.get(key) if filter_view_map else None
            if fv_id is not None:
                url = (
                    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
                    f"/edit#gid={ing_sheet_id}&fvid={fv_id}"
                )
            else:
                first_row, last_row = recipe_row_map.get(key, (2, 2))
                url = (
                    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
                    f"/edit#gid={ing_sheet_id}&range=A{first_row}:H{last_row}"
                )
            ing_cell = f'=HYPERLINK("{url}"; "Ver ingredientes")'
        else:
            ing_cell = r["ingredientes"]

        sheet_rows.append([
            r["result"],
            r["level"],
            *lot_cols,
            ing_cell,
        ])

    _api_call(ws.update, "A1", sheet_rows, value_input_option="USER_ENTERED")

    # Construir requests de formato + ancho de columnas en una sola llamada
    requests = [
        # Encabezado: fondo azul, texto blanco y negrita
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.2, "green": 0.35, "blue": 0.6},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        # Columnas de ganancia (E, H, K, N → índices 4, 7, 10, 13): fondo verde oscuro
        *[
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                              "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": {"red": 0.1, "green": 0.45, "blue": 0.2},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                    }},
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            }
            for col in (4, 7, 10, 13)
        ],
        # Columnas C..N: formato numérico sin decimales
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 14},
                "cell": {"userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                }},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        # Ancho de columnas basado en contenido
        *[
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": _col_width(sheet_rows, i) + (10 if i > 0 else 0)},
                    "fields": "pixelSize",
                }
            }
            for i in range(len(HEADERS))
        ],
        # Color por fila en columnas de ganancia (índices 4, 7, 10, 13)
        *_ganancia_color_requests(sheet_id, rows),
        # Líneas gruesas verticales entre grupos de lotes (después de B, E, H, K, N)
        *[
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1 + len(rows),
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    },
                    "right": {"style": "SOLID_THICK", "color": {"red": 0, "green": 0, "blue": 0}},
                }
            }
            for col in (1, 4, 7, 10, 13)
        ],
        # Alto de filas
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1 + len(rows),
                },
                "properties": {"pixelSize": 30},
                "fields": "pixelSize",
            }
        },
        # Fijar primera fila y primera columna
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1},
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        },
        # Filtro básico (tabla)
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1 + len(rows),
                        "startColumnIndex": 0,
                        "endColumnIndex": len(HEADERS),
                    }
                }
            }
        },
    ]

    _api_call(ws.spreadsheet.batch_update, {"requests": requests})


# ── Main ──────────────────────────────────────────────────────────────────────

def _connect() -> gspread.Spreadsheet:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def _validate_config() -> bool:
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] No se encontró: {CREDENTIALS_FILE}")
        print("  → Descarga las credenciales de tu Service Account desde Google Cloud.")
        return False
    if SPREADSHEET_ID == "TU_SPREADSHEET_ID_AQUI":
        print("[ERROR] Falta configurar SPREADSHEET_ID en este script.")
        print("  → Copia el ID de la URL de tu Google Sheet.")
        return False
    return True


def export_profession(profession: str):
    """Exporta una única profesión a su hoja en Google Sheets."""
    if not _validate_config():
        return

    data = load_recipes_by_profession()
    cap  = profession.capitalize()
    icon = PROFESSION_ICONS.get(cap, "")
    norm = f"{cap} {icon}" if icon else cap
    if norm not in data:
        available = ", ".join(sorted(data.keys()))
        print(f"[ERROR] Profesión '{profession}' no encontrada.")
        print(f"  Disponibles: {available}")
        return

    print("Conectando a Google Sheets …")
    spreadsheet = _connect()
    print("Escribiendo hoja de ingredientes …")
    ing_sheet_id, recipe_row_map, filter_view_map = write_ingredients_sheet(spreadsheet, data)
    rows = data[norm]
    ws = get_or_create_worksheet(spreadsheet, norm)
    write_profession_sheet(ws, rows, profession=norm,
                           ing_sheet_id=ing_sheet_id, recipe_row_map=recipe_row_map,
                           filter_view_map=filter_view_map)
    print(f"[DONE] {norm}: {len(rows)} recetas exportadas.")


def export_all_professions():
    """Exporta todas las profesiones a Google Sheets."""
    if not _validate_config():
        return

    print("Cargando recetas …")
    data = load_recipes_by_profession()

    if not data:
        print("[ERROR] No se encontraron archivos de recetas.")
        return

    print("Conectando a Google Sheets …")
    spreadsheet = _connect()

    print("Escribiendo hoja de ingredientes …")
    ing_sheet_id, recipe_row_map, filter_view_map = write_ingredients_sheet(spreadsheet, data)
    time.sleep(2)

    for profession, rows in sorted(data.items()):
        ws = get_or_create_worksheet(spreadsheet, profession)
        write_profession_sheet(ws, rows, profession=profession,
                               ing_sheet_id=ing_sheet_id, recipe_row_map=recipe_row_map,
                               filter_view_map=filter_view_map)
        print(f"  {profession:<20} {len(rows)} recetas exportadas")
        time.sleep(2)

    print(f"\n[DONE] {len(data)} profesiones exportadas.")


def main():
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1].lower() == "ingredientes":
            if not _validate_config():
                return
            print("Cargando recetas …")
            data = load_recipes_by_profession()
            print("Conectando a Google Sheets …")
            write_ingredients_sheet(_connect(), data)
            print("[DONE] Hoja de ingredientes exportada.")
        else:
            export_profession(sys.argv[1])
    else:
        export_all_professions()


if __name__ == "__main__":
    main()