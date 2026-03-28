"""
Ganadero – Orquestador
======================
Conecta la UI con los módulos de core/.
"""

import sys
import json
import tkinter as tk
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR.parent))

from core.carburante_efficiency import analizar, calcular_costo_dragopavo, MONTURAS_POR_CERCADO
from ui.ui import GanaderoUI

# ── Settings ──────────────────────────────────────────────────────────────────
SETTINGS_FILE = ROOT_DIR / "data" / "settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


# ── App ───────────────────────────────────────────────────────────────────────

class GanaderoApp:
    def __init__(self):
        self._settings = _load_settings()
        self._root = tk.Tk()

        self._ui = GanaderoUI(self._root, callbacks={
            "refresh": self._refresh,
        }, settings=self._settings)

        self._refresh()

    def _refresh(self):
        umbral = self._ui.umbral_var.get()

        # Guardar settings
        self._settings["umbral"] = umbral
        _save_settings(self._settings)

        # Calcular
        resultado = analizar()
        costos = calcular_costo_dragopavo()

        # Actualizar UI
        self._ui.update_topes(resultado, umbral)
        self._ui.update_costos(costos, MONTURAS_POR_CERCADO)
        self._ui.update_status(
            f"Umbral: {umbral:,} k (costo total)  |  "
            f"Verde = bajo umbral   Rojo = sobre umbral"
        )

    def run(self):
        self._root.mainloop()


if __name__ == "__main__":
    GanaderoApp().run()
