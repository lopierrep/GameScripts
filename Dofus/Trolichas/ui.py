import tkinter as tk

from shared.ui.colors import C
from shared.ui.font  import FONT as F, TITLE, HEADER, BASE, SMALL
from shared.ui.status_bar import StatusBar
from Trolichas.config import SECONDS_PER_TICKET


class LarvaRaceApp:
    def __init__(self, root: tk.Tk, on_start, on_finish, on_calibrate, on_edit_tickets=None):
        self.root = root
        self._on_start = on_start
        self._on_finish = on_finish
        self._on_calibrate = on_calibrate
        self._on_edit_tickets = on_edit_tickets or (lambda: None)
        self._running = False
        self._initial_tickets = 0
        self._detached = False
        self._toplevel: tk.Toplevel | None = None
        self._hub_parent = root

        # StringVars (persisten entre rebuilds)
        self.ticket_var = tk.StringVar(value="Tickets: 0")
        self.eta_var = tk.StringVar(value="")
        self.race_var = tk.StringVar(value="Carreras: 0")
        self._status_text = "Listo"
        self._status_color = C["dim"]

        self._container: tk.Frame | None = None
        self._status_bar: StatusBar | None = None
        self._progress_bar: tk.Frame | None = None

        self._build(root)

    # ── Construcción / reconstrucción ─────────────────────────────────────

    def _build(self, parent):
        """Construye todos los widgets dentro de parent."""
        container = tk.Frame(parent, bg=C["bg"])
        container.pack(fill="both", expand=True)
        self._container = container

        # ── Título ────────────────────────────────────────────────────
        title_bar = tk.Frame(container, bg=C["bg"])
        title_bar.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(title_bar, text="🏁 Trolichas", bg=C["bg"], fg=C["accent"],
                 font=(F, TITLE, "bold")).pack(side="left")

        btn_text = "↙ Integrar" if self._detached else "↗ Extraer"
        tk.Button(title_bar, text=btn_text, bg=C["surface"], fg=C["dim"],
                  font=(F, SMALL), relief="flat", cursor="hand2", padx=6,
                  command=self._toggle_detach).pack(side="right")

        # ── Card principal ────────────────────────────────────────────
        card = tk.Frame(container, bg=C["surface"], padx=20, pady=14,
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="x", padx=16, pady=(10, 0))

        # Tickets
        ticket_row = tk.Frame(card, bg=C["surface"])
        ticket_row.pack(fill="x", pady=(0, 2))
        tk.Label(ticket_row, textvariable=self.ticket_var,
                 bg=C["surface"], fg=C["yellow"],
                 font=(F, HEADER, "bold"), anchor="w").pack(side="left")
        tk.Button(ticket_row, text="+", bg=C["surface"], fg=C["yellow"],
                  font=(F, BASE, "bold"), relief="flat", cursor="hand2", padx=4,
                  command=self._on_edit_tickets).pack(side="left", padx=(4, 0))

        # ETA
        tk.Label(card, textvariable=self.eta_var, bg=C["surface"], fg=C["dim"],
                 font=(F, SMALL), anchor="w").pack(fill="x")

        # Barra de progreso
        progress_frame = tk.Frame(card, bg=C["border"], height=6)
        progress_frame.pack(fill="x", pady=(6, 8))
        progress_frame.pack_propagate(False)
        self._progress_bar = tk.Frame(progress_frame, bg=C["accent"], height=6)
        self._progress_bar.place(relwidth=0, relheight=1)

        # Carreras
        tk.Label(card, textvariable=self.race_var, bg=C["surface"], fg=C["accent"],
                 font=(F, HEADER, "bold"), anchor="w").pack(fill="x")

        # ── Botones ───────────────────────────────────────────────────
        btn_frame = tk.Frame(container, bg=C["bg"])
        btn_frame.pack(fill="x", padx=16, pady=(10, 0))

        self.toggle_btn = tk.Button(
            btn_frame, text="▶ Start",
            bg=C["green"], fg=C["bg"], font=(F, HEADER, "bold"),
            relief="flat", padx=10, pady=3, command=self._on_toggle,
        )
        self.toggle_btn.pack(fill=tk.X)

        self.calibrate_btn = tk.Button(
            btn_frame, text="⚙ Calibrar",
            bg=C["surface"], fg=C["dim"], font=(F, BASE),
            relief="flat", padx=10, pady=3, command=self._on_calibrate,
        )
        self.calibrate_btn.pack(fill=tk.X, pady=(8, 0))

        # ── Status bar ────────────────────────────────────────────────
        self._status_bar = StatusBar(container)
        self._status_bar.set(self._status_text, self._status_color)

        # Restaurar estado visual
        self._apply_running(self._running)
        # Refrescar progreso
        current_text = self.ticket_var.get()
        if current_text.startswith("Tickets: "):
            try:
                count = int(current_text.split(": ")[1])
                ratio = max(0, count / self._initial_tickets) if self._initial_tickets > 0 else 0
                self._progress_bar.place(relwidth=ratio, relheight=1)
            except ValueError:
                pass

    def _destroy_content(self):
        if self._container:
            self._container.destroy()
            self._container = None

    # ── Extraer / Integrar ────────────────────────────────────────────────

    def _toggle_detach(self):
        if self._detached:
            self._integrate()
        else:
            self._detach()

    def _detach(self):
        self._destroy_content()
        self._detached = True

        top = tk.Toplevel(self.root)
        top.title("Trolichas")
        top.configure(bg=C["bg"])
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.protocol("WM_DELETE_WINDOW", self._integrate)
        self._toplevel = top

        self._build(top)

        top.update_idletasks()
        w = top.winfo_reqwidth()
        h = top.winfo_reqheight()
        x = top.winfo_screenwidth() * 3 // 4 - w // 2
        y = (top.winfo_screenheight() - h) // 2
        top.geometry(f"+{x}+{y}")

    def _integrate(self):
        self._destroy_content()
        self._detached = False

        if self._toplevel:
            self._toplevel.destroy()
            self._toplevel = None

        self._build(self._hub_parent)

    # ── API pública ───────────────────────────────────────────────────────

    def set_tickets(self, count: int):
        self.root.after(0, lambda: self._update_tickets(count))

    def _update_tickets(self, count: int):
        if count > self._initial_tickets:
            self._initial_tickets = count
        self.ticket_var.set(f"Tickets: {count}")

        if self._initial_tickets > 0:
            ratio = max(0, count / self._initial_tickets)
        else:
            ratio = 0
        if self._progress_bar:
            self._progress_bar.place(relwidth=ratio, relheight=1)

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

    def set_status(self, msg: str, color: str = C["dim"]):
        self._status_text = msg
        self._status_color = color
        self.root.after(0, lambda: self._status_bar.set(msg, color) if self._status_bar else None)

    def set_race_count(self, count: int):
        self.root.after(0, lambda: self.race_var.set(f"Carreras: {count}"))

    def _on_toggle(self):
        if self._running:
            self._on_finish()
        else:
            self._on_start()

    def set_running(self, running: bool):
        self.root.after(0, lambda: self._apply_running(running))

    def _apply_running(self, running: bool):
        self._running = running
        if running:
            self.toggle_btn.config(text="■ Stop (S)", bg=C["red"])
            self.calibrate_btn.config(state=tk.DISABLED)
        else:
            self.toggle_btn.config(text="▶ Start", bg=C["green"])
            self.calibrate_btn.config(state=tk.NORMAL)
            self._initial_tickets = 0
