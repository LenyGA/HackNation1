"""Terrain analysis of the elevation grid around the parcel. Pure, no I/O.

- slope (central differences, % rise), mean and maximum over cells whose centre lies in the parcel,
- dominant aspect (direction of the mean downslope gradient),
- depressions: priority-flood filling (Barnes et al. 2014, "Priority-flood: An optimal depression-filling and
  watershed-labeling algorithm", Computers & Geosciences 62) — cells where filled − original ≥
  DEPRESSION_MIN_DEPTH_M,
- flow routing D8 (O'Callaghan & Mark 1984) on the ε-filled surface and flow accumulation (contributing area),
- outlets: parcel cells that pass their flow to a cell outside the parcel, ranked by contributing area.

The grid is in EPSG:2180 (metres); output geometries are GeoJSON in EPSG:4326.
"""

import heapq
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from affine import Affine
from rasterio.features import geometry_mask, shapes
from shapely import unary_union
from shapely.geometry import Point, mapping, shape
from shapely.geometry.base import BaseGeometry

from app.sources.base import METRIC_CRS, to_crs
from app.sources.dem import ElevationGrid

DEPRESSION_MIN_DEPTH_M = 0.2
DEPRESSION_MIN_CELLS = 2
FLOW_PATH_MIN_AREA_M2 = 5_000.0  # 0.5 ha of contributing area = concentrated flow
FLAT_SLOPE_PCT = 1.0
MAX_SITES = 5
MAX_OUTLETS = 3
OUTLET_MIN_SPACING_M = 50.0
OUTLET_MIN_SHARE = 0.2  # secondary outlets must drain at least this share of the main outlet's area
EPSILON_M = 1e-6

# 8 neighbours: (row offset, col offset); direction codes for the report.
NEIGHBOURS: list[tuple[int, int]] = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


@dataclass(frozen=True)
class RetentionSite:
    kind: str  # "depression" | "flow_path"
    geometry: dict[str, Any]  # GeoJSON EPSG:4326 (polygon)
    centroid: dict[str, Any]  # GeoJSON point
    area_m2: float
    inside_parcel_share: float
    max_depth_m: float | None  # depressions
    volume_m3: float | None  # depressions: water held when filled to the spill level
    contributing_area_m2: float  # largest contributing area of a cell in the site


@dataclass(frozen=True)
class Outlet:
    geometry: dict[str, Any]  # GeoJSON point, EPSG:4326
    contributing_area_m2: float
    direction: str | None  # compass direction of the outflow; None when unknown (next to no-data)


@dataclass(frozen=True)
class TerrainResult:
    dataset: str
    resolution_m: float
    parcel_cells: int
    slope_mean_pct: float
    slope_max_pct: float
    relief_m: float  # max − min elevation within the parcel
    aspect: str | None  # compass direction the slope faces; None on flat ground
    depressions: list[RetentionSite]
    flow_paths: list[RetentionSite]
    outlets: list[Outlet]
    notes: list[str] = field(default_factory=list)


# "Main depression on the parcel" (Q7): one definition for the recommendation text, the slope profile and
# the map. At least half of it inside the parcel and fed by at least 0.1 ha.
DEPRESSION_MIN_INSIDE_SHARE = 0.5
DEPRESSION_MIN_CONTRIBUTING_M2 = 1_000.0


def is_main_depression(site: RetentionSite) -> bool:
    return (
        site.inside_parcel_share >= DEPRESSION_MIN_INSIDE_SHARE
        and site.contributing_area_m2 >= DEPRESSION_MIN_CONTRIBUTING_M2
    )


def main_depressions(t: TerrainResult) -> list[RetentionSite]:
    """Depressions that count as "on the parcel", largest first (the order of the terrain analysis)."""
    return [d for d in t.depressions if is_main_depression(d)]


def _grid_array(grid: ElevationGrid) -> np.ndarray:
    return np.array(
        [[np.nan if v is None else v for v in row] for row in grid.elevation_m],
        dtype=np.float64,
    )


def slope_pct(z: np.ndarray, res: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slope (%) and gradient components (east, north) in m/m."""
    d_row, d_col = np.gradient(z, res)
    gx = d_col  # +x = east
    gy = -d_row  # rows go south, so north gradient is the negative row gradient
    return 100 * np.hypot(gx, gy), gx, gy


def compass(dx: float, dy: float) -> str:
    """Compass direction of a vector (dx east, dy north)."""
    angle = (math.degrees(math.atan2(dx, dy)) + 360) % 360
    return COMPASS[int((angle + 22.5) // 45) % 8]


def priority_flood(z: np.ndarray, epsilon: float = EPSILON_M) -> np.ndarray:
    """ε-filled surface: every valid cell drains to the grid edge or a no-data cell (Barnes 2014, alg. 3)."""
    rows, cols = z.shape
    valid = np.isfinite(z)
    filled = np.where(valid, z, np.nan)
    done = ~valid
    heap: list[tuple[float, int, int]] = []
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                continue
            edge = r in (0, rows - 1) or c in (0, cols - 1)
            if not edge:
                edge = any(not valid[r + dr, c + dc] for dr, dc in NEIGHBOURS)
            if edge:
                heapq.heappush(heap, (float(z[r, c]), r, c))
                done[r, c] = True
    while heap:
        level, r, c = heapq.heappop(heap)
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or done[nr, nc]:
                continue
            done[nr, nc] = True
            value = max(float(z[nr, nc]), level + epsilon)
            filled[nr, nc] = value
            heapq.heappush(heap, (value, nr, nc))
    return filled


def d8_receivers(filled: np.ndarray) -> np.ndarray:
    """Index (r * cols + c) of the steepest downslope neighbour, −1 for cells draining off the grid."""
    rows, cols = filled.shape
    padded = np.pad(filled, 1, constant_values=np.nan)
    best_drop = np.zeros_like(filled)
    receiver = np.full(filled.shape, -1, dtype=np.int64)
    rr, cc = np.indices(filled.shape)
    for dr, dc in NEIGHBOURS:
        neighbour = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        drop = (filled - neighbour) / math.hypot(dr, dc)
        better = np.isfinite(drop) & (drop > best_drop)
        best_drop = np.where(better, drop, best_drop)
        receiver = np.where(better, (rr + dr) * cols + (cc + dc), receiver)
    receiver[~np.isfinite(filled)] = -1
    return receiver


def flow_accumulation(filled: np.ndarray, receiver: np.ndarray) -> np.ndarray:
    """Number of cells draining through each cell (itself included)."""
    flat_rcv = receiver.ravel()
    order = np.argsort(np.where(np.isfinite(filled), filled, -np.inf).ravel(), kind="stable")[::-1]
    acc = np.where(np.isfinite(filled), 1.0, 0.0).ravel()
    for i in order:
        j = flat_rcv[i]
        if j >= 0:
            acc[j] += acc[i]
    return acc.reshape(filled.shape)


def _cell_centre(transform: Affine, r: int, c: int) -> tuple[float, float]:
    x, y = transform @ (c + 0.5, r + 0.5)
    return float(x), float(y)


def _to_wgs84(geom: BaseGeometry) -> BaseGeometry:
    return to_crs(geom, 4326, src_crs=METRIC_CRS)


def _regions(mask: np.ndarray, transform: Affine) -> list[tuple[BaseGeometry, np.ndarray]]:
    """Connected regions (4-connectivity) of a boolean mask as polygons with their cell masks."""
    out: list[tuple[BaseGeometry, np.ndarray]] = []
    labels = np.zeros(mask.shape, dtype=np.int32)
    label = 0
    rows, cols = mask.shape
    for r0, c0 in zip(*np.nonzero(mask), strict=True):
        if labels[r0, c0]:
            continue
        label += 1
        stack = [(int(r0), int(c0))]
        labels[r0, c0] = label
        while stack:
            r, c = stack.pop()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not labels[nr, nc]:
                    labels[nr, nc] = label
                    stack.append((nr, nc))
    polys: dict[int, list[BaseGeometry]] = {}
    for g, v in shapes(labels, mask=labels > 0, transform=transform):
        polys.setdefault(int(v), []).append(shape(g))
    for lab, parts in sorted(polys.items()):
        out.append((unary_union(parts), labels == lab))
    return out


def _site(
    kind: str,
    geom: BaseGeometry,
    cells: np.ndarray,
    parcel_2180: BaseGeometry,
    cell_area: float,
    acc_m2: np.ndarray,
    depth: np.ndarray | None,
) -> RetentionSite:
    inside = geom.intersection(parcel_2180).area / geom.area if geom.area else 0.0
    max_depth = float(np.nanmax(depth[cells])) if depth is not None else None
    volume = float(np.nansum(depth[cells]) * cell_area) if depth is not None else None
    return RetentionSite(
        kind=kind,
        geometry=dict(mapping(_to_wgs84(geom))),
        centroid=dict(mapping(_to_wgs84(geom.centroid))),
        area_m2=round(float(cells.sum()) * cell_area, 1),
        inside_parcel_share=round(inside, 3),
        max_depth_m=None if max_depth is None else round(max_depth, 2),
        volume_m3=None if volume is None else round(volume, 1),
        contributing_area_m2=round(float(acc_m2[cells].max()), 1),
    )


def analyse_terrain(grid: ElevationGrid, parcel_wgs84: BaseGeometry) -> TerrainResult | None:
    """None when the parcel covers no valid grid cell or its slope cannot be computed."""
    z = _grid_array(grid)
    transform = Affine(*grid.transform[:6])
    res = grid.resolution_m
    cell_area = res * res
    parcel_2180 = to_crs(parcel_wgs84, METRIC_CRS)
    inside = geometry_mask([mapping(parcel_2180)], out_shape=z.shape, transform=transform, invert=True)
    if not (inside & np.isfinite(z)).any():
        inside = geometry_mask(
            [mapping(parcel_2180)], out_shape=z.shape, transform=transform, invert=True, all_touched=True
        )
    inside &= np.isfinite(z)
    if not inside.any():
        return None
    notes: list[str] = []
    if inside.sum() < 9:
        notes.append("small_parcel")

    slope, gx, gy = slope_pct(z, res)
    with_slope = inside & np.isfinite(slope)
    if not with_slope.any():
        # Every parcel cell borders no-data: slope is unknown, never reported as flat.
        return None
    slope_in = slope[with_slope]
    slope_mean = float(slope_in.mean())
    slope_max = float(slope_in.max())
    z_in = z[inside]
    mean_gx = float(gx[with_slope].mean())
    mean_gy = float(gy[with_slope].mean())
    aspect = None if 100 * math.hypot(mean_gx, mean_gy) < FLAT_SLOPE_PCT else compass(-mean_gx, -mean_gy)

    filled = priority_flood(z)
    depth = np.where(np.isfinite(z), filled - z, 0.0)
    receiver = d8_receivers(filled)
    acc_m2 = flow_accumulation(filled, receiver) * cell_area

    # Depressions that touch the parcel.
    dep_mask = depth >= DEPRESSION_MIN_DEPTH_M
    depressions: list[RetentionSite] = []
    for geom, cells in _regions(dep_mask, transform):
        if cells.sum() < DEPRESSION_MIN_CELLS or not (cells & inside).any():
            continue
        depressions.append(_site("depression", geom, cells, parcel_2180, cell_area, acc_m2, depth))
    depressions.sort(key=lambda s: -(s.volume_m3 or 0.0))

    # Concentrated flow inside the parcel.
    flow_mask = inside & (acc_m2 >= FLOW_PATH_MIN_AREA_M2) & ~dep_mask
    flow_paths = [
        _site("flow_path", geom, cells, parcel_2180, cell_area, acc_m2, None)
        for geom, cells in _regions(flow_mask, transform)
    ]
    flow_paths.sort(key=lambda s: -s.contributing_area_m2)

    # Outlets: parcel cells whose receiver is outside the parcel (or off the grid).
    cols = z.shape[1]
    candidates: list[tuple[float, int, int, int]] = []
    inside_flat = inside.ravel()
    for r, c in zip(*np.nonzero(inside), strict=True):
        j = int(receiver[r, c])
        if j < 0 or not inside_flat[j]:
            candidates.append((float(acc_m2[r, c]), int(r), int(c), j))
    candidates.sort(reverse=True)
    outlets: list[Outlet] = []
    chosen: list[tuple[float, float]] = []
    top_area = candidates[0][0] if candidates else 0.0
    for area, r, c, j in candidates:
        if len(outlets) >= MAX_OUTLETS or area < OUTLET_MIN_SHARE * top_area:
            break
        x, y = _cell_centre(transform, r, c)
        if any(math.hypot(x - px, y - py) < OUTLET_MIN_SPACING_M for px, py in chosen):
            continue
        direction: str | None
        if j >= 0:
            jr, jc = divmod(j, cols)
            jx, jy = _cell_centre(transform, jr, jc)
            direction = compass(jx - x, jy - y)
        else:
            dx, dy = -float(gx[r, c]), -float(gy[r, c])
            # Next to no-data cells the gradient is unknown, so the direction is not reported.
            direction = compass(dx, dy) if math.isfinite(dx) and math.isfinite(dy) else None
        chosen.append((x, y))
        outlets.append(
            Outlet(
                geometry=dict(mapping(_to_wgs84(Point(x, y)))),
                contributing_area_m2=round(area, 1),
                direction=direction,
            )
        )

    return TerrainResult(
        dataset=grid.dataset,
        resolution_m=res,
        parcel_cells=int(inside.sum()),
        slope_mean_pct=round(slope_mean, 1),
        slope_max_pct=round(slope_max, 1),
        relief_m=round(float(np.nanmax(z_in) - np.nanmin(z_in)), 1),
        aspect=aspect,
        depressions=depressions[:MAX_SITES],
        flow_paths=flow_paths[:MAX_SITES],
        outlets=outlets,
        notes=notes,
    )
