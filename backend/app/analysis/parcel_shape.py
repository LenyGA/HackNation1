"""Parcel length, width and compactness from the ULDK geometry (G10, plan33 M5.1). Pure: the caller passes
the geometry already in a metric CRS (EPSG:2180).

Length and width are the sides of the minimum rotated rectangle around the parcel, so a strip lying at any
angle reads as its real length and width. Compactness = parcel area / rectangle area: 1 for a rectangle,
≈ 0.79 for a circle, low for L-shapes and wedges (the irrigation machine leaves corners dry).
"""

from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class ParcelShape:
    length_m: float
    width_m: float
    compactness: float
    parts: int = 1  # separate polygons; length and width describe the largest one

    @property
    def elongation(self) -> float:
        return self.length_m / self.width_m if self.width_m > 0 else float("inf")


def parcel_shape_metrics(geom_metric: BaseGeometry) -> ParcelShape | None:
    if geom_metric.is_empty or geom_metric.area <= 0:
        return None
    parts = [g for g in getattr(geom_metric, "geoms", [geom_metric]) if g.area > 0]
    if len(parts) > 1:
        # A parcel in separate pieces: the machine works each piece, so measure the largest one.
        geom_metric = max(parts, key=lambda g: g.area)
    rect = geom_metric.minimum_rotated_rectangle
    if not isinstance(rect, Polygon) or rect.area <= 0:
        return None
    xs, ys = rect.exterior.coords.xy
    sides = [((xs[i + 1] - xs[i]) ** 2 + (ys[i + 1] - ys[i]) ** 2) ** 0.5 for i in range(2)]
    length, width = max(sides), min(sides)
    return ParcelShape(
        length_m=float(length),
        width_m=float(width),
        compactness=float(geom_metric.area / rect.area),
        parts=max(1, len(parts)),
    )
