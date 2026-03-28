"""
Ganadero – Capa de presentación (GanaderoUI)
=============================================
Construye y actualiza todos los widgets de la ventana.
No contiene lógica de negocio ni llamadas a módulos de core/.
"""

import tkinter as tk
from tkinter import ttk

from shared.colors import C

TOPES = [40000, 70000, 90000, 100000]
INDICADORES = ["aporreadora", "acariciador", "dragonalgas", "fulminadora", "abrevadero", "pesebre"]

RANGOS_CONSUMO = [
    {"label": "0-40k",   "rate": 1},
    {"label": "40k-70k", "rate": 2},
    {"label": "70k-90k", "rate": 3},
    {"label": "90k-100k","rate": 4},
]

XP_NIVEL_200 = 867582
STAT_MAX = 20000
STATS_TIEMPO = [
    ("XP (nivel 200)", XP_NIVEL_200),
    ("Amor",           STAT_MAX),
    ("Resistencia",    STAT_MAX),
    ("Madurez",        STAT_MAX),
]

COLUMNS = [
    ("indicador",   "Indicador",       120),
    ("nombre",      "Carburante",      160),
    ("level",       "Nivel",            50),
    ("recarga",     "Recarga",          65),
    ("mejor_modo",  "Modo",             70),
    ("mejor_lote",  "Lote",             45),
    ("precio_ud",   "Precio unitario",  90),
    ("cantidad",    "Uds.",             45),
    ("costo_total", "Costo total",     100),
]


class GanaderoUI:
    """
    Construye la UI y expone métodos para actualizar las tablas.

    Callbacks esperados:
        refresh  ()  →  recalcular datos y repintar
    """

    def __init__(self, root: tk.Tk, callbacks: dict, settings: dict):
        self.root = root
        self._cb = callbacks
        self.umbral_var = tk.IntVar(value=settings.get("umbral", 10000))
        self._trees: dict[str, ttk.Treeview] = {}
        self._monturas = settings.get("monturas", 10)

        self._setup_window()
        self._apply_styles()
        self._build_ui()

    # ── Ventana ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Ganadero - Eficiencia de Carburantes")
        self.root.geometry("1500x700+40+40")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(1200, 500)

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
                        background=C["surface"], foreground=C["text"],
                        fieldbackground=C["surface"], rowheight=26,
                        font=("Consolas", 10))
        style.configure("Treeview.Heading",
                        background=C["bg"], foreground=C["dim"],
                        font=("Consolas", 11, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", C["bg"])])

        style.configure("TScrollbar", background=C["surface"], troughcolor=C["bg"],
                        borderwidth=0, arrowsize=12)

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_main_area()
        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["bg"], pady=8)
        bar.pack(fill="x", padx=12)

        tk.Label(bar, text="Ganadero", bg=C["bg"], fg=C["accent"],
                 font=("Consolas", 16, "bold")).pack(side="left")
        tk.Label(bar, text=" - Eficiencia de Carburantes", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left")

        tk.Label(bar, text="   Umbral:", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(20, 4))
        e = tk.Entry(bar, textvariable=self.umbral_var, width=6,
                     bg=C["surface"], fg=C["text"], font=("Consolas", 12),
                     insertbackground=C["text"], relief="flat")
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._cb["refresh"]())
        tk.Label(bar, text="k (costo total)", bg=C["bg"], fg=C["dim"],
                 font=("Consolas", 10)).pack(side="left", padx=(4, 0))

        tk.Button(bar, text="Recalcular", bg=C["orange"], fg=C["bg"],
                  font=("Consolas", 11, "bold"), relief="flat", padx=10, pady=3,
                  cursor="hand2", command=self._cb["refresh"]).pack(side="left", padx=(12, 0))

    def _build_main_area(self):
        main = tk.PanedWindow(self.root, orient="horizontal", bg=C["dim"],
                              sashwidth=4, sashrelief="flat")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        # ── Panel izquierdo: carburantes ──────────────────────────────────
        left = tk.Frame(main, bg=C["bg"])

        for tope in TOPES:
            tk.Label(left, text=f"Tope {tope:,}", bg=C["bg"],
                     fg=C["accent"], font=("Consolas", 11, "bold"),
                     anchor="w").pack(fill="x", padx=20, pady=(10, 2))
            self._trees[str(tope)] = self._build_tree(left)

        # ── Panel derecho: tiempos y costos ───────────────────────────────
        right = tk.Frame(main, bg=C["bg"])

        self._build_tiempos(right)

        main.add(left, minsize=830)
        main.add(right)

        # Dividir 50/50 tras renderizar y al redimensionar
        self._paned = main
        self.root.update_idletasks()
        main.sash_place(0, self.root.winfo_width() // 2, 0)
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is self.root:
            self._paned.sash_place(0, event.width // 2, 0)

    def _build_tree(self, parent: tk.Frame) -> ttk.Treeview:
        frame = tk.Frame(parent, bg=C["bg"])
        frame.pack(fill="x", padx=20, pady=(0, 4))

        cols = [c[0] for c in COLUMNS]
        tree = ttk.Treeview(frame, columns=cols, show="headings",
                            selectmode="browse", height=6)

        for col_id, col_text, col_w in COLUMNS:
            tree.heading(col_id, text=col_text)
            anchor = "w" if col_id in ("indicador", "nombre") else "center"
            tree.column(col_id, width=col_w, minwidth=40, anchor=anchor,
                        stretch=(col_id == "nombre"))

        tree.pack(fill="x")

        tree.tag_configure("ok",    foreground=C["green"])
        tree.tag_configure("caro",  foreground=C["red"])
        tree.tag_configure("alt",   background="#252535")

        return tree

    @staticmethod
    def _fmt_tiempo(segundos: float) -> str:
        if segundos >= 86400:
            d = int(segundos // 86400)
            h = int((segundos % 86400) // 3600)
            return f"{d}d {h:02d}h"
        if segundos >= 3600:
            h = int(segundos // 3600)
            m = int((segundos % 3600) // 60)
            return f"{h}h {m:02d}m"
        m = int(segundos // 60)
        s = int(segundos % 60)
        return f"{m}m {s:02d}s"

    def _build_tiempos(self, parent: tk.Frame):
        # ── Tiempo por stat ──────────────────────────────────────────────
        tk.Label(parent, text="Tiempo para llenar cada stat",
                 bg=C["bg"], fg=C["accent"], font=("Consolas", 11, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(10, 4))

        cols_t = [("stat", "Estadistica", 130)]
        for r in RANGOS_CONSUMO:
            cols_t.append((r["label"], f'{r["label"]} ({r["rate"]}/s)', 110))

        frame = tk.Frame(parent, bg=C["bg"])
        frame.pack(fill="x", padx=20, pady=(0, 8))

        tree = ttk.Treeview(frame, columns=[c[0] for c in cols_t],
                            show="headings", selectmode="browse", height=4)
        for col_id, col_text, col_w in cols_t:
            tree.heading(col_id, text=col_text)
            tree.column(col_id, width=col_w, minwidth=60,
                        anchor="w" if col_id == "stat" else "center")
        tree.tag_configure("alt", background="#252535")

        for i, (nombre, total) in enumerate(STATS_TIEMPO):
            vals = [nombre] + [self._fmt_tiempo(total / r["rate"]) for r in RANGOS_CONSUMO]
            tree.insert("", "end", values=vals, tags=(("alt",) if i % 2 == 1 else ()))
        tree.pack(fill="x")

        # ── Consumo por tope ─────────────────────────────────────────────
        tk.Label(parent, text="Consumo de cada tope",
                 bg=C["bg"], fg=C["accent"], font=("Consolas", 11, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(10, 4))

        cols_d = [("tope","Tope",80),("tramo","Tramo",120),
                  ("rate","Consumo",80),("tiempo","Tramo",100),("acum","Total",100)]
        frame_d = tk.Frame(parent, bg=C["bg"])
        frame_d.pack(fill="x", padx=20, pady=(0, 8))

        tree_d = ttk.Treeview(frame_d, columns=[c[0] for c in cols_d],
                               show="headings", selectmode="browse", height=4)
        for col_id, col_text, col_w in cols_d:
            tree_d.heading(col_id, text=col_text)
            tree_d.column(col_id, width=col_w, minwidth=50, anchor="center")
        tree_d.tag_configure("alt", background="#252535")

        tope_ant, acum = 0, 0
        for i, r in enumerate(RANGOS_CONSUMO):
            t = TOPES[i]
            tramo = t - tope_ant
            seg = tramo / r["rate"]
            acum += seg
            tree_d.insert("", "end", tags=(("alt",) if i % 2 == 1 else ()), values=(
                f"{t:,}", f"{tope_ant:,} - {t:,}", f'{r["rate"]}/s',
                self._fmt_tiempo(seg), self._fmt_tiempo(acum)))
            tope_ant = t
        tree_d.pack(fill="x")

        # ── Costo por dragopavo ──────────────────────────────────────────
        tk.Label(parent, text=f"Costo por dragopavo ({self._monturas} monturas/cercado)",
                 bg=C["bg"], fg=C["accent"], font=("Consolas", 11, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(10, 4))

        cols_c = [("stat", "Estadistica", 110)]
        for t in TOPES:
            cols_c.append((f"t{t}", f"Tope {t:,}", 110))

        frame2 = tk.Frame(parent, bg=C["bg"])
        frame2.pack(fill="x", padx=20)

        self._tree_costos = ttk.Treeview(frame2, columns=[c[0] for c in cols_c],
                                          show="headings", selectmode="browse", height=7)
        for col_id, col_text, col_w in cols_c:
            self._tree_costos.heading(col_id, text=col_text)
            self._tree_costos.column(col_id, width=col_w, minwidth=70,
                                      anchor="w" if col_id == "stat" else "center")
        self._tree_costos.tag_configure("alt",      background="#252535")
        self._tree_costos.tag_configure("subtotal", foreground=C["yellow"], font=("Consolas", 11, "bold"))
        self._tree_costos.tag_configure("total",    foreground=C["accent"], font=("Consolas", 11, "bold"))
        self._tree_costos.pack(fill="x")

    def _build_statusbar(self):
        self.status_lbl = tk.Label(self.root, text="", bg=C["bg"], fg=C["dim"],
                                   font=("Consolas", 11), anchor="w")
        self.status_lbl.pack(fill="x", padx=14, pady=(0, 6))

    # ── Métodos públicos para actualizar desde el orquestador ─────────────────

    def update_topes(self, resultado: dict, umbral: int):
        for tope in TOPES:
            tree = self._trees[str(tope)]
            tree.delete(*tree.get_children())
            data = resultado.get(str(tope), {})

            for i, indicador in enumerate(INDICADORES):
                ranking = data.get(indicador, [])
                if not ranking:
                    continue
                m = ranking[0]
                costo_total = m["costo_total"]
                tag = "caro" if costo_total > umbral else "ok"
                if i % 2 == 1:
                    tag = (tag, "alt")

                tree.insert("", "end", tags=tag, values=(
                    indicador.capitalize(), m["nombre"], m["level"],
                    m["cantidad_recarga"], m["mejor_modo"], m["mejor_lote"],
                    f"{m['precio_unitario']:,}", m["uds"], f"{costo_total:,}",
                ))

    def update_costos(self, datos: dict, monturas: int):
        tree = self._tree_costos
        tree.delete(*tree.get_children())

        labels = {
            "fulminadora": "Resistencia",
            "abrevadero":  "Madurez",
            "dragonalgas": "Amor",
            "pesebre":     "XP (nv 200)",
        }
        stats_keys = ["fulminadora", "abrevadero", "dragonalgas"]

        for i, key in enumerate(stats_keys):
            tag = ("alt",) if i % 2 == 1 else ()
            vals = [labels[key]]
            for tope in TOPES:
                m = datos[str(tope)]["detalle"].get(key)
                vals.append(f"{m['costo_total'] // monturas:,}" if m else "N/A")
            tree.insert("", "end", tags=tag, values=vals)

        vals_sub = ["Subtotal stats"]
        for tope in TOPES:
            vals_sub.append(f"{datos[str(tope)]['costo_stats']:,}")
        tree.insert("", "end", tags=("subtotal",), values=vals_sub)

        vals_xp = [labels["pesebre"]]
        for tope in TOPES:
            m = datos[str(tope)]["detalle"].get("pesebre")
            vals_xp.append(f"{m['costo_total'] // monturas:,}" if m else "N/A")
        tree.insert("", "end", values=vals_xp)

        vals_tot = ["TOTAL"]
        for tope in TOPES:
            vals_tot.append(f"{datos[str(tope)]['costo_total']:,}")
        tree.insert("", "end", tags=("total",), values=vals_tot)

    def update_status(self, text: str):
        self.status_lbl.config(text=text)
