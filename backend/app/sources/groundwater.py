"""Groundwater level near the parcel: the nearest automatic monitoring station of the Polish Hydrogeological
Survey (PSH, PIG-PIB) within SEARCH_RADIUS_M that has measurements before the analysis date.

- Stations: ArcGIS REST layer mwp_auto/0 (EPSG:2180).
- Measurements: mwp_auto/2 (PSH_MONITORING_ID, TIME, VALUE in m). The automatic series is published without
  validation. VALUE is the depth of the water table below ground (it matches the manual depth readings), so a
  growing value means a falling water table.
- Trend without downloading the hourly series: server-side averages (outStatistics) over the WINDOW_DAYS
  before
  the analysis date and over the same windows 1, 2 and 3 years earlier (same season, no seasonal bias).
  Only measurements on or before the analysis date are used (CLAUDE.md rule 3).
"""

import asyncio
import logging
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from app.analysis.series import same_day_in_year
from app.core.cache import get_cache
from app.core.http import request
from app.core.models import Confidence, Parcel, Period, SourceResult, SourceStatus
from app.sources.base import METRIC_CRS, cache_ttl, missing, parcel_shape, result, to_crs, unc, within_budget

log = logging.getLogger(__name__)

NAME = "groundwater"
BASE = "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/mwp_auto/MapServer"
SOURCE = (
    "PIG-PIB, Państwowa Służba Hydrogeologiczna — automatyczny monitoring wód podziemnych "
    "(dane bez walidacji), "
    "https://cbdgmapa.pgi.gov.pl/"
)
LICENSE = "Dane publiczne PIG-PIB, bezpłatne, z podaniem źródła"
SEARCH_RADIUS_M = 50_000.0
MAX_STATIONS = 3  # nearest stations queried (3 × 4 window queries in parallel)
# A trend is taken from a station at most this far; farther away only the level is reported.
TREND_MAX_KM = 25.0
WINDOW_DAYS = 60
YEARS_BACK = 3
TIMEOUT_S = 4.0  # per query; stations then windows → worst case ~8 s within BUDGET_S
BUDGET_S = 9.0
STABLE_M = 0.15  # change of the mean depth smaller than this over the period: "stable"
MIN_COUNT = 10  # measurements needed in a window
MIN_SPAN_SHARE = 0.7  # first-to-last measurement must cover this share of the window

Trend = Literal["falling", "stable", "rising"]


class GroundwaterData(BaseModel):
    station_id: int
    station_name: str
    distance_km: float
    depth_now_m: float
    depth_before_m: float | None  # None: the station has no measurements from previous years
    years_compared: int
    change_m: float | None  # positive = water table higher than before
    trend: Trend | None
    window_start: date
    window_end: date


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


async def _query(layer: int, params: dict[str, str]) -> dict[str, Any]:
    resp = await request(
        "GET", f"{BASE}/{layer}/query", params={**params, "f": "json"}, timeout_s=TIMEOUT_S, retries=0
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    if "error" in data:
        raise httpx.HTTPError(str(data["error"])[:120])
    return data


async def _stations(x: float, y: float) -> list[tuple[float, int, str]]:
    r = SEARCH_RADIUS_M
    data = await _query(
        0,
        {
            "geometry": f"{x - r},{y - r},{x + r},{y + r}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": str(METRIC_CRS),
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ID_PKT_MWP,MIEJSCOWOSC,WSP_X_1992,WSP_Y_1992",
            "returnGeometry": "false",
        },
    )
    out: list[tuple[float, int, str]] = []
    for f in data.get("features", []):
        a = f.get("attributes", {})
        sx, sy, sid = a.get("WSP_X_1992"), a.get("WSP_Y_1992"), a.get("ID_PKT_MWP")
        if sx is None or sy is None or sid is None:
            continue
        dist = math.hypot(float(sx) - x, float(sy) - y)
        if dist <= SEARCH_RADIUS_M:
            out.append((dist, int(sid), str(a.get("MIEJSCOWOSC") or "").strip()))
    out.sort()
    return out[:MAX_STATIONS]


async def _window_mean(station_id: int, end: date) -> float | None:
    start = end - timedelta(days=WINDOW_DAYS - 1)
    data = await _query(
        2,
        {
            "where": (
                f"PSH_MONITORING_ID={station_id} AND TIME >= TIMESTAMP '{start.isoformat()} 00:00:00' "
                f"AND TIME < TIMESTAMP '{(end + timedelta(days=1)).isoformat()} 00:00:00'"
            ),
            "outStatistics": (
                '[{"statisticType":"avg","onStatisticField":"VALUE","outStatisticFieldName":"m"},'
                '{"statisticType":"count","onStatisticField":"VALUE","outStatisticFieldName":"n"},'
                '{"statisticType":"min","onStatisticField":"TIME","outStatisticFieldName":"t0"},'
                '{"statisticType":"max","onStatisticField":"TIME","outStatisticFieldName":"t1"}]'
            ),
        },
    )
    feats = data.get("features") or []
    if not feats:
        return None
    a = feats[0].get("attributes", {})
    if (a.get("n") or 0) < MIN_COUNT or a.get("m") is None:
        return None
    # The measurements must span most of the window (a week of readings is not a 2-month mean).
    t0, t1 = a.get("t0"), a.get("t1")
    if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
        return None
    if (t1 - t0) / 86_400_000 < MIN_SPAN_SHARE * WINDOW_DAYS:
        return None
    return float(a["m"])


async def _station_trend(station_id: int, day: date) -> tuple[float, float | None, int] | None:
    """(mean depth now, mean depth in the same window k years earlier, k); None without current data."""
    ends = [same_day_in_year(day, day.year - k) for k in range(YEARS_BACK + 1)]
    means = await asyncio.gather(*(_window_mean(station_id, e) for e in ends))
    now = means[0]
    if now is None:
        return None
    for k in range(YEARS_BACK, 0, -1):
        before = means[k]
        if before is not None:
            return now, before, k
    return now, None, 0


def classify(change_m: float) -> Trend:
    if abs(change_m) < STABLE_M:
        return "stable"
    return "rising" if change_m > 0 else "falling"


async def _fetch(parcel: Parcel, day: date) -> SourceResult[GroundwaterData]:
    c = to_crs(parcel_shape(parcel), METRIC_CRS).centroid
    cache = get_cache()
    params = {"x": round(c.x, -2), "y": round(c.y, -2), "day": day.isoformat(), "v": 1}
    cached = cache.get(NAME, params)
    data: GroundwaterData | None = GroundwaterData.model_validate(cached) if cached is not None else None
    if data is None:
        try:
            stations = await _stations(c.x, c.y)
        except httpx.HTTPError:
            return missing(
                NAME,
                source=SOURCE,
                license=LICENSE,
                message_pl="Usługa monitoringu wód podziemnych (PIG-PIB) nie odpowiedziała. "
                "Poziomu wód podziemnych nie sprawdzono.",
            )
        trends = await asyncio.gather(
            *(_station_trend(sid, day) for _, sid, _ in stations), return_exceptions=True
        )
        fallback: GroundwaterData | None = None
        for (dist, sid, name), tr in zip(stations, trends, strict=True):
            if isinstance(tr, BaseException) or tr is None:
                continue
            now, before, years = tr
            change = None if before is None else before - now  # depth decreased → water table rose
            candidate = GroundwaterData(
                station_id=sid,
                station_name=name or f"punkt {sid}",
                distance_km=round(dist / 1000, 1),
                depth_now_m=round(now, 2),
                depth_before_m=None if before is None else round(before, 2),
                years_compared=years,
                change_m=None if change is None else round(change, 2),
                trend=None if change is None else classify(change),
                window_start=day - timedelta(days=WINDOW_DAYS - 1),
                window_end=day,
            )
            if candidate.trend is not None and candidate.distance_km <= TREND_MAX_KM:
                data = candidate
                break
            if candidate.trend is not None:
                # Too far for a trend: report the level only (the station may tap a different aquifer).
                candidate = candidate.model_copy(
                    update={"trend": None, "change_m": None, "depth_before_m": None}
                )
            fallback = fallback or candidate
        data = data or fallback
        if data is None:
            return missing(
                NAME,
                source=SOURCE,
                license=LICENSE,
                message_pl=(
                    f"W promieniu {SEARCH_RADIUS_M / 1000:.0f} km nie ma stacji automatycznego "
                    "monitoringu wód "
                    "podziemnych z pomiarami sprzed daty analizy (wiele stacji mierzy dopiero od niedawna). "
                    "Poziomu wód podziemnych nie oceniamy."
                ),
            )
        cache.set(NAME, params, data.model_dump(mode="json"), cache_ttl(day))
    return result(
        NAME,
        SourceStatus.OK if data.trend is not None else SourceStatus.DEGRADED,
        data,
        source=SOURCE,
        license=LICENSE,
        period=Period(start=data.window_start, end=data.window_end),
        message_pl=None
        if data.trend is not None
        else (
            "Najbliższa stacja nie ma pomiarów z poprzednich lat (albo jest za daleko), "
            "więc kierunku zmian poziomu wody nie oceniamy."
        ),
        uncertainty=unc(
            Confidence.MEDIUM if data.distance_km <= 20 and data.trend is not None else Confidence.LOW,
            f"Stacja ok. {data.distance_km:.0f} km od działki; dane automatyczne bez walidacji. Poziom wody "
            "w studni pomiarowej opisuje okolicę, a nie samą działkę.",
        ),
    )


async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[GroundwaterData]:
    return await within_budget(
        NAME,
        _fetch(parcel, analysis_date),
        BUDGET_S,
        lambda: missing(
            NAME,
            source=SOURCE,
            license=LICENSE,
            message_pl=(
                "Dane o wodach podziemnych nie zostały pobrane na czas. Poziomu wód podziemnych nie oceniamy."
            ),
        ),
    )
