"""
Sincronizacion de precios de Almanax via Google Sheets.

Usa la infraestructura compartida en shared/sync/.
"""

import json
import os
import sys

_ROOT = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.config import PRICES_FILE
from shared.sync.engine import validate_config, connect, download_bundle, upload_bundle
from shared.sync.merge import merge_nested_prices

_SYNC_SHEET = "_sync_almanax"


def _load_local() -> dict:
    if not PRICES_FILE.exists():
        return {}
    with open(PRICES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_local(prices: dict):
    PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


def sync_data() -> list[str]:
    """
    Sincronizacion bidireccional de precios de Almanax.
    Devuelve lista de advertencias.
    """
    if not validate_config():
        raise RuntimeError("Configuracion de Google Sheets incompleta.")

    print("Cargando precios locales ...")
    local_prices = _load_local()

    print("Conectando a Google Sheets ...")
    ss = connect()
    bundle = download_bundle(ss, _SYNC_SHEET)

    if not bundle:
        print("No hay datos remotos -- subiendo datos locales ...")
        upload_bundle(ss, _SYNC_SHEET, {"item_prices": local_prices})
        print("[DONE] Primera sincronizacion completada.")
        return []

    remote_prices = bundle.get("item_prices", {})
    print(f"  Ultima sync remota: {bundle.get('exported_at', '?')}")

    print("Mergeando precios ...")
    merged, local_wins, remote_wins = merge_nested_prices(local_prices, remote_prices)
    print(f"  Precios: {local_wins} locales, {remote_wins} remotos")

    print("Guardando localmente ...")
    _save_local(merged)

    print("Subiendo a Google Sheets ...")
    upload_bundle(ss, _SYNC_SHEET, {"item_prices": merged})

    total = local_wins + remote_wins
    print(f"[DONE] Sync completa -- {total} datos procesados.")
    return []
