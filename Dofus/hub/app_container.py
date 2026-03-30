"""
AppContainer — lazy-loader de las 4 apps del hub.

Problema de imports: cada app añade su directorio a sys.path y usa nombres
genéricos como `config`, `ui`, `core`. Si se cargan varias apps en el mismo
proceso, esos nombres chocan en sys.modules.

Solución:
  1. Se guarda sys.path tal como estaba al iniciar el hub.
  2. Antes de cargar cada app, se restaura sys.path al estado original
     y se añade solo el directorio de esa app al frente.
  3. Se eliminan del caché los módulos con nombres genéricos.
Así cada app ve un sys.path limpio, sin rutas de otras apps.
"""

import sys
import os
import importlib.util
import tkinter as tk
from shared.ui.colors import C

# Prefijos de módulo genéricos que las apps usan localmente
_GENERIC_PREFIXES = ("config", "ui", "core", "calibration", "automation", "utils", "race_loop")

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_APP_DIRS = {
    "crafting":  os.path.join(_DOFUS_DIR, "Crafting"),
    "almanax":   os.path.join(_DOFUS_DIR, "Almanax"),
    "ganadero":  os.path.join(_DOFUS_DIR, "Ganadero"),
    "trolichas": os.path.join(_DOFUS_DIR, "Trolichas"),
}

# sys.path tal como estaba al importar este módulo (antes de que ninguna app lo modifique)
_BASE_SYSPATH = list(sys.path)


def _clear_generic_modules():
    """Elimina módulos con nombres genéricos del caché de Python."""
    to_remove = [
        k for k in list(sys.modules)
        if any(k == p or k.startswith(p + ".") for p in _GENERIC_PREFIXES)
    ]
    for k in to_remove:
        del sys.modules[k]


def _load_app_main(app_key: str):
    """Carga el main.py de la app con un nombre único para evitar colisiones."""
    app_dir = _APP_DIRS[app_key]

    # Restaurar sys.path al estado base + solo el directorio de esta app al frente.
    # Evita que rutas de otras apps contaminen la resolución de módulos.
    sys.path[:] = [app_dir] + _BASE_SYSPATH

    # Limpiar módulos genéricos para que la app cargue los suyos
    _clear_generic_modules()

    main_path = os.path.join(app_dir, "main.py")
    unique_name = f"_hub_{app_key}_main"
    spec = importlib.util.spec_from_file_location(unique_name, main_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _init_app(app_key: str, host):
    """Instancia la app dentro del FrameHost dado."""
    mod = _load_app_main(app_key)

    if app_key == "crafting":
        return mod.CraftingApp(host)
    elif app_key == "almanax":
        return mod.AlmanaxApp(host)
    elif app_key == "ganadero":
        return mod.GanaderoApp(host)
    elif app_key == "trolichas":
        return mod.build_trolichas_app(host)

    raise ValueError(f"App desconocida: {app_key}")


class AppContainer:
    def __init__(self, parent: tk.Frame, real_root: tk.Tk):
        self._parent = parent
        self._real_root = real_root
        self._frames: dict[str, tk.Frame] = {}
        self._apps: dict[str, object] = {}
        self._active: str | None = None

    def show(self, key: str):
        # Ocultar frame actual
        if self._active and self._active in self._frames:
            self._frames[self._active].pack_forget()

        # Lazy-init en la primera visita
        if key not in self._frames:
            from hub.frame_host import FrameHost
            import traceback

            if key == "trolichas":
                # Trolichas es una UI compacta: centrarla dentro de un outer frame
                outer = tk.Frame(self._parent, bg=C["bg"])
                outer.pack(fill="both", expand=True)
                host = FrameHost(outer, self._real_root)
                self._frames[key] = outer
            else:
                host = FrameHost(self._parent, self._real_root)
                host.pack(fill="both", expand=True)
                self._frames[key] = host

            try:
                self._apps[key] = _init_app(key, host)
                if key == "trolichas":
                    host.update_idletasks()
                    host.place(relx=0.5, rely=0.5, anchor="center")
            except Exception:
                traceback.print_exc()
                err_frame = self._frames[key] if key != "trolichas" else host
                self._show_error(err_frame, traceback.format_exc())
                self._active = key
                return
        else:
            self._frames[key].pack(fill="both", expand=True)

        self._active = key

    def _show_error(self, parent: tk.Frame, msg: str):
        from shared.ui.colors import C
        from shared.ui.font import FONT, SMALL
        tk.Label(
            parent,
            text=f"Error al cargar la app:\n\n{msg}",
            bg=C["bg"], fg=C["red"],
            font=(FONT, SMALL),
            justify="left", wraplength=800, anchor="nw",
        ).pack(fill="both", expand=True, padx=20, pady=20)
