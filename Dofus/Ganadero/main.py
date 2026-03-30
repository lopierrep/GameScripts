"""
Ganadero – Orquestador
======================
Conecta la UI con los módulos de core/.
"""

import sys
import json
import threading
import tkinter as tk
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR.parent))

from Ganadero.core.carburante_efficiency import analizar
from Ganadero.core.ciclo_diario import calcular_ciclo_diario, calcular_estrategia_nocturna
from shared.ui.colors import C
from Ganadero.ui.ui import GanaderoUI

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


# ── Stdout redirect ───────────────────────────────────────────────────────────

class _StdoutRedirect:
    def __init__(self, callback):
        self._cb = callback
    def write(self, text):
        if text:
            self._cb(text)
    def flush(self):
        pass


# ── App ───────────────────────────────────────────────────────────────────────

class GanaderoApp:
    def __init__(self, root=None):
        self._settings = _load_settings()
        if root is None:
            self._root = tk.Tk()
            self._root.withdraw()
        else:
            self._root = root  # FrameHost cuando está embebido en el hub
        self._stop_flag = [False]
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

        self._ui = GanaderoUI(self._root, callbacks={
            "refresh": self._refresh,
            "update_prices": self._start_update,
            "stop_update": self._stop_update,
            "calibrate": self._calibrate,
            "sync": self._sync,
        }, settings=self._settings)

        self._refresh()
        self._ui.update_status("Listo", C["dim"])
        self._root.update_idletasks()
        if root is None:
            self._root.deiconify()

    def _refresh(self):
        try:
            umbral = self._ui.umbral_var.get()
            horas_juego = max(1, min(23, self._ui.horas_juego_var.get()))
        except (tk.TclError, ValueError):
            return

        # Guardar settings
        self._settings["umbral"] = umbral
        self._settings["horas_juego"] = horas_juego
        _save_settings(self._settings)

        # Calcular
        resultado = analizar()
        ciclo = calcular_ciclo_diario(horas_juego)
        nocturna = calcular_estrategia_nocturna(24 - horas_juego)

        # Actualizar UI
        self._ui.update_topes(resultado, umbral)
        self._ui.update_costos(ciclo)
        self._ui.update_ciclo_diario(ciclo)
        self._ui.update_nocturna(nocturna)

    # ── Calibración ─────────────────────────────────────────────────────────

    def _calibrate(self):
        from shared.automation.calibration import CalibrationWindow
        from Crafting.calibration.calibration_config import CALIBRATION_POINTS, CALIBRATION_FILE, transform
        CalibrationWindow(
            self._root,
            CALIBRATION_POINTS,
            CALIBRATION_FILE,
            on_done=lambda: self._ui.update_status("✓ Calibración guardada", C["green"]),
            transform=transform,
        )

    # ── Sync ───────────────────────────────────────────────────────────────────

    def _sync(self):
        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self):
        try:
            self._root.after(0, self._ui.update_status, "Sincronizando…", C["accent"])
            from shared.sync.sheets import sync_data
            sync_data()
            self._root.after(0, self._refresh)
            self._root.after(0, self._ui.update_status, "✓ Sincronizado", C["green"])
        except Exception as e:
            self._root.after(0, self._ui.update_status, f"Error: {e}", C["red"])

    # ── Actualización de precios ─────────────────────────────────────────────

    def _start_update(self):
        self._stop_flag[0] = False
        self._ui.set_scanning(True)
        self._ui.update_status("Actualizando precios…", C["accent"])
        sys.stdout = _StdoutRedirect(lambda _: None)
        sys.stderr = _StdoutRedirect(lambda _: None)
        threading.Thread(target=self._run_update, daemon=True).start()

    def _stop_update(self):
        self._stop_flag[0] = True
        self._root.after(0, self._ui.hide_prompt)
        self._ui.update_status("Deteniendo…", C["yellow"])

    def _on_progress(self, msg: str):
        self._ui.update_status(msg, C["yellow"])

    def _restore_io(self):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

    def _run_update(self):
        from Ganadero.core.update_prices import run_update, MARKET_NAMES
        try:
            run_update(
                is_stopped=lambda: self._stop_flag[0],
                on_progress=lambda msg: self._root.after(
                    0, self._on_progress, msg,
                ),
                on_market_switch=self._ask_market_confirm,
            )
            self._root.after(0, self._on_update_done)
        except Exception as e:
            self._root.after(0, self._ui.update_status, f"Error: {e}", C["red"])
            self._root.after(0, self._ui.set_scanning, False)
            self._root.after(0, self._restore_io)

    def _ask_market_confirm(self, market_name: str, n_items: int) -> bool:
        """Bloquea el hilo worker hasta que el usuario confirme estar en el mercado."""
        if self._stop_flag[0]:
            return False
        from Ganadero.core.update_prices import MARKET_NAMES
        display = MARKET_NAMES.get(market_name, market_name)
        ev = threading.Event()

        def on_confirm():
            ev.set()

        self._root.after(
            0, self._ui.show_confirm,
            f"Ve al mercadillo de {display} y pulsa CONTINUAR ({n_items} items)",
            on_confirm,
        )
        while not ev.wait(timeout=0.2):
            if self._stop_flag[0]:
                self._root.after(0, self._ui.hide_prompt)
                return False
        return True

    def _on_update_done(self):
        self._restore_io()
        self._ui.set_scanning(False)
        self._refresh()

    def run(self):
        self._root.mainloop()


if __name__ == "__main__":
    GanaderoApp().run()
