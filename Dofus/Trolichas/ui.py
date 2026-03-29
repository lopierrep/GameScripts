import tkinter as tk

from shared.ui.colors import C
from shared.ui.font  import FONT as F, HEADER, BASE, SMALL
from config import SECONDS_PER_TICKET


class LarvaRaceApp:
    def __init__(self, root: tk.Tk, on_start, on_finish, on_calibrate):
        self.root = root
        self.root.withdraw()
        self.root.title("Larva Race")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg=C["bg"])

        # Status
        self.status_var = tk.StringVar(value="Listo")
        tk.Label(root, textvariable=self.status_var, width=30, wraplength=260,
                 justify=tk.CENTER, bg=C["bg"], fg=C["text"],
                 font=(F, BASE)).pack(pady=(16, 8), padx=20)

        # Tickets counter (clickeable)
        self.ticket_var = tk.StringVar(value="Tickets: 0")
        self.ticket_label = tk.Label(root, textvariable=self.ticket_var, width=30,
                 justify=tk.CENTER, bg=C["bg"], fg=C["yellow"],
                 font=(F, HEADER, "bold"), cursor="hand2")
        self.ticket_label.pack(pady=(0, 0), padx=20)

        # Estimated time
        self.eta_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.eta_var, width=30, justify=tk.CENTER,
                 bg=C["bg"], fg=C["dim"],
                 font=(F, SMALL)).pack(pady=(0, 4), padx=20)

        # Race counter
        self.race_var = tk.StringVar(value="Carreras: 0")
        tk.Label(root, textvariable=self.race_var, width=30, justify=tk.CENTER,
                 bg=C["bg"], fg=C["accent"],
                 font=(F, HEADER, "bold")).pack(pady=(0, 10), padx=20)

        # Buttons
        btn_frame = tk.Frame(root, bg=C["bg"])
        btn_frame.pack(pady=(6, 16), padx=20)

        top_row = tk.Frame(btn_frame, bg=C["bg"])
        top_row.pack()

        self.start_btn = tk.Button(
            top_row, text="Start", width=12,
            bg=C["green"], fg=C["bg"], font=(F, HEADER, "bold"),
            relief="flat", command=on_start
        )
        self.start_btn.pack(side=tk.LEFT, padx=6)

        self.finish_btn = tk.Button(
            top_row, text="Finish (S)", width=12,
            bg=C["red"], fg=C["bg"], font=(F, HEADER, "bold"),
            relief="flat", command=on_finish, state=tk.DISABLED
        )
        self.finish_btn.pack(side=tk.LEFT, padx=6)

        self.calibrate_btn = tk.Button(
            btn_frame, text="Calibrar puntos",
            bg=C["surface"], fg=C["dim"], font=(F, BASE),
            relief="flat", command=on_calibrate
        )
        self.calibrate_btn.pack(fill=tk.X, padx=6, pady=(8, 0))

        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        x = self.root.winfo_screenwidth() * 3 // 4 - w // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()

    def set_tickets(self, count: int):
        self.root.after(0, lambda: self._update_tickets(count))

    def _update_tickets(self, count: int):
        self.ticket_var.set(f"Tickets: {count}")
        if count <= 0:
            self.eta_var.set("~0m restantes")
            return
        secs = int(count * SECONDS_PER_TICKET)
        h, rem = divmod(secs, 3600)
        m = rem // 60
        parts = []
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        if not parts:
            parts.append("<1m")
        self.eta_var.set(f"~{' '.join(parts)} restantes")

    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def set_race_count(self, count: int):
        self.root.after(0, lambda: self.race_var.set(f"Carreras: {count}"))

    def set_running(self, running: bool):
        self.root.after(0, lambda: self._apply_running(running))

    def _apply_running(self, running: bool):
        if running:
            self.start_btn.config(state=tk.DISABLED)
            self.finish_btn.config(state=tk.NORMAL)
            self.calibrate_btn.config(state=tk.DISABLED)
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.finish_btn.config(state=tk.DISABLED)
            self.calibrate_btn.config(state=tk.NORMAL)
