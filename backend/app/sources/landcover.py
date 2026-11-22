"""Land cover shares on the parcel from ESA WorldCover 10 m (2021, v200), Planetary Computer COGs.

Windowed read of the parcel bbox only; tiles are 3° × 3° in EPSG:4326 and every intersecting tile is read, so
parcels on a tile boundary are handled. This is a single-year map (2021), which goes to report limitations.

The same read also covers a ring of SURROUNDINGS_RADIUS_M around the parcel: shares of trees, open water,
wetlands and built-up land and the distance from the parcel edge to the nearest pixel of each. When the OSM
map (sources/hydro.py) does not answer, these replace it for trees, ponds and wetlands (only ditches are then
unknown, Q4).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import shapely
from pydantic import BaseModel
from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.geometry.base import BaseGeometry

from app.core.cache import get_cache
from app.core.models import Confidence, Parcel, Period, SourceResult, SourceStatus
from app.sources import planetary
from app.sources.base import (
    METRIC_CRS,
    SourceError,
    geometry_hash,
    missing,
    parcel_shape,
    result,
    to_crs,
    unc,
)
from app.sources.sentinel2 import parcel_mask

log = logging.getLogger(__name__)

NAME = "landcover"
COLLECTION = "esa-worldcover"
SOURCE = (
    "ESA WorldCover 10 m {year} {version}, katalog Microsoft Planetary Computer, https://esa-worldcover.org/"
)
LICENSE = "CC BY 4.0"
# Available map editions. The edition not later than analysis_date is preferred (no future data);
# for earlier dates the oldest edition is used and the mismatch is stated.
MAP_VERSIONS: dict[int, str] = {2020: "v100", 2021: "v200"}
TIMEOUT_S = 10.0
# Below this share of cropland + grassland the parcel is flagged as possibly not agricultural.
MIN_AGRI_SHARE_PCT = 50.0
SURROUNDINGS_RADIUS_M = 500.0
SURROUNDING_KINDS = ("trees", "water", "wetland", "built_up")
CACHE_VERSION = 2  # v2: parcel counts + surroundings ring

CLASSES: dict[int, str] = {
    10: "trees",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare",
    70: "snow_ice",
    80: "water",
    90: "wetland",
    95: "mangroves",
    100: "moss_lichen",
}


class Surroundings(BaseModel):
    """Land cover in a ring of `radius_m` around the parcel (parcel itself excluded)."""

    radius_m: float
    pixels: int
    shares_pct: dict[str, float]  # trees, water, wetland, built_up: % of ring pixels
    nearest_m: dict[str, float | None]  # distance from the parcel edge to the nearest pixel centre


class LandCoverData(BaseModel):
    map_year: int
    pixels: int
    shares_pct: dict[str, float]  # class name -> % of parcel pixels (only classes present)
    cropland_pct: float
    grassland_pct: float
    trees_pct: float
    built_up_pct: float
    looks_agricultural: bool
    surroundings: Surroundings | None = None


def count_classes(arr: np.ndarray, inside: np.ndarray) -> dict[int, int]:
    vals, counts = np.unique(arr[inside], return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, counts, strict=True) if int(v) in CLASSES}


def map_year_for(analysis_date: date) -> int:
    """Newest edition whose year ended before analysis_date; otherwise the oldest edition."""
    eligible = [y for y in MAP_VERSIONS if date(y, 12, 31) < analysis_date]
    return max(eligible) if eligible else min(MAP_VERSIONS)


def shares(counts: dict[int, int], map_year: int) -> LandCoverData | None:
    total = sum(counts.values())
    if total == 0:
        return None
    pct = {CLASSES[k]: round(100 * v / total, 1) for k, v in sorted(counts.items())}
    crop, grass = pct.get("cropland", 0.0), pct.get("grassland", 0.0)
    return LandCoverData(
        map_year=map_year,
        pixels=total,
        shares_pct=pct,
        cropland_pct=crop,
        grassland_pct=grass,
        trees_pct=pct.get("trees", 0.0),
        built_up_pct=pct.get("built_up", 0.0),
        looks_agricultural=crop + grass >= MIN_AGRI_SHARE_PCT,
    )


@dataclass
class _Counts:
    parcel: dict[int, int]
    ring: dict[int, int]
    nearest_m: dict[str, float | None]


def _ring_bounds(geom: BaseGeometry) -> tuple[BaseGeometry, BaseGeometry, tuple[float, float, float, float]]:
    """(parcel in metres, ring around it in WGS84, WGS84 bbox of parcel + ring)."""
    metric = to_crs(geom, METRIC_CRS)
    ring = to_crs(metric.buffer(SURROUNDINGS_RADIUS_M).difference(metric), 4326, src_crs=METRIC_CRS)
    return metric, ring, ring.bounds


def surroundings_from(
    arr: np.ndarray, transform: Any, ring: BaseGeometry, parcel_m: BaseGeometry
) -> tuple[dict[int, int], dict[str, float | None]]:
    """Pure: class counts inside the ring and, per kind, distance (m) from the parcel to the nearest pixel."""
    inside = parcel_mask(ring, arr.shape, transform)
    counts = count_classes(arr, inside)
    to_metric = Transformer.from_crs(4326, METRIC_CRS, always_xy=True)
    nearest: dict[str, float | None] = {}
    codes = {name: code for code, name in CLASSES.items()}
    for kind in SURROUNDING_KINDS:
        rows, cols = np.nonzero(inside & (arr == codes[kind]))
        if rows.size == 0:
            nearest[kind] = None
            continue
        xs = transform.c + (cols + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e
        mx, my = to_metric.transform(xs, ys)
        dist = shapely.distance(parcel_m, shapely.points(np.column_stack([mx, my])))
        nearest[kind] = round(float(np.min(dist)), 0)
    return counts, nearest


def read_items(items: list[dict[str, Any]], token: str, geom: BaseGeometry) -> _Counts:
    """Blocking: count classes of pixels inside the parcel and in the ring around it over all tiles."""
    counts: dict[int, int] = {}
    ring_counts: dict[int, int] = {}
    nearest: dict[str, float | None] = dict.fromkeys(SURROUNDING_KINDS)
    parcel_m, ring, (minx, miny, maxx, maxy) = _ring_bounds(geom)
    pad = 0.0002  # ~15-20 m
    for item in items:
        href = item.get("assets", {}).get("map", {}).get("href")
        if not href:
            continue
        try:
            win = planetary.read_window(
                planetary.sign(href, token), (minx - pad, miny - pad, maxx + pad, maxy + pad)
            )
        except SourceError:
            continue
        if win.array.size == 0:
            continue
        inside = parcel_mask(geom, win.array.shape, win.transform)
        for k, v in count_classes(win.array, inside).items():
            counts[k] = counts.get(k, 0) + v
        rc, rn = surroundings_from(win.array, win.transform, ring, parcel_m)
        for k, v in rc.items():
            ring_counts[k] = ring_counts.get(k, 0) + v
        for kind, d in rn.items():
            if d is not None and (nearest[kind] is None or d < (nearest[kind] or 0)):
                nearest[kind] = d
    return _Counts(counts, ring_counts, nearest)


def surroundings(ring_counts: dict[int, int], nearest: dict[str, float | None]) -> Surroundings | None:
    total = sum(ring_counts.values())
    if total == 0:
        return None
    codes = {name: code for code, name in CLASSES.items()}
    return Surroundings(
        radius_m=SURROUNDINGS_RADIUS_M,
        pixels=total,
        shares_pct={k: round(100 * ring_counts.get(codes[k], 0) / total, 1) for k in SURROUNDING_KINDS},
        nearest_m=nearest,
    )


def items_for_year(items: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    return [
        it for it in items if str(it.get("properties", {}).get("start_datetime", "")).startswith(str(year))
    ]


async def _fetch_counts(geom: BaseGeometry, year: int) -> _Counts:
    token = await planetary.get_token(COLLECTION)
    items = items_for_year(
        # Tiles touching the ring too (3° tile edges cross Poland), not only the parcel (review M1).
        await planetary.search(
            {"collections": [COLLECTION], "intersects": mapping(box(*_ring_bounds(geom)[2])), "limit": 8}
        ),
        year,
    )
    if not items:
        raise SourceError("Brak mapy pokrycia terenu dla tego miejsca.")
    counts: _Counts = await planetary.run_in_pool(read_items, items, token, geom)
    return counts


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[LandCoverData]:
    """WorldCover is a single-year snapshot; the edition is chosen from analysis_date."""
    year = map_year_for(analysis_date)
    source = SOURCE.format(year=year, version=MAP_VERSIONS[year])
    geom = parcel_shape(parcel)
    period = Period(start=date(year, 1, 1), end=date(year, 12, 31))
    cache = get_cache()
    params = {"geom": geometry_hash(parcel.geometry), "year": year, "v": CACHE_VERSION}
    cached = cache.get(NAME, params)
    if cached is not None:
        c = _Counts(
            {int(k): int(v) for k, v in cached["parcel"].items()},
            {int(k): int(v) for k, v in cached["ring"].items()},
            dict(cached["nearest_m"]),
        )
    else:
        try:
            c = await asyncio.wait_for(_fetch_counts(geom, year), TIMEOUT_S)
        except (SourceError, TimeoutError) as exc:
            msg = (
                exc.message_pl
                if isinstance(exc, SourceError)
                else "Serwis mapy pokrycia terenu nie odpowiedział na czas."
            )
            return missing(NAME, source=source, license=LICENSE, period=period, message_pl=msg)
        if c.parcel:
            cache.set(
                NAME,
                params,
                {
                    "parcel": {str(k): v for k, v in c.parcel.items()},
                    "ring": {str(k): v for k, v in c.ring.items()},
                    "nearest_m": c.nearest_m,
                },
            )

    data = shares(c.parcel, year)
    if data is not None:
        data = data.model_copy(update={"surroundings": surroundings(c.ring, c.nearest_m)})
    if data is None:
        return missing(
            NAME,
            source=source,
            license=LICENSE,
            period=period,
            message_pl="Mapa pokrycia terenu nie ma danych dla tej działki.",
        )
    messages = [f"Mapa pokrycia terenu pokazuje stan z {year} r., nie z dnia analizy."]
    if date(year, 1, 1) > analysis_date:
        messages.append(f"Starszej mapy nie ma, więc użyto późniejszej (z {year} r.).")
    status = SourceStatus.OK
    if not data.looks_agricultural:
        status = SourceStatus.DEGRADED
        messages.append(
            f"Według mapy z {year} r. tylko {data.cropland_pct + data.grassland_pct:.0f}% działki "
            "to pole lub łąka "
            "— działka może nie być użytkowana rolniczo, co obniża wiarygodność oceny."
        )
    return result(
        NAME,
        status,
        data,
        source=source,
        license=LICENSE,
        period=period,
        uncertainty=unc(
            Confidence.MEDIUM if data.pixels >= 10 else Confidence.LOW,
            f"Mapa satelitarna 10 m z {year} r.; użytkowanie mogło się od tego czasu zmienić.",
        ),
        message_pl=" ".join(messages),
    )
