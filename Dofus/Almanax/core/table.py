"""
Lógica de clasificación y etiquetado de filas de la tabla Almanax.
"""

from datetime import date, datetime, timezone, timedelta

# Umbral de ganancia (kamas) que separa "alta rentabilidad" de "bajo margen"
MIN_HIGH_PROFIT = 500


def today_fr() -> date:
    """Fecha actual en hora francesa (CET UTC+1 / CEST UTC+2)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Paris")).date()
    except Exception:
        utc = datetime.now(timezone.utc)
        y   = utc.year
        def _last_sun(month: int) -> date:
            d = date(y, month, 31)
            while d.weekday() != 6:
                d -= timedelta(days=1)
            return d
        s3  = _last_sun(3)
        s10 = _last_sun(10)
        spring = datetime(y, s3.month,  s3.day,  1, tzinfo=timezone.utc)
        autumn = datetime(y, s10.month, s10.day, 1, tzinfo=timezone.utc)
        offset = timedelta(hours=2 if spring <= utc < autumn else 1)
        return (utc + offset).date()


def day_label(entry_date: date) -> str:
    """Devuelve 'Hoy' o '+Nd' según los días de diferencia respecto a hoy."""
    delta = (entry_date - today_fr()).days
    return "Hoy" if delta == 0 else f"+{delta}d"


def profit_tag(profit) -> str:
    """Clasifica la ganancia en una etiqueta visual."""
    if profit is None:       return "sin_precio"
    if profit >= MIN_HIGH_PROFIT: return "alta"
    if profit >= 0:          return "media"
    return "perdida"
