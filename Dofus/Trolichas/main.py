import sys
import os

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

import tkinter as tk
from tkinter import messagebox
import threading
import keyboard

from shared.calibration import CalibrationWindow, load_calibration
from config.calibration_config import CALIBRATION_POINTS, CALIBRATION_FILE
from race_loop import run_race_loop
from ui import LarvaRaceApp


def main():
    root = tk.Tk()
    running = False

    def on_start():
        nonlocal running
        calibration = load_calibration(CALIBRATION_FILE)
        if calibration is None:
            messagebox.showerror("Error", "No hay calibración. Por favor calibra primero.")
            return

        running = True
        app.set_race_count(0)
        app.set_running(True)

        keyboard.add_hotkey("s", on_finish)
        threading.Thread(
            target=run_race_loop,
            args=(calibration, lambda: running, app.set_status, app.set_race_count),
            daemon=True
        ).start()
        root.after(100, _poll_stopped)

    def on_finish():
        nonlocal running
        running = False
        app.set_status("Deteniendo...")
        keyboard.remove_hotkey("s")

    def on_calibrate():
        CalibrationWindow(root, CALIBRATION_POINTS, CALIBRATION_FILE)

    def _poll_stopped():
        if running:
            root.after(200, _poll_stopped)
        else:
            app.set_running(False)

    app = LarvaRaceApp(root, on_start=on_start, on_finish=on_finish, on_calibrate=on_calibrate)
    root.mainloop()


if __name__ == "__main__":
    main()
