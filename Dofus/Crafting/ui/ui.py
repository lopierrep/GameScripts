"""
Crafting - UI
==============
Interfaz gráfica única: sidebar izquierdo + área principal derecha.
"""

import re
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta

from core.table_filter import compute_summary, filter_rows, profitable_rows
from shared.ui.colors import C, style_scrollbar
from shared.ui.font  import FONT as F, TITLE, HEADER, BASE, SMALL
from shared.ui.prompt_bar import PromptBar
from shared.ui.status_bar import StatusBar
from shared.ui.toast import show_copy_toast

_BOGOTA = timezone(timedelta(hours=-5))

_RECOLECCION = {"alquimista", "campesino", "cazador", "ganadero", "leñador", "minero", "pescador"}

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

_MONO      = "Consolas"
_ROW_HEIGHT = 26


def _prof_display(name: str) -> str:
    icon = _PROF_ICONS.get(name, "•")
    return f"{icon}  {name.capitalize()}"


def _prof_from_display(display: str) -> str:
    name = display.split("  ", 1)[-1] if "  " in display else display
    name = name.split(" (")[0]
    return name.lower()


def _to_bogota(utc_str: str) -> str:
    if not utc_str:
        return ""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BOGOTA).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return utc_str[:16]



def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".") if n is not None else "—"


class CraftingUI:

    def __init__(self, root: tk.Tk, callbacks: dict, professions: list,
                 load_settings, save_settings, prof_counts: dict = None):
        self.root          = root
        self._cbs          = callbacks
        self._load_settings = load_settings
        self._save_settings = save_settings
        self._prof_counts  = prof_counts or {}
        self._all_rows: list = []
        self._row_data: dict = {}
        self._selected_recipe_iid: str | None = None

        self.C  = C
        self.M  = _MONO
        self.RH = _ROW_HEIGHT

        self._build_ui(professions)

    # ── Layout principal ─────────────────────────────────────────────────────

    def _build_ui(self, professions: list):
        self._setup_window()
        self._apply_styles()

        self._status_bar = StatusBar(self.root)
        self._outer = tk.Frame(self.root, bg=self.C["bg"])
        self._outer.pack(fill="both", expand=True)
        self._sidebar = tk.Frame(self._outer, bg=self.C["bg2"],
                                 width=195, relief="flat")
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._main_area = tk.Frame(self._outer, bg=self.C["bg"])
        self._main_area.pack(side="left", fill="both", expand=True)

        self._build_sidebar(professions)
        self._build_filterbar()
        self._build_table()
        self._build_prompt()

        self.root.update_idletasks()
        self.root.deiconify()

    # ── Window ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        C = self.C
        self.root.title("Crafting")
        w, h = 1100, 720
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(800, 540)
        self.root.configure(bg=C["bg"])

    # ── Estilos ttk ──────────────────────────────────────────────────────────

    def _apply_styles(self):
        C  = self.C
        RH = self.RH
        s  = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"],
                    fieldbackground=C["surface"], borderwidth=0,
                    font=(F, BASE))
        s.configure("TCombobox", fieldbackground=C["surface"],
                    foreground=C["text"], background=C["surface"],
                    arrowcolor=C["dim"], selectbackground=C["surface"],
                    font=(F, BASE))
        s.map("TCombobox",
              fieldbackground=[("readonly", C["surface"])],
              foreground=[("readonly", C["text"])])
        s.configure("Craft.Horizontal.TProgressbar",
                    troughcolor=C["surface"], background=C["accent"],
                    borderwidth=0, relief="flat")
        s.configure("Craft.Treeview",
                    background=C["surface"], foreground=C["text"],
                    fieldbackground=C["surface"], rowheight=RH,
                    borderwidth=0, indent=14, font=(F, BASE))
        s.configure("Craft.Treeview.Heading",
                    background=C["bg"], foreground=C["dim"],
                    borderwidth=0, font=(F, BASE, "bold"), relief="flat")
        s.map("Craft.Treeview",
              background=[("selected", C["accent"])],
              foreground=[("selected", C["bg"])])
        style_scrollbar(s)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self, professions: list):
        C  = self.C
        sb = self._sidebar

        # Titulo
        tk.Label(sb, text="⚒ Crafting", bg=C["bg2"],
                 fg=C["accent"], font=(F, TITLE, "bold"),
                 pady=14, padx=12).pack(fill="x")

        self._sep(sb)

        # ── Profesión (canvas scrollable, altura dinámica) ────────────────
        self._prof_section = tk.Frame(sb, bg=C["bg2"])
        self._prof_section.pack(fill="x", padx=8, pady=(6, 0))
        self._prof_section.pack_propagate(False)

        self._prof_label = tk.Label(self._prof_section, text="Profesion",
                                    bg=C["bg2"], fg=C["dim"],
                                    font=(F, BASE, "bold"))
        self._prof_label.pack(anchor="w", pady=(0, 4))

        # Ordenar: recolección (alfabético) → separador → oficios (alfabético)
        recoleccion = sorted([p for p in professions if p in _RECOLECCION])
        oficios     = sorted([p for p in professions if p not in _RECOLECCION])
        ordered     = recoleccion + ["__sep__"] + oficios if oficios else recoleccion

        prof_display_values = [_prof_display(p) for p in ordered if p != "__sep__"]

        # Combobox oculto para compatibilidad con main.py
        self._prof_var = tk.StringVar()
        self._prof_cb = ttk.Combobox(
            sb, textvariable=self._prof_var,
            values=prof_display_values, state="readonly",
            font=(F, BASE), width=1,
        )
        if prof_display_values:
            self._prof_var.set(prof_display_values[0])

        self._prof_canvas = tk.Canvas(self._prof_section, bg=C["bg2"],
                                      highlightthickness=0, bd=0)
        self._prof_btn_frame = tk.Frame(self._prof_canvas, bg=C["bg2"])
        self._prof_canvas.pack(fill="both", expand=True)

        win_id = self._prof_canvas.create_window((0, 0), window=self._prof_btn_frame, anchor="nw")

        def _on_btn_frame_configure(_e=None):
            self._prof_canvas.configure(scrollregion=self._prof_canvas.bbox("all"))

        def _on_canvas_configure(_e=None):
            self._prof_canvas.itemconfigure(win_id, width=self._prof_canvas.winfo_width())

        self._prof_btn_frame.bind("<Configure>", _on_btn_frame_configure)
        self._prof_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            bbox = self._prof_canvas.bbox("all")
            if bbox and bbox[3] > self._prof_canvas.winfo_height():
                self._prof_canvas.yview_scroll(-1 * (e.delta // 120), "units")

        self._prof_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._prof_buttons: list = []
        for item in ordered:
            if item == "__sep__":
                tk.Frame(self._prof_btn_frame, bg=C["border"],
                         height=1).pack(fill="x", padx=6, pady=4)
                continue
            pv = _prof_display(item)
            count = self._prof_counts.get(item, 0)
            label = f"{pv} ({count})" if count else pv
            b = tk.Label(self._prof_btn_frame, text=label,
                         bg=C["bg2"], fg=C["subtext"],
                         font=(F, SMALL), padx=10, pady=5,
                         anchor="w", cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, v=pv: self._select_profession(v))
            b.bind("<Enter>", lambda e, w=b: w.config(bg=C["surface"]))
            b.bind("<Leave>", lambda e, w=b, v=None: self._restore_prof_btn_bg(w))
            self._prof_buttons.append((b, pv, label))

        if prof_display_values:
            self._update_prof_btn_highlight(prof_display_values[0])

        # ── Acciones ─────────────────────────────────────────────────────────
        self._actions_sep = tk.Frame(sb, bg=C["border"], height=1)
        self._actions_sep.pack(fill="x", padx=6, pady=4)
        self._btn_frame = tk.Frame(sb, bg=C["bg2"])
        self._btn_frame.pack(fill="x", padx=8, pady=(0, 2))
        tk.Label(self._btn_frame, text="Acciones", bg=C["bg2"], fg=C["dim"],
                 font=(F, BASE, "bold")).pack(anchor="w", pady=(0, 4))

        self._busy = False
        self._toggle_btn = self._sidebar_btn(self._btn_frame, "▶ Actualizar Precios",
                                             C["green"], C["bg"], self._on_toggle)
        self._toggle_btn.pack(fill="x", pady=(0, 2))
        self._sidebar_btn(self._btn_frame, "↻ Sincronizar", C["surface"], C["accent"],
                          self._on_sync).pack(fill="x")

        # ── Calibrar (pegado al borde inferior) ──────────────────────────────
        self._calibrar_btn = self._sidebar_btn(sb, "⚙ Calibrar", C["surface"], C["dim"],
                                               self._on_calibrate, size=BASE)
        self._calibrar_btn.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self._calibrar_sep = tk.Frame(sb, bg=C["border"], height=1)
        self._calibrar_sep.pack(side="bottom", fill="x", padx=6, pady=4)

        # ── Altura dinámica de la zona de profesiones ────────────────────────
        def _resize_prof(_e=None):
            sb.update_idletasks()
            content_h = self._prof_btn_frame.winfo_reqheight() + self._prof_label.winfo_reqheight() + 12
            used = sum(w.winfo_reqheight() for w in sb.pack_slaves()
                       if w is not self._prof_section)
            available = sb.winfo_height() - used - 60
            self._prof_section.configure(height=min(content_h, max(available, 50)))

        sb.bind("<Configure>", _resize_prof)

    def _sidebar_btn(self, parent, text, bg, fg, cmd, state="normal", size=HEADER):
        return tk.Button(parent, text=text, bg=bg, fg=fg,
                         font=(F, size, "bold"), relief="flat", bd=0,
                         padx=10, pady=5, command=cmd, state=state)

    def _sep(self, parent):
        tk.Frame(parent, bg=self.C["border"], height=1).pack(fill="x", padx=6, pady=4)

    def _select_profession(self, display_val: str):
        self._prof_var.set(display_val)
        self._update_prof_btn_highlight(display_val)
        self._prof_cb.event_generate("<<ComboboxSelected>>")

    def _update_prof_btn_highlight(self, selected_display: str):
        C = self.C
        for btn, val, label in self._prof_buttons:
            if val == selected_display:
                btn.config(bg=C["accent_bg"], fg=C["accent"],
                           font=(F, SMALL, "bold"))
            else:
                btn.config(bg=C["bg2"], fg=C["subtext"],
                           font=(F, BASE), text=label)

    def _restore_prof_btn_bg(self, widget):
        C = self.C
        for btn, val, label in self._prof_buttons:
            if btn is widget:
                if val == self._prof_var.get():
                    widget.config(bg=C["accent_bg"])
                else:
                    widget.config(bg=C["bg2"])
                break

    # ── Filter bar ───────────────────────────────────────────────────────────

    def _build_filterbar(self):
        C = self.C
        ff = tk.Frame(self._main_area, bg=C["bg"])
        ff.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(ff, text="Buscar:", bg=C["bg"], fg=C["dim"],
                 font=(F, BASE)).pack(side="left")
        self._filter_name = tk.StringVar()
        self._filter_name.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(ff, textvariable=self._filter_name, width=20,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=(F, BASE)).pack(side="left", padx=(4, 12))

        tk.Label(ff, text="Ganancia min:", bg=C["bg"], fg=C["dim"],
                 font=(F, BASE)).pack(side="left")
        self._filter_profit = tk.StringVar()
        self._filter_profit.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(ff, textvariable=self._filter_profit, width=10,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=(F, BASE)).pack(side="left", padx=(4, 12))

        tk.Label(ff, text="Nivel:", bg=C["bg"], fg=C["dim"],
                 font=(F, BASE)).pack(side="left")
        self._filter_lvl_min = tk.StringVar()
        self._filter_lvl_min.trace_add("write", lambda *_: self._apply_filter())
        self._filter_lvl_max = tk.StringVar()
        self._filter_lvl_max.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(ff, textvariable=self._filter_lvl_min, width=5,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=(F, BASE)).pack(side="left", padx=(4, 2))
        tk.Label(ff, text="-", bg=C["bg"], fg=C["dim"],
                 font=(F, BASE)).pack(side="left")
        tk.Entry(ff, textvariable=self._filter_lvl_max, width=5,
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=(F, BASE)).pack(side="left", padx=(2, 12))

        tk.Button(ff, text="Limpiar", bg=C["surface"], fg=C["dim"],
                  font=(F, BASE), relief="flat", bd=0,
                  padx=8, pady=3, command=self._clear_filter).pack(side="left")

    # ── Table ────────────────────────────────────────────────────────────────

    def _build_table(self):
        C = self.C
        self._table_frame = tk.Frame(self._main_area, bg=C["bg"])
        self._table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 2))

        cols = ("result", "profit", "lot", "qty", "craft", "sell", "level", "updated")
        self._tree = ttk.Treeview(
            self._table_frame, columns=cols, show="tree headings",
            style="Craft.Treeview", selectmode="browse",
        )
        self._tree.column("#0", width=46, minwidth=46, stretch=False)
        headings = {
            "result":  ("Receta / Ingrediente", 300, "w"),
            "profit":  ("Ganancia Total",        110, "center"),
            "lot":     ("Mejor Lote",             90, "center"),
            "qty":     ("Cantidad",               80, "center"),
            "craft":   ("Costo Total",           110, "center"),
            "sell":    ("Venta Total",           110, "center"),
            "level":   ("Niv.",                   50, "center"),
            "updated": ("Actualizado",           130, "center"),
        }
        for col, (head, width, anchor) in headings.items():
            self._tree.heading(col, text=head, command=lambda c=col: self._sort_col(c))
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(self._table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        self._tree.tag_configure("top",             foreground=C["mauve"])
        self._tree.tag_configure("profit",          foreground=C["green"])
        self._tree.tag_configure("loss",            foreground=C["red"])
        self._tree.tag_configure("neutral",         foreground=C["dim"])
        self._tree.tag_configure("missing",         foreground="#a0b0d0")
        self._tree.tag_configure("ing",             foreground=C["dim"])
        self._tree.tag_configure("ing_buy",         foreground=C["dim"])
        self._tree.tag_configure("ing_craft",       foreground=C["accent"])
        self._tree.tag_configure("sub_ing",         foreground=C["accent"])
        self._tree.tag_configure("selected_recipe",
                                 background=C["today"], foreground=C["text"])

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Button-1>",         self._on_tree_press)
        self._tree.bind("<ButtonRelease-1>",  self._on_tree_release)
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

    # ── Summary bar ──────────────────────────────────────────────────────────

    # ── Prompt ───────────────────────────────────────────────────────────────

    def _build_prompt(self):
        self._prompt_bar = PromptBar(self._main_area)

    # ── Button handlers ──────────────────────────────────────────────────────

    def _on_toggle(self):
        if self._busy:
            if "stop" in self._cbs:
                self._cbs["stop"]()
        else:
            if "start" in self._cbs:
                self._cbs["start"](self.profession(), self.visible_recipe_names())

    def _on_sync(self):
        if "sync" in self._cbs:
            self._cbs["sync"]()

    def _on_calibrate(self):
        if "calibrate" in self._cbs:
            self._cbs["calibrate"]()

    # ── Row selection ────────────────────────────────────────────────────────

    def _show_copy_toast(self, name: str):
        show_copy_toast(self.root, name, bg=self.C["accent"], fg=self.C["bg"])

    def _on_tree_press(self, event):
        iid = self._tree.identify_row(event.y)
        self._pre_click_iid  = iid or None
        self._pre_click_open = self._tree.item(iid, "open") if iid else None

    def _on_tree_release(self, event):
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

        recipe_iid = iid
        while self._tree.parent(recipe_iid):
            recipe_iid = self._tree.parent(recipe_iid)
        if self._selected_recipe_iid and self._selected_recipe_iid != recipe_iid:
            orig = self._row_tags.get(self._selected_recipe_iid, "neutral")
            self._tree.item(self._selected_recipe_iid, tags=(orig,))
        self._selected_recipe_iid = recipe_iid
        self._tree.item(recipe_iid, tags=("selected_recipe",))

        if is_recipe:
            row  = self._row_data.get(iid)
            name = row.get("result", "") if row else ""
        else:
            name = re.sub(r"\s*\(\d+\)$", "", self._tree.set(iid, "result").strip())

        if name:
            self.root.clipboard_clear()
            self.root.clipboard_append(name)
            self._show_copy_toast(name)

    # ── Filters ──────────────────────────────────────────────────────────────

    def _apply_filter(self, profitable: list = None):
        name = self._filter_name.get().strip()
        pv   = self._filter_profit.get().strip().replace(".", "").replace(",", "")
        lmin = self._filter_lvl_min.get().strip()
        lmax = self._filter_lvl_max.get().strip()

        rows = filter_rows(
            self._all_rows,
            name       = name or None,
            min_profit = int(pv)   if pv.lstrip("-").isdigit() else None,
            lvl_min    = int(lmin) if lmin.isdigit()           else None,
            lvl_max    = int(lmax) if lmax.isdigit()           else None,
        )
        self._populate_tree(rows, profitable=profitable)

    def _clear_filter(self):
        self._filter_name.set("")
        self._filter_profit.set("")
        self._filter_lvl_min.set("")
        self._filter_lvl_max.set("")
        self._populate_tree(self._all_rows)

    def _populate_tree(self, rows: list, profitable: list = None):
        rows = sorted(rows, key=lambda r: (r.get("profit_total") or float("-inf")), reverse=True)

        if profitable is None:
            profitable = profitable_rows(rows)
        top_names = {r["result"] for r in profitable[:3]}

        self._tree.delete(*self._tree.get_children())
        self._row_data = {}
        self._selected_recipe_iid = None
        self._row_tags: dict = {}

        for row in rows:
            profit_total = row.get("profit_total")
            craft   = row.get("craft_cost")
            sell    = row.get("sell_price")
            level   = row.get("level", "")
            lot     = row.get("best_lot", "—")
            updated = row.get("updated", "")
            name    = row.get("result", "")

            craft_str  = _fmt(craft)
            sell_str   = _fmt(sell)
            if profit_total is None:
                profit_str = "—"
            else:
                tsign = "+" if profit_total >= 0 else "-"
                profit_str = f"{tsign}{_fmt(abs(profit_total))}"

            if profit_total is None:
                tag = "missing"
            elif name in top_names:
                tag = "top"
            elif profit_total > 0:
                tag = "profit"
            elif profit_total < 0:
                tag = "loss"
            else:
                tag = "neutral"

            iid = self._tree.insert("", "end", values=(
                name, profit_str, lot, "", craft_str, sell_str,
                level, _to_bogota(updated),
            ), tags=(tag,))
            self._row_data[iid] = row
            self._row_tags[iid] = tag

            for ing in row.get("ingredients", []):
                self._insert_ing(iid, ing)

    def _insert_ing(self, parent_iid: str, ing: dict, depth: int = 0):
        indent   = "      " * depth
        qty      = ing.get("quantity", 1)
        ing_name = indent + ing.get("name", "") + f" ({qty})"
        sell_size    = ing.get("sell_size")
        buy_lot      = ing.get("buy_lot") or "—"
        price        = ing.get("unit_price")
        total_lote   = ing.get("total")
        ing_updated  = ing.get("prices_updated_at", "")
        buy_or_craft = ing.get("buy_or_craft")

        has_subs = bool(ing.get("sub_ingredients"))
        if depth == 0 and has_subs:
            ing_tag = "sub_ing"
        elif buy_or_craft == "Craft":
            ing_tag = "ing_craft"
        else:
            ing_tag = "ing_buy"

        if buy_or_craft == "Craft":
            price_str = f"{_fmt(price)} (Craft) · {_fmt(total_lote)}" if price else "Craft"
        else:
            price_str = f"{_fmt(price)} (Buy) · {_fmt(total_lote)}" if price else "—"

        qty_display = _fmt(qty * sell_size) if sell_size else str(qty)

        child_iid = self._tree.insert(parent_iid, "end", values=(
            ing_name, "", buy_lot, qty_display, price_str, "", "", _to_bogota(ing_updated),
        ), tags=(ing_tag,))

        for sub in ing.get("sub_ingredients", []):
            self._insert_ing(child_iid, sub, depth + 1)

    # ── Public API ───────────────────────────────────────────────────────────

    def profession(self) -> str:
        return _prof_from_display(self._prof_var.get())

    def visible_recipe_names(self) -> set | None:
        iids = self._tree.get_children()
        if not iids or not self._row_data:
            return None
        has_filter = (self._filter_name.get().strip()
                      or self._filter_profit.get().strip()
                      or self._filter_lvl_min.get().strip()
                      or self._filter_lvl_max.get().strip())
        if not has_filter:
            return None
        return {self._row_data[iid]["result"]
                for iid in iids if iid in self._row_data}

    def set_status(self, text: str, color: str = None):
        self._status_bar.set(text, color or C["dim"])

    def set_busy(self, busy: bool):
        C = self.C
        self._busy = busy
        if busy:
            self._toggle_btn.config(text="■ Detener", bg=C["red"], fg=C["bg"])
        else:
            self._toggle_btn.config(text="▶ Actualizar Precios", bg=C["green"], fg=C["bg"])

    def refresh_table(self, rows: list):
        self._all_rows = rows
        summary = compute_summary(rows)
        self._apply_filter(profitable=summary["profitable"])

        # Actualizar count en el botón de profesión activo
        selected = self._prof_var.get()
        count = summary["total"]
        for i, (btn, val, _old_label) in enumerate(self._prof_buttons):
            if val == selected:
                new_label = f"{val} ({count})"
                btn.config(text=new_label)
                self._prof_buttons[i] = (btn, val, new_label)
                break

    def show_confirm(self, text: str, on_confirm):
        self._prompt_bar.show_confirm(
            text, on_confirm, fill="x", padx=10, pady=(0, 4))

    def show_price_prompt(self, name: str, is_selling: bool, on_confirm):
        self._prompt_bar.show_price_prompt(
            name, is_selling, on_confirm, fill="x", padx=10, pady=(0, 4))

    def hide_prompt(self):
        self._prompt_bar.hide()
