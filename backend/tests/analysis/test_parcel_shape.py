"""G10 / M5.1: parcel length, width and compactness from the geometry (minimum rotated rectangle)."""

import pytest
from shapely import affinity
from shapely.geometry import Polygon, box

from app.analysis.parcel_shape import parcel_shape_metrics


def test_strip_950_by_80_m() -> None:
    s = parcel_shape_metrics(box(0, 0, 950, 80))
    assert s is not None
    assert s.length_m == pytest.approx(950)
    assert s.width_m == pytest.approx(80)
    assert s.compactness == pytest.approx(1.0)
    assert s.elongation == pytest.approx(950 / 80)


def test_square() -> None:
    s = parcel_shape_metrics(box(0, 0, 200, 200))
    assert s is not None
    assert s.length_m == pytest.approx(200) and s.width_m == pytest.approx(200)


def test_rotated_strip_keeps_its_real_sides() -> None:
    s = parcel_shape_metrics(affinity.rotate(box(0, 0, 950, 80), 37, origin="centroid"))
    assert s is not None
    assert s.length_m == pytest.approx(950, rel=1e-3) and s.width_m == pytest.approx(80, rel=1e-3)


def test_l_shape_is_not_compact() -> None:
    l_shape = Polygon([(0, 0), (300, 0), (300, 50), (50, 50), (50, 300), (0, 300)])
    s = parcel_shape_metrics(l_shape)
    assert s is not None and s.compactness < 0.7


def test_empty_geometry() -> None:
    assert parcel_shape_metrics(Polygon()) is None
