import sys
import os
import json

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

import tkinter as tk
from tkinter import messagebox
import threading
import winsound
import keyboard

from shared.automation.calibration import CalibrationWindow, load_calibration
from shared.ui.colors import C
from calibration.calibration_config import CALIBRATION_POINTS, CALIBRATION_FILE
from config import ALERT_BEEP_FREQ, ALERT_BEEP_DURATION, ALERT_BEEP_INTERVAL, STOP_HOTKEY
from race_loop import run_race_loop
from ui import LarvaRaceApp


class TicketDialog(tk.Toplevel):
    """Popup estilizado para comprar tickets."""

    def __init__(self, parent, message):
        super().__init__(parent)
        self.title("Tickets")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = None

        tk.Label(
            self, text=message, bg=C["bg"], fg=C["text"],
            font=("Segoe UI", 10), wraplength=250, justify=tk.CENTER
        ).pack(pady=(16, 10), padx=20)

        entry_frame = tk.Frame(self, bg=C["bg"])
        entry_frame.pack(pady=(0, 10), padx=20)

        tk.Label(
            entry_frame, text="Cantidad:", bg=C["bg"], fg=C["dim"],
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.entry = tk.Entry(
            entry_frame, width=10, bg=C["surface"], fg=C["text"],
            insertbackground=C["text"], font=("Segoe UI", 10),
            relief="flat", justify=tk.CENTER
        )
        self.entry.pack(side=tk.LEFT)
        self.entry.focus_set()

        btn_frame = tk.Frame(self, bg=C["bg"])
        btn_frame.pack(pady=(0, 14), padx=20)

        tk.Button(
            btn_frame, text="Aceptar", width=10,
            bg=C["green"], fg=C["bg"], font=("Segoe UI", 9, "bold"),
            relief="flat", command=self._on_accept
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Cancelar", width=10,
            bg=C["red"], fg=C["bg"], font=("Segoe UI", 9, "bold"),
            relief="flat", command=self._on_cancel
        ).pack(side=tk.LEFT, padx=4)

        self.entry.bind("<Return>", lambda e: self._on_accept())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.transient(parent)
        self.grab_set()
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = self.winfo_screenwidth() * 3 // 4 - w // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")
        self.wait_window()

    def _on_accept(self):
        try:
            val = int(self.entry.get())
            if val > 0:
                self.result = val
        except ValueError:
            pass
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

_TICKETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets.json")


def _load_tickets() -> int:
    try:
        with open(_TICKETS_FILE, "r") as f:
            return json.load(f).get("tickets", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def _save_tickets(count: int):
    with open(_TICKETS_FILE, "w") as f:
        json.dump({"tickets": count}, f)


def build_trolichas_app(root):
    """Inicializa la app de Trolichas en el root/frame dado. Retorna el widget app."""
    stop_event = threading.Event()
    alert_event = threading.Event()
    race_thread = None
    user_stopped = False
    tickets = _load_tickets()

    def _ask_buy_tickets(message="No tienes tickets.\n¿Cuántos tickets compraste?"):
        dlg = TicketDialog(root, message)
        nonlocal tickets
        if dlg.result:
            tickets += dlg.result
            _save_tickets(tickets)
            app.set_tickets(tickets)
        return dlg.result

    def _consume_ticket():
        nonlocal tickets
        if tickets <= 0:
            return False
        tickets -= 1
        _save_tickets(tickets)
        app.set_tickets(tickets)
        return True

    def _alert_loop():
        while not alert_event.is_set():
            winsound.Beep(ALERT_BEEP_FREQ, ALERT_BEEP_DURATION)
            alert_event.wait(ALERT_BEEP_INTERVAL)

    def _stop_alert():
        alert_event.set()

    def _start_loop(calibration, reset_count=True):
        nonlocal race_thread, user_stopped
        user_stopped = False
        stop_event.clear()
        alert_event.set()
        if reset_count:
            app.set_race_count(0)
        app.set_running(True)

        keyboard.add_hotkey(STOP_HOTKEY, on_finish)
        race_thread = threading.Thread(
            target=run_race_loop,
            args=(calibration, lambda: not stop_event.is_set(), app.set_status, app.set_race_count, _consume_ticket),
            daemon=True
        )
        race_thread.start()
        root.after(100, _poll_stopped)

    def on_start():
        if tickets <= 0:
            if not _ask_buy_tickets():
                return

        calibration = load_calibration(CALIBRATION_FILE)
        if calibration is None:
            messagebox.showerror("Error", "No hay calibración. Por favor calibra primero.")
            return

        _start_loop(calibration)

    def on_finish():
        nonlocal user_stopped
        user_stopped = True
        stop_event.set()
        _stop_alert()
        app.set_status("Deteniendo...")
        try:
            keyboard.remove_hotkey(STOP_HOTKEY)
        except KeyError:
            pass

    def on_calibrate():
        CalibrationWindow(root, CALIBRATION_POINTS, CALIBRATION_FILE)

    def _poll_stopped():
        if race_thread is not None and race_thread.is_alive():
            root.after(200, _poll_stopped)
        else:
            calibration = load_calibration(CALIBRATION_FILE)
            stop_event.set()
            try:
                keyboard.remove_hotkey(STOP_HOTKEY)
            except KeyError:
                pass
            app.set_running(False)
            if tickets <= 0 and not user_stopped:
                alert_event.clear()
                threading.Thread(target=_alert_loop, daemon=True).start()
                app.set_status("Sin tickets. Recarga para continuar.")
                _ask_buy_tickets("¡Se acabaron los tickets!\n¿Cuántos tickets compraste?")
                _stop_alert()
                if tickets > 0 and calibration:
                    _start_loop(calibration, reset_count=False)

    def _on_edit_tickets():
        nonlocal tickets
        dlg = TicketDialog(root, "¿Cuántos tickets tienes?")
        if dlg.result is not None:
            tickets = dlg.result
            _save_tickets(tickets)
            app.set_tickets(tickets)

    app = LarvaRaceApp(root, on_start=on_start, on_finish=on_finish, on_calibrate=on_calibrate)
    app.ticket_label.bind("<Button-1>", lambda e: _on_edit_tickets())
    app.set_tickets(tickets)
    return app


def main():
    root = tk.Tk()
    build_trolichas_app(root)
    root.mainloop()


if __name__ == "__main__":
    main()
