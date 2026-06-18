"""
Helper para añadir edición manual de precios de ingredientes con click derecho.

Engancha <Button-3> en un Treeview y al disparar:
    1. Resuelve el item de la fila vía callback `get_item_for_row(iid)`.
    2. Abre PriceEditDialog con los precios actuales.
    3. Al confirmar, guarda en materials_prices.json y llama `on_saved`.

Usable por cualquier proyecto cuyo Treeview muestre items presentes en
materials_prices.json (Almanax, Ganadero, etc.).
"""
from typing import Callable

from shared.market.prices import save_ingredient_lot_prices
from shared.ui.price_edit_dialog import PriceEditDialog


def attach_ingredient_price_edit(
    tree,
    root,
    *,
    prices_file,
    get_item_for_row: Callable,
    on_saved: Callable | None = None,
):
    """
    tree:             ttk.Treeview a bindear.
    root:             widget root para el dialog.
    prices_file:      ruta a materials_prices.json (cada proyecto la suya).
    get_item_for_row: fn(iid) → {"name": str, "label": str,
                                 "lot_prices": {"1": unit, "10": unit, ...}} | None.
    on_saved:         fn(name) opcional, llamado tras guardar OK.
    """
    def _on_right_click(event):
        iid = tree.identify_row(event.y)
        if not iid:
            return
        info = get_item_for_row(iid)
        if not info:
            return

        items = [{
            "label":  info["label"],
            "name":   info["name"],
            "kind":   "ingredient",
            "prices": info.get("lot_prices") or {},
        }]

        def _on_confirm(prices_by_name):
            saved_any = False
            for name, payload in prices_by_name.items():
                payload.pop("_kind", None)
                if save_ingredient_lot_prices(name, payload, prices_file):
                    saved_any = True
            if saved_any and on_saved:
                on_saved(info["name"])

        PriceEditDialog(
            root,
            title=f"Precio: {info['label']}",
            items=items,
            on_confirm=_on_confirm,
        )

    tree.bind("<Button-3>", _on_right_click)
