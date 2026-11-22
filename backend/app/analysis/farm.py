"""Farm mode (G11, plan33 M7): several parcels of one farm in one analysis. Pure, no I/O.

Only the main parcel is analysed (weather, soil, satellite, terrain, surroundings). The extra parcels share
its crop and its water situation and add their area to every volume in m³ (water plan, rescue irrigation,
retention coverage, the water-law threshold) and to the irrigation economics. The report says which results
are sums.
"""

from collections.abc import Sequence

from shapely.errors import ShapelyError

from app.core.models import Parcel
from app.sources.base import METRIC_CRS, parcel_shape, to_crs


def farm_area_ha(main: Parcel, extra: Sequence[Parcel]) -> float:
    """Sum of the cadastral areas (ULDK geometry), unrounded."""
    return main.area_ha + sum(p.area_ha for p in extra)


def distance_m(main: Parcel, other: Parcel) -> float | None:
    """Shortest distance between the parcel outlines in metres (0 when they touch); None when malformed."""
    try:
        a = to_crs(parcel_shape(main), METRIC_CRS)
        b = to_crs(parcel_shape(other), METRIC_CRS)
        return float(a.distance(b))
    except (KeyError, ValueError, TypeError, AttributeError, ShapelyError):
        return None
