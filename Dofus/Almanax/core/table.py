"""
Lógica de clasificación y etiquetado de filas de la tabla Almanax.
"""

from datetime import date

# Umbral de ganancia (kamas) que separa "alta rentabilidad" de "bajo margen"
MIN_HIGH_PROFIT = 500


def day_label(entry_date: date) -> str:
    """Devuelve 'Hoy' o '+Nd' según los días de diferencia respecto a hoy."""
    delta = (entry_date - date.today()).days
    return "Hoy" if delta == 0 else f"+{delta}d"


def profit_tag(profit) -> str:
    """Clasifica la ganancia en una etiqueta visual."""
    if profit is None:       return "sin_precio"
    if profit >= MIN_HIGH_PROFIT: return "alta"
    if profit >= 0:          return "media"
    return "perdida"
