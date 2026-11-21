"""Sentinel-2 source on synthetic UTM GeoTIFFs (no network): planetary.search/get_token are monkeypatched."""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from affine import Affine
from dateutil.relativedelta import relativedelta

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.sources import planetary, sentinel2
from app.sources.base import SourceError, to_crs
from tests.helpers import metric_square_parcel, write_tif

EPSG = 32633
ANALYSIS_DATE = date(2025, 7, 15)
TODAY = date(2026, 11, 21)
# Surface reflectance used in every clear scene: red 0.05, NIR 0.30, SWIR 0.15.
RED, NIR, SWIR = 500, 3000, 1500
EXPECTED_NDVI = round((NIR - RED) / (NIR + RED), 3)
EXPECTED_NDMI = round((NIR - SWIR) / (NIR + SWIR), 3)


def _parcel(width_m: float, height_m: float) -> Parcel:
    return metric_square_parcel(15.0, 52.0, width_m, height_m, EPSG)


def _write_scene(
    root: Path, name: str, parcel: Parcel, *, red: int, nir: int, swir: int, scl: int, offset: int
) -> dict[str, dict[str, str]]:
    """10 m B04/B08 and 20 m B11/SCL around the parcel; grid origin on a multiple of 60 m like S2 tiles."""
    geom = to_crs(sentinel2.parcel_shape(parcel), EPSG)
    minx, miny, maxx, maxy = geom.bounds
    x0 = math.floor((minx - 300) / 60) * 60
    y1 = math.ceil((maxy + 300) / 60) * 60
    x1 = math.ceil((maxx + 300) / 60) * 60
    y0 = math.floor((miny - 300) / 60) * 60
    assets: dict[str, dict[str, str]] = {}
    for band, value, res in (("B04", red, 10), ("B08", nir, 10), ("B11", swir, 20), ("SCL", scl, 20)):
        h, w = (y1 - y0) // res, (x1 - x0) // res
        dn = value if band == "SCL" else value - offset
        arr = np.full((h, w), dn, dtype="uint16" if band != "SCL" else "uint8")
        path = write_tif(root / f"{name}_{band}.tif", arr, Affine(res, 0, x0, 0, -res, y1), f"EPSG:{EPSG}", 0)
        assets[band] = {"href": path}
    return assets


def _item(scene_id: str, day: date, baseline: str, assets: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {
        "id": scene_id,
        "properties": {
            "datetime": f"{day.isoformat()}T10:05:31.024000Z",
            "proj:epsg": EPSG,
            "s2:processing_baseline": baseline,
            "eo:cloud_cover": 3.0,
        },
        "assets": assets,
    }


@dataclass
class FakeCatalog:
    items: list[dict[str, Any]]
    # Returned for every query regardless of the date range (a misbehaving catalog).
    always: list[dict[str, Any]] = field(default_factory=list)
    bodies: list[dict[str, Any]] = field(default_factory=list)

    async def search(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        self.bodies.append(body)
        lo, hi = (date.fromisoformat(s[:10]) for s in body["datetime"].split("/"))
        hits = [it for it in self.items if lo <= sentinel2._item_date(it) <= hi]
        return hits + self.always


class Scenes:
    def __init__(self, root: Path, parcel: Parcel) -> None:
        self.parcel = parcel
        # DN = reflectance * 10000 (+1000 since baseline 04.00)
        self.old = _write_scene(root, "old", parcel, red=RED, nir=NIR, swir=SWIR, scl=4, offset=0)
        self.new = _write_scene(root, "new", parcel, red=RED, nir=NIR, swir=SWIR, scl=4, offset=-1000)
        self.cloudy = _write_scene(root, "cloudy", parcel, red=RED, nir=NIR, swir=SWIR, scl=9, offset=-1000)
        self.other = _write_scene(root, "future", parcel, red=2000, nir=2500, swir=2000, scl=4, offset=-1000)

    def clear(self, scene_id: str, day: date) -> dict[str, Any]:
        if day >= date(2022, 1, 25):
            return _item(scene_id, day, "05.10", self.new)
        return _item(scene_id, day, "02.14", self.old)

    def history(self) -> list[dict[str, Any]]:
        return [
            self.clear(f"hist-{y}", ANALYSIS_DATE - relativedelta(years=y) + timedelta(days=3))
            for y in range(1, 11)
        ]


def _install(monkeypatch: pytest.MonkeyPatch, catalog: FakeCatalog) -> None:
    async def token(collection: str) -> str:
        return "st=fake&sig=fake"

    monkeypatch.setattr(planetary, "get_token", token)
    monkeypatch.setattr(planetary, "search", catalog.search)


@pytest.fixture
def scenes(tmp_path: Path) -> Scenes:
    return Scenes(tmp_path, _parcel(100, 100))


def test_boa_offset_by_processing_baseline() -> None:
    assert sentinel2.boa_offset({"properties": {"s2:processing_baseline": "04.00"}}) == -1000.0
    assert sentinel2.boa_offset({"properties": {"s2:processing_baseline": "05.10"}}) == -1000.0
    assert sentinel2.boa_offset({"properties": {"s2:processing_baseline": "02.14"}}) == 0.0
    assert sentinel2.boa_offset({"properties": {}}) == 0.0


def test_same_reflectance_gives_same_ndvi_for_old_and_new_baseline() -> None:
    inside = np.ones((3, 3), dtype=bool)
    scl = np.full((3, 3), 4)

    def full(v: int) -> np.ndarray:
        return np.full((3, 3), v, dtype="uint16")

    old = sentinel2.compute_indices(full(RED), full(NIR), full(SWIR), scl, inside, 0.0)
    new = sentinel2.compute_indices(
        full(RED + 1000), full(NIR + 1000), full(SWIR + 1000), scl, inside, -1000.0
    )
    assert old[0] == pytest.approx(new[0])
    assert old[1] == pytest.approx(new[1])
    assert old[0] == pytest.approx(EXPECTED_NDVI, abs=1e-3)


def test_scl_masks_cloudy_pixels() -> None:
    inside = np.ones((2, 2), dtype=bool)
    scl = np.array([[4, 9], [8, 5]])
    red = np.array([[RED, 9000], [9000, RED]], dtype="uint16")
    nir = np.array([[NIR, 9000], [9000, NIR]], dtype="uint16")
    ndvi, _, clear, total = sentinel2.compute_indices(red, nir, None, scl, inside, 0.0)
    assert (clear, total) == (2, 4)
    assert ndvi == pytest.approx(EXPECTED_NDVI, abs=1e-3)


async def test_full_profile_ok(monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, scenes: Scenes) -> None:
    current_clear = scenes.clear("cur-clear", ANALYSIS_DATE - timedelta(days=5))
    cloudy = _item("cur-cloudy", ANALYSIS_DATE - timedelta(days=2), "05.10", scenes.cloudy)
    future = _item("future", ANALYSIS_DATE + timedelta(days=5), "05.10", scenes.other)
    catalog = FakeCatalog(items=[current_clear, cloudy, *scenes.history()], always=[future])
    _install(monkeypatch, catalog)

    res = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)

    assert res.status is SourceStatus.OK, res.message_pl
    assert res.data is not None
    # Cloudy scene rejected by SCL, future scene never used.
    assert [s.scene_id for s in res.data.current] == ["cur-clear"]
    used = res.data.current + res.data.history
    assert all(s.date <= ANALYSIS_DATE for s in used)
    assert "future" not in {s.scene_id for s in used}
    # Same reflectance before and after baseline 04.00 -> same NDVI everywhere.
    assert {s.ndvi_mean for s in used} == {EXPECTED_NDVI}
    assert {s.ndmi_mean for s in used} == {EXPECTED_NDMI}
    assert res.data.years_with_data == 10
    assert [s.date.year for s in res.data.history] == list(range(2015, 2025))
    assert 90 <= res.data.parcel_pixels <= 110
    assert res.data.current[0].clear_share == 1.0
    # The search itself never asks for dates after analysis_date.
    for body in catalog.bodies:
        assert date.fromisoformat(body["datetime"].split("/")[1][:10]) <= ANALYSIS_DATE


async def test_only_cloudy_current_scene_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, scenes: Scenes
) -> None:
    cloudy = _item("cur-cloudy", ANALYSIS_DATE - timedelta(days=2), "05.10", scenes.cloudy)
    _install(monkeypatch, FakeCatalog(items=[cloudy, *scenes.history()]))

    res = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)

    assert res.status is SourceStatus.MISSING
    assert res.data is None
    assert res.message_pl is not None and "chmur" in res.message_pl


async def test_small_parcel_is_degraded(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path
) -> None:
    small = Scenes(tmp_path, _parcel(20, 30))
    catalog = FakeCatalog(items=[small.clear("cur", ANALYSIS_DATE - timedelta(days=1)), *small.history()])
    _install(monkeypatch, catalog)

    res = await sentinel2.fetch(small.parcel, ANALYSIS_DATE, today=TODAY)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None
    assert 0 < res.data.parcel_pixels < sentinel2.MIN_PARCEL_PIXELS
    assert res.message_pl is not None and "pikseli" in res.message_pl
    assert res.uncertainty.level.value == "low"


async def test_few_history_years_is_degraded(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, scenes: Scenes
) -> None:
    catalog = FakeCatalog(
        items=[scenes.clear("cur", ANALYSIS_DATE - timedelta(days=1)), *scenes.history()[:2]]
    )
    _install(monkeypatch, catalog)

    res = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None and res.data.years_with_data == 2


async def test_second_call_served_from_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, scenes: Scenes
) -> None:
    catalog = FakeCatalog(items=[scenes.clear("cur", ANALYSIS_DATE - timedelta(days=1)), *scenes.history()])
    _install(monkeypatch, catalog)

    first = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)
    n_searches = len(catalog.bodies)
    second = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)

    assert n_searches == 11
    assert len(catalog.bodies) == n_searches  # no new search: every slot came from cache
    assert first.data == second.data


async def test_token_failure_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache) -> None:
    async def token(collection: str) -> str:
        raise SourceError("Serwis danych satelitarnych (Planetary Computer) nie odpowiedział.")

    monkeypatch.setattr(planetary, "get_token", token)
    res = await sentinel2.fetch(_parcel(100, 100), ANALYSIS_DATE, today=TODAY)
    assert res.status is SourceStatus.MISSING
    assert res.message_pl is not None and "Planetary Computer" in res.message_pl


async def test_catalog_down_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache) -> None:
    async def token(collection: str) -> str:
        return "tok"

    async def search(body: dict[str, Any]) -> list[dict[str, Any]]:
        raise SourceError("Katalog danych satelitarnych (Planetary Computer) nie odpowiedział.")

    monkeypatch.setattr(planetary, "get_token", token)
    monkeypatch.setattr(planetary, "search", search)
    res = await sentinel2.fetch(_parcel(100, 100), ANALYSIS_DATE, today=TODAY)
    assert res.status is SourceStatus.MISSING
    assert res.data is None


async def test_scene_clipped_at_tile_edge_is_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_cache: DiskCache, tmp_path: Path, scenes: Scenes
) -> None:
    """A tile covering only part of the parcel must not be stretched over it; the scene is skipped."""
    geom = to_crs(sentinel2.parcel_shape(scenes.parcel), EPSG)
    minx, _, _, maxy = geom.bounds
    x0 = math.floor((minx - 300) / 60) * 60
    y1 = math.ceil((maxy + 300) / 60) * 60
    edge = int(math.floor((minx + 40) / 60) * 60)  # tile ends inside the parcel
    assets: dict[str, dict[str, str]] = {}
    for band, value, res in (("B04", RED, 10), ("B08", NIR, 10), ("B11", SWIR, 20), ("SCL", 4, 20)):
        arr = np.full((60, (edge - x0) // res), value, dtype="uint16")
        path = write_tif(
            tmp_path / f"edge_{band}.tif", arr, Affine(res, 0, x0, 0, -res, y1), f"EPSG:{EPSG}", 0
        )
        assets[band] = {"href": path}
    clipped = _item("edge", ANALYSIS_DATE - timedelta(days=1), "02.14", assets)
    _install(monkeypatch, FakeCatalog(items=[clipped, *scenes.history()]))

    res = await sentinel2.fetch(scenes.parcel, ANALYSIS_DATE, today=TODAY)

    assert res.status is SourceStatus.MISSING
