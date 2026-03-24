"""
Lógica de compra automática en el mercadillo (sin dependencias de UI).
"""
import threading
import time
from typing import Callable

from config.config import MARKET_NAMES


class AutoBuyer:
    """
    Compra ítems automáticamente en el mercadillo agrupando por tipo.

    Recibe las funciones de interacción con el mercadillo como parámetros
    (inyección de dependencias) para facilitar pruebas y desacoplamiento de la UI.
    """

    def __init__(
        self,
        search_item:        Callable[[str], None],
        find_exact_result:  Callable[[str], tuple | None],
        click_at:           Callable[..., None],
        init_cal:           Callable[[], None],
        press_esc:          Callable[[], None],
    ):
        self._search_item       = search_item
        self._find_exact_result = find_exact_result
        self._click_at          = click_at
        self._init_cal          = init_cal
        self._press_esc         = press_esc

    def buy(
        self,
        items_by_subtype: dict[str, list[tuple[str, list]]],
        buy_cal:          dict,
        stop_event:       threading.Event,
        on_progress:      Callable[[str], None],
        on_market_switch: Callable[[str, int], bool],
    ) -> list[str]:
        """
        Compra los ítems automáticamente agrupando por tipo de mercadillo.

        Parámetros:
          items_by_subtype  dict {subtype: [(nombre, plan), ...]}
                            plan = [(lot_size, n_lots), ...]
          buy_cal           calibración con lot_buttons y buy_btn
          stop_event        evento para cancelar (tecla Y)
          on_progress       callback(mensaje) para actualizar la UI
          on_market_switch  callback(market_name, n_items) → bool

        Devuelve lista de nombres de ítems que no se pudieron comprar.
        """
        import keyboard as _kb

        failed: list[str] = []
        _kb.add_hotkey("s", stop_event.set)
        self._init_cal()

        try:
            for subtype, group in items_by_subtype.items():
                if stop_event.is_set():
                    failed.extend(name for name, _ in group)
                    continue

                market_name = MARKET_NAMES.get(subtype, subtype.capitalize())
                if not on_market_switch(market_name, len(group)):
                    failed.extend(name for name, _ in group)
                    continue

                for i in range(5, 0, -1):
                    if stop_event.is_set():
                        break
                    on_progress(f"[{market_name}] Cambia al juego… {i}s  (S para parar)")
                    time.sleep(1)

                for name, plan in group:
                    if stop_event.is_set():
                        failed.append(name)
                        continue
                    try:
                        self._buy_item(name, plan, buy_cal, stop_event, on_progress, market_name)
                    except Exception:
                        failed.append(name)
                        self._press_esc()
                        time.sleep(0.3)
        finally:
            _kb.remove_hotkey("s")

        return failed

    def _buy_item(
        self,
        name:        str,
        plan:        list[tuple[int, int]],
        buy_cal:     dict,
        stop_event:  threading.Event,
        on_progress: Callable[[str], None],
        market_name: str,
    ):
        self._search_item(name)
        pos = self._find_exact_result(name)
        if pos is None:
            raise RuntimeError(f"Ítem '{name}' no encontrado en resultados")

        self._click_at(pos, delay=0.4)

        total_ops = sum(n for _, n in plan)
        done = 0

        for lot_size, n_lots in plan:
            if stop_event.is_set():
                break
            row_pos     = buy_cal["lot_buttons"][str(lot_size)]
            confirm_pos = buy_cal["buy_btn"]
            first_click = True   # cada cambio de lote requiere confirmar una vez

            for _ in range(n_lots):
                if stop_event.is_set():
                    break
                self._click_at(row_pos, delay=0.25)
                if first_click:
                    self._click_at(confirm_pos, delay=0.4)
                    first_click = False
                time.sleep(1)
                done += 1
                on_progress(f"[{market_name}] {name[:25]}: {done}/{total_ops}…  (S para parar)")

        self._press_esc()
        time.sleep(0.3)