"""
Motor generico de sincronizacion via Google Sheets.

Provee conexion, chunking, upload/download de bundles JSON.
Los proyectos usan este modulo a traves de adaptadores especificos.
"""

import json
import time
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from shared.sync.config import CREDENTIALS_FILE, SPREADSHEET_ID, SCOPES

_CHUNK_SIZE   = 45_000
_SYNC_VERSION = 1


# -- Conexion -----------------------------------------------------------------

def api_call(fn, *args, retries: int = 5, **kwargs):
    """Llama fn(*args, **kwargs) reintentando con backoff exponencial si hay 429."""
    delay = 10
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                print(f"    [RATE LIMIT] Esperando {delay}s ...")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def validate_config() -> bool:
    """Verifica que el archivo de credenciales exista."""
    if not __import__("os").path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] No se encontro: {CREDENTIALS_FILE}")
        print("  -> Descarga las credenciales de tu Service Account desde Google Cloud.")
        return False
    return True


def connect() -> gspread.Spreadsheet:
    """Autentica y abre el spreadsheet configurado."""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    """Devuelve la hoja con ese titulo, creandola si no existe."""
    try:
        return api_call(spreadsheet.worksheet, title)
    except gspread.exceptions.WorksheetNotFound:
        return api_call(spreadsheet.add_worksheet, title=title, rows=500, cols=10)


# -- Bundle I/O ---------------------------------------------------------------

def download_bundle(ss: gspread.Spreadsheet, sheet_name: str) -> dict | None:
    """Descarga y parsea el bundle JSON de la hoja indicada. Devuelve None si no existe."""
    try:
        ws = ss.worksheet(sheet_name)
    except Exception:
        return None
    rows = ws.get_all_values()
    chunks = [row[0] for row in rows if row and row[0]]
    if not chunks:
        return None
    bundle = json.loads("".join(chunks))
    if bundle.get("version") != _SYNC_VERSION:
        return None
    return bundle


def upload_bundle(ss: gspread.Spreadsheet, sheet_name: str, payload: dict):
    """Sube un dict como bundle JSON chunked a la hoja indicada."""
    bundle = {
        "version":     _SYNC_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    text = json.dumps(bundle, ensure_ascii=False)
    chunks = [text[i:i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
    print(f"  {len(text):,} chars -> {len(chunks)} filas")

    ws = get_or_create_worksheet(ss, sheet_name)
    ws.clear()
    ws.update([[c] for c in chunks], value_input_option="RAW")
