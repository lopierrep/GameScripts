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
    if name is None and min_profit is None and lvl_min is None and lvl_max is None:
        return rows
    needle = name.lower() if name else None
    return [
        r for r in rows
        if (needle is None or needle in r.get("result", "").lower())
        and (min_profit is None or (r.get("profit_total") or 0) >= min_profit)
        and (lvl_min is None or (str(r.get("level", "0")).isdigit() and int(r.get("level", 0)) >= lvl_min))
        and (lvl_max is None or (str(r.get("level", "999")).isdigit() and int(r.get("level", 999)) <= lvl_max))
    ]


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
