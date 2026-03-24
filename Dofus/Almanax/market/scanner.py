"""
Lógica de escaneo de precios en el mercadillo (sin dependencias de UI).
"""
import threading
import time
from typing import Callable

from core.models import LOTS, MARKET_NAMES


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
        self._init_cal    = init_cal
        self._press_esc   = press_esc

    def scan(
        self,
        items_by_subtype: dict[str, list[str]],
        stop_event:       threading.Event,
        on_progress:      Callable[[str], None],
        on_market_switch: Callable[[str, int], bool],
    ) -> dict[str, dict]:
        """
        Escanea precios por mercadillo.

        Parámetros:
          items_by_subtype  dict {subtype: [nombre_item, ...]}
          stop_event        evento para cancelar el escaneo
          on_progress       callback(mensaje) para actualizar la UI
          on_market_switch  callback(market_name, n_items) → bool (True = continuar)

        Devuelve:
          dict {nombre_item: {"x1": int, "x10": int, "x100": int, "x1000": int}}
        """
        self._init_cal()

        results: dict[str, dict] = {}
        total   = sum(len(v) for v in items_by_subtype.values())
        scanned = 0

        for subtype, items in items_by_subtype.items():
            if stop_event.is_set():
                break

            market_name = MARKET_NAMES.get(subtype, subtype.capitalize())
            if not on_market_switch(market_name, len(items)):
                break

            for i in range(3, 0, -1):
                if stop_event.is_set():
                    break
                on_progress(f"[{market_name}] Cambia al juego… {i}s")
                time.sleep(1)

            if stop_event.is_set():
                break

            for item in items:
                if stop_event.is_set():
                    break

                scanned += 1
                on_progress(f"[{market_name}] [{scanned}/{total}] {item[:30]}…  (S para parar)")

                try:
                    self._search_item(item)
                    raw = self._read_prices(item)
                    self._press_esc()
                    time.sleep(0.3)
                except Exception:
                    continue

                entry = {f"x{s}": self._parse_price(raw, str(s)) for s in LOTS}
                if any(v > 0 for v in entry.values()):
                    results[item] = entry

        return results