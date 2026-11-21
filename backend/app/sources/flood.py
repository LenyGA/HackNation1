"""Flood hazard at the parcel: ISOK flood hazard maps (Wody Polskie, MZP, 2nd planning cycle) and areas at
risk of
groundwater flooding (PIG-PIB, "podtopienia").

- MZP: WMS GetFeatureInfo (text/plain, one block per scenario) on layer NZ.Fluvial at a few points of the
  parcel
  (centroid and points along its edge), in parallel. Scenario return periods: 10 years (Q10 %), 100 years
  (Q1 %), 500 years (Q0,2 %). The parcel is "in a zone" when any checked point is. The full polygons (WFS,
  JSON)
  are megabytes per river reach, so they are never downloaded.
- Historical floods (WORP, NZ.ObservedEvent): the service did not answer within 20 s in tests on
  2026-11-21, so it
  is queried with a short timeout and reported as "not checked" when it fails.
- Groundwater flooding: PIG-PIB ArcGIS REST point query (coarse regional polygons).

The maps describe hazard "now" (maps of 2020–2022); they do not depend on the analysis date.
"""

import asyncio
import logging
import re
from datetime import date, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.cache import get_cache
from app.core.http import request
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
from app.sources.base import (
    METRIC_CRS,
    geometry_hash,
    missing,
    parcel_shape,
    result,
    to_crs,
    unc,
    within_budget,
)

log = logging.getLogger(__name__)

NAME = "flood"
MZP_WMS = "https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS"
MZP_LAYER = "NZ.Fluvial"
WORP_WMS = "https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_WORP_WMS"
WORP_LAYER = "NZ.ObservedEvent"
PODTOPIENIA_URL = (
    "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/podtopienia/MapServer/0/query"
)
SOURCE = (
    "Wody Polskie (KZGW), mapy zagrożenia powodziowego ISOK (II cykl), usługa WMS "
    "https://wody.isok.gov.pl/; PIG-PIB, obszary zagrożone podtopieniami, https://cbdgmapa.pgi.gov.pl/"
)
LICENSE = "Dane publiczne (INSPIRE) Wód Polskich i PIG-PIB, bezpłatne, z podaniem źródła"
TIMEOUT_S = 9.0
WORP_TIMEOUT_S = 5.0
BUDGET_S = 11.0
CACHE_TTL = timedelta(days=30)
POINT_BOX_M = 50.0
EDGE_INSET_M = 5.0
BOUNDARY_STEP_M = 50.0
MAX_EDGE_POINTS = 11  # + centroid: at most 12 WMS queries per parcel, in parallel

ZoneId = Literal["q10", "q1", "q02"]
RETURN_PERIOD_ZONE: dict[int, ZoneId] = {10: "q10", 100: "q1", 500: "q02"}
_RETURN_PERIOD = re.compile(r"loo_ql_returnperiod\s*=\s*(\d+)")


class FloodData(BaseModel):
    zones: dict[str, bool]  # q10 / q1 / q02 → parcel touches the zone
    points_checked: int
    points_total: int = 0  # sample points asked; fewer answered → the "no zone" result is only partial
    historical: bool | None  # None = the historical-flood service did not answer
    groundwater_flooding: bool | None
    groundwater_flooding_name: str | None = None


def sample_points(parcel_2180: BaseGeometry) -> list[Point]:
    """Centroid plus points along the parcel edge (5 m inside it), every BOUNDARY_STEP_M or sparser.

    A flood zone usually enters a parcel from one side (the river), so the edge matters more than the middle.
    """
    c = parcel_2180.centroid
    pts = [c if parcel_2180.contains(c) else parcel_2180.representative_point()]
    inner = parcel_2180.buffer(-EDGE_INSET_M)
    ring_src = inner if not inner.is_empty and inner.area > 0 else parcel_2180
    polys = list(ring_src.geoms) if hasattr(ring_src, "geoms") else [ring_src]
    rings = [p.exterior for p in polys if isinstance(p, Polygon)]
    perimeter = sum(r.length for r in rings)
    if perimeter <= 0:
        return pts
    step = max(BOUNDARY_STEP_M, perimeter / MAX_EDGE_POINTS)
    for ring in rings:
        n = max(1, int(ring.length // step))
        for i in range(n):
            if len(pts) > MAX_EDGE_POINTS:
                return pts
            pts.append(ring.interpolate(i * ring.length / n))
    return pts


def parse_return_periods(text: str) -> set[int]:
    return {int(m) for m in _RETURN_PERIOD.findall(text)}


async def _feature_info(url: str, layer: str, p: Point, timeout_s: float) -> str:
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "SRS": f"EPSG:{METRIC_CRS}",
        "BBOX": f"{p.x - POINT_BOX_M},{p.y - POINT_BOX_M},{p.x + POINT_BOX_M},{p.y + POINT_BOX_M}",
        "WIDTH": "101",
        "HEIGHT": "101",
        "X": "50",
        "Y": "50",
        "INFO_FORMAT": "text/plain",
        "FEATURE_COUNT": "10",
        "STYLES": "",
    }
    resp = await request("GET", url, params=params, timeout_s=timeout_s, retries=0)
    resp.raise_for_status()
    if "ServiceException" in resp.text:
        raise httpx.HTTPError("WMS service exception")
    return resp.text


async def _historical(p: Point) -> bool | None:
    try:
        text = await _feature_info(WORP_WMS, WORP_LAYER, p, WORP_TIMEOUT_S)
    except httpx.HTTPError:
        return None
    if "no features were found" in text:
        return False
    return "=" in text  # any attribute block means an observed flood event at the point


async def _podtopienia(p: Point) -> tuple[bool | None, str | None]:
    params = {
        "geometry": f"{p.x},{p.y}",
        "geometryType": "esriGeometryPoint",
        "inSR": str(METRIC_CRS),
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        resp = await request("GET", PODTOPIENIA_URL, params=params, timeout_s=6.0, retries=0)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError):
        return None, None
    if "features" not in data:
        return None, None
    feats = data["features"]
    if not feats:
        return False, None
    attrs = feats[0].get("attributes", {})
    name = next((v for k, v in attrs.items() if isinstance(v, str) and "podtop" in v.lower()), None)
    return True, name


async def _fetch(parcel: Parcel) -> SourceResult[FloodData]:
    cache = get_cache()
    params = {"geom": geometry_hash(parcel.geometry), "v": 1}
    cached = cache.get(NAME, params)
    if cached is not None:
        data = FloodData.model_validate(cached)
    else:
        geom = to_crs(parcel_shape(parcel), METRIC_CRS)
        points = sample_points(geom)
        tasks = [_feature_info(MZP_WMS, MZP_LAYER, p, TIMEOUT_S) for p in points]
        mzp, hist, (podt, podt_name) = await asyncio.gather(
            asyncio.gather(*tasks, return_exceptions=True), _historical(points[0]), _podtopienia(points[0])
        )
        answered = [r for r in mzp if isinstance(r, str)]
        if not answered:
            return missing(
                NAME,
                source=SOURCE,
                license=LICENSE,
                message_pl="Usługa map zagrożenia powodziowego (Wody Polskie) nie odpowiedziała na czas. "
                "Zagrożenia powodzią nie sprawdzono.",
            )
        periods: set[int] = set()
        for text in answered:
            periods |= parse_return_periods(text)
        zones = {zone: rp in periods for rp, zone in RETURN_PERIOD_ZONE.items()}
        # A 10-year zone lies inside the 100- and 500-year ones.
        if zones["q10"]:
            zones["q1"] = zones["q02"] = True
        if zones["q1"]:
            zones["q02"] = True
        data = FloodData(
            zones=zones,
            points_checked=len(answered),
            points_total=len(points),
            historical=hist,
            groundwater_flooding=podt,
            groundwater_flooding_name=podt_name,
        )
        if len(answered) == len(points):
            cache.set(NAME, params, data.model_dump(mode="json"), CACHE_TTL)
    partial = data.points_checked < max(data.points_total, 1)
    notes: list[str] = []
    if partial:
        notes.append(
            f"Sprawdzono {data.points_checked} z {data.points_total} punktów działki — "
            "reszta nie odpowiedziała."
        )
    if data.historical is None:
        notes.append("Mapa powodzi historycznych nie odpowiedziała — tego nie sprawdzono.")
    return result(
        NAME,
        SourceStatus.DEGRADED if notes and not any(data.zones.values()) else SourceStatus.OK,
        data,
        source=SOURCE,
        license=LICENSE,
        message_pl=" ".join(notes) or None,
        uncertainty=unc(
            Confidence.MEDIUM if partial else Confidence.HIGH,
            "Mapy zagrożenia powodziowego z modelu hydraulicznego dla większych rzek; nie obejmują "
            "małych cieków i lokalnych podtopień po ulewach.",
        ),
    )


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[FloodData]:
    """Flood maps are static (2nd planning cycle); analysis_date keeps the common source signature."""
    return await within_budget(
        NAME,
        _fetch(parcel),
        BUDGET_S,
        lambda: missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            message_pl=(
                "Mapy zagrożenia powodziowego nie odpowiedziały na czas. Zagrożenia powodzią nie sprawdzono."
            ),
        ),
    )
