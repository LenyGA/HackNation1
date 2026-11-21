"""Synthetic inputs for analysis tests (no network): weather, soil, DEM, satellite, AnalysisInputs."""

import math
import random
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
from shapely.geometry.base import BaseGeometry

from app.analysis.context import AnalysisInputs
from app.analysis.series import same_day_in_year
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
from app.crops.catalog import Crop, load_crops
from app.sources.base import METRIC_CRS, missing, parcel_shape, result, to_crs, unc
from app.sources.dem import ElevationGrid
from app.sources.hydro import HydroData
from app.sources.open_meteo import DailySeries, WeatherData, history_start
from app.sources.sentinel2 import SceneStat, Sentinel2Data
from app.sources.soilgrids import SoilData, SoilLayer
from tests.helpers import metric_square_parcel

SOILGRIDS_DEPTHS = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 100)]
DayFn = Callable[[date], float | None]


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def seasonal_et0(d: date) -> float:
    return max(0.2, 2.5 + 2.5 * math.sin((d.timetuple().tm_yday - 110) / 365 * 2 * math.pi))


def seasonal_t(d: date) -> float:
    return 8 + 10 * math.sin((d.timetuple().tm_yday - 110) / 365 * 2 * math.pi)


def daily_series(
    start: date,
    end: date,
    precip: DayFn,
    et0: DayFn = seasonal_et0,
    tmean: DayFn = seasonal_t,
) -> DailySeries:
    dates = date_range(start, end)
    t = [tmean(d) for d in dates]
    return DailySeries(
        dates=dates,
        precip_mm=[precip(d) for d in dates],
        et0_mm=[et0(d) for d in dates],
        tmin_c=[None if v is None else v - 5 for v in t],
        tmax_c=[None if v is None else v + 5 for v in t],
        tmean_c=t,
    )


def random_precip(seed: int = 1) -> DayFn:
    rng = random.Random(seed)
    cache: dict[date, float] = {}

    def fn(d: date) -> float:
        if d not in cache:
            cache[d] = max(0.0, rng.gauss(1.6, 3.0))
        return cache[d]

    return fn


KW = {"source": "synthetic", "license": "test"}


def ok[T](name: str, data: T, status: SourceStatus = SourceStatus.OK) -> SourceResult[T]:
    return result(
        name,
        status,
        data,
        uncertainty=unc(Confidence.HIGH, "test"),
        message_pl=None if status is SourceStatus.OK else "test",
        **KW,
    )


def absent[T](name: str) -> SourceResult[T]:
    return missing(name, message_pl="brak", **KW)


def weather_result(daily: DailySeries) -> SourceResult[WeatherData]:
    data = WeatherData(
        provider="open_meteo_archive", latitude=52.4, longitude=17.35, daily=daily, missing_days=0
    )
    return ok("open_meteo", data)


def soil_layers(
    sand: float | None, silt: float | None, clay: float | None, soc: float | None
) -> list[SoilLayer]:
    return [
        SoilLayer(
            depth_top_cm=a,
            depth_bottom_cm=b,
            sand_pct=sand,
            silt_pct=silt,
            clay_pct=clay,
            soc_g_per_kg=soc,
            bulk_density_g_per_cm3=1.5,
        )
        for a, b in SOILGRIDS_DEPTHS
    ]


def soil_data(layers: list[SoilLayer]) -> SoilData:
    return SoilData(latitude=52.4, longitude=17.35, layers=layers, neighbour_used=False)


LOAMY_SAND = (80.0, 12.0, 8.0, 8.0)


def default_parcel() -> Parcel:
    return metric_square_parcel(17.35, 52.4, 200, 150, METRIC_CRS)


def grid_around(
    geom_wgs84: BaseGeometry,
    z_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
    res: float = 10.0,
    buffer_m: float = 150.0,
) -> ElevationGrid:
    """EPSG:2180 grid over the parcel bbox + buffer; z_fn(x, y) gets cell-centre coordinates (m)."""
    g = to_crs(geom_wgs84, METRIC_CRS)
    minx, miny, maxx, maxy = g.buffer(buffer_m).bounds
    w = int((maxx - minx) // res)
    h = int((maxy - miny) // res)
    xs = minx + (np.arange(w) + 0.5) * res
    ys = maxy - (np.arange(h) + 0.5) * res
    xx, yy = np.meshgrid(xs, ys)
    z = z_fn(xx, yy)
    rows = [[None if not np.isfinite(v) else float(v) for v in row] for row in z]
    return ElevationGrid(
        dataset="copernicus_glo30",
        crs="EPSG:2180",
        transform=[res, 0, minx, 0, -res, maxy],
        resolution_m=res,
        native_resolution_m=30,
        width=w,
        height=h,
        elevation_m=rows,
    )


def tilted_grid(parcel: Parcel, slope: float = 0.04) -> ElevationGrid:
    g = to_crs(parcel_shape(parcel), METRIC_CRS)
    x0 = g.bounds[0]
    return grid_around(parcel_shape(parcel), lambda x, y: 100 - slope * (x - x0))


def hydro_data(nearest_water_m: float | None = 800.0) -> HydroData:
    return HydroData(
        radius_m=1000,
        features=[],
        counts={},
        nearest_m={"water_body": nearest_water_m},
        ditch_length_along_boundary_m=0,
        truncated=False,
    )


def scene(d: date, ndvi: float) -> SceneStat:
    return SceneStat(
        scene_id=f"S2_{d.isoformat()}",
        date=d,
        ndvi_mean=ndvi,
        ndmi_mean=None,
        clear_pixels=100,
        parcel_pixels=100,
        clear_share=1.0,
        scene_cloud_pct=0.0,
    )


def sentinel_data(analysis_date: date, ndvi_now: float, ndvi_history: float = 0.7) -> Sentinel2Data:
    history = [
        scene(same_day_in_year(analysis_date, analysis_date.year - k), ndvi_history) for k in range(10, 0, -1)
    ]
    return Sentinel2Data(
        parcel_pixels=100,
        current=[scene(analysis_date - timedelta(days=3), ndvi_now)],
        history=history,
        years_requested=10,
        years_with_data=10,
    )


def crop(crop_id: str) -> Crop:
    return load_crops()[crop_id]


def make_inputs(
    analysis_date: date,
    crop_id: str = "maize",
    *,
    precip: DayFn | None = None,
    et0: DayFn = seasonal_et0,
    weather_end: date | None = None,
    weather: SourceResult[WeatherData] | None | bool = True,
    soil: SourceResult[SoilData] | None | bool = True,
    sentinel2: SourceResult[Sentinel2Data] | None = None,
    dem: SourceResult[ElevationGrid] | None | bool = True,
    hydro: bool = True,
    parcel: Parcel | None = None,
) -> AnalysisInputs:
    """Whole AnalysisInputs; True = default synthetic source, False/None = missing, or an explicit result."""
    parcel = parcel or default_parcel()
    if weather is True:
        daily = daily_series(
            history_start(analysis_date), weather_end or analysis_date, precip or random_precip(), et0
        )
        w: SourceResult[WeatherData] = weather_result(daily)
    elif isinstance(weather, SourceResult):
        w = weather
    else:
        w = absent("open_meteo")
    if soil is True:
        s: SourceResult[SoilData] = ok("soilgrids", soil_data(soil_layers(*LOAMY_SAND)))
    elif isinstance(soil, SourceResult):
        s = soil
    else:
        s = absent("soilgrids")
    if dem is True:
        d: SourceResult[ElevationGrid] = ok("dem", tilted_grid(parcel), SourceStatus.DEGRADED)
    elif isinstance(dem, SourceResult):
        d = dem
    else:
        d = absent("dem")
    h: SourceResult[HydroData] = ok("hydro", hydro_data()) if hydro else absent("hydro")
    return AnalysisInputs(
        parcel=parcel,
        crop=crop(crop_id),
        analysis_date=analysis_date,
        weather=w,
        soil=s,
        sentinel2=sentinel2 if sentinel2 is not None else absent("sentinel2"),
        dem=d,
        hydro=h,
        landcover=absent("landcover"),
    )
