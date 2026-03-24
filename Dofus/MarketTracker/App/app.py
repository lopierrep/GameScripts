"""
MarketTracker - Ventana flotante minimal (Opción C)
===================================================
Ventana pequeña siempre visible que reemplaza la consola:
  - Selector de profesión / receta única
  - Log de progreso con colores
  - Botones INICIAR / DETENER
  - Área de prompt que reemplaza los input() del backend
"""

import builtins
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

# Cuando corre como .exe compilado, los datos están junto al ejecutable.
# Cuando corre como script, están en la carpeta raíz del proyecto.
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

RECIPES_DIR = ROOT_DIR / "Recipes"
sys.path.insert(0, str(ROOT_DIR))


# ── Redirección de stdout ─────────────────────────────────────────────────────

class _StdoutRedirect:
    def __init__(self, callback):
        self._cb = callback

    def write(self, text):
        if text:
            self._cb(text)

    def flush(self):
        pass



# ── Aplicación ────────────────────────────────────────────────────────────────

class MarketTrackerApp:
    C = {
        "bg":      "#1e1e2e",
        "surface": "#2a2a3e",
        "accent":  "#89b4fa",
        "green":   "#a6e3a1",
        "red":     "#f38ba8",
        "yellow":  "#f9e2af",
        "text":    "#cdd6f4",
        "dim":     "#6c7086",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self._stop_flag   = False
        self._input_event = threading.Event()
        self._input_value = ""
        self._worker: threading.Thread | None = None
        self._orig_input  = builtins.input
        self._drag_x = self._drag_y = 0

        self._setup_window()
        self._build_ui()
        self._load_professions()
        self._intercept_io()

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("MarketTracker")
        self.root.geometry("330x580+20+20")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.C["bg"])
        self.root.overrideredirect(True)

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self._on_restore)

    def _on_restore(self, _e):
        self.root.overrideredirect(True)
        self.root.unbind("<Map>")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        C = self.C

        # Barra de título
        tb = tk.Frame(self.root, bg=C["surface"])
        tb.pack(fill="x")
        tb.bind("<ButtonPress-1>", self._drag_start)
        tb.bind("<B1-Motion>",     self._drag_move)

        lbl = tk.Label(tb, text="  MarketTracker", bg=C["surface"],
                       fg=C["accent"], font=("Segoe UI", 10, "bold"))
        lbl.pack(side="left", pady=5)
        lbl.bind("<ButtonPress-1>", self._drag_start)
        lbl.bind("<B1-Motion>",     self._drag_move)

        tk.Button(tb, text="×", bg=C["surface"], fg=C["red"], relief="flat",
                  font=("Segoe UI", 13, "bold"), bd=0,
                  command=self.root.destroy).pack(side="right", padx=6)
        tk.Button(tb, text="─", bg=C["surface"], fg=C["dim"], relief="flat",
                  font=("Segoe UI", 10), bd=0,
                  command=self._minimize).pack(side="right")

        # Selector de modo
        mf = tk.Frame(self.root, bg=C["bg"])
        mf.pack(fill="x", padx=10, pady=(8, 2))
        self._mode = tk.StringVar(value="profesion")
        for val, lbl_text in (("profesion", "Profesión"), ("receta", "Receta única")):
            tk.Radiobutton(mf, text=lbl_text, variable=self._mode, value=val,
                           bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
                           activebackground=C["bg"], font=("Segoe UI", 9),
                           command=self._on_mode_change).pack(side="left", padx=(0, 8))

        # Frame profesión
        self._prof_frame = tk.Frame(self.root, bg=C["bg"])
        tk.Label(self._prof_frame, text="Profesión", bg=C["bg"],
                 fg=C["dim"], font=("Segoe UI", 8)).pack(anchor="w")
        self._prof_var = tk.StringVar()
        self._prof_cb  = ttk.Combobox(self._prof_frame, textvariable=self._prof_var,
                                       state="readonly", font=("Segoe UI", 9))
        self._prof_cb.pack(fill="x")
        lf = tk.Frame(self._prof_frame, bg=C["bg"])
        lf.pack(fill="x", pady=(4, 0))
        tk.Label(lf, text="Límite (opcional):", bg=C["bg"],
                 fg=C["dim"], font=("Segoe UI", 8)).pack(side="left")
        self._limit_var = tk.StringVar()
        tk.Entry(lf, textvariable=self._limit_var, width=6,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=4)

        # Frame receta única
        self._recipe_frame = tk.Frame(self.root, bg=C["bg"])
        tk.Label(self._recipe_frame, text="Nombre de receta", bg=C["bg"],
                 fg=C["dim"], font=("Segoe UI", 8)).pack(anchor="w")
        self._recipe_var = tk.StringVar()
        tk.Entry(self._recipe_frame, textvariable=self._recipe_var,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 9)).pack(fill="x")

        # Estado
        self._status_var = tk.StringVar(value="Listo")
        tk.Label(self.root, textvariable=self._status_var, bg=C["bg"],
                 fg=C["accent"], font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(6, 0))

        # Barra de progreso
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("MT.Horizontal.TProgressbar",
                         troughcolor=C["surface"], background=C["accent"],
                         borderwidth=0, relief="flat")
        self._prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(self.root, variable=self._prog_var,
                        style="MT.Horizontal.TProgressbar",
                        maximum=100).pack(fill="x", padx=10, pady=2)
        self._prog_lbl = tk.Label(self.root, text="", bg=C["bg"],
                                   fg=C["dim"], font=("Segoe UI", 8))
        self._prog_lbl.pack(anchor="w", padx=10)

        # Log
        log_outer = tk.Frame(self.root, bg=C["surface"])
        log_outer.pack(fill="both", expand=True, padx=10, pady=4)
        self._log = tk.Text(log_outer, bg=C["surface"], fg=C["text"],
                             font=("Consolas", 8), relief="flat",
                             state="disabled", wrap="word", height=11,
                             selectbackground=C["accent"])
        sb = tk.Scrollbar(log_outer, command=self._log.yview,
                          bg=C["surface"], troughcolor=C["surface"])
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self._log.tag_config("ok",     foreground=C["green"])
        self._log.tag_config("skip",   foreground=C["dim"])
        self._log.tag_config("error",  foreground=C["red"])
        self._log.tag_config("info",   foreground=C["accent"])
        self._log.tag_config("warn",   foreground=C["yellow"])
        self._log.tag_config("manual", foreground=C["yellow"])
        self._log.tag_config("done",   foreground=C["green"])

        # Botones principales (se packean antes del prompt para usar before=)
        self._btn_frame = tk.Frame(self.root, bg=C["bg"])
        self._btn_frame.pack(fill="x", padx=10, pady=(2, 10))
        self._start_btn = tk.Button(
            self._btn_frame, text="INICIAR", bg=C["green"], fg=C["bg"],
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, pady=6,
            command=self._start)
        self._start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._stop_btn = tk.Button(
            self._btn_frame, text="DETENER", bg=C["surface"], fg=C["dim"],
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, pady=6,
            command=self._stop, state="disabled")
        self._stop_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Área de prompt (oculta, se inserta antes de los botones cuando es necesaria)
        self._prompt_frame = tk.Frame(self.root, bg=C["surface"])
        self._prompt_lbl = tk.Label(
            self._prompt_frame, text="", bg=C["surface"],
            fg=C["yellow"], font=("Segoe UI", 9),
            wraplength=290, justify="left")
        self._prompt_lbl.pack(padx=8, pady=(6, 2), anchor="w")
        self._prompt_entry = tk.Entry(
            self._prompt_frame, bg=C["bg"], fg=C["text"],
            insertbackground=C["text"], relief="flat", font=("Segoe UI", 9))
        tk.Button(
            self._prompt_frame, text="CONTINUAR →", bg=C["accent"], fg=C["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, pady=4,
            command=self._on_continue).pack(fill="x", padx=8, pady=(2, 6))

        self._on_mode_change()

    # ── Modo ──────────────────────────────────────────────────────────────────

    def _on_mode_change(self):
        if self._mode.get() == "profesion":
            self._recipe_frame.pack_forget()
            self._prof_frame.pack(fill="x", padx=10, pady=2)
        else:
            self._prof_frame.pack_forget()
            self._recipe_frame.pack(fill="x", padx=10, pady=2)

    # ── Profesiones ───────────────────────────────────────────────────────────

    def _load_professions(self):
        profs = sorted(
            f[len("recipes_"):-len(".json")]
            for f in os.listdir(RECIPES_DIR)
            if f.startswith("recipes_") and f.endswith(".json")
        )
        self._prof_cb["values"] = profs
        if profs:
            self._prof_var.set(profs[0])

    # ── Interceptar I/O ───────────────────────────────────────────────────────

    def _intercept_io(self):
        sys.stdout    = _StdoutRedirect(self._log_from_thread)
        sys.stderr    = _StdoutRedirect(self._log_from_thread)
        builtins.input = self._ui_input

    def restore_io(self):
        sys.stdout    = sys.__stdout__
        sys.stderr    = sys.__stderr__
        builtins.input = self._orig_input

    def _ui_input(self, prompt=""):
        """Reemplaza input(): muestra el prompt en la UI y bloquea hasta que el
        usuario pulse CONTINUAR. Se llama desde el hilo del worker."""
        needs_entry = any(kw in prompt for kw in ("Precio", "precio", "Ingresa"))
        self.root.after(0, self._show_prompt, prompt.strip(), needs_entry)
        self._input_event.clear()
        self._input_event.wait()
        return self._input_value

    def _show_prompt(self, text: str, needs_entry: bool):
        self._prompt_lbl.config(text=text)
        if needs_entry:
            self._prompt_entry.delete(0, "end")
            self._prompt_entry.pack(fill="x", padx=8, pady=(0, 2))
            self._prompt_entry.focus()
        else:
            self._prompt_entry.pack_forget()
        self._prompt_frame.pack(fill="x", padx=10, pady=2,
                                 before=self._btn_frame)

    def _on_continue(self):
        self._input_value = self._prompt_entry.get().strip()
        self._prompt_frame.pack_forget()
        self._input_event.set()

    # ── Log ───────────────────────────────────────────────────────────────────

    def _log_from_thread(self, text: str):
        self.root.after(0, self._append_log, text)

    def _append_log(self, raw: str):
        # Manejar \r (sobreescribir última línea, como el countdown)
        if "\r" in raw and not raw.startswith("\n"):
            parts = raw.split("\r")
            text  = parts[-1].strip()
            if not text:
                return
            self._log.configure(state="normal")
            idx = self._log.index("end-2l linestart")
            self._log.delete(idx, "end-1c")
            self._log.insert("end", text + "\n", self._tag(text))
            self._log.see("end")
            self._log.configure(state="disabled")
            return

        text = raw.strip()
        if not text:
            return
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", self._tag(text))
        self._log.see("end")
        self._log.configure(state="disabled")

    @staticmethod
    def _tag(text: str) -> str:
        u = text.upper()
        if "[OK]"    in u: return "ok"
        if "[SKIP]"  in u: return "skip"
        if "[ERROR]" in u or "ERROR —" in u: return "error"
        if "[DONE]"  in u: return "done"
        if "[AVISO]" in u: return "warn"
        if "[MANUAL]" in u: return "manual"
        return "info"

    def _set_status(self, text: str):
        self._status_var.set(text)

    # ── Iniciar / Detener ─────────────────────────────────────────────────────

    def _start(self):
        self._stop_flag = False
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._prog_var.set(0)
        self._prog_lbl.config(text="")
        self._start_btn.config(state="disabled", bg=self.C["dim"])
        self._stop_btn.config(state="normal", bg=self.C["red"], fg=self.C["bg"])

        if self._mode.get() == "profesion":
            prof  = self._prof_var.get()
            ls    = self._limit_var.get().strip()
            limit = int(ls) if ls.isdigit() else None
            target = lambda: self._run_profession(prof, limit)
        else:
            recipe = self._recipe_var.get().strip()
            target = lambda: self._run_single_recipe(recipe)

        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()

    def _stop(self):
        self._stop_flag = True
        try:
            import update_profession_recipes as upr
            upr.stop_requested = True
        except Exception:
            pass
        try:
            import update_single_recipe as usr
            usr.stop_requested = True
        except Exception:
            pass
        # Desbloquear cualquier input() pendiente
        self._input_value = ""
        self._input_event.set()
        self._prompt_frame.pack_forget()
        self.root.after(0, self._set_status, "Deteniendo…")

    def _on_done(self):
        self._start_btn.config(state="normal", bg=self.C["green"])
        self._stop_btn.config(state="disabled", bg=self.C["surface"],
                               fg=self.C["dim"])
        self._prompt_frame.pack_forget()
        self._set_status("Listo")

    def _run_profession(self, profession: str, limit):
        try:
            self.root.after(0, self._set_status, f"Actualizando {profession}…")
            import update_profession_recipes as upr
            upr.stop_requested = False
            upr.update_profession(profession, limit)
        except Exception as e:
            self._log_from_thread(f"[ERROR] {e}")
        finally:
            self.root.after(0, self._on_done)

    def _run_single_recipe(self, recipe_name: str):
        try:
            self.root.after(0, self._set_status, f"Actualizando '{recipe_name}'…")
            import update_single_recipe as usr
            usr.stop_requested = False
            usr.run(recipe_name)
        except Exception as e:
            self._log_from_thread(f"[ERROR] {e}")
        finally:
            self.root.after(0, self._on_done)


# ── Entrada ───────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app  = MarketTrackerApp(root)
    try:
        root.mainloop()
    finally:
        app.restore_io()


if __name__ == "__main__":
    main()