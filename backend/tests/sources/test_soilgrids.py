"""SoilGrids WCS source. sand 0-5 cm is a recorded response; the other coverages are synthetic 3x3 tiles
on the same grid (generated in memory)."""

import asyncio
from collections.abc import Callable
from datetime import date

import httpx
import numpy as np
import pytest
import respx
from affine import Affine
from rasterio.io import MemoryFile

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.sources import soilgrids
from tests.helpers import FIXTURES

LAT, LON = 52.40017, 17.35004
DATE = date(2025, 6, 15)  # soil is static; the date only keeps the common signature
RECORDED = (FIXTURES / "soilgrids" / "sand_0-5cm_52.40017_17.35004.tif").read_bytes()
TRANSFORM = Affine(0.002, 0.0, 17.34704, 0.0, -0.002, 52.40317)
# Mapped units: g/kg (texture), dg/kg (SOC), cg/cm3 (bulk density).
MAPPED = {"sand": 759, "silt": 170, "clay": 71, "soc": 152, "bdod": 145}


def _tiff(values: np.ndarray) -> bytes:
    with MemoryFile() as mf:
        with mf.open(
            driver="GTiff", height=3, width=3, count=1, dtype="int16", crs="EPSG:4326", transform=TRANSFORM
        ) as ds:
            ds.write(values.astype("int16"), 1)
        return bytes(mf.read())


def _parcel() -> Parcel:
    return Parcel(
        id="302108_5.0014.88/8",
        area_ha=0.36,
        centroid_lat=LAT,
        centroid_lon=LON,
        geometry={"type": "Point", "coordinates": [LON, LAT]},
    )


def _responder(grid: Callable[[str], np.ndarray]) -> Callable[[httpx.Request], httpx.Response]:
    def respond(request: httpx.Request) -> httpx.Response:
        coverage = request.url.params["COVERAGEID"]
        if coverage == "sand_0-5cm_mean":
            return httpx.Response(200, content=RECORDED)
        return httpx.Response(200, content=_tiff(grid(coverage)))

    return respond


def _uniform(coverage: str) -> np.ndarray:
    return np.full((3, 3), MAPPED[coverage.split("_")[0]])


def test_recorded_tile_centre_value() -> None:
    assert soilgrids.parse_tiff(RECORDED, LAT, LON) == (759.0, False)


def test_pick_value_uses_nearest_neighbour_for_zero() -> None:
    arr = np.array([[0, 0, 0], [0, 0, 420], [0, 0, 0]])
    assert soilgrids.pick_value(arr, 1, 1) == (420.0, True)
    assert soilgrids.pick_value(np.zeros((3, 3)), 1, 1) == (None, False)


async def test_units_converted_to_field_units(tmp_cache: DiskCache) -> None:
    with respx.mock() as mock:
        route = mock.get(soilgrids.WCS_URL).mock(side_effect=_responder(_uniform))
        res = await soilgrids.fetch(_parcel(), DATE)

    assert route.call_count == len(soilgrids.PROPERTIES) * len(soilgrids.DEPTHS)
    assert res.status is SourceStatus.OK
    assert res.uncertainty.level.value == "medium"  # 250 m grid: never high
    assert res.data is not None
    top = res.data.layers[0]
    assert (top.depth_top_cm, top.depth_bottom_cm) == (0, 5)
    assert top.sand_pct == 75.9
    assert top.silt_pct == 17.0
    assert top.clay_pct == 7.1
    assert top.soc_g_per_kg == 15.2
    assert top.bulk_density_g_per_cm3 == 1.45
    assert [(lyr.depth_top_cm, lyr.depth_bottom_cm) for lyr in res.data.layers][-1] == (60, 100)
    assert res.data.neighbour_used is False


async def test_zero_at_centroid_uses_neighbour_and_is_degraded(tmp_cache: DiskCache) -> None:
    def holes(coverage: str) -> np.ndarray:
        arr = _uniform(coverage)
        if coverage.startswith("clay"):
            arr[1, 1] = 0  # built-up / water cell at the centroid
            arr[0, :] = 0
            arr[2, :] = 0
            arr[1, 0] = 0
            arr[1, 2] = 88
        return arr

    with respx.mock() as mock:
        mock.get(soilgrids.WCS_URL).mock(side_effect=_responder(holes))
        res = await soilgrids.fetch(_parcel(), DATE)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None and res.data.neighbour_used
    assert res.data.layers[0].clay_pct == 8.8
    assert res.message_pl is not None and "najbliższej komórki" in res.message_pl


async def test_all_requests_failing_is_missing(tmp_cache: DiskCache) -> None:
    with respx.mock() as mock:
        mock.get(soilgrids.WCS_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        res = await soilgrids.fetch(_parcel(), DATE)

    assert res.status is SourceStatus.MISSING
    assert res.data is None
    assert res.message_pl is not None and "nie odpowiedział" in res.message_pl


async def test_hard_timeout_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache) -> None:
    monkeypatch.setattr(soilgrids, "TIMEOUT_S", 0.2)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, content=RECORDED)

    with respx.mock(assert_all_called=False) as mock:
        mock.get(soilgrids.WCS_URL).mock(side_effect=slow)
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        res = await soilgrids.fetch(_parcel(), DATE)
        elapsed = loop.time() - t0

    assert elapsed < 2
    assert res.status is SourceStatus.MISSING


async def test_partial_failure_is_degraded_and_not_cached(tmp_cache: DiskCache) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params["COVERAGEID"].startswith("bdod"):
            return httpx.Response(500)
        return _responder(_uniform)(request)

    with respx.mock() as mock:
        route = mock.get(soilgrids.WCS_URL).mock(side_effect=respond)
        res = await soilgrids.fetch(_parcel(), DATE)
        await soilgrids.fetch(_parcel(), DATE)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None
    assert all(lyr.bulk_density_g_per_cm3 is None for lyr in res.data.layers)
    assert res.data.layers[0].sand_pct == 75.9
    assert route.call_count == 2 * 25  # incomplete results are not cached


async def test_second_call_served_from_cache(tmp_cache: DiskCache) -> None:
    with respx.mock() as mock:
        route = mock.get(soilgrids.WCS_URL).mock(side_effect=_responder(_uniform))
        first = await soilgrids.fetch(_parcel(), DATE)
        second = await soilgrids.fetch(_parcel(), DATE)
    assert route.call_count == 25
    assert first.data == second.data
