"""
Lógica de filtrado y resumen de filas de la tabla de crafting.
"""


def filter_rows(
    rows: list,
    min_profit: int | None = None,
    lvl_min: int | None = None,
    lvl_max: int | None = None,
    name: str | None = None,
) -> list:
    result = rows
    if name:
        needle = name.lower()
        result = [r for r in result if needle in r.get("result", "").lower()]
    if min_profit is not None:
        result = [r for r in result if (r.get("profit_total") or 0) >= min_profit]
    if lvl_min is not None:
        result = [r for r in result
                  if str(r.get("level", "0")).isdigit()
                  and int(r.get("level", 0)) >= lvl_min]
    if lvl_max is not None:
        result = [r for r in result
                  if str(r.get("level", "999")).isdigit()
                  and int(r.get("level", 999)) <= lvl_max]
    return result


def profitable_rows(rows: list) -> list:
    return sorted(
        [r for r in rows if (r.get("profit_total") or 0) > 0],
        key=lambda r: r["profit_total"],
        reverse=True,
    )


def compute_summary(rows: list) -> dict:
    """
    Devuelve estadísticas de un conjunto de filas.
    {total, profitable, n_profitable, avg_profit, top}
    """
    profitable = profitable_rows(rows)
    avg = sum(r["profit_total"] for r in profitable) / len(profitable) if profitable else 0
    top = profitable[0] if profitable else None
    return {
        "total":        len(rows),
        "profitable":   profitable,
        "n_profitable": len(profitable),
        "avg_profit":   avg,
        "top":          top,
    }
