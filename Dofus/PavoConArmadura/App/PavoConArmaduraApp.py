import tkinter as tk
from tkinter import messagebox
import threading
import pyautogui
import keyboard
import time
import random
import json
import os
import sys

if getattr(sys, "frozen", False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

CALIBRATION_FILE = os.path.join(BASE_PATH, "calibration.json")

pyautogui.FAILSAFE = True

CALIBRATION_POINTS = [
    ("NPCLocation",         "el NPC"),
    ("OptionLocation1",     "la opción de raza 1"),
    ("OptionLocation2",     "la opción de raza 2"),
    ("OptionLocation3",     "la opción de raza 3"),
    ("OptionLocation4",     "la opción de raza 4 (85%)"),
    ("StartButtonLocation", "el botón de iniciar carrera"),
]


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


class PavoConArmaduraApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pavo Con Armadura")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.running = False
        self.race_count = 0

        # Status
        self.status_var = tk.StringVar(value="Listo")
        tk.Label(root, textvariable=self.status_var, width=30, wraplength=200, justify=tk.CENTER).pack(
            pady=(12, 6), padx=14
        )

        # Race counter
        self.race_var = tk.StringVar(value="Carreras: 0")
        tk.Label(root, textvariable=self.race_var, width=30, justify=tk.CENTER,
                 font=("Segoe UI", 10, "bold")).pack(pady=(0, 6), padx=14)

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=(4, 4), padx=14)

        self.start_btn = tk.Button(
            btn_frame, text="Start", width=10,
            bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"),
            command=self.on_start
        )
        self.start_btn.pack(side=tk.LEFT, padx=6)

        self.finish_btn = tk.Button(
            btn_frame, text="Finish (S)", width=10,
            bg="#f44336", fg="white", font=("Segoe UI", 10, "bold"),
            command=self.on_finish, state=tk.DISABLED
        )
        self.finish_btn.pack(side=tk.LEFT, padx=6)

        self.calibrate_btn = tk.Button(
            root, text="Calibrar puntos", width=24,
            command=self.on_calibrate
        )
        self.calibrate_btn.pack(pady=(4, 12), padx=14)

    # ── helpers ────────────────────────────────────────────────────────────────

    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def set_race_count(self, count: int):
        self.root.after(0, lambda: self.race_var.set(f"Carreras: {count}"))

    def load_calibration(self):
        if not os.path.exists(CALIBRATION_FILE):
            return None
        with open(CALIBRATION_FILE, "r") as f:
            return json.load(f)

    def custom_move(self, x1, y1, x2, y2):
        steps = int(random.uniform(3, 5))
        for i in range(steps):
            t = i / steps
            x = x1 + (x2 - x1) * t + random.randint(-2, 2)
            y = y1 + (y2 - y1) * t + random.randint(-2, 2)
            pyautogui.moveTo(x, y)
            time.sleep(random.uniform(0.000001, 0.000003))
        pyautogui.moveTo(x2, y2)

    # ── button callbacks ───────────────────────────────────────────────────────

    def on_start(self):
        calibration = self.load_calibration()
        if calibration is None:
            messagebox.showerror("Error", "No hay calibración. Por favor calibra primero.")
            return

        self.running = True
        self.race_count = 0
        self.set_race_count(0)
        self.start_btn.config(state=tk.DISABLED)
        self.finish_btn.config(state=tk.NORMAL)
        self.calibrate_btn.config(state=tk.DISABLED)

        keyboard.add_hotkey("s", self.on_finish)
        threading.Thread(target=self.run_loop, args=(calibration,), daemon=True).start()

    def on_finish(self):
        self.running = False
        self.set_status("Deteniendo...")
        keyboard.remove_hotkey("s")

    def on_calibrate(self):
        CalibrationWindow(self.root)

    # ── main loop ──────────────────────────────────────────────────────────────

    def run_loop(self, calibration):
        while self.running:
            delay = random.uniform(0.5, 1)
            self.set_status(f"Iniciando en {delay:.1f}s...")
            time.sleep(delay)
            if not self.running:
                break

            self.race_count += 1
            self.set_race_count(self.race_count)

            # 1. Click NPC
            npc = calibration["NPCLocation"]
            tx = npc[0] + random.uniform(-2.5, 2.5)
            ty = npc[1] + random.uniform(-2.5, 2.5)
            self.set_status("Moviendo al NPC...")
            cx, cy = pyautogui.position()
            self.custom_move(cx, cy, tx, ty)
            pyautogui.click()
            time.sleep(random.uniform(0.5, 1))
            if not self.running:
                break

            # 2. Click race option (weighted)
            option_key = random.choices(
                ["OptionLocation1", "OptionLocation2", "OptionLocation3", "OptionLocation4"],
                weights=[5, 5, 5, 85]
            )[0]
            opt = calibration[option_key]
            tx = opt[0] + random.uniform(-5, 5)
            ty = opt[1] + random.uniform(-2.5, 2.5)
            self.set_status("Seleccionando opción...")
            cx, cy = pyautogui.position()
            self.custom_move(cx, cy, tx, ty)
            pyautogui.click()
            time.sleep(random.uniform(2, 3))
            if not self.running:
                break

            # 3. Click start race
            btn = calibration["StartButtonLocation"]
            tx = btn[0] + random.uniform(-15, 15)
            ty = btn[1] + random.uniform(-15, 15)
            self.set_status("Iniciando carrera...")
            cx, cy = pyautogui.position()
            self.custom_move(cx, cy, tx, ty)
            pyautogui.click()

            # 4. Wait race duration
            race_dur = random.uniform(32, 35)
            end_time = time.time() + race_dur
            while self.running and time.time() < end_time:
                remaining = end_time - time.time()
                self.set_status(f"Carrera en curso... {remaining:.0f}s")
                time.sleep(0.5)

        self.set_status("Proceso terminado.")
        self.root.after(0, self._on_stopped)

    def _on_stopped(self):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.finish_btn.config(state=tk.DISABLED)
        self.calibrate_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    PavoConArmaduraApp(root)
    root.mainloop()
