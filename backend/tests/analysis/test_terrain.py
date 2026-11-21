from collections.abc import Callable

import numpy as np
import pytest
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

from app.analysis.terrain import analyse_terrain, compass, priority_flood
from app.sources.base import METRIC_CRS, parcel_shape, to_crs
from tests.analysis.builders import grid_around
from tests.helpers import metric_square_parcel, parcel_from_polygon

SLOPE = 0.02  # 2 % downhill to the east
BASIN_R_M = 40.0
BASIN_DEPTH_M = 3.0


def _parcel_geom() -> BaseGeometry:
    return parcel_shape(metric_square_parcel(17.35, 52.4, 200, 150, METRIC_CRS))


def _basin_surface(geom: BaseGeometry) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    g = to_crs(geom, METRIC_CRS)
    x0 = g.bounds[0]
    cx, cy = g.centroid.x, g.centroid.y

    def z(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        r2 = ((x - cx) ** 2 + (y - cy) ** 2) / BASIN_R_M**2
        bowl = np.where(r2 < 1, BASIN_DEPTH_M * (1 - r2), 0.0)
        return 100 - SLOPE * (x - x0) - bowl

    return z


def test_tilted_plane_with_basin() -> None:
    geom = _parcel_geom()
    grid = grid_around(geom, _basin_surface(geom))
    res = analyse_terrain(grid, geom)
    assert res is not None
    assert res.aspect == "E"
    assert res.slope_mean_pct > 1.0
    assert res.parcel_cells == pytest.approx(20 * 15, abs=40)

    # The basin is found as a depression inside the parcel, around the parcel centre.
    assert res.depressions, "basin not detected"
    dep = res.depressions[0]
    assert dep.kind == "depression"
    assert dep.inside_parcel_share > 0.9
    assert dep.max_depth_m is not None and 1.0 < dep.max_depth_m <= BASIN_DEPTH_M
    assert dep.volume_m3 is not None and dep.volume_m3 > 0
    centre = shape(dep.centroid)
    assert geom.contains(centre)
    assert centre.distance(geom.centroid) < 0.0005  # ~ 35 m

    # The main outlet is on the downslope (east) side of the parcel.
    assert res.outlets
    main = res.outlets[0]
    assert main.direction in {"E", "NE", "SE"}
    pt = to_crs(shape(main.geometry), METRIC_CRS)
    g = to_crs(geom, METRIC_CRS)
    assert pt.x > g.bounds[2] - 20  # last cell column on the east edge
    # GeoJSON output in WGS84
    lon, lat = shape(main.geometry).coords[0]
    assert 14 < lon < 25 and 49 < lat < 55


def test_tilted_plane_without_basin_has_no_depression() -> None:
    geom = _parcel_geom()
    g = to_crs(geom, METRIC_CRS)
    x0 = g.bounds[0]
    res = analyse_terrain(grid_around(geom, lambda x, y: 100 - SLOPE * (x - x0)), geom)
    assert res is not None
    assert res.depressions == []
    assert res.slope_mean_pct == pytest.approx(2.0, abs=0.1)
    assert res.relief_m == pytest.approx(SLOPE * 190, abs=0.5)


def test_north_facing_slope() -> None:
    geom = _parcel_geom()
    g = to_crs(geom, METRIC_CRS)
    y0 = g.bounds[1]
    # higher to the south -> slope faces north
    res = analyse_terrain(grid_around(geom, lambda x, y: 100 + 0.05 * (y0 - y)), geom)
    assert res is not None
    assert res.aspect == "N"
    assert res.outlets and res.outlets[0].direction in {"N", "NE", "NW"}


def test_flat_plane_has_no_aspect() -> None:
    geom = _parcel_geom()
    res = analyse_terrain(grid_around(geom, lambda x, y: np.full_like(x, 120.0)), geom)
    assert res is not None
    assert res.aspect is None
    assert res.slope_mean_pct == 0.0 and res.slope_max_pct == 0.0
    assert res.depressions == []


def test_parcel_outside_the_grid_returns_none() -> None:
    geom = _parcel_geom()
    grid = grid_around(geom, lambda x, y: 100 - 0.01 * x)
    far = parcel_shape(metric_square_parcel(19.0, 50.0, 100, 100, METRIC_CRS))
    assert analyse_terrain(grid, far) is None


def test_all_nodata_grid_returns_none() -> None:
    geom = _parcel_geom()
    grid = grid_around(geom, lambda x, y: np.full_like(x, np.nan))
    assert analyse_terrain(grid, geom) is None


@pytest.mark.parametrize("size_m", [4.0, 12.0, 20.0])
def test_tiny_parcel(size_m: float) -> None:
    geom = parcel_shape(metric_square_parcel(17.35, 52.4, size_m, size_m, METRIC_CRS))
    g = to_crs(geom, METRIC_CRS)
    x0 = g.bounds[0]
    res = analyse_terrain(grid_around(geom, lambda x, y: 100 - 0.03 * (x - x0)), geom)
    assert res is not None
    assert 1 <= res.parcel_cells <= 9
    assert "small_parcel" in res.notes


def test_nodata_holes_inside_parcel() -> None:
    geom = _parcel_geom()
    surf = _basin_surface(geom)
    g = to_crs(geom, METRIC_CRS)
    cx = g.centroid.x

    def z(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        out = surf(x, y)
        return np.where(np.abs(x - cx - 60) < 10, np.nan, out)

    res = analyse_terrain(grid_around(geom, z), geom)
    assert res is not None
    assert np.isfinite(res.slope_mean_pct)


def test_non_rectangular_parcel() -> None:
    sq = to_crs(_parcel_geom(), METRIC_CRS)
    minx, miny, maxx, maxy = sq.bounds
    l_shape = box(minx, miny, maxx, maxy).difference(box((minx + maxx) / 2, (miny + maxy) / 2, maxx, maxy))
    geom = parcel_shape(parcel_from_polygon(to_crs(l_shape, 4326, src_crs=METRIC_CRS)))
    res = analyse_terrain(grid_around(geom, lambda x, y: 100 - 0.02 * (x - minx)), geom)
    assert res is not None and res.aspect == "E"


def test_priority_flood_fills_pit() -> None:
    z = np.array([[5, 5, 5], [5, 1, 5], [5, 5, 5]], dtype=float)
    filled = priority_flood(z)
    assert filled[1, 1] == pytest.approx(5.0, abs=1e-3)


@pytest.mark.parametrize(
    ("dx", "dy", "name"), [(0, 1, "N"), (1, 0, "E"), (0, -1, "S"), (-1, 0, "W"), (1, 1, "NE"), (-1, -1, "SW")]
)
def test_compass(dx: float, dy: float, name: str) -> None:
    assert compass(dx, dy) == name
