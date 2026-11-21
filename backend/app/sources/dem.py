"""Terrain elevation grid around the parcel (parcel + 150 m buffer), in EPSG:2180.

Primary (per M1 measurements): Copernicus DEM GLO-30 from Planetary Computer, status `degraded` — 30 m and a
surface model (trees and buildings raise the height). Resampled bilinearly to a 10 m working grid so that
flow directions follow the parcel outline; the native resolution is reported so analysis does not
over-interpret it.

Preferred: GUGiK NMT 1 m (lidar) sampled on a regular 5 m grid (coarser for big parcels) through the GUGiK
point-height service (GetHByPointList, about 1.5 s for 10 000 points). The NMT WCS GetCoverage never answered
from the event network (all requests timed out), so it is no longer used. On failure: Copernicus 30 m.
Disable with RSW_DEM_TRY_NMT=false.
"""

import asyncio
import logging
import math
import random
from datetime import date, timedelta
from typing import Any, Literal

import httpx
import numpy as np
from affine import Affine
from pydantic import BaseModel
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.http import request
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
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
    within_budget,
)

log = logging.getLogger(__name__)

NAME = "dem"
COP_COLLECTION = "cop-dem-glo-30"
SOURCE_COP = "Copernicus DEM GLO-30 (ESA/Airbus), katalog Microsoft Planetary Computer, https://planetarycomputer.microsoft.com/"
LICENSE_COP = "Licencja Copernicus DEM — bezpłatna, wymagane podanie źródła"
NMT_URL = "https://services.gugik.gov.pl/nmt/"
SOURCE_NMT = (
    "GUGiK, Numeryczny Model Terenu (NMT, 1 m, lidar), usługa wysokości punktów GetHByPointList, "
    "https://services.gugik.gov.pl/nmt/"
)
LICENSE_NMT = "Dane publiczne GUGiK, udostępniane bezpłatnie"

BUFFER_M = 150.0
COP_RESOLUTION_M = 10.0
NMT_RESOLUTION_M = 5.0
MAX_CELLS = 400  # per side; resolution is coarsened for very large parcels
NMT_TIMEOUT_S = 7.0
NMT_MAX_POINTS = 8_000  # per parcel; the sampling step grows for big parcels
NMT_CHUNK = 1_000  # the service returns heights for at most 1000 points per request
NMT_PARALLEL = 3  # more parallel requests trip the GUGiK firewall (redirects to an error page)
NMT_DEADLINE_S = 9.0  # retries of firewall-blocked requests stop here (then Copernicus)
NMT_RETRY_PAUSE_S = 0.4
BUDGET_S = 18.0  # hard limit for the whole source (NMT attempt + Copernicus)
# Copernicus result cached after a failed NMT attempt expires, so NMT is retried later.
NMT_RETRY_TTL = timedelta(hours=6)


class ElevationGrid(BaseModel):
    dataset: Literal["copernicus_glo30", "gugik_nmt"]
    crs: str  # always "EPSG:2180"
    # Affine transform of the grid (a, b, c, d, e, f) — rasterio/affine order.
    transform: list[float]
    resolution_m: float
    native_resolution_m: float
    width: int
    height: int
    elevation_m: list[list[float | None]]  # row-major, north to south


def target_grid(geom_2180: BaseGeometry, resolution_m: float) -> tuple[Affine, int, int, float]:
    """Grid covering the buffered parcel, snapped to the resolution; coarsened if larger than MAX_CELLS."""
    minx, miny, maxx, maxy = geom_2180.buffer(BUFFER_M).bounds
    res = max(resolution_m, math.ceil(max(maxx - minx, maxy - miny) / MAX_CELLS))
    minx, miny = math.floor(minx / res) * res, math.floor(miny / res) * res
    maxx, maxy = math.ceil(maxx / res) * res, math.ceil(maxy / res) * res
    width, height = int(round((maxx - minx) / res)), int(round((maxy - miny) / res))
    return Affine(res, 0.0, minx, 0.0, -res, maxy), width, height, float(res)


def to_model(
    arr: np.ndarray,
    transform: Affine,
    res: float,
    dataset: Literal["copernicus_glo30", "gugik_nmt"],
    native: float,
) -> ElevationGrid:
    rows: list[list[float | None]] = [
        [None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in arr
    ]
    return ElevationGrid(
        dataset=dataset,
        crs=f"EPSG:{METRIC_CRS}",
        transform=[transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
        resolution_m=res,
        native_resolution_m=native,
        width=arr.shape[1],
        height=arr.shape[0],
        elevation_m=rows,
    )


def _reproject_into(
    dst: np.ndarray,
    src: np.ndarray,
    src_transform: Any,
    src_crs: Any,
    src_nodata: float | None,
    dst_transform: Affine,
) -> None:
    src_f = src.astype("float32")
    if src_nodata is not None:
        src_f[src == src_nodata] = np.nan
    tmp = np.full_like(dst, np.nan)
    reproject(
        source=src_f,
        destination=tmp,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=np.nan,
        dst_transform=dst_transform,
        dst_crs=CRS.from_epsg(METRIC_CRS),
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    fill = np.isnan(dst) & np.isfinite(tmp)
    dst[fill] = tmp[fill]


def read_cop_items(items: list[dict[str, Any]], token: str, geom_2180: BaseGeometry) -> ElevationGrid | None:
    """Blocking: mosaic the needed windows of all intersecting 1° tiles onto the 2180 grid."""
    transform, width, height, res = target_grid(geom_2180, COP_RESOLUTION_M)
    dst = np.full((height, width), np.nan, dtype="float32")
    # Source window in EPSG:4326 with a margin of ~2 source pixels for bilinear interpolation.
    minx, miny, maxx, maxy = to_crs(geom_2180.buffer(BUFFER_M + 90), 4326, src_crs=METRIC_CRS).bounds
    for item in items:
        href = item.get("assets", {}).get("data", {}).get("href")
        if not href:
            continue
        try:
            win = planetary.read_window(planetary.sign(href, token), (minx, miny, maxx, maxy))
        except SourceError:
            continue
        if win.array.size == 0:
            continue
        _reproject_into(dst, win.array, win.transform, win.crs, win.nodata, transform)
    if not np.isfinite(dst).any():
        return None
    return to_model(dst, transform, res, "copernicus_glo30", 30.0)


async def _from_copernicus(geom_wgs84: BaseGeometry, geom_2180: BaseGeometry) -> ElevationGrid:
    token = await planetary.get_token(COP_COLLECTION)
    search_geom = to_crs(geom_2180.buffer(BUFFER_M), 4326, src_crs=METRIC_CRS)
    items = await planetary.search(
        {"collections": [COP_COLLECTION], "intersects": mapping(search_geom), "limit": 4}
    )
    if not items:
        raise SourceError("Brak modelu wysokości terenu dla tego miejsca.")
    grid: ElevationGrid | None = await planetary.run_in_pool(read_cop_items, items, token, geom_2180)
    if grid is None:
        raise SourceError("Nie udało się odczytać modelu wysokości terenu.")
    return grid


def nmt_grid_points(geom_2180: BaseGeometry) -> tuple[Affine, int, int, float, list[tuple[float, float]]]:
    """Cell centres (E, N) of the working grid for the NMT point sampling."""
    minx, miny, maxx, maxy = geom_2180.buffer(BUFFER_M).bounds
    res = max(NMT_RESOLUTION_M, math.ceil(math.sqrt((maxx - minx) * (maxy - miny) / NMT_MAX_POINTS)))
    transform, width, height, res = target_grid(geom_2180, res)
    points = [
        (transform.c + (c + 0.5) * res, transform.f - (r + 0.5) * res)
        for r in range(height)
        for c in range(width)
    ]
    return transform, width, height, res, points


def parse_nmt_points(text: str, expected: int) -> list[float]:
    """'N E H,N E H,...' → heights in request order.

    "No data" comes as a point without a height ('N E'). Outside Poland the service answers 0.0; a real
    height can also be 0.0 m (polders of Żuławy lie at or below sea level), so 0.0 counts as "no data" only
    when every height of the chunk is 0.0.
    """
    out: list[float] = []
    for item in text.strip().split(","):
        parts = item.split()
        if len(parts) not in (2, 3):
            raise SourceError("Usługa NMT zwróciła nieczytelną odpowiedź.")
        try:
            out.append(float(parts[2]) if len(parts) == 3 else math.nan)
        except ValueError as exc:
            raise SourceError("Usługa NMT zwróciła nieczytelną odpowiedź.") from exc
    if len(out) != expected:
        raise SourceError("Usługa NMT zwróciła niepełną odpowiedź.")
    present = [h for h in out if not math.isnan(h)]
    if present and all(h == 0.0 for h in present):
        return [math.nan] * len(out)
    return out


async def _nmt_chunk(
    points: list[tuple[float, float]], slots: asyncio.Semaphore, deadline: float
) -> list[float]:
    """One request of ≤ 1000 points.

    GUGiK's web firewall randomly answers part of the requests with a redirect to an error page
    (302 → integracja01.gugik.gov.pl, a body announced as 4 GB). Redirects are never followed; such a
    request is repeated after a short pause until NMT_DEADLINE_S, then the source falls back to Copernicus.
    """
    body = {"request": "GetHByPointList", "list": ",".join(f"{n:.1f} {e:.1f}" for e, n in points)}
    loop = asyncio.get_running_loop()
    while True:
        try:
            async with slots:
                resp = await request(
                    "POST", NMT_URL, data=body, timeout_s=NMT_TIMEOUT_S, retries=0, follow_redirects=False
                )
            return parse_nmt_points(resp.text, len(points))
        except (httpx.HTTPError, SourceError) as exc:
            if loop.time() + NMT_RETRY_PAUSE_S >= deadline:
                if isinstance(exc, SourceError):
                    raise
                raise SourceError("Usługa NMT (GUGiK) nie odpowiedziała poprawnie na czas.") from exc
        await asyncio.sleep(NMT_RETRY_PAUSE_S + random.random() * NMT_RETRY_PAUSE_S)


async def _from_nmt(geom_2180: BaseGeometry) -> ElevationGrid:
    transform, width, height, res, points = nmt_grid_points(geom_2180)
    chunks = [points[i : i + NMT_CHUNK] for i in range(0, len(points), NMT_CHUNK)]
    slots = asyncio.Semaphore(NMT_PARALLEL)
    deadline = asyncio.get_running_loop().time() + NMT_DEADLINE_S
    parts = await asyncio.gather(*(_nmt_chunk(c, slots, deadline) for c in chunks))
    heights = np.array([h for part in parts for h in part], dtype="float32").reshape(height, width)
    if np.isnan(heights).mean() > 0.5:
        raise SourceError("Usługa NMT nie ma danych dla tego miejsca.")
    return to_model(heights, transform, res, "gugik_nmt", 1.0)


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[ElevationGrid]:
    """Terrain is treated as static; analysis_date keeps the common source signature."""
    return await within_budget(
        NAME,
        _fetch(parcel),
        BUDGET_S,
        lambda: missing(
            NAME,
            source=SOURCE_COP,
            license=LICENSE_COP,
            message_pl=(
                "Model wysokości terenu nie został pobrany na czas. "
                "Spadków terenu i spływu wody nie oceniamy."
            ),
        ),
    )


async def _fetch(parcel: Parcel) -> SourceResult[ElevationGrid]:
    geom = parcel_shape(parcel)
    geom_2180 = to_crs(geom, METRIC_CRS)
    cache = get_cache()
    try_nmt = get_settings().dem_try_nmt
    params = {"geom": geometry_hash(parcel.geometry), "nmt": try_nmt}
    cached = cache.get(NAME, params)
    grid: ElevationGrid | None = ElevationGrid.model_validate(cached) if cached is not None else None
    notes: list[str] = []
    cop_task: asyncio.Task[ElevationGrid] | None = None
    if grid is None and try_nmt:
        # Copernicus is fetched at the same time, so a slow or blocked NMT costs no extra time.
        cop_task = asyncio.create_task(_from_copernicus(geom, geom_2180))
        # A Copernicus error is read here when NMT succeeded (no "exception never retrieved" warning).
        cop_task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
        try:
            grid = await _from_nmt(geom_2180)
        except SourceError as exc:
            notes.append(exc.message_pl)
        if grid is not None:
            cop_task.cancel()
    if grid is None:
        try:
            grid = await cop_task if cop_task is not None else await _from_copernicus(geom, geom_2180)
        except SourceError as exc:
            return missing(
                NAME,
                source=SOURCE_COP,
                license=LICENSE_COP,
                message_pl=f"{exc.message_pl} Spadków terenu i spływu wody nie oceniamy.",
            )
    if cached is None:
        nmt_failed = try_nmt and grid.dataset != "gugik_nmt"
        cache.set(NAME, params, grid.model_dump(mode="json"), NMT_RETRY_TTL if nmt_failed else None)

    if grid.dataset == "gugik_nmt":
        return result(
            NAME,
            SourceStatus.OK,
            grid,
            source=SOURCE_NMT,
            license=LICENSE_NMT,
            uncertainty=unc(
                Confidence.HIGH,
                "Numeryczny model terenu z pomiaru lotniczego (lidar), "
                f"próbkowany co {grid.resolution_m:.0f} m; wysokości podane co 0,1 m, więc spadki poniżej "
                "ok. 1 % są na granicy dokładności.",
            ),
        )
    return result(
        NAME,
        SourceStatus.DEGRADED,
        grid,
        source=SOURCE_COP,
        license=LICENSE_COP,
        uncertainty=unc(
            Confidence.MEDIUM,
            "Model wysokości 30 m; drzewa i zabudowa zawyżają wysokość, drobne zagłębienia nie są widoczne.",
        ),
        message_pl=" ".join(
            [
                *notes,
                "Ukształtowanie terenu oceniono z ogólnoświatowego modelu wysokości o rozdzielczości 30 m, "
                "więc drobne zagłębienia i rowy na działce mogą nie być widoczne.",
            ]
        ),
    )
