"""Terrain elevation grid around the parcel (parcel + 150 m buffer), in EPSG:2180.

Primary (per M1 measurements): Copernicus DEM GLO-30 from Planetary Computer, status `degraded` — 30 m and a
surface model (trees and buildings raise the height). Resampled bilinearly to a 10 m working grid so that
flow directions follow the parcel outline; the native resolution is reported so analysis does not
over-interpret it.

Optional: GUGiK NMT 1 m WCS (enable with RSW_DEM_TRY_NMT=true). From the event network a 500 × 500 m
subset took > 30 s, so it is off by default and tried with a strict timeout before the fallback when enabled.
"""

import logging
import math
from datetime import date, timedelta
from typing import Any, Literal

import httpx
import numpy as np
from affine import Affine
from pydantic import BaseModel
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.errors import RasterioError
from rasterio.io import MemoryFile
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
NMT_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
NMT_COVERAGE = "DTM_PL-KRON86-NH_TIFF"
SOURCE_NMT = "GUGiK, Numeryczny Model Terenu (NMT, 1 m), usługa WCS, https://www.geoportal.gov.pl/"
LICENSE_NMT = "Dane publiczne GUGiK, udostępniane bezpłatnie"

BUFFER_M = 150.0
COP_RESOLUTION_M = 10.0
NMT_RESOLUTION_M = 5.0
MAX_CELLS = 400  # per side; resolution is coarsened for very large parcels
NMT_TIMEOUT_S = 8.0
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


def parse_nmt(content: bytes, geom_2180: BaseGeometry) -> ElevationGrid:
    if not content.startswith((b"II", b"MM")):
        raise SourceError("Usługa NMT nie zwróciła rastra.")
    transform, width, height, res = target_grid(geom_2180, NMT_RESOLUTION_M)
    dst = np.full((height, width), np.nan, dtype="float32")
    try:
        with MemoryFile(content) as mf, mf.open() as ds:
            src = ds.read(1)
            # The NMT WCS response is in EPSG:2180; this only resamples 1 m -> working resolution.
            _reproject_into(dst, src, ds.transform, ds.crs or CRS.from_epsg(METRIC_CRS), ds.nodata, transform)
    except RasterioError as exc:
        raise SourceError("Nieczytelny raster z usługi NMT.") from exc
    if not np.isfinite(dst).any():
        raise SourceError("Usługa NMT zwróciła pusty raster.")
    return to_model(dst, transform, res, "gugik_nmt", 1.0)


async def _from_nmt(geom_2180: BaseGeometry) -> ElevationGrid:
    minx, miny, maxx, maxy = geom_2180.buffer(BUFFER_M).bounds
    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", NMT_COVERAGE),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"x({minx:.0f},{maxx:.0f})"),
        ("SUBSET", f"y({miny:.0f},{maxy:.0f})"),
    ]
    try:
        resp = await request("GET", NMT_URL, params=params, timeout_s=NMT_TIMEOUT_S, retries=0)
    except httpx.HTTPError as exc:
        raise SourceError("Usługa NMT (GUGiK) nie odpowiedziała na czas.") from exc
    grid: ElevationGrid = await planetary.run_in_pool(parse_nmt, resp.content, geom_2180)
    return grid


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
    if grid is None and try_nmt:
        try:
            grid = await _from_nmt(geom_2180)
        except SourceError as exc:
            notes.append(exc.message_pl)
    if grid is None:
        try:
            grid = await _from_copernicus(geom, geom_2180)
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
            uncertainty=unc(Confidence.HIGH, "Numeryczny model terenu 1 m z pomiaru lotniczego (lidar)."),
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
