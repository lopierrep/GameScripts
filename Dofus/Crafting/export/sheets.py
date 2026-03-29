"""
Sincronizacion de datos de Crafting via Google Sheets.

Merge bidireccional dato por dato: compara el campo ``prices_updated_at``
de cada receta y material, y se queda con el mas reciente de cada lado.
El resultado mergeado se escribe tanto en local como en el spreadsheet.

Requisitos:
  pip install gspread google-auth

Configuracion inicial (solo una vez):
  1. Ir a https://console.cloud.google.com
  2. Crear proyecto -> habilitar "Google Sheets API"
  3. Crear Service Account -> descargar JSON de credenciales
  4. Guardar el JSON como: shared/sync/credentials.json
  5. Abrir tu Google Sheet -> compartirlo con el email del Service Account
"""

import json
import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_DOFUS = os.path.normpath(os.path.join(_ROOT, ".."))
for _p in (_ROOT, _DOFUS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.config import PRICES_FILE
from utils.loaders import get_recipe_files
from shared.sync.engine import validate_config, connect, download_bundle, upload_bundle
from shared.sync.merge import merge_nested_prices

_SYNC_SHEET = "_sync_crafting"
_OLD_SYNC_SHEET = "_sync"


# -- Datos locales ------------------------------------------------------------

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


# -- Merge de recetas (especifico de Crafting) ---------------------------------

def _ts(obj: dict) -> str:
    return obj.get("prices_updated_at", "")


def _merge_recipes(local: dict[str, list], remote: dict[str, list]) -> tuple[dict[str, list], int, int]:
    """
    Merge dato por dato de recetas por profesion.
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


# -- Migracion de hoja vieja ---------------------------------------------------

def _migrate_old_sheet(ss) -> dict | None:
    """Si existe la hoja _sync (nombre viejo), descarga sus datos."""
    bundle = download_bundle(ss, _OLD_SYNC_SHEET)
    if bundle:
        print("  Migrando datos de hoja '_sync' -> '_sync_crafting' ...")
    return bundle


# -- API publica ---------------------------------------------------------------

def sync_data() -> list[str]:
    """
    Sincronizacion bidireccional dato por dato.
    Compara prices_updated_at de cada receta/material y se queda con el mas reciente.
    Escribe el resultado mergeado tanto en local como en Sheets.
    Devuelve lista de advertencias.
    """
    if not validate_config():
        raise RuntimeError("Configuracion de Google Sheets incompleta.")

    print("Cargando datos locales ...")
    local_mat, local_rec = _load_local()

    print("Conectando a Google Sheets ...")
    ss = connect()

    # Intentar descargar de la hoja nueva, o migrar de la vieja
    bundle = download_bundle(ss, _SYNC_SHEET)
    if not bundle:
        bundle = _migrate_old_sheet(ss)

    if not bundle:
        print("No hay datos remotos -- subiendo datos locales ...")
        upload_bundle(ss, _SYNC_SHEET, {
            "materials_prices": local_mat,
            "recipes": local_rec,
        })
        print("[DONE] Primera sincronizacion completada.")
        return []

    remote_mat = bundle.get("materials_prices", {})
    remote_rec = bundle.get("recipes", {})
    print(f"  Ultima sync remota: {bundle.get('exported_at', '?')}")

    print("Mergeando materiales ...")
    merged_mat, mat_local, mat_remote = merge_nested_prices(local_mat, remote_mat)
    print(f"  Materiales: {mat_local} locales, {mat_remote} remotos")

    print("Mergeando recetas ...")
    merged_rec, rec_local, rec_remote = _merge_recipes(local_rec, remote_rec)
    print(f"  Recetas: {rec_local} locales, {rec_remote} remotas")

    print("Guardando localmente ...")
    _save_local(merged_mat, merged_rec)

    print("Subiendo a Google Sheets ...")
    upload_bundle(ss, _SYNC_SHEET, {
        "materials_prices": merged_mat,
        "recipes": merged_rec,
    })

    warnings = []
    remote_only_profs = set(remote_rec) - set(local_rec)
    for prof in remote_only_profs:
        warnings.append(f"Profesion remota sin archivo local (ignorada): {prof}")

    total = mat_local + mat_remote + rec_local + rec_remote
    print(f"[DONE] Sync completa -- {total} datos procesados.")
    return warnings
