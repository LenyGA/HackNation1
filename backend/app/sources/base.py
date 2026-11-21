"""Helpers shared by all source modules: building SourceResult values, cache TTL policy, geometry projection.

Source modules only fetch, parse and normalise units. They never invent values: when data is unavailable the
result is `missing` with a Polish message for the farmer.
"""

import asyncio
import hashlib
import json
import logging
import threading
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.core.cache import CURRENT_DATA_TTL
from app.core.config import today_local
from app.core.models import Confidence, Parcel, Period, SourceResult, SourceStatus, Uncertainty

# Data for dates closer to "today" than this may still be revised by providers (e.g. ERA5T), so it gets a TTL.
RECENT_DATA_WINDOW = timedelta(days=10)

log = logging.getLogger(__name__)

# Poland-wide metric CRS (PUWG 1992). Used for areas, distances and terrain grids.
METRIC_CRS = 2180


class SourceError(Exception):
    """Raised inside a source module when the provider failed; carries a message for the farmer."""

    def __init__(self, message_pl: str) -> None:
        super().__init__(message_pl)
        self.message_pl = message_pl


def now_utc() -> datetime:
    return datetime.now(UTC)


def cache_ttl(analysis_date: date, today: date | None = None) -> timedelta | None:
    """Historical data never expires; data touching the last days before today is cached briefly."""
    today = today or today_local()
    return CURRENT_DATA_TTL if analysis_date >= today - RECENT_DATA_WINDOW else None


def geometry_hash(geometry: dict[str, Any]) -> str:
    """Stable short hash of a GeoJSON geometry, used in cache keys."""
    canonical = json.dumps(geometry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def parcel_shape(parcel: Parcel) -> BaseGeometry:
    return shape(parcel.geometry)


_local = threading.local()


def _transformer(src_crs: Any, dst_crs: Any) -> Transformer:
    """Per-thread Transformer cache (pyproj Transformers must not be shared between threads)."""
    cache: dict[tuple[Any, Any], Transformer] | None = getattr(_local, "transformers", None)
    if cache is None:
        cache = _local.transformers = {}
    tr = cache.get((src_crs, dst_crs))
    if tr is None:
        tr = cache[(src_crs, dst_crs)] = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return tr


def to_crs(geom: BaseGeometry, dst_crs: Any, src_crs: Any = 4326) -> BaseGeometry:
    """Reproject a shapely geometry (lon/lat order for EPSG:4326). Transformers are cached per CRS pair."""
    return shapely.transform(geom, _transformer(src_crs, dst_crs).transform, interleaved=False)


def unc(level: Confidence, reason_pl: str) -> Uncertainty:
    return Uncertainty(level=level, reason_pl=reason_pl)


def result[T](
    name: str,
    status: SourceStatus,
    data: T | None,
    *,
    source: str,
    license: str,
    uncertainty: Uncertainty,
    period: Period | None = None,
    message_pl: str | None = None,
) -> SourceResult[T]:
    return SourceResult[T](
        name=name,
        status=status,
        source=source,
        license=license,
        fetched_at=now_utc(),
        period=period,
        uncertainty=uncertainty,
        message_pl=message_pl,
        data=data,
    )


def missing[T](
    name: str,
    *,
    source: str,
    license: str,
    message_pl: str,
    reason_pl: str | None = None,
    period: Period | None = None,
) -> SourceResult[T]:
    return result(
        name,
        SourceStatus.MISSING,
        None,
        source=source,
        license=license,
        period=period,
        uncertainty=unc(Confidence.LOW, reason_pl or message_pl),
        message_pl=message_pl,
    )


async def within_budget[T](
    name: str,
    coro: Awaitable[SourceResult[T]],
    budget_s: float,
    on_timeout: Callable[[], SourceResult[T]],
) -> SourceResult[T]:
    """Hard time limit for a whole source: on timeout return `on_timeout()` (a `missing` result)."""
    try:
        return await asyncio.wait_for(coro, budget_s)
    except TimeoutError:
        log.warning("source %s exceeded its %.0f s budget", name, budget_s)
        return on_timeout()
