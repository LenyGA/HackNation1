"""Water and landscape features around the parcel from OpenStreetMap (Overpass API).

Within SEARCH_RADIUS_M of the parcel: ditches and drains, watercourses, water bodies and ponds, wetlands,
woods and tree rows. Returns GeoJSON geometries, the distance from the parcel to the nearest feature of each
type and the length of ditches running along the parcel boundary (≤ BOUNDARY_BUFFER_M).

"Nothing in OSM" (status ok, counts 0) is distinguished from "the service did not answer" (status missing).
OSM completeness varies, which is always stated in the uncertainty.
"""

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel
from shapely.geometry import LineString, Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from app.core.cache import get_cache
from app.core.http import request
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
from app.sources.base import (
    METRIC_CRS,
    SourceError,
    geometry_hash,
    missing,
    parcel_shape,
    result,
    to_crs,
    unc,
    within_budget,
)

log = logging.getLogger(__name__)

NAME = "hydro"
# Public Overpass instances (https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances).
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
SOURCE = "OpenStreetMap, współtwórcy OSM, usługa Overpass API, https://www.openstreetmap.org/"
LICENSE = "ODbL 1.0 (© współtwórcy OpenStreetMap)"
TIMEOUT_S = 7.0  # per request; one retry round fits in BUDGET_S
BUDGET_S = 15.0
ATTEMPTS = 2
# After every mirror failed, Overpass is treated as down for this long (process-wide): the next analyses
# fall back to WorldCover at once instead of each waiting the whole budget (review M1: 15 s per analysis).
DOWN_COOLDOWN_S = 300.0
_down_until = 0.0


def _mark_down() -> None:
    global _down_until
    _down_until = time.monotonic() + DOWN_COOLDOWN_S


def _is_down() -> bool:
    return time.monotonic() < _down_until


SEARCH_RADIUS_M = 1000
BOUNDARY_BUFFER_M = 30.0
MAX_FEATURES = 400
# Day-long cache: OSM changes slowly, and the map is "as of now" anyway (not historical).
CACHE_TTL_DAYS = 1

FeatureKind = Literal["ditch", "watercourse", "water_body", "wetland", "trees"]
KINDS: tuple[FeatureKind, ...] = ("ditch", "watercourse", "water_body", "wetland", "trees")
AREA_KINDS = {"water_body", "wetland", "trees"}


class HydroFeature(BaseModel):
    kind: FeatureKind
    osm_id: str
    name: str | None
    geometry: dict[str, Any]  # GeoJSON, EPSG:4326
    distance_m: float


class HydroData(BaseModel):
    radius_m: int
    features: list[HydroFeature]
    counts: dict[str, int]
    nearest_m: dict[str, float | None]
    ditch_length_along_boundary_m: float
    truncated: bool


def build_query(lat: float, lon: float, radius_m: int) -> str:
    a = f"(around:{radius_m},{lat:.6f},{lon:.6f})"
    return (
        "[out:json][timeout:6];("  # below TIMEOUT_S: Overpass answers before we give up
        f'way["waterway"~"^(ditch|drain|canal|stream|river|brook)$"]{a};'
        f'way["natural"~"^(water|wetland|wood|tree_row)$"]{a};'
        f'relation["natural"~"^(water|wetland|wood)$"]{a};'
        f'way["landuse"~"^(forest|reservoir|basin)$"]{a};'
        f'relation["landuse"="forest"]{a};'
        ");out geom;"
    )


def classify(tags: dict[str, str]) -> FeatureKind | None:
    ww = tags.get("waterway")
    if ww in ("ditch", "drain"):
        return "ditch"
    if ww in ("canal", "stream", "river", "brook"):
        return "watercourse"
    nat, lu = tags.get("natural"), tags.get("landuse")
    if nat == "water" or lu in ("reservoir", "basin"):
        return "water_body"
    if nat == "wetland":
        return "wetland"
    if nat in ("wood", "tree_row") or lu == "forest":
        return "trees"
    return None


def _way_geom(coords: list[tuple[float, float]], as_area: bool) -> BaseGeometry | None:
    if len(coords) < 2:
        return None
    if as_area and len(coords) >= 4 and coords[0] == coords[-1]:
        poly = Polygon(coords)
        return poly if poly.is_valid else poly.buffer(0)
    return LineString(coords)


def element_geometries(el: dict[str, Any], kind: FeatureKind) -> list[BaseGeometry]:
    as_area = kind in AREA_KINDS and el.get("tags", {}).get("natural") != "tree_row"
    if el.get("type") == "way":
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry") or []]
        g = _way_geom(coords, as_area)
        return [g] if g is not None else []
    outer: list[LineString] = []
    inner: list[LineString] = []
    for m in el.get("members") or []:
        coords = [(p["lon"], p["lat"]) for p in m.get("geometry") or []]
        if m.get("type") != "way" or len(coords) < 2:
            continue
        if m.get("role") in ("outer", ""):
            outer.append(LineString(coords))
        elif m.get("role") == "inner":
            inner.append(LineString(coords))
    if not outer:
        return []
    if not as_area:
        return list(outer)
    # Multipolygon: outer rings may be split over several ways, inner rings are holes (e.g. a field in a
    # forest clearing must not be "inside the forest").
    shell = unary_union(list(polygonize(unary_union(outer))))
    if shell.is_empty:
        return list(outer)
    if inner:
        holes = unary_union(list(polygonize(unary_union(inner))))
        if not holes.is_empty:
            shell = shell.difference(holes)
    return [shell] if not shell.is_empty else []


def summarise(elements: list[dict[str, Any]], parcel_wgs84: BaseGeometry) -> HydroData:
    """Pure: classify elements, measure distances in EPSG:2180."""
    parcel_m = to_crs(parcel_wgs84, METRIC_CRS)
    boundary_zone = parcel_m.boundary.buffer(BOUNDARY_BUFFER_M)
    features: list[HydroFeature] = []
    nearest: dict[str, float | None] = dict.fromkeys(KINDS)
    counts: dict[str, int] = dict.fromkeys(KINDS, 0)
    ditch_len = 0.0
    seen: set[str] = set()
    for el in elements:
        kind = classify(el.get("tags") or {})
        if kind is None:
            continue
        osm_id = f"{el.get('type')}/{el.get('id')}"
        if osm_id in seen:
            continue
        seen.add(osm_id)
        geoms = element_geometries(el, kind)
        if not geoms:
            continue
        counts[kind] += 1
        for g in geoms:
            gm = to_crs(g, METRIC_CRS)
            dist = round(float(gm.distance(parcel_m)), 1)
            prev = nearest[kind]
            nearest[kind] = dist if prev is None else min(prev, dist)
            if kind == "ditch":
                ditch_len += float(gm.intersection(boundary_zone).length)
            features.append(
                HydroFeature(
                    kind=kind,
                    osm_id=osm_id,
                    name=(el.get("tags") or {}).get("name"),
                    geometry=dict(mapping(g)),
                    distance_m=dist,
                )
            )
    features.sort(key=lambda f: f.distance_m)
    truncated = len(features) > MAX_FEATURES
    return HydroData(
        radius_m=SEARCH_RADIUS_M,
        features=features[:MAX_FEATURES],
        counts=counts,
        nearest_m=nearest,
        ditch_length_along_boundary_m=round(ditch_len, 0),
        truncated=truncated,
    )


async def _query_server(url: str, query: str) -> list[dict[str, Any]]:
    try:
        resp = await request("POST", url, data={"data": query}, timeout_s=TIMEOUT_S, retries=0)
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"Overpass {url} failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict) or "elements" not in payload:
        raise SourceError("Overpass returned no elements key")
    # Overpass reports runtime errors (e.g. timeout) in "remark" with partial or empty elements.
    remark = str(payload.get("remark") or "")
    if "error" in remark.lower() or "timed out" in remark.lower():
        raise SourceError(f"Overpass remark: {remark[:120]}")
    return list(payload["elements"])


def _rotated(servers: list[str]) -> list[str]:
    """Servers in a rotating order. All mirrors are raced at once, so this only spreads which request is
    sent first; the robustness comes from the race and the retry round (Q4)."""
    global _rotation
    _rotation = (_rotation + 1) % len(servers)
    return servers[_rotation:] + servers[:_rotation]


_rotation = 0


async def _race(query: str, servers: list[str]) -> list[dict[str, Any]]:
    """Ask all servers at once and return the first successful answer."""
    tasks = [asyncio.create_task(_query_server(u, query)) for u in servers]
    try:
        for fut in asyncio.as_completed(tasks):
            try:
                return await fut
            except SourceError as exc:
                log.info("%s", exc)
        raise SourceError("Serwis danych o ciekach i rowach (OpenStreetMap) nie odpowiedział.")
    finally:
        for t in tasks:
            t.cancel()


async def query_first(query: str, attempts: int = ATTEMPTS) -> list[dict[str, Any]]:
    """Race all mirrors; if every one fails (fast errors or TIMEOUT_S), try once more within the budget."""
    last: SourceError | None = None
    for _ in range(attempts):
        try:
            return await _race(query, _rotated(SERVERS))
        except SourceError as exc:
            last = exc
    assert last is not None
    raise last


def _down_result(message_pl: str) -> SourceResult[HydroData]:
    return missing(NAME, source=SOURCE, license=LICENSE, message_pl=message_pl)


def _timed_out() -> SourceResult[HydroData]:
    _mark_down()
    return _down_result("Serwis danych o ciekach i rowach (OpenStreetMap) nie odpowiedział na czas.")


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[HydroData]:
    return await within_budget(
        NAME,
        _fetch(parcel),
        BUDGET_S,
        _timed_out,
    )


async def _fetch(parcel: Parcel) -> SourceResult[HydroData]:
    """OSM is the current map state (no history), so analysis_date is not used; noted in the uncertainty."""
    geom = parcel_shape(parcel)
    # Radius counted from the parcel edge: add the centroid-to-farthest-vertex distance.
    parcel_m = to_crs(geom, METRIC_CRS)
    centroid_m = parcel_m.centroid
    reach = max(centroid_m.distance(p) for p in _vertices(parcel_m))
    radius = int(SEARCH_RADIUS_M + reach)
    cache = get_cache()
    params = {"geom": geometry_hash(parcel.geometry), "radius": radius}
    cached = cache.get(NAME, params)
    if cached is not None:
        elements = cached
    elif _is_down():
        return _down_result(
            "Serwis danych o ciekach i rowach (OpenStreetMap) nie odpowiadał w ostatnich minutach."
        )
    else:
        try:
            elements = await query_first(build_query(parcel.centroid_lat, parcel.centroid_lon, radius))
        except SourceError as exc:
            _mark_down()
            return _down_result(exc.message_pl)
        cache.set(NAME, params, elements, timedelta(days=CACHE_TTL_DAYS))

    # Geometry work on hundreds of features is CPU-bound: keep it off the event loop.
    data = await asyncio.to_thread(summarise, elements, geom)
    found = sum(data.counts.values())
    messages = []
    if found == 0:
        messages.append(
            f"Na mapie OpenStreetMap w promieniu {SEARCH_RADIUS_M} m od działki nie ma rowów, cieków, "
            "zbiorników, mokradeł ani zadrzewień. Mapa może być niepełna."
        )
    return result(
        NAME,
        SourceStatus.OK,
        data,
        source=SOURCE,
        license=LICENSE,
        uncertainty=unc(
            Confidence.MEDIUM,
            "Mapa OpenStreetMap tworzona przez wolontariuszy bywa niepełna (zwłaszcza małe rowy i oczka); "
            "pokazuje stan obecny, nie z dnia analizy.",
        ),
        message_pl=" ".join(messages) or None,
    )


def _vertices(geom: BaseGeometry) -> list[Point]:
    hull = geom.convex_hull
    coords = list(hull.exterior.coords) if hasattr(hull, "exterior") else list(hull.coords)
    return [Point(c) for c in coords]
