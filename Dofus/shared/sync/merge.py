"""
Merge generico de estructuras de precios anidadas.

Estructura esperada: {market: {category: {item: {x1, x10, ..., prices_updated_at?}}}}
"""


def _ts(obj: dict, field: str = "prices_updated_at") -> str:
    """Extrae timestamp como string comparable, o '' si no existe."""
    return obj.get(field, "")


def merge_nested_prices(
    local: dict,
    remote: dict,
    ts_field: str = "prices_updated_at",
) -> tuple[dict, int, int]:
    """
    Merge dato por dato de una estructura market > category > item.
    Gana el item con el timestamp mas reciente.
    Devuelve (merged, n_local_wins, n_remote_wins).
    """
    merged = {}
    local_wins = remote_wins = 0

    all_markets = set(local) | set(remote)
    for market in all_markets:
        local_market  = local.get(market, {})
        remote_market = remote.get(market, {})
        merged[market] = {}

        all_categories = set(local_market) | set(remote_market)
        for category in all_categories:
            local_cat  = local_market.get(category, {})
            remote_cat = remote_market.get(category, {})
            merged[market][category] = {}

            all_items = set(local_cat) | set(remote_cat)
            for item in all_items:
                local_item  = local_cat.get(item)
                remote_item = remote_cat.get(item)

                if local_item and not remote_item:
                    merged[market][category][item] = local_item
                    local_wins += 1
                elif remote_item and not local_item:
                    merged[market][category][item] = remote_item
                    remote_wins += 1
                elif _ts(remote_item, ts_field) > _ts(local_item, ts_field):
                    merged[market][category][item] = remote_item
                    remote_wins += 1
                else:
                    merged[market][category][item] = local_item
                    local_wins += 1

    return merged, local_wins, remote_wins
