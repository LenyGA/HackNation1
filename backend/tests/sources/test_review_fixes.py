"""Regression tests for fixes from the M2 code review."""

from datetime import date
from typing import Any

from shapely.geometry import Polygon, box

from app.sources import landcover
from app.sources.hydro import element_geometries, summarise
from tests.helpers import parcel_from_polygon


def test_worldcover_edition_never_later_than_needed() -> None:
    assert landcover.map_year_for(date(2024, 7, 1)) == 2021
    assert landcover.map_year_for(date(2021, 6, 1)) == 2020
    assert landcover.map_year_for(date(2017, 6, 1)) == 2020  # oldest available, mismatch stated


def _ring(poly: Polygon) -> list[dict[str, float]]:
    return [{"lon": x, "lat": y} for x, y in poly.exterior.coords]


def test_field_in_forest_clearing_is_not_inside_forest() -> None:
    forest = box(17.30, 52.30, 17.40, 52.40)
    clearing = box(17.34, 52.34, 17.36, 52.36)
    rel: dict[str, Any] = {
        "type": "relation",
        "id": 1,
        "tags": {"natural": "wood"},
        "members": [
            {"type": "way", "role": "outer", "geometry": _ring(forest)},
            {"type": "way", "role": "inner", "geometry": _ring(clearing)},
        ],
    }
    (geom,) = element_geometries(rel, "trees")
    assert geom.area < forest.area
    parcel = parcel_from_polygon(box(17.349, 52.349, 17.351, 52.351))
    data = summarise([rel], parcel_from_polygon_shape(parcel))
    nearest = data.nearest_m["trees"]
    assert nearest is not None and nearest > 500


def test_outer_ring_split_over_two_ways_becomes_polygon() -> None:
    coords = list(box(17.30, 52.30, 17.40, 52.40).exterior.coords)
    first, second = coords[:3], coords[2:]
    rel: dict[str, Any] = {
        "type": "relation",
        "id": 2,
        "tags": {"natural": "wetland"},
        "members": [
            {"type": "way", "role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in first]},
            {"type": "way", "role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in second]},
        ],
    }
    parcel = parcel_from_polygon(box(17.349, 52.349, 17.351, 52.351))
    data = summarise([rel], parcel_from_polygon_shape(parcel))
    assert data.nearest_m["wetland"] == 0.0


def parcel_from_polygon_shape(parcel: Any) -> Any:
    from shapely.geometry import shape

    return shape(parcel.geometry)
