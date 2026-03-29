"""
Dofus Hub — Punto de entrada unificado.

Uso:
    python hub/main.py
    python -m hub.main
"""

import sys
import os

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

import tkinter as tk

from shared.ui.colors import C
from shared.ui.font import FONT, TITLE
from hub.sidebar import Sidebar
from hub.app_container import AppContainer

INITIAL_APP = "crafting"
WINDOW_SIZE = (1280, 760)

APP_TITLES = {
    "crafting":  "Dofus Hub — Crafting",
    "almanax":   "Dofus Hub — Almanax",
    "ganadero":  "Dofus Hub — Ganadero",
    "trolichas": "Dofus Hub — Trolichas",
}


def main():
    root = tk.Tk()
    root.title("Dofus Hub")
    w, h = WINDOW_SIZE
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.configure(bg=C["bg"])
    root.minsize(900, 560)

    # Layout: tabs arriba + contenido abajo
    outer = tk.Frame(root, bg=C["bg"])
    outer.pack(fill="both", expand=True)

    tabbar = Sidebar(outer, lambda key: on_select(key))
    tabbar.pack(side="top", fill="x")

    tk.Frame(outer, bg=C["border"], height=1).pack(side="top", fill="x")

    content = tk.Frame(outer, bg=C["bg"])
    content.pack(side="top", fill="both", expand=True)

    container = AppContainer(content, root)

    def on_select(key: str):
        container.show(key)
        tabbar.set_active(key)
        root.title(APP_TITLES.get(key, "Dofus Hub"))

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    on_select(INITIAL_APP)  # type: ignore[name-defined]
    root.mainloop()


if __name__ == "__main__":
    main()
