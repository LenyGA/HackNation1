"""Elevation grid on synthetic tiles: Copernicus DEM (EPSG:4326) and GUGiK NMT (EPSG:2180). No network."""

from datetime import date
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest
import respx
from affine import Affine
from rasterio.io import MemoryFile

from app.core.cache import DiskCache
from app.core.config import Settings
from app.core.models import Parcel, SourceStatus
from app.sources import dem, planetary
from app.sources.base import METRIC_CRS, SourceError, to_crs
from tests.helpers import metric_square_parcel, write_tif

DATE = date(2025, 6, 15)
# Parcel on the PUWG 1992 central meridian (19°E): grid north == geographic north, no rotation.
LON0, LAT0 = 19.0, 52.0
SLOPE_EAST = 0.02  # 2 % rising to the east
M_PER_DEG_LON = 68_640.0  # at 52°N


@pytest.fixture
def parcel() -> Parcel:
    return metric_square_parcel(LON0, LAT0, 100, 100, METRIC_CRS)


def _cop_tile(root: Path) -> str:
    res = 1 / 3600
    west, north = LON0 - 0.03, LAT0 + 0.03
    n = int(0.06 / res)
    lon = west + (np.arange(n) + 0.5) * res
    z = 100.0 + SLOPE_EAST * M_PER_DEG_LON * (lon - west)
    arr = np.tile(z.astype("float32"), (n, 1))
    return write_tif(root / "cop.tif", arr, Affine(res, 0, west, 0, -res, north), "EPSG:4326", -32767.0)


def _install(monkeypatch: pytest.MonkeyPatch, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bodies: list[dict[str, Any]] = []

    async def token(collection: str) -> str:
        return "tok"

    async def search(body: dict[str, Any]) -> list[dict[str, Any]]:
        bodies.append(body)
        return items

    monkeypatch.setattr(planetary, "get_token", token)
    monkeypatch.setattr(planetary, "search", search)
    return bodies


def _grid(values: list[list[float | None]]) -> np.ndarray:
    return np.array([[np.nan if v is None else v for v in row] for row in values], dtype=float)


async def test_copernicus_grid_in_2180_keeps_tilt(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path, parcel: Parcel
) -> None:
    bodies = _install(
        monkeypatch,
        [
            {
                "id": "Copernicus_DSM_COG_10_N52_00_E019_00_DEM",
                "assets": {"data": {"href": _cop_tile(tmp_path)}},
            }
        ],
    )

    res = await dem.fetch(parcel, DATE)

    assert bodies[0]["collections"] == [dem.COP_COLLECTION]
    assert res.status is SourceStatus.DEGRADED  # 30 m surface model
    assert res.message_pl is not None and "30 m" in res.message_pl
    g = res.data
    assert g is not None
    assert g.crs == "EPSG:2180"
    assert g.dataset == "copernicus_glo30"
    assert g.native_resolution_m == 30.0
    a, b, c, d, e, f = g.transform
    assert (a, b, d, e) == (10.0, 0.0, 0.0, -10.0)
    assert g.width == len(g.elevation_m[0]) and g.height == len(g.elevation_m)
    # Parcel (100 m) + 150 m buffer on each side -> about 400 m / 10 m.
    assert 39 <= g.width <= 42 and 39 <= g.height <= 42
    # The grid covers the buffered parcel.
    geom = to_crs(dem.parcel_shape(parcel), METRIC_CRS)
    minx, miny, maxx, maxy = geom.buffer(dem.BUFFER_M).bounds
    assert c <= minx and f >= maxy
    assert c + a * g.width >= maxx and f + e * g.height <= miny

    z = _grid(g.elevation_m)
    assert np.isfinite(z).all()
    dz_east = np.nanmean(np.diff(z, axis=1)) / a
    dz_south = np.nanmean(np.diff(z, axis=0)) / abs(e)
    assert dz_east == pytest.approx(SLOPE_EAST, rel=0.1)
    assert abs(dz_south) < 0.002


async def test_no_items_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, parcel: Parcel
) -> None:
    _install(monkeypatch, [])
    res = await dem.fetch(parcel, DATE)
    assert res.status is SourceStatus.MISSING
    assert res.data is None
    assert res.message_pl is not None and "Spadków terenu" in res.message_pl


async def test_unreadable_tile_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path, parcel: Parcel
) -> None:
    _install(monkeypatch, [{"id": "x", "assets": {"data": {"href": str(tmp_path / "does-not-exist.tif")}}}])
    res = await dem.fetch(parcel, DATE)
    assert res.status is SourceStatus.MISSING


async def test_catalog_failure_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, parcel: Parcel
) -> None:
    async def token(collection: str) -> str:
        raise SourceError("Serwis danych satelitarnych (Planetary Computer) nie odpowiedział.")

    monkeypatch.setattr(planetary, "get_token", token)
    res = await dem.fetch(parcel, DATE)
    assert res.status is SourceStatus.MISSING


async def test_second_call_served_from_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path, parcel: Parcel
) -> None:
    bodies = _install(monkeypatch, [{"id": "t", "assets": {"data": {"href": _cop_tile(tmp_path)}}}])
    first = await dem.fetch(parcel, DATE)
    second = await dem.fetch(parcel, DATE)
    assert len(bodies) == 1
    assert first.data == second.data


def _nmt_tiff(parcel: Parcel) -> bytes:
    """1 m terrain model in EPSG:2180 rising 5 % to the north."""
    geom = to_crs(dem.parcel_shape(parcel), METRIC_CRS)
    minx, miny, maxx, maxy = geom.buffer(dem.BUFFER_M + 10).bounds
    w, h = int(maxx - minx), int(maxy - miny)
    y = maxy - (np.arange(h) + 0.5)
    z = (200.0 + 0.05 * (y - miny)).astype("float32")
    arr = np.repeat(z[:, None], w, axis=1)
    with MemoryFile() as mf:
        with mf.open(
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype="float32",
            crs="EPSG:2180",
            transform=Affine(1, 0, minx, 0, -1, maxy),
        ) as ds:
            ds.write(arr, 1)
        return bytes(mf.read())


async def test_nmt_used_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, parcel: Parcel
) -> None:
    monkeypatch.setattr(dem, "get_settings", lambda: Settings(dem_try_nmt=True))
    with respx.mock() as mock:
        mock.get(dem.NMT_URL).mock(return_value=httpx.Response(200, content=_nmt_tiff(parcel)))
        res = await dem.fetch(parcel, DATE)

    assert res.status is SourceStatus.OK
    g = res.data
    assert g is not None and g.dataset == "gugik_nmt"
    assert g.resolution_m == 5.0 and g.crs == "EPSG:2180"
    z = _grid(g.elevation_m)
    assert np.isfinite(z).all()
    assert np.nanmean(np.diff(z, axis=0)) / 5.0 == pytest.approx(-0.05, rel=0.05)  # rows run north -> south
    assert abs(np.nanmean(np.diff(z, axis=1))) < 1e-3


async def test_nmt_failure_falls_back_to_copernicus(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path, parcel: Parcel
) -> None:
    monkeypatch.setattr(dem, "get_settings", lambda: Settings(dem_try_nmt=True))
    _install(monkeypatch, [{"id": "t", "assets": {"data": {"href": _cop_tile(tmp_path)}}}])
    with respx.mock() as mock:
        mock.get(dem.NMT_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        res = await dem.fetch(parcel, DATE)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None and res.data.dataset == "copernicus_glo30"
    assert res.message_pl is not None and "NMT" in res.message_pl
