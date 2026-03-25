import json
import os
import tkinter as tk
from tkinter import messagebox

import keyboard
import pyautogui

from shared.colors import C


def load_calibration(calibration_file: str):
    if not os.path.exists(calibration_file):
        return None
    with open(calibration_file, "r") as f:
        return json.load(f)


class CalibrationWindow:
    def __init__(self, parent, points, calibration_file, on_done=None, transform=None):
        self.points = list(points)
        self.calibration_file = calibration_file
        self.on_done = on_done
        self.transform = transform
        self.calibration = {}
        self.current_index = 0
        self.region_phase = None  # None | "tl" | "br"
        self.region_tl = None

        self.win = tk.Toplevel(parent)
        self.win.title("Calibración")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.configure(bg=C["bg"])

        self.info_label = tk.Label(self.win, text="", width=46, wraplength=320, justify=tk.LEFT,
                                   bg=C["bg"], fg=C["text"], font=("Segoe UI", 9))
        self.info_label.pack(pady=12, padx=14)

        self.cancel_btn = tk.Button(self.win, text="Cancelar", width=20,
                                    bg=C["surface"], fg=C["dim"], relief="flat",
                                    command=self._on_cancel)
        self.cancel_btn.pack(pady=(2, 12), padx=14)

        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)

        keyboard.add_hotkey("c", self.capture)
        self.update_label()

    def _current_type(self):
        entry = self.points[self.current_index]
        return entry[2] if len(entry) > 2 else "point"

    def update_label(self):
        entry = self.points[self.current_index]
        key, desc = entry[0], entry[1]
        kind = self._current_type()
        total = len(self.points)
        step = self.current_index + 1

        if kind == "info":
            text = (
                f"Paso {step} / {total}\n\n"
                f"{desc}\n\n"
                f"Cuando estés listo, pulsa C para continuar"
            )
        elif kind == "region" and self.region_phase == "br":
            text = (
                f"Paso {step} / {total}\n\n"
                f"Región: {desc}\n\n"
                f"Mueve el ratón a la esquina INFERIOR-DERECHA\n"
                f"Luego pulsa C para capturar"
            )
        elif kind == "region":
            text = (
                f"Paso {step} / {total}\n\n"
                f"Región: {desc}\n\n"
                f"Mueve el ratón a la esquina SUPERIOR-IZQUIERDA\n"
                f"Luego pulsa C para capturar"
            )
        else:
            text = (
                f"Paso {step} / {total}\n\n"
                f"Mueve el ratón a: {desc}\n\n"
                f"Luego pulsa C para capturar"
            )

        self.info_label.config(text=text)

    def capture(self):
        kind = self._current_type()
        entry = self.points[self.current_index]
        key = entry[0]

        if kind == "info":
            self.current_index += 1

        elif kind == "region":
            pos = list(pyautogui.position())
            if self.region_phase is None:
                self.region_tl = pos
                self.region_phase = "br"
                self.update_label()
                return
            else:
                br = pos
                tl = self.region_tl
                self.calibration[key] = [tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]]
                self.region_phase = None
                self.region_tl = None
                self.current_index += 1

        else:
            pos = list(pyautogui.position())
            self.calibration[key] = pos
            self.current_index += 1

        if self.current_index >= len(self.points):
            self._finish()
        else:
            self.update_label()

    def _finish(self):
        keyboard.remove_hotkey("c")
        data = self.calibration
        if self.transform:
            data = self.transform(data)
        os.makedirs(os.path.dirname(self.calibration_file), exist_ok=True)
        with open(self.calibration_file, "w") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Calibración completa", "Calibración guardada correctamente.", parent=self.win)
        self.win.destroy()
        if self.on_done:
            self.on_done()

    def _on_cancel(self):
        keyboard.remove_hotkey("c")
        self.win.destroy()
