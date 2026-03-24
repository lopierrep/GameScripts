"""
Cliente de la API del Almanax de Dofus.
https://api.dofusdu.de/dofus3/v1/es/almanax
"""
import json
import urllib.request
from datetime import date

from .models import API_BASE


def fetch_almanax(start: date, end: date) -> list[dict]:
    """Obtiene los días del Almanax entre start y end (inclusive)."""
    url = f"{API_BASE}?range[from]={start.isoformat()}&range[to]={end.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "AlmanaxTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_entry(entry: dict) -> dict:
    """Convierte una entrada raw de la API al formato interno."""
    return dict(
        date       = entry["date"],
        item       = entry["tribute"]["item"]["name"],
        qty        = entry["tribute"]["quantity"],
        kamas      = entry["reward_kamas"],
        price      = 0,
        cost       = 0,
        profit     = None,
        guijarros  = 0,
        bonus      = entry["bonus"]["description"],
        bonus_type = entry["bonus"]["type"]["name"],
        subtype    = entry["tribute"]["item"].get("subtype", "resources"),
        price_dict = {},
    )