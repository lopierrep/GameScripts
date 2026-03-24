"""Shim de compatibilidad — el código real está en shared/market/search_item_prices.py."""
import sys
import os

_DOFUS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

import shared.market.search_item_prices as _m
sys.modules[__name__] = _m
