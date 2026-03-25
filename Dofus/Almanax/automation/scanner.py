"""
Lógica de escaneo de precios en el mercadillo (sin dependencias de UI).
"""
import threading
from typing import Callable

from config.config import LOTS, MARKET_NAMES
from shared.market.scanner import MarketScanner as _BaseScanner


class MarketScanner:
    """
    Escanea precios del mercadillo para una lista de ítems agrupados por tipo.

    Recibe las funciones de interacción con el mercadillo como parámetros
    (inyección de dependencias) para facilitar pruebas y desacoplamiento de la UI.
    """

    def __init__(
        self,
        search_item:  Callable[[str], None],
        read_prices:  Callable[[str], dict],
        parse_price:  Callable[[dict, str], int],
        init_cal:     Callable[[], None],
        press_esc:    Callable[[], None],
    ):
        self._search_item = search_item
        self._read_prices = read_prices
        self._parse_price = parse_price
        self._scanner = _BaseScanner(
            press_esc=press_esc,
            init_cal=init_cal,
            delay=0.3,
            countdown=3,
        )

    def scan(
        self,
        items_by_subtype: dict[str, list[str]],
        stop_event:       threading.Event,
        on_progress:      Callable[[str], None],
        on_market_switch: Callable[[str, int], bool],
    ) -> dict[str, dict]:
        """
        Parámetros:
          items_by_subtype  dict {subtype: [nombre_item, ...]}
          stop_event        evento para cancelar el escaneo
          on_progress       callback(mensaje) para actualizar la UI
          on_market_switch  callback(market_name, n_items) → bool (True = continuar)

        Devuelve:
          dict {nombre_item: {"x1": int, "x10": int, "x100": int, "x1000": int}}
        """
        items_by_market = {
            MARKET_NAMES.get(k, k.capitalize()): v
            for k, v in items_by_subtype.items()
        }

        search_item = self._search_item
        read_prices = self._read_prices
        parse_price = self._parse_price

        def _process(item: str) -> dict:
            search_item(item)
            raw   = read_prices(item)
            entry = {f"x{s}": parse_price(raw, str(s)) for s in LOTS}
            if not any(v > 0 for v in entry.values()):
                raise ValueError("sin precios")
            return entry

        return self._scanner.scan(
            items_by_market  = items_by_market,
            is_stopped       = stop_event.is_set,
            on_progress      = on_progress,
            on_market_switch = on_market_switch,
            process_item     = _process,
        )
