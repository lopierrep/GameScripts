"""
AppContainer — lazy-loader de las 4 apps del hub.

Las apps son paquetes Python con imports relativos, por lo que no hay
colisiones de nombres entre ellas. Se importan directamente.
"""

import tkinter as tk
from shared.ui.colors import C


def _init_app(app_key: str, host, on_sync_done=None):
    """Instancia la app dentro del FrameHost dado."""
    if app_key == "crafting":
        from Crafting.main import CraftingApp
        return CraftingApp(host, on_sync_done=on_sync_done)
    elif app_key == "almanax":
        from Almanax.main import AlmanaxApp
        return AlmanaxApp(host, on_sync_done=on_sync_done)
    elif app_key == "ganadero":
        from Ganadero.main import GanaderoApp
        return GanaderoApp(host, on_sync_done=on_sync_done)
    elif app_key == "trolichas":
        from Trolichas.main import build_trolichas_app
        return build_trolichas_app(host)
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
                self._apps[key] = _init_app(key, host, on_sync_done=lambda k=key: self._notify_sync_done(k))
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

    def _notify_sync_done(self, source_key: str):
        """Refresca todas las apps cargadas excepto la que hizo el sync."""
        for key, app in self._apps.items():
            if key != source_key and hasattr(app, "refresh_from_sync"):
                app.refresh_from_sync()

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
