"""Static parcel map for the PDF (plan step M6.3): parcel outline + retention places drawn as inline SVG.

No external tiles: geometries from the report are projected to EPSG:2180 (metres) and scaled into the SVG box.
"""

from html import escape
from typing import Any

from shapely import unary_union
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box, shape
from shapely.geometry.base import BaseGeometry

from app.report.models import Report
from app.sources.base import METRIC_CRS, to_crs

WIDTH = 640.0
HEIGHT = 400.0
PAD = 16.0
MIN_MARGIN_M = 80.0

STYLE: dict[str, str] = {
    "trees": 'fill="#9ccc8a" fill-opacity="0.6" stroke="#5b8f4a" stroke-width="0.8"',
    "wetland": 'fill="#8fd0c8" fill-opacity="0.6" stroke="#3f8f86" stroke-width="0.8"',
    "water_body": 'fill="#6fa8dc" fill-opacity="0.8" stroke="#2f6aa3" stroke-width="0.8"',
    "depression": 'fill="#3d85c6" fill-opacity="0.45" stroke="#1c4f80" stroke-width="1.2"',
    "flow_path": 'fill="none" stroke="#e69138" stroke-width="2.2" stroke-dasharray="6 3"',
    "ditch": 'fill="none" stroke="#2f6aa3" stroke-width="1.6"',
    "watercourse": 'fill="none" stroke="#1c4f80" stroke-width="2.6"',
    "outlet": 'fill="#cc0000" stroke="#ffffff" stroke-width="1.2"',
}
# Drawing order: areas first, then lines, then points.
ORDER = ["trees", "wetland", "water_body", "depression", "ditch", "watercourse", "flow_path", "outlet"]


class _Projector:
    def __init__(self, bounds: tuple[float, float, float, float]) -> None:
        minx, miny, maxx, maxy = bounds
        self.minx, self.maxy = minx, maxy
        self.scale = min((WIDTH - 2 * PAD) / (maxx - minx), (HEIGHT - 2 * PAD) / (maxy - miny))
        self.offx = (WIDTH - (maxx - minx) * self.scale) / 2
        self.offy = (HEIGHT - (maxy - miny) * self.scale) / 2

    def xy(self, x: float, y: float) -> tuple[float, float]:
        return (self.offx + (x - self.minx) * self.scale, self.offy + (self.maxy - y) * self.scale)

    def path(self, coords: Any, close: bool) -> str:
        pts = [self.xy(x, y) for x, y, *_ in coords]
        if not pts:
            return ""
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        return d + (" Z" if close else "")


def _paths(geom: BaseGeometry, proj: _Projector) -> list[tuple[str, bool]]:
    """SVG path data for a geometry; the bool tells whether it is an area."""
    if isinstance(geom, Polygon):
        rings = [geom.exterior, *geom.interiors]
        d = " ".join(proj.path(r.coords, True) for r in rings)
        return [(d, True)]
    if isinstance(geom, MultiPolygon):
        return [p for g in geom.geoms for p in _paths(g, proj)]
    if isinstance(geom, LineString):
        return [(proj.path(geom.coords, False), False)]
    if isinstance(geom, MultiLineString):
        return [p for g in geom.geoms for p in _paths(g, proj)]
    if hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in _paths(g, proj)]
    return []


def _scale_bar(proj: _Projector) -> str:
    target_px = 120.0
    metres = target_px / proj.scale
    nice = next((n for n in (10, 20, 50, 100, 200, 500, 1000, 2000) if n >= metres * 0.6), 2000)
    px = nice * proj.scale
    x0, y0 = PAD, HEIGHT - PAD
    label = f"{nice} m" if nice < 1000 else f"{nice // 1000} km"
    return (
        f'<g class="scale"><rect x="{x0 - 4}" y="{y0 - 18}" width="{px + 8}" height="22" fill="#ffffff" '
        f'fill-opacity="0.8"/><line x1="{x0}" y1="{y0}" x2="{x0 + px:.1f}" y2="{y0}" stroke="#000" '
        f'stroke-width="2"/><text x="{x0}" y="{y0 - 5}" font-size="10">{label}</text></g>'
    )


def _north_arrow() -> str:
    x, y = WIDTH - PAD - 10, PAD + 4
    return (
        f'<g class="north"><path d="M{x},{y} L{x + 7},{y + 20} L{x},{y + 15} L{x - 7},{y + 20} Z" '
        f'fill="#000"/><text x="{x}" y="{y + 32}" font-size="10" text-anchor="middle">N</text></g>'
    )


def parcel_map_svg(report: Report) -> str:
    parcel = to_crs(shape(report.parcel.geometry), METRIC_CRS)
    # The frame covers the parcel and every place a recommendation points to, so no numbered marker is lost.
    linked = [to_crs(shape(f.geometry), METRIC_CRS) for f in report.map.features if f.recommendation_numbers]
    minx, miny, maxx, maxy = unary_union([parcel, *linked]).bounds
    margin = max(MIN_MARGIN_M, 0.3 * max(maxx - minx, maxy - miny))
    frame = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
    proj = _Projector(frame.bounds)

    layers: dict[str, list[str]] = {k: [] for k in ORDER}
    markers: list[str] = []
    for feature in report.map.features:
        geom = to_crs(shape(feature.geometry), METRIC_CRS)
        clipped = geom.intersection(frame)
        if clipped.is_empty:
            continue
        style = STYLE[feature.kind]
        if feature.kind == "outlet":
            pt = clipped if isinstance(clipped, Point) else clipped.representative_point()
            x, y = proj.xy(pt.x, pt.y)
            layers["outlet"].append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" {style}/>')
        else:
            for d, _area in _paths(clipped, proj):
                layers[feature.kind].append(f'<path d="{d}" {style}/>')
        if feature.recommendation_numbers:
            anchor = clipped.representative_point()
            x, y = proj.xy(anchor.x, anchor.y)
            label = escape(",".join(str(n) for n in feature.recommendation_numbers))
            r = 8 + 3 * (len(label) - 1)
            markers.append(
                f'<g class="marker"><circle cx="{x:.1f}" cy="{y - 14:.1f}" r="{r}" fill="#ffffff" '
                f'stroke="#000" stroke-width="1.2"/><text x="{x:.1f}" y="{y - 10.5:.1f}" font-size="10" '
                f'font-weight="bold" text-anchor="middle">{label}</text></g>'
            )

    outline = " ".join(d for d, _ in _paths(parcel, proj))
    body = "".join("".join(layers[k]) for k in ORDER)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH:.0f} {HEIGHT:.0f}" '
        f'class="parcel-map" role="img" aria-label="Mapa działki">'
        f'<rect x="0" y="0" width="{WIDTH:.0f}" height="{HEIGHT:.0f}" fill="#f7f5ee"/>'
        f"{body}"
        f'<path d="{outline}" fill="none" stroke="#000" stroke-width="2.4"/>'
        f"{''.join(markers)}{_scale_bar(proj)}{_north_arrow()}</svg>"
    )
