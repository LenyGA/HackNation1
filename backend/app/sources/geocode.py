"""GUGiK address search (Usługa Uniwersalnego Geokodowania, UUG): address → point to find a parcel (M8.7).

https://services.gugik.gov.pl/uug/?request=GetAddress&address=<text> answers JSON with `type` (address, street
or city) and `results` keyed "1", "2", …; each result has `x` (easting) and `y` (northing) in EPSG:2180 and
`jednostka` = "{Polska,voivodeship,county,commune}". The service expects "City, Street Number" or, in a
village without streets, "Village Number"; a query with no match comes back with `results: null`.
"""

import logging
import re
from datetime import timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel
from shapely.geometry import Point

from app.core.cache import get_cache
from app.core.http import request
from app.sources.base import METRIC_CRS, SourceError, to_crs

log = logging.getLogger(__name__)

NAME = "uug"
URL = "https://services.gugik.gov.pl/uug/"
SOURCE = "GUGiK, Usługa Uniwersalnego Geokodowania (punkty adresowe PRG), https://services.gugik.gov.pl/uug/"
TIMEOUT_S = 5.0
CACHE_TTL = timedelta(days=7)
# The service now and then answers "returned objects: 0" for a query it can match; an empty answer is
# therefore kept only briefly.
EMPTY_CACHE_TTL = timedelta(hours=1)
MAX_RESULTS = 8

MSG_UNAVAILABLE = (
    "Wyszukiwarka adresów (GUGiK) chwilowo nie odpowiada. Wpisz numer działki albo znajdź ją na mapie."
)
MSG_BAD_RESPONSE = "Wyszukiwarka adresów (GUGiK) zwróciła nieczytelną odpowiedź. Spróbuj ponownie za chwilę."

PlaceKind = Literal["address", "street", "city"]


class Place(BaseModel):
    kind: PlaceKind
    label_pl: str
    detail_pl: str
    lat: float
    lon: float


class GeocodeServiceError(SourceError):
    """The address service did not answer or answered nonsense."""


def _units(raw: Any) -> list[str]:
    """'{Polska,łódzkie,"łódzki wschodni",Nowosolna}' → ['łódzkie', 'łódzki wschodni', 'Nowosolna']."""
    # Street results carry "{City,TERYT}" instead: no administrative units to show.
    if not isinstance(raw, str) or not raw.startswith("{Polska"):
        return []
    parts = [p.strip().strip('"') for p in raw.strip("{}").split(",")]
    return [p for p in parts if p and p != "Polska"]


def _detail(r: dict[str, Any]) -> str:
    units = _units(r.get("jednostka"))
    voiv = r.get("voivodeship") or (units[0] if units else None)
    county = r.get("county") or (units[1] if len(units) > 1 else None)
    commune = r.get("commune") or (units[2] if len(units) > 2 else None)
    out = []
    if commune:
        out.append(f"gm. {commune}")
    if county and county != commune:
        out.append(f"pow. {county}")
    if voiv:
        out.append(f"woj. {voiv}")
    return ", ".join(out)


def _label(kind: str, r: dict[str, Any]) -> str:
    city = str(r.get("city") or "").strip()
    street = str(r.get("street") or "").strip()
    number = str(r.get("number") or "").strip()
    if kind == "address":
        return f"{city}, {street} {number}".strip() if street else f"{city} {number}".strip()
    if kind == "street":
        return f"{city}, {street}".strip(", ")
    return city


def parse(body: Any) -> list[Place]:
    if not isinstance(body, dict):
        raise GeocodeServiceError(MSG_BAD_RESPONSE)
    kind = body.get("type")
    results = body.get("results")
    if kind not in ("address", "street", "city") or not results:
        return []
    if not isinstance(results, dict):
        raise GeocodeServiceError(MSG_BAD_RESPONSE)
    places: list[Place] = []
    seen: set[tuple[str, str]] = set()
    for key in sorted(results, key=lambda k: int(k) if str(k).isdigit() else 0):
        r = results[key]
        try:
            x, y = float(r["x"]), float(r["y"])
        except (KeyError, TypeError, ValueError):
            continue
        pt = to_crs(Point(x, y), 4326, METRIC_CRS)
        label, detail = _label(kind, r), _detail(r)
        if not label or (label, detail) in seen:
            continue
        seen.add((label, detail))
        lat, lon = round(pt.y, 6), round(pt.x, 6)
        places.append(Place(kind=kind, label_pl=label, detail_pl=detail, lat=lat, lon=lon))
        if len(places) >= MAX_RESULTS:
            break
    return places


def _variants(q: str) -> list[str]:
    """The query as typed; without a comma also "City, Street Number" (the service needs the comma)."""
    q = re.sub(r"\s+", " ", q).strip()
    out = [q]
    if "," not in q:
        m = re.match(r"^(\S+)\s+(\D.*\s\d\S*)$", q)
        if m:
            out.append(f"{m.group(1)}, {m.group(2)}")
    return out


async def _fetch(q: str) -> list[dict[str, Any]]:
    try:
        resp = await request(
            "GET", URL, timeout_s=TIMEOUT_S, retries=0, params={"request": "GetAddress", "address": q}
        )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.info("uug failed: %s", type(exc).__name__)
        raise GeocodeServiceError(MSG_UNAVAILABLE) from exc
    return [p.model_dump() for p in parse(body)]


async def search(q: str) -> list[Place]:
    """Places matching the text, best first; an empty list when nothing matches."""
    cache = get_cache()
    for variant in _variants(q):
        params = {"q": variant.lower()}
        found = cache.get(NAME, params)
        if found is None:
            found = await _fetch(variant)
            cache.set(NAME, params, found, CACHE_TTL if found else EMPTY_CACHE_TTL)
        if found:
            return [Place.model_validate(p) for p in found]
    return []
