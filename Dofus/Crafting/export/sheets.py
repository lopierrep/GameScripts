"""
Sincronización de datos entre usuarios vía Google Sheets.

Merge bidireccional dato por dato: compara el campo ``prices_updated_at``
de cada receta y material, y se queda con el más reciente de cada lado.
El resultado mergeado se escribe tanto en local como en el spreadsheet.

Requisitos:
  pip install gspread google-auth

Configuración inicial (solo una vez):
  1. Ir a https://console.cloud.google.com
  2. Crear proyecto → habilitar "Google Sheets API"
  3. Crear Service Account → descargar JSON de credenciales
  4. Guardar el JSON como: Crafting/export/credentials.json
  5. Abrir tu Google Sheet → compartirlo con el email del Service Account
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.config import CREDENTIALS_FILE, PRICES_FILE, SPREADSHEET_ID
from utils.loaders import get_recipe_files

# ── Configuración ────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_SYNC_SHEET   = "_sync"
_CHUNK_SIZE   = 45_000
_SYNC_VERSION = 1


# ── Conexión ─────────────────────────────────────────────────────────────────

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


def _connect() -> gspread.Spreadsheet:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def _validate_config() -> bool:
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] No se encontró: {CREDENTIALS_FILE}")
        print("  → Descarga las credenciales de tu Service Account desde Google Cloud.")
        return False
    return True


def _get_or_create_worksheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    """Devuelve la hoja con ese título, creándola si no existe."""
    try:
        return _api_call(spreadsheet.worksheet, title)
    except gspread.exceptions.WorksheetNotFound:
        return _api_call(spreadsheet.add_worksheet, title=title, rows=500, cols=10)


# ── Datos locales ────────────────────────────────────────────────────────────

def _load_local() -> tuple[dict, dict[str, list]]:
    """Devuelve (materials, {profesion: [recetas]}) desde los archivos locales."""
    with open(PRICES_FILE, encoding="utf-8") as f:
        materials = json.load(f)

    recipes = {}
    for path in get_recipe_files():
        prof = os.path.splitext(os.path.basename(path))[0].replace("recipes_", "")
        with open(path, encoding="utf-8") as f:
            recipes[prof] = json.load(f)

    return materials, recipes


def _save_local(materials: dict, recipes: dict[str, list]):
    """Escribe materials y recetas a los archivos locales."""
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(materials, f, ensure_ascii=False, indent=2)

    recipe_file_map = {
        os.path.splitext(os.path.basename(p))[0].replace("recipes_", ""): p
        for p in get_recipe_files()
    }
    for prof, data in recipes.items():
        path = recipe_file_map.get(prof)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


# ── Datos remotos ────────────────────────────────────────────────────────────

def _download_bundle(ss: gspread.Spreadsheet) -> dict | None:
    """Descarga y parsea el bundle del tab _sync. Devuelve None si no existe."""
    try:
        ws = ss.worksheet(_SYNC_SHEET)
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


def _upload_bundle(ss: gspread.Spreadsheet, materials: dict, recipes: dict[str, list]):
    """Sube un bundle mergeado al tab _sync."""
    bundle = {
        "version":          _SYNC_VERSION,
        "exported_at":      datetime.now(timezone.utc).isoformat(),
        "materials_prices": materials,
        "recipes":          recipes,
    }
    text = json.dumps(bundle, ensure_ascii=False)
    chunks = [text[i:i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
    print(f"  {len(text):,} chars → {len(chunks)} filas")

    ws = _get_or_create_worksheet(ss, _SYNC_SHEET)
    ws.clear()
    ws.update([[c] for c in chunks], value_input_option="RAW")


# ── Merge ────────────────────────────────────────────────────────────────────

def _ts(obj: dict) -> str:
    """Extrae prices_updated_at como string comparable, o '' si no existe."""
    return obj.get("prices_updated_at", "")


def _merge_materials(local: dict, remote: dict) -> tuple[dict, int, int]:
    """
    Merge dato por dato de materials_prices.
    Estructura: {market: {category: {item: {x1, x10, ..., prices_updated_at?}}}}
    Devuelve (merged, n_local_wins, n_remote_wins).
    """
    merged = {}
    local_wins = remote_wins = 0

    all_markets = set(local) | set(remote)
    for market in all_markets:
        local_market  = local.get(market, {})
        remote_market = remote.get(market, {})
        merged[market] = {}

        all_categories = set(local_market) | set(remote_market)
        for category in all_categories:
            local_cat  = local_market.get(category, {})
            remote_cat = remote_market.get(category, {})
            merged[market][category] = {}

            all_items = set(local_cat) | set(remote_cat)
            for item in all_items:
                local_item  = local_cat.get(item)
                remote_item = remote_cat.get(item)

                if local_item and not remote_item:
                    merged[market][category][item] = local_item
                    local_wins += 1
                elif remote_item and not local_item:
                    merged[market][category][item] = remote_item
                    remote_wins += 1
                elif _ts(remote_item) > _ts(local_item):
                    merged[market][category][item] = remote_item
                    remote_wins += 1
                else:
                    merged[market][category][item] = local_item
                    local_wins += 1

    return merged, local_wins, remote_wins


def _merge_recipes(local: dict[str, list], remote: dict[str, list]) -> tuple[dict[str, list], int, int]:
    """
    Merge dato por dato de recetas por profesión.
    Clave de cada receta: campo "result".
    Devuelve (merged, n_local_wins, n_remote_wins).
    """
    merged = {}
    local_wins = remote_wins = 0

    all_profs = set(local) | set(remote)
    for prof in all_profs:
        local_list  = {r["result"]: r for r in local.get(prof, [])}
        remote_list = {r["result"]: r for r in remote.get(prof, [])}

        merged_list = {}
        all_recipes = set(local_list) | set(remote_list)
        for name in all_recipes:
            local_r  = local_list.get(name)
            remote_r = remote_list.get(name)

            if local_r and not remote_r:
                merged_list[name] = local_r
                local_wins += 1
            elif remote_r and not local_r:
                merged_list[name] = remote_r
                remote_wins += 1
            elif _ts(remote_r) > _ts(local_r):
                merged_list[name] = remote_r
                remote_wins += 1
            else:
                merged_list[name] = local_r
                local_wins += 1

        # Mantener el orden original local, agregando nuevas del remoto al final
        local_order = [r["result"] for r in local.get(prof, [])]
        new_from_remote = [n for n in remote_list if n not in local_list]
        ordered = local_order + new_from_remote
        merged[prof] = [merged_list[n] for n in ordered if n in merged_list]

    return merged, local_wins, remote_wins


# ── API pública ──────────────────────────────────────────────────────────────

def sync_data() -> list[str]:
    """
    Sincronización bidireccional dato por dato.
    Compara prices_updated_at de cada receta/material y se queda con el más reciente.
    Escribe el resultado mergeado tanto en local como en Sheets.
    Devuelve lista de advertencias.
    """
    if not _validate_config():
        raise RuntimeError("Configuración de Google Sheets incompleta.")

    print("Cargando datos locales …")
    local_mat, local_rec = _load_local()

    print("Conectando a Google Sheets …")
    ss = _connect()
    bundle = _download_bundle(ss)

    if not bundle:
        print("No hay datos remotos — subiendo datos locales …")
        _upload_bundle(ss, local_mat, local_rec)
        print("[DONE] Primera sincronización completada.")
        return []

    remote_mat = bundle.get("materials_prices", {})
    remote_rec = bundle.get("recipes", {})
    print(f"  Última sync remota: {bundle.get('exported_at', '?')}")

    print("Mergeando materiales …")
    merged_mat, mat_local, mat_remote = _merge_materials(local_mat, remote_mat)
    print(f"  Materiales: {mat_local} locales, {mat_remote} remotos")

    print("Mergeando recetas …")
    merged_rec, rec_local, rec_remote = _merge_recipes(local_rec, remote_rec)
    print(f"  Recetas: {rec_local} locales, {rec_remote} remotas")

    print("Guardando localmente …")
    _save_local(merged_mat, merged_rec)

    print("Subiendo a Google Sheets …")
    _upload_bundle(ss, merged_mat, merged_rec)

    warnings = []
    remote_only_profs = set(remote_rec) - set(local_rec)
    for prof in remote_only_profs:
        warnings.append(f"Profesión remota sin archivo local (ignorada): {prof}")

    total = mat_local + mat_remote + rec_local + rec_remote
    print(f"[DONE] Sync completa — {total} datos procesados.")
    return warnings
