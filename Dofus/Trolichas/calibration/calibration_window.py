import json
import tkinter as tk
from tkinter import messagebox

import pyautogui

from calibration.calibration import CALIBRATION_FILE, CALIBRATION_POINTS


class CalibrationWindow:
    def __init__(self, parent, on_done=None):
        self.on_done = on_done
        self.calibration = {}
        self.points = list(CALIBRATION_POINTS)
        self.current_index = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Calibración")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.grab_set()

        self.info_label = tk.Label(self.win, text="", width=42, wraplength=300, justify=tk.LEFT)
        self.info_label.pack(pady=12, padx=14)

        self.capture_btn = tk.Button(
            self.win, text="Capturar posición",
            width=20, bg="#2196F3", fg="white",
            command=self.capture
        )
        self.capture_btn.pack(pady=4, padx=14)

        self.cancel_btn = tk.Button(self.win, text="Cancelar", width=20, command=self.win.destroy)
        self.cancel_btn.pack(pady=(2, 12), padx=14)

        self.win.bind("<c>", lambda e: self.capture())
        self.win.bind("<C>", lambda e: self.capture())

        self.update_label()

    def update_label(self):
        key, desc = self.points[self.current_index]
        self.info_label.config(
            text=(
                f"Punto {self.current_index + 1} / {len(self.points)}\n\n"
                f"Mueve el ratón a: {desc}\n\n"
                f"Luego haz clic en 'Capturar posición'\n"
                f"(o pulsa la tecla C)"
            )
        )

    def capture(self):
        pos = pyautogui.position()
        key, _ = self.points[self.current_index]
        self.calibration[key] = [pos.x, pos.y]
        self.current_index += 1

        if self.current_index >= len(self.points):
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(self.calibration, f, indent=2)
            messagebox.showinfo("Calibración completa", "Calibración guardada correctamente.", parent=self.win)
            self.win.destroy()
            if self.on_done:
                self.on_done()
        else:
            self.update_label()
