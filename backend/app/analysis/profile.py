"""Elevation profile across the parcel along the main downslope direction (for the slope chart). Pure, no I/O.

- Direction: the mean downslope gradient over the parcel cells (as for the aspect). On flat ground, where the
  gradient has no direction, the long axis of the parcel is used.
- The line goes through the parcel centroid, is clipped to the parcel (the longest piece) and oriented from
  the higher to the lower end. Elevations are sampled bilinearly from the grid, about every grid cell.
- Places on the line where the depression-filled surface is ≥ DEPRESSION_MIN_DEPTH_M above the ground are
  marked as hollows (water collects there after rain).
"""

import math
from dataclasses import dataclass

import numpy as np
from affine import Affine
from rasterio.features import geometry_mask
from shapely.geometry import LineString, MultiLineString, Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry

from app.analysis.terrain import DEPRESSION_MIN_DEPTH_M, FLAT_SLOPE_PCT, compass, priority_flood, slope_pct
from app.sources.base import METRIC_CRS, to_crs
from app.sources.dem import ElevationGrid

MAX_POINTS = 120
# Parcels this many times longer than wide are profiled along their length (a cross-section of a strip says
# little about where water flows on the field).
ELONGATED_RATIO = 3.0
MIN_LENGTH_M = 20.0


@dataclass(frozen=True)
class ProfilePoint:
    distance_m: float
    elevation_m: float
    hollow: bool
    x_m: float = 0.0  # position in METRIC_CRS (EPSG:2180), to match hollows with terrain depressions
    y_m: float = 0.0


@dataclass(frozen=True)
class SlopeProfile:
    points: list[ProfilePoint]
    length_m: float
    drop_m: float
    mean_slope_pct: float
    direction: str | None  # compass direction the line runs downhill; None when the long axis was used
    along_long_axis: bool
    dataset: str
    resolution_m: float


def _bilinear(z: np.ndarray, inv: Affine, x: float, y: float) -> float | None:
    col, row = inv @ (x, y)
    c, r = col - 0.5, row - 0.5
    c0, r0 = math.floor(c), math.floor(r)
    if r0 < 0 or c0 < 0 or r0 + 1 >= z.shape[0] or c0 + 1 >= z.shape[1]:
        return None
    window = z[r0 : r0 + 2, c0 : c0 + 2]
    if not np.isfinite(window).all():
        return None
    fc, fr = c - c0, r - r0
    top = window[0, 0] * (1 - fc) + window[0, 1] * fc
    bottom = window[1, 0] * (1 - fc) + window[1, 1] * fc
    return float(top * (1 - fr) + bottom * fr)


def _elongation(parcel: BaseGeometry) -> float:
    rect = parcel.minimum_rotated_rectangle
    if not isinstance(rect, Polygon):
        return 1.0
    (x0, y0), (x1, y1), (x2, y2) = list(rect.exterior.coords)[:3]
    a, b = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
    return max(a, b) / max(min(a, b), 1e-6)


def _long_axis(parcel: BaseGeometry) -> tuple[float, float]:
    rect = parcel.minimum_rotated_rectangle
    coords = list(rect.exterior.coords) if hasattr(rect, "exterior") else []
    if len(coords) < 3:
        return 1.0, 0.0
    (x0, y0), (x1, y1), (x2, y2) = coords[0], coords[1], coords[2]
    a, b = (x1 - x0, y1 - y0), (x2 - x1, y2 - y1)
    dx, dy = a if math.hypot(*a) >= math.hypot(*b) else b
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def slope_profile(grid: ElevationGrid, parcel_wgs84: BaseGeometry) -> SlopeProfile | None:
    z = np.array([[np.nan if v is None else v for v in row] for row in grid.elevation_m], dtype=np.float64)
    if z.size == 0 or not np.isfinite(z).any():
        return None
    transform = Affine(*grid.transform[:6])
    inv = ~transform
    res = grid.resolution_m
    parcel = to_crs(parcel_wgs84, METRIC_CRS)
    inside = geometry_mask(
        [mapping(parcel)], out_shape=z.shape, transform=transform, invert=True, all_touched=True
    )
    _, gx, gy = slope_pct(z, res)
    ok = inside & np.isfinite(gx) & np.isfinite(gy)
    along_axis = True
    dx, dy = _long_axis(parcel)
    direction: str | None = None
    if ok.any() and _elongation(parcel) < ELONGATED_RATIO:
        mgx, mgy = float(gx[ok].mean()), float(gy[ok].mean())
        if 100 * math.hypot(mgx, mgy) >= FLAT_SLOPE_PCT:
            n = math.hypot(mgx, mgy)
            dx, dy = -mgx / n, -mgy / n
            along_axis = False
            direction = compass(dx, dy)

    c = parcel.centroid
    reach = math.hypot(parcel.bounds[2] - parcel.bounds[0], parcel.bounds[3] - parcel.bounds[1])
    line = LineString([(c.x - dx * reach, c.y - dy * reach), (c.x + dx * reach, c.y + dy * reach)])
    cut = line.intersection(parcel)
    if isinstance(cut, MultiLineString):
        cut = max(cut.geoms, key=lambda g: g.length)
    if not isinstance(cut, LineString) or cut.length < MIN_LENGTH_M:
        return None

    filled = priority_flood(z)
    n_points = int(min(MAX_POINTS, max(10, cut.length / max(res, 1.0) + 1)))
    samples: list[tuple[float, float, bool, float, float]] = []
    for i in range(n_points):
        d = cut.length * i / (n_points - 1)
        p: Point = cut.interpolate(d)
        elev = _bilinear(z, inv, p.x, p.y)
        top = _bilinear(filled, inv, p.x, p.y)
        if elev is None:
            continue
        samples.append((d, elev, top is not None and top - elev >= DEPRESSION_MIN_DEPTH_M, p.x, p.y))
    if len(samples) < 5:
        return None
    if samples[0][1] < samples[-1][1]:
        total = cut.length
        samples = [(total - d, e, h, x, y) for d, e, h, x, y in reversed(samples)]
        dx, dy = -dx, -dy
        if direction is not None:
            direction = compass(dx, dy)  # the line now runs the other way: name the direction it is drawn
    start = samples[0][0]
    points = [ProfilePoint(round(d - start, 1), round(e, 2), h, x, y) for d, e, h, x, y in samples]
    length = points[-1].distance_m
    drop = points[0].elevation_m - points[-1].elevation_m
    return SlopeProfile(
        points=points,
        length_m=round(length, 1),
        drop_m=round(drop, 2),
        mean_slope_pct=round(100 * drop / length, 1) if length > 0 else 0.0,
        direction=direction,
        along_long_axis=along_axis,
        dataset=grid.dataset,
        resolution_m=max(grid.native_resolution_m, grid.resolution_m),
    )
