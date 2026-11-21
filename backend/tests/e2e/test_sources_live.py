"""Live smoke test: every M2 source for one reference parcel on a historical date (needs network)."""

import asyncio
import time
from datetime import date
from typing import Any

import pytest

from app.core.cache import DiskCache
from app.core.models import SourceResult, SourceStatus
from app.sources import dem, hydro, landcover, open_meteo, sentinel2, soilgrids, uldk

PARCEL_ID = "302108_5.0014.88/8"
ANALYSIS_DATE = date(2024, 7, 15)
BUDGET_S = 30.0


@pytest.mark.e2e
async def test_all_sources_for_reference_parcel(tmp_cache: DiskCache) -> None:
    t0 = time.perf_counter()
    parcel = await uldk.get_parcel_by_id(PARCEL_ID)
    assert parcel.id == PARCEL_ID

    results: list[SourceResult[Any]] = list(
        await asyncio.gather(
            open_meteo.fetch(parcel, ANALYSIS_DATE),
            sentinel2.fetch(parcel, ANALYSIS_DATE),
            soilgrids.fetch(parcel, ANALYSIS_DATE),
            dem.fetch(parcel, ANALYSIS_DATE),
            hydro.fetch(parcel, ANALYSIS_DATE),
            landcover.fetch(parcel, ANALYSIS_DATE),
        )
    )
    elapsed = time.perf_counter() - t0

    for r in results:
        print(f"{r.name:12s} {r.status.value:9s} {r.uncertainty.level.value:6s} {r.message_pl or ''}")
    print(f"total {elapsed:.1f} s")

    assert elapsed < BUDGET_S
    for r in results:
        assert isinstance(r, SourceResult)
        assert r.status in set(SourceStatus)
        assert (r.data is None) == (r.status is SourceStatus.MISSING)
        if r.status is not SourceStatus.OK:
            assert r.message_pl
    weather = results[0]
    if weather.data is not None:
        assert weather.data.daily.dates[-1] == ANALYSIS_DATE
