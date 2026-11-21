"""Test helpers: building Parcel objects from fixtures or plain polygons, writing small GeoTIFFs."""

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from shapely.geometry import Polygon, box, mapping

from app.core.models import Parcel
from app.sources.base import METRIC_CRS, to_crs
from app.sources.uldk import parse_response, record_to_parcel

FIXTURES = Path(__file__).parent / "fixtures"


def uldk_fixture(name: str) -> str:
    return (FIXTURES / "uldk" / name).read_text(encoding="utf-8")


def parcel_from_uldk(name: str) -> Parcel:
    records = parse_response(uldk_fixture(name))
    assert records
    return record_to_parcel(records[0])


def parcel_from_polygon(poly: Polygon, parcel_id: str = "000000_0.0000.1") -> Parcel:
    """Parcel from a WGS84 polygon (lon/lat), with area and centroid computed like ULDK does."""
    metric = to_crs(poly, METRIC_CRS)
    centroid = to_crs(metric.centroid, 4326, src_crs=METRIC_CRS)
    return Parcel(
        id=parcel_id,
        area_ha=round(metric.area / 10_000, 4),
        centroid_lat=round(centroid.y, 6),
        centroid_lon=round(centroid.x, 6),
        geometry=dict(mapping(poly)),
    )


def metric_square_parcel(lon: float, lat: float, width_m: float, height_m: float, crs: int) -> Parcel:
    """Axis-aligned rectangle in `crs` (metres) whose lower-left corner is near (lon, lat)."""
    corner = to_crs(box(lon, lat, lon, lat).centroid, crs)
    rect = box(corner.x, corner.y, corner.x + width_m, corner.y + height_m)
    return parcel_from_polygon(to_crs(rect, 4326, src_crs=crs))


def write_tif(path: Path, array: np.ndarray, transform: Affine, crs: Any, nodata: float | None = None) -> str:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as ds:
        ds.write(array, 1)
    return str(path)
