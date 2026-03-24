import json
import os
import tkinter as tk
from tkinter import messagebox

import keyboard
import pyautogui


def load_calibration(calibration_file: str):
    if not os.path.exists(calibration_file):
        return None
    with open(calibration_file, "r") as f:
        return json.load(f)


class CalibrationWindow:
    def __init__(self, parent, points, calibration_file, on_done=None):
        self.points = list(points)
        self.calibration_file = calibration_file
        self.on_done = on_done
        self.calibration = {}
        self.current_index = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Calibración")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.grab_set()

        self.info_label = tk.Label(self.win, text="", width=42, wraplength=300, justify=tk.LEFT)
        self.info_label.pack(pady=12, padx=14)

        self.cancel_btn = tk.Button(self.win, text="Cancelar", width=20, command=self.win.destroy)
        self.cancel_btn.pack(pady=(2, 12), padx=14)

        keyboard.add_hotkey("c", self.capture)
        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.cancel_btn.config(command=self._on_cancel)

        self.update_label()

    def update_label(self):
        key, desc = self.points[self.current_index]
        self.info_label.config(
            text=(
                f"Punto {self.current_index + 1} / {len(self.points)}\n\n"
                f"Mueve el ratón a: {desc}\n\n"
                f"Luego pulsa la tecla C para capturar"
            )
        )

    def capture(self):
        pos = pyautogui.position()
        key, _ = self.points[self.current_index]
        self.calibration[key] = [pos.x, pos.y]
        self.current_index += 1

        if self.current_index >= len(self.points):
            keyboard.remove_hotkey("c")
            with open(self.calibration_file, "w") as f:
                json.dump(self.calibration, f, indent=2)
            messagebox.showinfo("Calibración completa", "Calibración guardada correctamente.", parent=self.win)
            self.win.destroy()
            if self.on_done:
                self.on_done()
        else:
            self.update_label()

    def _on_cancel(self):
        keyboard.remove_hotkey("c")
        self.win.destroy()
