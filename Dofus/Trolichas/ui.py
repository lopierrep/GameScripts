import tkinter as tk

from shared.colors import C


class LarvaRaceApp:
    def __init__(self, root: tk.Tk, on_start, on_finish, on_calibrate):
        self.root = root
        self.root.title("Larva Race")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg=C["bg"])

        # Status
        self.status_var = tk.StringVar(value="Listo")
        tk.Label(root, textvariable=self.status_var, width=30, wraplength=200,
                 justify=tk.CENTER, bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 9)).pack(pady=(12, 6), padx=14)

        # Race counter
        self.race_var = tk.StringVar(value="Carreras: 0")
        tk.Label(root, textvariable=self.race_var, width=30, justify=tk.CENTER,
                 bg=C["bg"], fg=C["accent"],
                 font=("Segoe UI", 10, "bold")).pack(pady=(0, 6), padx=14)

        # Buttons
        btn_frame = tk.Frame(root, bg=C["bg"])
        btn_frame.pack(pady=(4, 4), padx=14)

        self.start_btn = tk.Button(
            btn_frame, text="Start", width=10,
            bg=C["green"], fg=C["bg"], font=("Segoe UI", 10, "bold"),
            relief="flat", command=on_start
        )
        self.start_btn.pack(side=tk.LEFT, padx=6)

        self.finish_btn = tk.Button(
            btn_frame, text="Finish (S)", width=10,
            bg=C["red"], fg=C["bg"], font=("Segoe UI", 10, "bold"),
            relief="flat", command=on_finish, state=tk.DISABLED
        )
        self.finish_btn.pack(side=tk.LEFT, padx=6)

        self.calibrate_btn = tk.Button(
            root, text="Calibrar puntos", width=24,
            bg=C["surface"], fg=C["dim"], relief="flat",
            command=on_calibrate
        )
        self.calibrate_btn.pack(pady=(4, 12), padx=14)

    def set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def set_race_count(self, count: int):
        self.root.after(0, lambda: self.race_var.set(f"Carreras: {count}"))

    def set_running(self, running: bool):
        if running:
            self.start_btn.config(state=tk.DISABLED)
            self.finish_btn.config(state=tk.NORMAL)
            self.calibrate_btn.config(state=tk.DISABLED)
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.finish_btn.config(state=tk.DISABLED)
            self.calibrate_btn.config(state=tk.NORMAL)
