"""
Loop de escaneo de precios en el mercadillo, compartido entre módulos.
"""
import time
from typing import Callable


class MarketScanner:
    """
    Itera sobre ítems agrupados por mercadillo y llama a process_item por cada uno.

    Parámetros de __init__:
      press_esc   fn() — pulsa Escape tras procesar un ítem
                         (omitido si el resultado incluye "_skipped": True)
      init_cal    fn() — inicializa calibración antes de empezar (opcional)
      delay       segundos de espera tras press_esc entre ítems (por defecto 0.3)
      countdown   segundos de cuenta atrás antes de cada mercadillo (0 = sin cuenta)
    """

    def __init__(
        self,
        press_esc:  Callable[[], None],
        init_cal:   Callable[[], None] | None = None,
        delay:      float = 0.3,
        countdown:  int   = 3,
    ):
        self._press_esc = press_esc
        self._init_cal  = init_cal
        self._delay     = delay
        self._countdown = countdown

    def scan(
        self,
        items_by_market:  dict[str, list[str]],
        is_stopped:       Callable[[], bool],
        on_progress:      Callable[[str], None],
        on_market_switch: Callable[[str, int], bool],
        process_item:     Callable[[str], dict],
    ) -> dict[str, dict]:
        """
        Parámetros:
          items_by_market   {nombre_mercadillo: [item, ...]}
          is_stopped        fn() → bool — True cancela el escaneo
          on_progress       fn(mensaje) — actualiza la UI o stdout
          on_market_switch  fn(nombre, n_items) → bool — False cancela el escaneo
          process_item      fn(item) → dict
                            • puede incluir "_skipped": True para omitir press_esc
                            • lanza Exception para saltar el ítem sin añadirlo

        Devuelve:
          {item: dict_resultado} para ítems procesados correctamente
        """
        if self._init_cal:
            self._init_cal()

        results: dict[str, dict] = {}
        total   = sum(len(v) for v in items_by_market.values())
        scanned = 0

        for market_name, items in items_by_market.items():
            if is_stopped():
                break
            if not items:
                continue

            if not on_market_switch(market_name, len(items)):
                break

            for i in range(self._countdown, 0, -1):
                if is_stopped():
                    break
                on_progress(f"[{market_name}] Cambia al juego… {i}s")
                time.sleep(1)

            if is_stopped():
                break

            for item in items:
                if is_stopped():
                    break

                scanned += 1
                on_progress(f"[{market_name}] [{scanned}/{total}] {item[:30]}…")

                try:
                    result = process_item(item)
                except Exception:
                    continue

                if not (isinstance(result, dict) and result.get("_skipped")):
                    self._press_esc()
                    time.sleep(self._delay)

                results[item] = result

        return results
