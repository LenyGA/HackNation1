"""Sentinel-2 L2A vegetation condition (NDVI) and moisture (NDMI) for the parcel (Planetary Computer COGs).

Scene selection (decision from plan M2.3 / M1.2):
- current state: up to CURRENT_MAX_SCENES best clear scenes from the CURRENT_WINDOW_DAYS before analysis_date,
- history: one best clear scene per previous year from a ±HISTORY_HALF_WINDOW_DAYS window around the same
  day of the year (the parcel is compared with its own history, never with a global threshold).

Only windows covering the parcel are read. Clouds are masked with the SCL band and selection uses the clear
share *over the parcel*, not the scene-level cloud cover. Since processing baseline 04.00 (25.01.2022)
reflectances carry a -1000 offset (BOA_ADD_OFFSET) which is corrected here; without it NDVI after 2022
looks ~0.2 lower.
"""

import asyncio
import logging
import math
import time
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.core.cache import get_cache
from app.core.config import HISTORY_YEARS, today_local
from app.core.models import Confidence, Parcel, Period, SourceResult, SourceStatus
from app.sources import planetary
from app.sources.base import (
    SourceError,
    cache_ttl,
    geometry_hash,
    missing,
    parcel_shape,
    result,
    to_crs,
    unc,
    within_budget,
)

log = logging.getLogger(__name__)

NAME = "sentinel2"
COLLECTION = "sentinel-2-l2a"
SOURCE = "Copernicus Sentinel-2 L2A (ESA), katalog Microsoft Planetary Computer, https://planetarycomputer.microsoft.com/"
LICENSE = "Dane Copernicus Sentinel — bezpłatne, wymagane podanie źródła"

CURRENT_WINDOW_DAYS = 45
CURRENT_MAX_SCENES = 3
CURRENT_CANDIDATES = 6
HISTORY_HALF_WINDOW_DAYS = 20
HISTORY_CANDIDATES = 3
MAX_SCENE_CLOUD_PCT = 70
# A scene is usable when at least this share of the parcel's pixels is clear (SCL 4/5/6).
MIN_CLEAR_SHARE = 0.6
MIN_PARCEL_PIXELS = 10
MIN_HISTORY_YEARS = 5
TIMEOUT_S = 15.0  # scene search + reads; partial result after this
BUDGET_S = 20.0  # hard limit for the whole source incl. token

SCL_CLEAR = (4, 5)  # vegetation, bare soil (water excluded: it would pull NDVI down)
GRID_SNAP_M = 60  # common multiple of 10 m and 20 m pixel grids (S2 tile origins are multiples of 60 m)
MISSION_START = date(2015, 7, 1)  # first Sentinel-2A acquisitions
BOA_OFFSET_BASELINE = "04.00"
BOA_OFFSET = -1000.0


class SceneStat(BaseModel):
    scene_id: str
    date: date
    ndvi_mean: float
    ndmi_mean: float | None
    clear_pixels: int
    parcel_pixels: int
    clear_share: float
    scene_cloud_pct: float | None


class Sentinel2Data(BaseModel):
    parcel_pixels: int
    current: list[SceneStat]  # newest first
    history: list[SceneStat]  # one per previous year, oldest first
    years_requested: int
    years_with_data: int


class _Slot(BaseModel):
    key: str  # "current" or the year offset ("y1".."y10")
    start: date
    end: date
    max_scenes: int
    candidates: int


def build_slots(analysis_date: date) -> list[_Slot]:
    slots = [
        _Slot(
            key="current",
            start=analysis_date - timedelta(days=CURRENT_WINDOW_DAYS),
            end=analysis_date,
            max_scenes=CURRENT_MAX_SCENES,
            candidates=CURRENT_CANDIDATES,
        )
    ]
    for y in range(1, HISTORY_YEARS + 1):
        centre = analysis_date - relativedelta(years=y)
        slots.append(
            _Slot(
                key=f"y{y}",
                start=centre - timedelta(days=HISTORY_HALF_WINDOW_DAYS),
                end=min(centre + timedelta(days=HISTORY_HALF_WINDOW_DAYS), analysis_date),
                max_scenes=1,
                candidates=HISTORY_CANDIDATES,
            )
        )
    return slots


def boa_offset(item: dict[str, Any]) -> float:
    baseline = str(item.get("properties", {}).get("s2:processing_baseline") or "00.00")
    return BOA_OFFSET if baseline >= BOA_OFFSET_BASELINE else 0.0


def _snap_bounds(geom: BaseGeometry, pad_m: float = 20.0) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = geom.bounds
    s = GRID_SNAP_M
    return (
        math.floor((minx - pad_m) / s) * s,
        math.floor((miny - pad_m) / s) * s,
        math.ceil((maxx + pad_m) / s) * s,
        math.ceil((maxy + pad_m) / s) * s,
    )


def parcel_mask(geom: BaseGeometry, shape: tuple[int, int], transform: Any) -> np.ndarray:
    """Pixels whose centre lies inside the parcel; falls back to touched pixels for tiny parcels."""
    inside = geometry_mask([mapping(geom)], out_shape=shape, transform=transform, invert=True)
    if not inside.any():
        inside = geometry_mask(
            [mapping(geom)], out_shape=shape, transform=transform, invert=True, all_touched=True
        )
    return np.asarray(inside, dtype=bool)


def compute_indices(
    red_dn: np.ndarray,
    nir_dn: np.ndarray,
    swir_dn: np.ndarray | None,
    scl: np.ndarray,
    inside: np.ndarray,
    offset: float,
) -> tuple[float | None, float | None, int, int]:
    """Mean NDVI/NDMI over clear parcel pixels. Returns (ndvi, ndmi, clear_pixels, parcel_pixels). Pure."""
    parcel_pixels = int(inside.sum())
    valid = inside & np.isin(scl, SCL_CLEAR) & (red_dn > 0) & (nir_dn > 0)
    clear = int(valid.sum())
    if clear == 0:
        return None, None, 0, parcel_pixels
    red = np.clip((red_dn[valid].astype("float64") + offset) / 10_000, 0, None)
    nir = np.clip((nir_dn[valid].astype("float64") + offset) / 10_000, 0, None)
    denom = nir + red
    ok = denom > 0
    if not ok.any():
        return None, None, clear, parcel_pixels
    ndvi = float(np.mean((nir[ok] - red[ok]) / denom[ok]))
    ndmi: float | None = None
    if swir_dn is not None:
        swir_valid = swir_dn[valid] > 0
        swir = np.clip((swir_dn[valid].astype("float64") + offset) / 10_000, 0, None)
        d2 = nir + swir
        ok2 = swir_valid & (d2 > 0)
        if ok2.any():
            ndmi = float(np.mean((nir[ok2] - swir[ok2]) / d2[ok2]))
    return ndvi, ndmi, clear, parcel_pixels


class _DeadlineExceeded(SourceError):
    pass


def _check_deadline(deadline: float | None) -> None:
    # Cancelled asyncio tasks do not stop pool threads, so reads check the deadline themselves.
    if deadline is not None and time.monotonic() > deadline:
        raise _DeadlineExceeded("deadline")


def scene_stats(
    item: dict[str, Any], geom_wgs84: BaseGeometry, token: str, deadline: float | None = None
) -> SceneStat | None:
    """Blocking: read SCL first and only fetch reflectance bands when the parcel is clear enough."""
    props = item.get("properties", {})
    epsg = props.get("proj:epsg")
    if not epsg:
        return None
    assets = item.get("assets", {})
    if not all(b in assets for b in ("B04", "B08", "SCL")):
        return None
    geom = to_crs(geom_wgs84, int(epsg))
    bounds = _snap_bounds(geom)
    w = int(round((bounds[2] - bounds[0]) / 10))
    h = int(round((bounds[3] - bounds[1]) / 10))
    shape = (h, w)

    _check_deadline(deadline)
    scl = planetary.read_window(
        planetary.sign(assets["SCL"]["href"], token), bounds, out_shape=shape, resampling=Resampling.nearest
    )
    if scl.clipped:  # parcel at the tile edge: the overlapping tile of the same pass covers it fully
        return None
    inside = parcel_mask(geom, shape, scl.transform)
    parcel_pixels = int(inside.sum())
    if parcel_pixels == 0:
        return None
    clear_share = float((inside & np.isin(scl.array, SCL_CLEAR)).sum()) / parcel_pixels
    if clear_share < MIN_CLEAR_SHARE:
        return None

    _check_deadline(deadline)
    red = planetary.read_window(planetary.sign(assets["B04"]["href"], token), bounds, out_shape=shape)
    _check_deadline(deadline)
    nir = planetary.read_window(planetary.sign(assets["B08"]["href"], token), bounds, out_shape=shape)
    _check_deadline(deadline)
    swir = (
        planetary.read_window(
            planetary.sign(assets["B11"]["href"], token),
            bounds,
            out_shape=shape,
            resampling=Resampling.nearest,
        ).array
        if "B11" in assets
        else None
    )
    ndvi, ndmi, clear, n = compute_indices(red.array, nir.array, swir, scl.array, inside, boa_offset(item))
    if ndvi is None:
        return None
    cloud = props.get("eo:cloud_cover")
    return SceneStat(
        scene_id=str(item.get("id")),
        date=datetime.fromisoformat(str(props["datetime"]).replace("Z", "+00:00")).date(),
        ndvi_mean=round(ndvi, 3),
        ndmi_mean=None if ndmi is None else round(ndmi, 3),
        clear_pixels=clear,
        parcel_pixels=n,
        clear_share=round(clear / n, 3),
        scene_cloud_pct=None if cloud is None else round(float(cloud), 1),
    )


def _search_body(geom: BaseGeometry, slot: _Slot) -> dict[str, Any]:
    return {
        "collections": [COLLECTION],
        "intersects": mapping(geom),
        "datetime": f"{slot.start.isoformat()}T00:00:00Z/{slot.end.isoformat()}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": MAX_SCENE_CLOUD_PCT}},
        "sortby": [{"field": "eo:cloud_cover", "direction": "asc"}],
        "limit": slot.candidates,
    }


def _item_date(item: dict[str, Any]) -> date:
    return datetime.fromisoformat(str(item["properties"]["datetime"]).replace("Z", "+00:00")).date()


async def _process_slot(
    slot: _Slot, geom: BaseGeometry, token: str, analysis_date: date, deadline: float | None = None
) -> tuple[list[SceneStat], bool]:
    """Return accepted scenes and whether the slot was fully processed (only complete slots are cached)."""
    items = await planetary.search(_search_body(geom, slot))
    items = [it for it in items if _item_date(it) <= analysis_date][: slot.candidates]
    complete = True

    async def one(item: dict[str, Any]) -> SceneStat | None:
        nonlocal complete
        try:
            stat: SceneStat | None = await planetary.run_in_pool(
                scene_stats, item, geom, token, deadline, pool=planetary.SENTINEL_POOL
            )
        except SourceError:
            complete = False
            return None
        return stat

    stats = [s for s in await asyncio.gather(*(one(it) for it in items)) if s is not None]
    # One acquisition appears once per overlapping MGRS tile: keep the best per date.
    best: dict[date, SceneStat] = {}
    for s in stats:
        if s.date not in best or s.clear_share > best[s.date].clear_share:
            best[s.date] = s
    stats = list(best.values())
    if slot.key == "current":
        stats.sort(key=lambda s: s.date, reverse=True)
    else:
        stats.sort(key=lambda s: (-s.clear_share, s.scene_cloud_pct or 0.0))
    return stats[: slot.max_scenes], complete


async def _cached_slot(
    slot: _Slot,
    geom: BaseGeometry,
    geom_key: str,
    token: str,
    analysis_date: date,
    today: date,
    deadline: float | None = None,
) -> list[SceneStat]:
    cache = get_cache()
    params = {"geom": geom_key, "start": slot.start.isoformat(), "end": slot.end.isoformat()}
    cached = cache.get(NAME, params)
    if cached is not None:
        return [SceneStat.model_validate(s) for s in cached]
    stats, complete = await _process_slot(slot, geom, token, analysis_date, deadline)
    if complete:
        # Recent windows may still receive newly ingested scenes, so their entries expire (decided now).
        cache.set(NAME, params, [s.model_dump(mode="json") for s in stats], cache_ttl(slot.end, today))
    return stats


async def fetch(
    parcel: Parcel, analysis_date: date, today: date | None = None
) -> SourceResult[Sentinel2Data]:
    return await within_budget(
        NAME,
        _fetch(parcel, analysis_date, today or today_local()),
        BUDGET_S,
        lambda: missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            message_pl=(
                "Serwis zdjęć satelitarnych nie odpowiedział na czas. Ocena opiera się na pogodzie i glebie."
            ),
        ),
    )


async def _fetch(parcel: Parcel, analysis_date: date, today: date) -> SourceResult[Sentinel2Data]:
    geom = parcel_shape(parcel)
    geom_key = geometry_hash(parcel.geometry)
    slots = build_slots(analysis_date)
    period = Period(start=slots[-1].start, end=analysis_date)
    try:
        token = await planetary.get_token(COLLECTION)
    except SourceError as exc:
        return missing(NAME, source=SOURCE, license=LICENSE, message_pl=exc.message_pl, period=period)

    deadline = time.monotonic() + TIMEOUT_S
    tasks = {
        s.key: asyncio.create_task(_cached_slot(s, geom, geom_key, token, analysis_date, today, deadline))
        for s in slots
    }
    done, pending = await asyncio.wait(tasks.values(), timeout=TIMEOUT_S)
    for t in pending:
        t.cancel()
    timed_out = bool(pending)
    failed = 0
    by_key: dict[str, list[SceneStat]] = {}
    for key, task in tasks.items():
        if task not in done:
            continue
        if task.exception() is not None:
            failed += 1
            continue
        by_key[key] = task.result()

    if not by_key and (failed or timed_out):
        return missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            period=period,
            message_pl=(
                "Serwis zdjęć satelitarnych nie odpowiedział na czas. Ocena opiera się na pogodzie i glebie."
            ),
        )

    current = by_key.get("current", [])
    history = sorted((s for k, v in by_key.items() if k != "current" for s in v[:1]), key=lambda s: s.date)
    parcel_pixels = max([s.parcel_pixels for s in current + history], default=0)
    data = Sentinel2Data(
        parcel_pixels=parcel_pixels,
        current=current,
        history=history,
        years_requested=HISTORY_YEARS,
        years_with_data=len(history),
    )

    if "current" not in by_key:
        return missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            period=period,
            message_pl=(
                "Nie udało się pobrać bieżących zdjęć satelitarnych działki. "
                "Ocena opiera się na pogodzie i glebie."
            ),
        )
    if not current:
        return missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            period=period,
            message_pl=(
                f"W ciągu {CURRENT_WINDOW_DAYS} dni przed datą analizy nie było zdjęcia satelitarnego, "
                "na którym działka byłaby wolna od chmur. Kondycji roślin nie oceniamy; "
                "ocena opiera się na pogodzie i glebie."
            ),
        )

    messages: list[str] = []
    status = SourceStatus.OK
    # Satellite is a confirmation only: past crops are unknown, so confidence never exceeds medium.
    level = Confidence.MEDIUM
    reasons = [
        "nie znamy upraw w poprzednich latach (płodozmian), więc porównanie z historią jest przybliżone"
    ]
    if parcel_pixels < MIN_PARCEL_PIXELS:
        status, level = SourceStatus.DEGRADED, Confidence.LOW
        messages.append(
            f"Działka obejmuje tylko {parcel_pixels} pikseli zdjęcia satelitarnego (10 × 10 m), "
            "więc wynik jest mało pewny."
        )
        reasons.append("działka mała w stosunku do rozdzielczości zdjęć")
    if len(history) < MIN_HISTORY_YEARS:
        status, level = SourceStatus.DEGRADED, Confidence.LOW
        messages.append(
            f"Bezchmurne zdjęcia z tej pory roku są dostępne tylko z {len(history)} "
            f"z {HISTORY_YEARS} poprzednich lat."
            + (
                " Zdjęcia Sentinel-2 wykonywane są dopiero od połowy 2015 r."
                if any(s.end < MISSION_START for s in slots)
                else ""
            )
        )
        reasons.append("mało lat do porównania")
    if timed_out or failed:
        status = SourceStatus.DEGRADED
        messages.append("Część zdjęć nie została pobrana na czas, wynik jest częściowy.")
    return result(
        NAME,
        status,
        data,
        source=SOURCE,
        license=LICENSE,
        period=period,
        uncertainty=unc(level, "; ".join(reasons).capitalize() + "."),
        message_pl=" ".join(messages) or None,
    )
