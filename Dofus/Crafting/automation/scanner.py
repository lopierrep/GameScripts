"""
Construcción de ScanItems para el scanner unificado.
"""
from Crafting.config.config import SIZES
from shared.market.item_price_scanner import ScanItem


def build_scan_items(
    market_groups:   dict,
    item_lookup:     dict,
    markets:         dict,
    craftable_map:   dict,
    result_file_map: dict,
) -> list:
    """
    Convierte market_groups en una lista plana de ScanItem.

    market_groups: {market_name: {"results": [...], "ingredients": [...]}}
    craftable_map: {result_name: recipe_dict} para todas las profesiones
    result_file_map: {result_name: recipe_file_path}
    """
    items: list = []

    for market_name, group in market_groups.items():
        for name in group.get("results", []):
            recipe    = craftable_map.get(name, {})
            has_price = any(recipe.get(f"unit_selling_price_{s}", 0) > 0 for s in SIZES)
            items.append(ScanItem(
                name              = name,
                market            = market_name,
                category          = recipe.get("category", ""),
                type              = "result",
                prices_updated_at = recipe.get("prices_updated_at"),
                has_price         = has_price,
                recipe_file       = result_file_map.get(name),
            ))

        for name in group.get("ingredients", []):
            val               = item_lookup.get(name)
            market, category  = val if val else (market_name, "")
            entry             = markets.get(market, {}).get("data", {}).get(category, {}).get(name, {})
            has_price         = any(entry.get(s, 0) > 0 for s in SIZES)
            items.append(ScanItem(
                name              = name,
                market            = market,
                category          = category,
                type              = "ingredient",
                prices_updated_at = entry.get("prices_updated_at"),
                has_price         = has_price,
            ))

    return items
