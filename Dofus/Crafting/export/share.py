"""
Sincronización de datos entre usuarios vía Google Sheets.

Escribe/lee un tab oculto '_sync' en el mismo spreadsheet, con el JSON
completo (materiales + recetas) dividido en chunks de 45 000 chars por fila.
"""

import json
import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from datetime import datetime, timezone

from config.config import PRICES_FILE
from utils.loaders import get_recipe_files
from export.export_to_sheets import _connect, _validate_config, get_or_create_worksheet

_SYNC_SHEET  = "_sync"
_CHUNK_SIZE  = 45_000
_VERSION     = 1


def _serialize() -> str:
    with open(PRICES_FILE, encoding="utf-8") as f:
        materials = json.load(f)

    recipes = {}
    for path in get_recipe_files():
        prof = os.path.splitext(os.path.basename(path))[0].replace("recipes_", "")
        with open(path, encoding="utf-8") as f:
            recipes[prof] = json.load(f)

    bundle = {
        "version":      _VERSION,
        "exported_at":  datetime.now(timezone.utc).isoformat(),
        "materials_prices": materials,
        "recipes":      recipes,
    }
    return json.dumps(bundle, ensure_ascii=False)


def export_data():
    """Sube los datos actuales al tab '_sync' del spreadsheet."""
    if not _validate_config():
        raise RuntimeError("Configuración de Google Sheets incompleta.")

    print("Serializando datos …")
    text   = _serialize()
    chunks = [text[i:i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
    print(f"  {len(text):,} chars → {len(chunks)} filas")

    print("Conectando a Google Sheets …")
    ss = _connect()
    ws = get_or_create_worksheet(ss, _SYNC_SHEET)
    ws.clear()
    ws.update([[c] for c in chunks], value_input_option="RAW")
    print(f"[DONE] Datos subidos al tab '{_SYNC_SHEET}'.")


def import_data() -> list[str]:
    """
    Descarga los datos del tab '_sync' y sobreescribe los archivos locales.
    Devuelve lista de advertencias.
    """
    if not _validate_config():
        raise RuntimeError("Configuración de Google Sheets incompleta.")

    print("Conectando a Google Sheets …")
    ss = _connect()

    try:
        ws = ss.worksheet(_SYNC_SHEET)
    except Exception:
        raise RuntimeError(f"No se encontró el tab '{_SYNC_SHEET}'. Pide a alguien que exporte primero.")

    print("Descargando datos …")
    rows   = ws.get_all_values()
    chunks = [row[0] for row in rows if row and row[0]]
    if not chunks:
        raise RuntimeError("El tab de sincronización está vacío.")

    text   = "".join(chunks)
    bundle = json.loads(text)

    if bundle.get("version") != _VERSION:
        raise RuntimeError(f"Versión de archivo no soportada: {bundle.get('version')}")

    print(f"  Exportado el: {bundle.get('exported_at', '?')}")

    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(bundle["materials_prices"], f, ensure_ascii=False, indent=2)

    recipe_file_map = {
        os.path.splitext(os.path.basename(p))[0].replace("recipes_", ""): p
        for p in get_recipe_files()
    }

    warnings = []
    for prof, data in bundle.get("recipes", {}).items():
        path = recipe_file_map.get(prof)
        if not path:
            warnings.append(f"Profesión desconocida ignorada: {prof}")
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[DONE] {len(bundle.get('recipes', {}))} profesiones importadas.")
    return warnings
