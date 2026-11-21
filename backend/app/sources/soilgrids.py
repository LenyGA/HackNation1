"""SoilGrids 2.0 (ISRIC): texture, organic carbon and bulk density at the parcel centroid, down to 100 cm.

Uses the WCS endpoint (the REST API was rejected in M1: slow and mostly null for Poland). One tiny GeoTIFF per
property × depth, requested in parallel, with a hard overall timeout. Value 0 means "no data" (built-up areas,
water). Units are converted from SoilGrids mapped units to the units in field names.
Resolution is 250 m, so confidence is at most "medium".
"""

import asyncio
import logging
from datetime import date

import httpx
import numpy as np
from pydantic import BaseModel
from rasterio.errors import RasterioError
from rasterio.io import MemoryFile

from app.core.cache import get_cache
from app.core.http import request
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
from app.sources.base import missing, result, unc

log = logging.getLogger(__name__)

NAME = "soilgrids"
WCS_URL = "https://maps.isric.org/mapserv"
SOURCE = "ISRIC SoilGrids 2.0 (siatka 250 m), usługa WCS, https://soilgrids.org/"
LICENSE = "CC BY 4.0"
TIMEOUT_S = 8.0  # hard limit for the whole source
REQUEST_TIMEOUT_S = 6.0
HALF_WINDOW_DEG = 0.003  # ~ ±300 m around the centroid; enough for a 3x3 neighbourhood at 250 m
EPSG4326 = "http://www.opengis.net/def/crs/EPSG/0/4326"

DEPTHS: list[tuple[str, int, int]] = [
    ("0-5cm", 0, 5),
    ("5-15cm", 5, 15),
    ("15-30cm", 15, 30),
    ("30-60cm", 30, 60),
    ("60-100cm", 60, 100),
]
# property -> (output field, divisor from mapped units).
# Mapped units: g/kg for texture, dg/kg SOC, cg/cm3 bdod.
PROPERTIES: dict[str, tuple[str, float]] = {
    "sand": ("sand_pct", 10.0),
    "silt": ("silt_pct", 10.0),
    "clay": ("clay_pct", 10.0),
    "soc": ("soc_g_per_kg", 10.0),
    "bdod": ("bulk_density_g_per_cm3", 100.0),
}


class SoilLayer(BaseModel):
    depth_top_cm: int
    depth_bottom_cm: int
    sand_pct: float | None
    silt_pct: float | None
    clay_pct: float | None
    soc_g_per_kg: float | None
    bulk_density_g_per_cm3: float | None


class SoilData(BaseModel):
    latitude: float
    longitude: float
    layers: list[SoilLayer]
    # True when the centroid cell had no data and the nearest valid neighbouring cell (≤ ~300 m) was used.
    neighbour_used: bool


class _Missing(Exception):
    pass


def pick_value(arr: np.ndarray, row: int, col: int) -> tuple[float | None, bool]:
    """Value at (row, col); if 0/no-data, the nearest non-zero cell. Returns (value, used_neighbour)."""
    if 0 <= row < arr.shape[0] and 0 <= col < arr.shape[1] and arr[row, col] > 0:
        return float(arr[row, col]), False
    rows, cols = np.nonzero(arr > 0)
    if rows.size == 0:
        return None, False
    d2 = (rows - row) ** 2 + (cols - col) ** 2
    i = int(np.argmin(d2))
    return float(arr[rows[i], cols[i]]), True


def parse_tiff(content: bytes, lat: float, lon: float) -> tuple[float | None, bool]:
    if not content.startswith((b"II", b"MM")):
        raise _Missing("not a tiff")
    try:
        with MemoryFile(content) as mf, mf.open() as ds:
            arr = ds.read(1)
            row, col = ds.index(lon, lat)
    except RasterioError as exc:
        raise _Missing("bad tiff") from exc
    return pick_value(arr, row, col)


async def _get_one(prop: str, depth: str, lat: float, lon: float) -> tuple[float | None, bool]:
    params = [
        ("map", f"/map/{prop}.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", f"{prop}_{depth}_mean"),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"long({lon - HALF_WINDOW_DEG:.5f},{lon + HALF_WINDOW_DEG:.5f})"),
        ("SUBSET", f"lat({lat - HALF_WINDOW_DEG:.5f},{lat + HALF_WINDOW_DEG:.5f})"),
        ("SUBSETTINGCRS", EPSG4326),
        ("OUTPUTCRS", EPSG4326),
    ]
    try:
        resp = await request("GET", WCS_URL, params=params, timeout_s=REQUEST_TIMEOUT_S, retries=0)
    except httpx.HTTPError as exc:
        raise _Missing(type(exc).__name__) from exc
    return parse_tiff(resp.content, lat, lon)


async def _fetch_all(lat: float, lon: float) -> dict[tuple[str, str], tuple[float | None, bool] | None]:
    keys = [(p, d) for p in PROPERTIES for d, _, _ in DEPTHS]

    async def one(key: tuple[str, str]) -> tuple[float | None, bool] | None:
        try:
            return await _get_one(key[0], key[1], lat, lon)
        except Exception as exc:  # any failure of one layer must not crash the source
            log.info("SoilGrids %s %s failed: %s", key[0], key[1], exc)
            return None

    tasks = [asyncio.create_task(one(k)) for k in keys]
    done, pending = await asyncio.wait(tasks, timeout=TIMEOUT_S)
    for t in pending:
        t.cancel()
    return {k: (t.result() if t in done else None) for k, t in zip(keys, tasks, strict=True)}


def build_soil(
    raw: dict[tuple[str, str], tuple[float | None, bool] | None], lat: float, lon: float
) -> tuple[SoilData, int, int]:
    """Assemble layers. Returns data, number of failed requests and number of no-data values."""
    failed = sum(1 for v in raw.values() if v is None)
    nodata = sum(1 for v in raw.values() if v is not None and v[0] is None)
    neighbour = any(v is not None and v[1] for v in raw.values())
    layers: list[SoilLayer] = []
    for depth, top, bottom in DEPTHS:
        vals: dict[str, float | None] = {}
        for prop, (field, div) in PROPERTIES.items():
            v = raw.get((prop, depth))
            vals[field] = None if v is None or v[0] is None else round(v[0] / div, 2)
        layers.append(SoilLayer(depth_top_cm=top, depth_bottom_cm=bottom, **vals))
    return SoilData(latitude=lat, longitude=lon, layers=layers, neighbour_used=neighbour), failed, nodata


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[SoilData]:
    """Soil does not depend on analysis_date (static map), the argument keeps the common source signature."""
    lat, lon = round(parcel.centroid_lat, 5), round(parcel.centroid_lon, 5)
    cache = get_cache()
    params = {"lat": lat, "lon": lon}
    cached = cache.get(NAME, params, None)
    if cached is not None:
        raw = {
            (k.split("|")[0], k.split("|")[1]): (None if v is None else (v[0], bool(v[1])))
            for k, v in cached.items()
        }
    else:
        raw = await _fetch_all(lat, lon)
        if all(v is not None for v in raw.values()):
            cache.set(
                NAME, params, {f"{p}|{d}": (None if v is None else list(v)) for (p, d), v in raw.items()}
            )

    data, failed, nodata = build_soil(raw, lat, lon)
    total = len(raw)
    if failed + nodata == total:
        msg = (
            "Serwis danych glebowych nie odpowiedział na czas."
            if failed
            else "Mapa gleb nie ma danych dla tego miejsca (np. teren zabudowany lub woda)."
        )
        return missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            message_pl=msg + " Pojemności wodnej gleby nie liczymy; ocena opiera się na pogodzie.",
        )

    status = SourceStatus.OK
    messages: list[str] = []
    reasons = ["mapa gleb w siatce 250 m, wartości modelowane, nie z pomiaru na działce"]
    level = Confidence.MEDIUM
    if failed or nodata:
        status, level = SourceStatus.DEGRADED, Confidence.LOW
        messages.append(f"Brakuje części danych glebowych ({failed + nodata} z {total} wartości).")
    if data.neighbour_used:
        status, level = SourceStatus.DEGRADED, Confidence.LOW
        messages.append(
            "Dla środka działki mapa gleb nie ma danych, użyto najbliższej komórki mapy (do ok. 300 m)."
        )
        reasons.append("użyto sąsiedniej komórki mapy")
    return result(
        NAME,
        status,
        data,
        source=SOURCE,
        license=LICENSE,
        uncertainty=unc(level, "; ".join(reasons).capitalize() + "."),
        message_pl=" ".join(messages) or None,
    )
