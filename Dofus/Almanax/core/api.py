"""
Cliente de la API del Almanax de Dofus.
https://api.dofusdu.de/dofus3/v1/es/almanax
"""
import json
import urllib.request
import urllib.error
from datetime import date

from Almanax.config.config import API_BASE, ALMANAX_FILE, ITEMS_API_BASE, USER_AGENT, API_TIMEOUT, API_TIMEOUT_RESOLVE


def fetch_almanax(start: date, end: date) -> list[dict]:
    """Obtiene los días del Almanax entre start y end (inclusive)."""
    url = f"{API_BASE}?range[from]={start.isoformat()}&range[to]={end.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_subtype(ankama_id: int) -> str:
    """Determina la categoría correcta del item probando los 3 endpoints."""
    for category in ("resources", "consumables", "equipment"):
        url = f"{ITEMS_API_BASE}/{category}/{ankama_id}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            urllib.request.urlopen(req, timeout=API_TIMEOUT_RESOLVE)
            return category
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        except Exception:
            continue
    return "resources"


def save_almanax(entries: list[dict]):
    """Guarda los campos relevantes de los días del Almanax en disco."""
    ALMANAX_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields = ("date", "item", "qty", "kamas", "bonus", "bonus_type", "subtype", "ankama_id", "market", "category")
    data   = [{k: e[k] for k in fields} for e in entries]
    with open(ALMANAX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_almanax() -> list[dict]:
    """Carga los datos del Almanax desde disco y añade campos calculados vacíos."""
    if not ALMANAX_FILE.exists():
        return []
    try:
        with open(ALMANAX_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []
    return [dict(
        date=e["date"], item=e["item"], qty=e["qty"], kamas=e["kamas"],
        bonus=e["bonus"], bonus_type=e["bonus_type"], subtype=e["subtype"],
        ankama_id=e.get("ankama_id", 0),
        market=e.get("market", ""), category=e.get("category", ""),
        price=0, cost=0, profit=None, guijarros=0, price_dict={},
    ) for e in raw]


def parse_entry(entry: dict, subtype: str | None = None) -> dict:
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
        ankama_id  = entry["tribute"]["item"]["ankama_id"],
        subtype    = subtype or entry["tribute"]["item"].get("subtype", "resources"),
        market     = "",
        category   = "",
        price_dict = {},
    )
