"""Scenarios for recommendation tests: weather (dry / wet), soils, terrain shapes and OSM features."""

import dataclasses
from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
from shapely.geometry import LineString, mapping

from app.analysis.assessment import Assessment, assess
from app.analysis.context import AnalysisInputs
from app.core.models import Parcel, SourceStatus
from app.recommendations.engine import recommend
from app.recommendations.models import Recommendation
from app.sources.base import METRIC_CRS, parcel_shape, to_crs
from app.sources.dem import ElevationGrid
from app.sources.hydro import HydroData, HydroFeature
from tests.analysis.builders import (
    LOAMY_SAND,
    default_parcel,
    grid_around,
    make_inputs,
    ok,
    soil_data,
    soil_layers,
)

SUMMER = date(2024, 7, 15)
CLAY_LOAM_RICH = (25.0, 35.0, 40.0, 20.0)  # heavy soil, plenty of organic carbon


def dry(_: date) -> float:
    return 0.3


def wet(d: date) -> float:
    # The analysis year is wetter than every previous year, so percentiles show no deficit either.
    return 12.0 if d.year >= SUMMER.year else 10.0


Surface = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _surface(
    parcel: Parcel, fn: Callable[[np.ndarray, np.ndarray, float, float, float], np.ndarray]
) -> Surface:
    g = to_crs(parcel_shape(parcel), METRIC_CRS)
    x0 = g.bounds[0]
    cx, cy = g.centroid.x, g.centroid.y
    return lambda x, y: fn(x, y, x0, cx, cy)


def flat(parcel: Parcel) -> Surface:
    return _surface(parcel, lambda x, y, x0, cx, cy: np.full_like(x, 100.0))


def tilted(parcel: Parcel, slope: float) -> Surface:
    return _surface(parcel, lambda x, y, x0, cx, cy: 100 - slope * (x - x0))


def basin(parcel: Parcel, slope: float = 0.01, radius: float = 40.0, depth: float = 2.0) -> Surface:
    def z(x: np.ndarray, y: np.ndarray, x0: float, cx: float, cy: float) -> np.ndarray:
        r2 = ((x - cx) ** 2 + (y - cy) ** 2) / radius**2
        return 100 - slope * (x - x0) - np.where(r2 < 1, depth * (1 - r2), 0.0)

    return _surface(parcel, z)


def valley(parcel: Parcel, slope: float = 0.03, side: float = 0.05) -> Surface:
    """Plane falling east with a V-shaped valley along the parcel's east–west axis: flow concentrates."""
    return _surface(parcel, lambda x, y, x0, cx, cy: 100 - slope * (x - x0) + side * np.abs(y - cy))


def dem_result(parcel: Parcel, surface: Surface) -> Any:
    grid: ElevationGrid = grid_around(parcel_shape(parcel), surface)
    return ok("dem", grid, SourceStatus.DEGRADED)


def soil_result(texture: tuple[float, float, float, float]) -> Any:
    return ok("soilgrids", soil_data(soil_layers(*texture)))


def feature(kind: str, distance_m: float, parcel: Parcel) -> HydroFeature:
    lon, lat = parcel.centroid_lon, parcel.centroid_lat
    return HydroFeature(
        kind=kind,  # type: ignore[arg-type]
        osm_id=f"way/{kind}{int(distance_m)}",
        name=None,
        geometry=dict(mapping(LineString([(lon, lat), (lon + 0.001, lat)]))),
        distance_m=distance_m,
    )


def hydro(
    parcel: Parcel,
    *,
    ditch_m: float = 0.0,
    trees_m: float | None = None,
    wetland_m: float | None = None,
    water_m: float | None = None,
) -> HydroData:
    feats: list[HydroFeature] = []
    nearest: dict[str, float | None] = {
        "ditch": None,
        "watercourse": None,
        "water_body": water_m,
        "wetland": wetland_m,
        "trees": trees_m,
    }
    if ditch_m:
        feats.append(feature("ditch", 0.0, parcel))
        nearest["ditch"] = 0.0
    for kind, dist in (("trees", trees_m), ("wetland", wetland_m), ("water_body", water_m)):
        if dist is not None:
            feats.append(feature(kind, dist, parcel))
    counts = {k: sum(1 for f in feats if f.kind == k) for k in nearest}
    return HydroData(
        radius_m=1000,
        features=sorted(feats, key=lambda f: f.distance_m),
        counts=counts,
        nearest_m=nearest,
        ditch_length_along_boundary_m=ditch_m,
        truncated=False,
    )


def scenario(
    *,
    crop_id: str = "maize",
    day: date = SUMMER,
    precip: Callable[[date], float] = dry,
    texture: tuple[float, float, float, float] = LOAMY_SAND,
    surface: Callable[[Parcel], Surface] | None = None,
    soil: bool = True,
    dem: bool = True,
    hydro_data: Callable[[Parcel], HydroData] | None | bool = None,
    weather: bool = True,
    flood: Any = None,
) -> tuple[Assessment, AnalysisInputs, list[Recommendation]]:
    parcel = default_parcel()
    inputs = make_inputs(
        day,
        crop_id,
        precip=precip,
        soil=soil_result(texture) if soil else False,
        dem=dem_result(parcel, (surface or flat)(parcel)) if dem else False,
        hydro=(
            False if hydro_data is False else hydro_data(parcel) if callable(hydro_data) else hydro(parcel)
        ),
        weather=weather,
        parcel=parcel,
    )
    if flood is not None:
        inputs = dataclasses.replace(inputs, flood=flood)
    a = assess(inputs)
    return a, inputs, recommend(a, inputs)


def ids(recs: list[Recommendation]) -> list[str]:
    return [r.id for r in recs]


def by_id(recs: list[Recommendation], rule_id: str) -> Recommendation:
    return next(r for r in recs if r.id == rule_id)
