"""
Crafting - UI principal
========================
Capa de presentación pura: tabla de recetas, filtros, detalle de ingredientes,
barra de resumen, prompt y log. Sin lógica de negocio.
"""

import math
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta

from shared.colors import C
from core.table_filter import compute_summary, filter_rows, profitable_rows

_BOGOTA = timezone(timedelta(hours=-5))

_PROF_ICONS: dict[str, str] = {
    "alquimista": "⚗",
    "base":       "📋",
    "campesino":  "🌾",
    "cazador":    "🏹",
    "escultor":   "🗿",
    "fabricante": "⚙",
    "ganadero":   "🐄",
    "herrero":    "🔨",
    "joyero":     "💎",
    "leñador":    "🪓",
    "manitas":    "🔧",
    "minero":     "⛏",
    "pescador":   "🎣",
    "sastre":     "🧵",
    "zapatero":   "👟",
}

class _Tooltip:
    """Tooltip simple que aparece al hacer hover sobre un widget."""
    def __init__(self, widget, text: str):
        self._widget = widget
        self._text   = text
        self._tip    = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        x = self._widget.winfo_rootx() + 0
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, bg=C["surface"], fg=C["dim"],
                 font=("Segoe UI", 8), relief="flat", padx=8, pady=4,
                 wraplength=260, justify="left").pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


def _prof_display(name: str) -> str:
    icon = _PROF_ICONS.get(name, "•")
    return f"{icon}  {name.capitalize()}"

def _prof_from_display(display: str) -> str:
    """Extrae el nombre de profesión desde el texto del combobox."""
    return display.split("  ", 1)[-1].lower() if "  " in display else display.lower()


def _to_bogota(utc_str: str) -> str:
    """Convierte un timestamp ISO UTC a hora de Bogotá (UTC-5)."""
    if not utc_str:
        return ""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BOGOTA).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return utc_str[:16]


def _auto_tag(text: str) -> str:
    u = text.upper()
    if "[OK]"    in u: return "ok"
    if "[SKIP]"  in u: return "skip"
    if "[ERROR]" in u or "ERROR —" in u: return "error"
    if "[DONE]"  in u: return "done"
    if "[AVISO]" in u: return "warn"
    if "[MANUAL]" in u: return "manual"
    return "info"


def _fmt(n) -> str:
    """Formatea un número con puntos de miles."""
    return f"{int(n):,}".replace(",", ".") if n is not None else "—"


class CraftingUI:
    """
    callbacks = {
        "start":     fn(target: str, limit: int|None, mode: str) -> None,
        "stop":      fn() -> None,
        "export":    fn(profession: str) -> None,
        "calibrate": fn() -> None,
    }
    """

    def __init__(self, root: tk.Tk, callbacks: dict, professions: list):
        self.root = root
        self._cbs = callbacks
        self._all_rows: list = []
        self._row_data: dict = {}
        self._selected_recipe_iid: str | None = None

        self._setup_window()
        self._apply_styles()
        self._build_titlebar()
        self._build_toolbar(professions)
        self._build_filterbar()
        self._build_table()
        self._build_summary_bar()
        self._build_prompt()
        self._build_log()

        self._on_mode_change()

    # ── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Crafting")
        self.root.geometry("1020x720")
        self.root.minsize(760, 540)
        self.root.configure(bg=C["bg"])

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"],
                    fieldbackground=C["surface"], borderwidth=0)
        s.configure("TCombobox", fieldbackground=C["surface"],
                    foreground=C["text"], background=C["surface"],
                    arrowcolor=C["dim"], selectbackground=C["surface"])
        s.map("TCombobox",
              fieldbackground=[("readonly", C["surface"])],
              foreground=[("readonly", C["text"])])
        s.configure("Craft.Horizontal.TProgressbar",
                    troughcolor=C["surface"], background=C["accent"],
                    borderwidth=0, relief="flat")
        s.configure("Craft.Treeview",
                    background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=22, borderwidth=0,
                    indent=14)
        s.configure("Craft.Treeview.Heading",
                    background=C["bg"], foreground=C["dim"],
                    borderwidth=0, font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Craft.Treeview",
              background=[("selected", C["accent"])],
              foreground=[("selected", C["bg"])])
        s.configure("TScrollbar",
                    background=C["surface"], troughcolor=C["bg"],
                    arrowcolor=C["dim"], borderwidth=0, relief="flat")

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=C["surface"])
        bar.pack(fill="x")
        tk.Label(bar, text="  ⚒ Crafting", bg=C["surface"],
                 fg=C["accent"], font=("Segoe UI", 12, "bold"),
                 pady=8, padx=4).pack(side="left")
        self._status_var = tk.StringVar(value="Listo")
        self._status_lbl = tk.Label(bar, textvariable=self._status_var,
                                    bg=C["surface"], fg=C["dim"],
                                    font=("Segoe UI", 9), padx=8)
        self._status_lbl.pack(side="left")

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self, professions: list):
        ctrl = tk.Frame(self.root, bg=C["bg"])
        ctrl.pack(fill="x", padx=12, pady=8)

        mf = tk.Frame(ctrl, bg=C["bg"])
        mf.pack(side="left")
        self._mode = tk.StringVar(value="profesion")
        for val, label in (("profesion", "Profesión"), ("receta", "Receta única")):
            tk.Radiobutton(
                mf, text=label, variable=self._mode, value=val,
                bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
                activebackground=C["bg"], font=("Segoe UI", 9),
                command=self._on_mode_change,
            ).pack(side="left", padx=(0, 8))

        tk.Frame(ctrl, bg=C["surface"], width=1).pack(side="left", fill="y", padx=10)

        self._input_area = tk.Frame(ctrl, bg=C["bg"])
        self._input_area.pack(side="left")

        self._prof_frame = tk.Frame(self._input_area, bg=C["bg"])
        tk.Label(self._prof_frame, text="Profesión:", bg=C["bg"],
                 fg=C["dim"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self._prof_var = tk.StringVar()
        prof_display_values = [_prof_display(p) for p in professions]
        self._prof_cb = ttk.Combobox(
            self._prof_frame, textvariable=self._prof_var,
            values=prof_display_values, state="readonly",
            font=("Segoe UI", 9), width=18,
        )
        if prof_display_values:
            self._prof_var.set(prof_display_values[0])
        self._prof_cb.pack(side="left")
        _limit_lbl = tk.Label(self._prof_frame, text="  Límite:", bg=C["bg"],
                              fg=C["dim"], font=("Segoe UI", 8))
        _limit_lbl.pack(side="left")
        self._limit_var = tk.StringVar()
        _limit_entry = tk.Entry(
            self._prof_frame, textvariable=self._limit_var, width=5,
            bg=C["surface"], fg=C["text"], insertbackground=C["text"],
            relief="flat", font=("Segoe UI", 9),
        )
        _limit_entry.pack(side="left", padx=(4, 0))
        _tip_text = "Limita cuántas recetas escanea.\nDejar vacío para procesar todas."
        _Tooltip(_limit_lbl, _tip_text)
        _Tooltip(_limit_entry, _tip_text)

        self._recipe_frame = tk.Frame(self._input_area, bg=C["bg"])
        tk.Label(self._recipe_frame, text="Receta:", bg=C["bg"],
                 fg=C["dim"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self._recipe_var = tk.StringVar()
        tk.Entry(
            self._recipe_frame, textvariable=self._recipe_var, width=28,
            bg=C["surface"], fg=C["text"], insertbackground=C["text"],
            relief="flat", font=("Segoe UI", 9),
        ).pack(side="left")

        tk.Frame(ctrl, bg=C["surface"], width=1).pack(side="left", fill="y", padx=10)

        def _btn(text, color, fg, cmd, state="normal"):
            return tk.Button(ctrl, text=text, bg=color, fg=fg,
                             font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                             padx=10, pady=5, command=cmd, state=state)

        self._start_btn = _btn("▶ Actualizar", C["green"],   C["bg"],  self._on_start)
        self._start_btn.pack(side="left", padx=(0, 4))
        self._stop_btn  = _btn("■ Detener",    C["surface"], C["dim"], self._on_stop, state="disabled")
        self._stop_btn.pack(side="left", padx=(0, 4))
        _btn("↑ Sheets",   C["surface"], C["accent"], self._on_export).pack(side="left", padx=(0, 4))
        _btn("⚙ Calibrar", C["surface"], C["dim"],    self._on_calibrate).pack(side="left")

    # ── Filter bar ────────────────────────────────────────────────────────────

    def _build_filterbar(self):
        ff = tk.Frame(self.root, bg=C["bg"])
        ff.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(ff, text="Ganancia mín:", bg=C["bg"], fg=C["dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._filter_profit = tk.StringVar()
        tk.Entry(ff, textvariable=self._filter_profit, width=10,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(4, 14))

        tk.Label(ff, text="Nivel:", bg=C["bg"], fg=C["dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._filter_lvl_min = tk.StringVar()
        self._filter_lvl_max = tk.StringVar()
        tk.Entry(ff, textvariable=self._filter_lvl_min, width=5,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        tk.Label(ff, text="–", bg=C["bg"], fg=C["dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(ff, textvariable=self._filter_lvl_max, width=5,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(2, 14))

        tk.Button(ff, text="Filtrar", bg=C["accent"], fg=C["bg"],
                  font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
                  padx=8, pady=3, command=self._apply_filter).pack(side="left", padx=(0, 4))
        tk.Button(ff, text="Limpiar", bg=C["surface"], fg=C["dim"],
                  font=("Segoe UI", 8), relief="flat", bd=0,
                  padx=8, pady=3, command=self._clear_filter).pack(side="left", padx=(0, 20))

        tk.Frame(ff, bg=C["surface"], width=1).pack(side="left", fill="y", padx=(0, 12))
        _tol_lbl = tk.Label(ff, text="Tolerancia lote:", bg=C["bg"], fg=C["dim"],
                            font=("Segoe UI", 8))
        _tol_lbl.pack(side="left")
        self._tolerance_var = tk.StringVar(value="5")
        _tol_entry = tk.Entry(ff, textvariable=self._tolerance_var, width=4,
                              bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                              relief="flat", font=("Segoe UI", 9))
        _tol_entry.pack(side="left", padx=(4, 2))
        tk.Label(ff, text="%", bg=C["bg"], fg=C["dim"],
                 font=("Segoe UI", 8)).pack(side="left")
        _tol_tip = (
            "Margen de precio aceptado al elegir lotes grandes.\n\n"
            "Compra: prefiere lotes grandes aunque sean hasta X% más caros por unidad.\n"
            "Venta: prefiere lotes grandes aunque la ganancia sea hasta X% menor.\n\n"
            "Ej. con 5%: si x1000 cuesta 5% más que x1, igual compra x1000."
        )
        _Tooltip(_tol_lbl,   _tol_tip)
        _Tooltip(_tol_entry, _tol_tip)

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self):
        self._table_frame = tk.Frame(self.root, bg=C["bg"])
        self._table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 2))

        cols = ("result", "profit", "lot", "qty", "craft", "sell", "level", "updated")
        self._tree = ttk.Treeview(
            self._table_frame, columns=cols, show="tree headings",
            style="Craft.Treeview", selectmode="browse",
        )
        self._tree.column("#0", width=46, minwidth=46, stretch=False)
        headings = {
            "result":  ("Receta / Ingrediente", 200, "w"),
            "profit":  ("Ganancia / Total",     110, "center"),
            "lot":     ("Mejor Lote",            90, "center"),
            "qty":     ("Cantidad",              80, "center"),
            "craft":   ("Costo/u",              110, "center"),
            "sell":    ("Venta/u",              110, "center"),
            "level":   ("Niv.",                  50, "center"),
            "updated": ("Actualizado",          130, "center"),
        }
        for col, (head, width, anchor) in headings.items():
            self._tree.heading(col, text=head,
                               command=lambda c=col: self._sort_col(c))
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(self._table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        self._tree.tag_configure("top",       foreground=C["orange"])
        self._tree.tag_configure("profit",    foreground=C["green"])
        self._tree.tag_configure("loss",      foreground=C["red"])
        self._tree.tag_configure("neutral",   foreground=C["dim"])
        self._tree.tag_configure("missing",   foreground=C["yellow"])
        self._tree.tag_configure("ing",             foreground=C["dim"])
        self._tree.tag_configure("ing_buy",         foreground=C["dim"])
        self._tree.tag_configure("ing_craft",       foreground=C["accent"])
        self._tree.tag_configure("sub_ing",         foreground=C["accent"])
        self._tree.tag_configure("selected_recipe", background=C["today"],
                                 foreground=C["text"])

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Button-1>",        self._on_tree_press)
        self._tree.bind("<ButtonRelease-1>", self._on_tree_release)
        self._sort_state: dict = {}
        self._pre_click_iid  = None
        self._pre_click_open = None

    def _sort_col(self, col: str):
        asc = not self._sort_state.get(col, True)
        self._sort_state[col] = asc
        items = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children()]

        def _sort_key(val):
            v = val.replace(".", "").replace("+", "").replace("—", "-999999").strip()
            try:
                return (0, float(v))
            except ValueError:
                return (1, v.lower())

        items.sort(key=lambda x: _sort_key(x[0]), reverse=not asc)
        for idx, (_, iid) in enumerate(items):
            self._tree.move(iid, "", idx)

    # ── Summary bar ───────────────────────────────────────────────────────────

    def _build_summary_bar(self):
        self._summary_bar = tk.Frame(self.root, bg=C["surface"])
        self._summary_bar.pack(fill="x")

        self._sum_total      = tk.Label(self._summary_bar, text="", bg=C["surface"],
                                         fg=C["dim"],    font=("Segoe UI", 8), padx=10, pady=4)
        self._sum_profitable = tk.Label(self._summary_bar, text="", bg=C["surface"],
                                         fg=C["green"],  font=("Segoe UI", 8))
        self._sum_avg        = tk.Label(self._summary_bar, text="", bg=C["surface"],
                                         fg=C["dim"],    font=("Segoe UI", 8), padx=10)
        self._sum_top        = tk.Label(self._summary_bar, text="", bg=C["surface"],
                                         fg=C["orange"], font=("Segoe UI", 8))

        for w in (self._sum_total, self._sum_profitable, self._sum_avg, self._sum_top):
            w.pack(side="left")

    # ── Prompt frame ──────────────────────────────────────────────────────────

    def _build_prompt(self):
        self._prompt_frame = tk.Frame(self.root, bg=C["surface"])

        self._prompt_lbl = tk.Label(
            self._prompt_frame, text="", bg=C["surface"],
            fg=C["yellow"], font=("Segoe UI", 10, "bold"),
            wraplength=800, justify="left",
        )
        self._prompt_lbl.pack(padx=12, pady=(8, 4), anchor="w")

        self._price_fields_frame = tk.Frame(self._prompt_frame, bg=C["surface"])
        self._price_entries: dict = {}
        for label, key in (("x1", "unit_price_x1"), ("x10", "unit_price_x10"),
                            ("x100", "unit_price_x100"), ("x1000", "unit_price_x1000")):
            col = tk.Frame(self._price_fields_frame, bg=C["surface"])
            col.pack(side="left", padx=10)
            tk.Label(col, text=label, bg=C["surface"], fg=C["dim"],
                     font=("Segoe UI", 8)).pack()
            e = tk.Entry(col, width=12, bg=C["bg"], fg=C["text"],
                         insertbackground=C["text"], relief="flat",
                         font=("Segoe UI", 9))
            e.pack()
            self._price_entries[key] = e

        btn_row = tk.Frame(self._prompt_frame, bg=C["surface"])
        btn_row.pack(fill="x", padx=12, pady=(4, 8))
        self._prompt_confirm_btn = tk.Button(
            btn_row, text="CONTINUAR →",
            bg=C["accent"], fg=C["bg"],
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            padx=16, pady=6, command=self._on_prompt_confirm,
        )
        self._prompt_confirm_btn.pack(side="left")

        self._prompt_confirm_cb = None
        self._prompt_mode = "confirm"

    def _on_prompt_confirm(self):
        cb = self._prompt_confirm_cb
        if self._prompt_mode == "price":
            prices = {}
            for key, entry in self._price_entries.items():
                val = entry.get().strip()
                prices[key] = int(val) if val.isdigit() else 0
            self.hide_prompt()
            if cb:
                cb(prices)
        else:
            self.hide_prompt()
            if cb:
                cb()

    # ── Log ───────────────────────────────────────────────────────────────────

    def _build_log(self):
        self._log_outer = tk.Frame(self.root, bg=C["surface"])
        self._log_outer.pack(fill="x", padx=12, pady=(0, 8))

        self._log = tk.Text(
            self._log_outer, bg=C["surface"], fg=C["text"],
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word", height=6,
            selectbackground=C["accent"],
        )
        sb = ttk.Scrollbar(self._log_outer, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        for tag, color in (
            ("ok",     C["green"]),
            ("skip",   C["dim"]),
            ("error",  C["red"]),
            ("info",   C["accent"]),
            ("warn",   C["yellow"]),
            ("manual", C["yellow"]),
            ("done",   C["green"]),
        ):
            self._log.tag_config(tag, foreground=color)

    # ── Mode toggle ───────────────────────────────────────────────────────────

    def _on_mode_change(self):
        if self._mode.get() == "profesion":
            self._recipe_frame.pack_forget()
            self._prof_frame.pack(side="left")
        else:
            self._prof_frame.pack_forget()
            self._recipe_frame.pack(side="left")

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_start(self):
        if "start" not in self._cbs:
            return
        mode = self._mode.get()
        if mode == "profesion":
            target = self.profession()
            lv = self._limit_var.get().strip()
            limit = int(lv) if lv.isdigit() else None
        else:
            target = self._recipe_var.get().strip()
            limit = None
        self._cbs["start"](target, limit, mode)

    def _on_stop(self):
        if "stop" in self._cbs:
            self._cbs["stop"]()

    def _on_export(self):
        if "export" in self._cbs:
            self._cbs["export"](self.profession())

    def _on_calibrate(self):
        if "calibrate" in self._cbs:
            self._cbs["calibrate"]()

    # ── Row selection ─────────────────────────────────────────────────────────

    def _show_copy_toast(self, name: str):
        toast = tk.Label(
            self.root, text=f"✓ Copiado: {name}",
            bg=C["accent"], fg=C["bg"],
            font=("Segoe UI", 9, "bold"), padx=12, pady=6,
            relief="flat",
        )
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-16)
        self.root.after(1800, toast.destroy)

    def _on_tree_press(self, event):
        """Guarda el estado open antes de que el nativo procese el clic."""
        iid = self._tree.identify_row(event.y)
        self._pre_click_iid  = iid or None
        self._pre_click_open = self._tree.item(iid, "open") if iid else None

    def _on_tree_release(self, event):
        """Si el nativo no cambió el estado (clic en fila, no en triángulo), lo toglea."""
        iid = self._tree.identify_row(event.y)
        if (iid and iid == self._pre_click_iid
                and self._tree.get_children(iid)
                and self._tree.item(iid, "open") == self._pre_click_open):
            self._tree.item(iid, open=not self._pre_click_open)
        self._pre_click_iid = self._pre_click_open = None

    def _on_row_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]

        is_recipe = not self._tree.parent(iid)

        # Subir hasta la receta raíz y aplicar highlight
        recipe_iid = iid
        while self._tree.parent(recipe_iid):
            recipe_iid = self._tree.parent(recipe_iid)
        if self._selected_recipe_iid and self._selected_recipe_iid != recipe_iid:
            orig = self._row_tags.get(self._selected_recipe_iid, "neutral")
            self._tree.item(self._selected_recipe_iid, tags=(orig,))
        self._selected_recipe_iid = recipe_iid
        self._tree.item(recipe_iid, tags=("selected_recipe",))

        # Copiar nombre al portapapeles
        if is_recipe:
            row  = self._row_data.get(iid)
            name = row.get("result", "") if row else ""
        else:
            name = self._tree.set(iid, "result").strip()

        if name:
            self.root.clipboard_clear()
            self.root.clipboard_append(name)
            self._show_copy_toast(name)

    # ── Filters ───────────────────────────────────────────────────────────────

    def _apply_filter(self, profitable: list = None):
        pv   = self._filter_profit.get().strip().replace(".", "").replace(",", "")
        lmin = self._filter_lvl_min.get().strip()
        lmax = self._filter_lvl_max.get().strip()

        rows = filter_rows(
            self._all_rows,
            min_profit = int(pv)   if pv.lstrip("-").isdigit() else None,
            lvl_min    = int(lmin) if lmin.isdigit()           else None,
            lvl_max    = int(lmax) if lmax.isdigit()           else None,
        )
        self._populate_tree(rows, profitable=profitable)

    def _clear_filter(self):
        self._filter_profit.set("")
        self._filter_lvl_min.set("")
        self._filter_lvl_max.set("")
        self._populate_tree(self._all_rows)

    def _populate_tree(self, rows: list, profitable: list = None):
        # Ordenar de mayor a menor ganancia por defecto
        rows = sorted(rows, key=lambda r: (r.get("profit") or float("-inf")), reverse=True)

        if profitable is None:
            profitable = profitable_rows(rows)
        top_names = {r["result"] for r in profitable[:3]}

        self._tree.delete(*self._tree.get_children())
        self._row_data = {}
        self._selected_recipe_iid = None
        self._row_tags: dict = {}

        for row in rows:
            profit  = row.get("profit")
            craft   = row.get("craft_cost")
            sell    = row.get("sell_price")
            level   = row.get("level", "")
            lot     = row.get("best_lot", "—")
            updated = row.get("updated", "")
            name    = row.get("result", "")

            craft_str  = _fmt(craft)
            sell_str   = _fmt(sell)
            if profit is None:
                profit_str = "—"
            elif profit >= 0:
                profit_str = f"+{_fmt(profit)}"
            else:
                profit_str = f"-{_fmt(abs(profit))}"

            if profit is None:
                tag = "missing"
            elif name in top_names:
                tag = "top"
            elif profit > 0:
                tag = "profit"
            elif profit < 0:
                tag = "loss"
            else:
                tag = "neutral"

            iid = self._tree.insert("", "end", values=(
                name, profit_str, lot, "", craft_str, sell_str,
                level, _to_bogota(updated),
            ), tags=(tag,))
            self._row_data[iid] = row
            self._row_tags[iid]  = tag

            for ing in row.get("ingredients", []):
                self._insert_ing(iid, ing)

    def _insert_ing(self, parent_iid: str, ing: dict, depth: int = 0):
        indent   = "      " * depth
        ing_name = indent + ing.get("name", "")
        qty          = ing.get("quantity", 1)
        sell_size    = ing.get("sell_size")
        buy_lot      = ing.get("buy_lot") or "—"
        price        = ing.get("unit_price")
        total        = ing.get("total")
        ing_updated  = ing.get("last_updated", "")
        buy_or_craft = ing.get("buy_or_craft")

        has_subs = bool(ing.get("sub_ingredients"))
        if depth == 0 and has_subs:
            ing_tag = "sub_ing"
        elif buy_or_craft == "Craft":
            ing_tag = "ing_craft"
        else:
            ing_tag = "ing_buy"

        if buy_or_craft == "Craft":
            price_str = f"{_fmt(price)} (⚒ Craft)" if price else "⚒ Craft"
        else:
            price_str = f"{_fmt(price)} (🛒 Buy)" if price else "—"

        if sell_size:
            qty_display = _fmt(qty * sell_size)
        else:
            qty_display = str(qty)

        total_str  = f" · {_fmt(total)}" if total else ""
        child_iid = self._tree.insert(parent_iid, "end", values=(
            ing_name,
            "",
            buy_lot,
            qty_display,
            f"{price_str}{total_str}",
            "",
            "",
            _to_bogota(ing_updated),
        ), tags=(ing_tag,))

        for sub in ing.get("sub_ingredients", []):
            self._insert_ing(child_iid, sub, depth + 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def mode(self) -> str:
        return self._mode.get()

    def profession(self) -> str:
        return _prof_from_display(self._prof_var.get())

    def limit(self):
        lv = self._limit_var.get().strip()
        return int(lv) if lv.isdigit() else None

    def recipe_name(self) -> str:
        return self._recipe_var.get().strip()

    def tolerance(self) -> float:
        try:
            return max(0.0, float(self._tolerance_var.get().strip()))
        except ValueError:
            return 5.0

    def set_status(self, text: str, color: str = None):
        self._status_var.set(text)
        if color:
            self._status_lbl.config(fg=color)

    def set_busy(self, busy: bool):
        if busy:
            self._start_btn.config(state="disabled", bg=C["dim"])
            self._stop_btn.config(state="normal", bg=C["red"], fg=C["bg"])
        else:
            self._start_btn.config(state="normal", bg=C["green"])
            self._stop_btn.config(state="disabled", bg=C["surface"], fg=C["dim"])

    def log(self, text: str, tag: str = None):
        """Thread-safe."""
        self.root.after(0, self._append_log, text, tag)

    def _write_log(self, text: str, tag: str):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _append_log(self, raw: str, tag: str = None):
        if "\r" in raw and not raw.startswith("\n"):
            parts = raw.split("\r")
            text = parts[-1].strip()
            if not text:
                return
            self._log.configure(state="normal")
            idx = self._log.index("end-2l linestart")
            self._log.delete(idx, "end-1c")
            self._log.configure(state="disabled")
            self._write_log(text, tag or _auto_tag(text))
            return
        text = raw.strip()
        if not text:
            return
        self._write_log(text, tag or _auto_tag(text))

    def clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def refresh_table(self, rows: list):
        """
        rows: list de dicts con keys:
          result, level, best_lot, craft_cost, sell_price, profit,
          updated, ingredients: [{name, quantity, unit_price, total}]
        """
        self._all_rows = rows
        summary = compute_summary(rows)
        self._apply_filter(profitable=summary["profitable"])
        self._update_summary(summary)

    def _update_summary(self, summary: dict):
        top = summary["top"]
        self._sum_total.config(text=f"Total: {summary['total']}")
        self._sum_profitable.config(text=f"  Rentables: {summary['n_profitable']}")
        self._sum_avg.config(
            text=f"  Media: +{_fmt(summary['avg_profit'])}" if summary["avg_profit"] else "  Media: —"
        )
        self._sum_top.config(
            text=f"  ★ {top['result']}  (+{_fmt(top['profit'])})" if top else ""
        )

    def show_confirm(self, text: str, on_confirm):
        self._prompt_mode = "confirm"
        self._prompt_confirm_cb = on_confirm
        self._prompt_lbl.config(text=text)
        self._price_fields_frame.pack_forget()
        self._prompt_confirm_btn.config(text="CONTINUAR →")
        self._prompt_frame.pack(fill="x", padx=12, pady=(0, 4),
                                 before=self._log_outer)

    def show_price_prompt(self, name: str, is_selling: bool, on_confirm):
        kind = "venta" if is_selling else "ingrediente"
        self._prompt_mode = "price"
        self._prompt_confirm_cb = on_confirm
        self._prompt_lbl.config(text=f"Precios manuales de '{name}' ({kind}):")
        for e in self._price_entries.values():
            e.delete(0, "end")
        self._price_fields_frame.pack(padx=12, pady=(0, 4))
        self._prompt_confirm_btn.config(text="CONFIRMAR ✓")
        list(self._price_entries.values())[0].focus()
        self._prompt_frame.pack(fill="x", padx=12, pady=(0, 4),
                                 before=self._log_outer)

    def hide_prompt(self):
        self._prompt_frame.pack_forget()
