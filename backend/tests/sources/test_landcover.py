"""ESA WorldCover shares on synthetic class rasters in EPSG:4326 (no network)."""

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from affine import Affine
from shapely.geometry import box

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.sources import landcover, planetary
from tests.helpers import parcel_from_polygon, write_tif

DATE = date(2025, 6, 15)
RES = 1 / 12000  # WorldCover pixel (~8.3e-5 deg)
WEST, NORTH = 19.0, 52.01
# Parcel = 40 x 40 pixels aligned to the grid, starting 20 px from the tile corner.
P0, PN = 20, 40


def _parcel() -> Parcel:
    w, n = WEST + P0 * RES, NORTH - P0 * RES
    return parcel_from_polygon(box(w, n - PN * RES, w + PN * RES, n))


def _tile(root: Path, name: str, fill: int, west_part: dict[int, int] | None = None) -> str:
    """80x80 tile of `fill`; inside the parcel the first columns get other classes (class -> width in px)."""
    arr = np.full((80, 80), fill, dtype="uint8")
    col = P0
    for cls, width in (west_part or {}).items():
        arr[P0 : P0 + PN, col : col + width] = cls
        col += width
    return write_tif(root / f"{name}.tif", arr, Affine(RES, 0, WEST, 0, -RES, NORTH), "EPSG:4326", 0)


def _item(href: str, start: str) -> dict[str, Any]:
    return {
        "id": f"ESA_WorldCover_10m_{start[:4]}_N51E018",
        "properties": {"start_datetime": start, "end_datetime": f"{start[:4]}-12-31T23:59:59Z"},
        "assets": {"map": {"href": href}},
    }


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


async def test_shares_from_class_raster(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    # Inside the parcel: 10 cols trees, 4 cols built-up, 6 cols grassland, remaining 20 cols cropland.
    href = _tile(tmp_path, "v200", 40, {10: 10, 50: 4, 30: 6})
    bodies = _install(monkeypatch, [_item(href, "2021-01-01T00:00:00Z")])

    res = await landcover.fetch(_parcel(), DATE)

    assert bodies[0]["collections"] == ["esa-worldcover"]
    assert res.status is SourceStatus.OK
    d = res.data
    assert d is not None
    assert d.pixels == PN * PN
    assert d.shares_pct == {"trees": 25.0, "grassland": 15.0, "cropland": 50.0, "built_up": 10.0}
    assert (d.cropland_pct, d.grassland_pct, d.trees_pct, d.built_up_pct) == (50.0, 15.0, 25.0, 10.0)
    assert d.looks_agricultural is True
    assert d.map_year == 2021
    assert res.period is not None and res.period.start.year == 2021
    assert res.message_pl is not None and "2021" in res.message_pl  # single-year map -> limitations


async def test_non_agricultural_parcel_is_degraded(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    href = _tile(tmp_path, "town", 50, {40: 8})  # 80 % built-up, 20 % cropland
    _install(monkeypatch, [_item(href, "2021-01-01T00:00:00Z")])

    res = await landcover.fetch(_parcel(), DATE)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None
    assert res.data.looks_agricultural is False
    assert res.data.built_up_pct == 80.0
    assert res.message_pl is not None and "może nie być użytkowana rolniczo" in res.message_pl


async def test_only_2021_v200_tile_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    v100 = _tile(tmp_path, "v100", 80)  # 2020 map: all water
    v200 = _tile(tmp_path, "v200", 40)  # 2021 map: all cropland
    _install(monkeypatch, [_item(v100, "2020-01-01T00:00:00Z"), _item(v200, "2021-01-01T00:00:00Z")])

    res = await landcover.fetch(_parcel(), DATE)

    assert res.data is not None
    assert res.data.shares_pct == {"cropland": 100.0}


async def test_no_2021_tile_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    _install(monkeypatch, [_item(_tile(tmp_path, "v100", 40), "2020-01-01T00:00:00Z")])
    res = await landcover.fetch(_parcel(), DATE)
    assert res.status is SourceStatus.MISSING
    assert res.data is None


async def test_parcel_across_tile_boundary_sums_both_tiles(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    # Two adjacent tiles split at column 40 (inside the parcel): west cropland, east grassland.
    west = write_tif(
        tmp_path / "w.tif",
        np.full((80, 40), 40, "uint8"),
        Affine(RES, 0, WEST, 0, -RES, NORTH),
        "EPSG:4326",
        0,
    )
    east = write_tif(
        tmp_path / "e.tif",
        np.full((80, 40), 30, "uint8"),
        Affine(RES, 0, WEST + 40 * RES, 0, -RES, NORTH),
        "EPSG:4326",
        0,
    )
    _install(monkeypatch, [_item(west, "2021-01-01T00:00:00Z"), _item(east, "2021-01-01T00:00:00Z")])

    res = await landcover.fetch(_parcel(), DATE)

    assert res.data is not None
    assert res.data.pixels == PN * PN
    assert res.data.shares_pct == {"grassland": 50.0, "cropland": 50.0}


async def test_second_call_served_from_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    bodies = _install(monkeypatch, [_item(_tile(tmp_path, "v200", 40), "2021-01-01T00:00:00Z")])
    first = await landcover.fetch(_parcel(), DATE)
    second = await landcover.fetch(_parcel(), DATE)
    assert len(bodies) == 1
    assert first.data == second.data
