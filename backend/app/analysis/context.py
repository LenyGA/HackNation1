"""Inputs of the assessment and the intermediate values computed once from them. Pure, no I/O."""

from dataclasses import dataclass
from datetime import date

from app.analysis.history import HistoryResult, analyse_history
from app.analysis.series import Weather
from app.analysis.soil import SoilProperties, soil_properties
from app.analysis.terrain import TerrainResult, analyse_terrain
from app.analysis.water_balance import BalanceDay, RootZoneBalance, crop_root_zone_balance
from app.core.models import Confidence, Parcel, SourceResult, SourceStatus
from app.crops.catalog import Crop, month_day
from app.sources.base import parcel_shape
from app.sources.dem import ElevationGrid
from app.sources.hydro import HydroData
from app.sources.landcover import LandCoverData
from app.sources.open_meteo import WeatherData
from app.sources.sentinel2 import Sentinel2Data
from app.sources.soilgrids import SoilData

# Vegetation period used to decide between in-season and off-season assessment (plan, decision 3).
VEGETATION_START = "03-21"
VEGETATION_END = "09-30"


@dataclass(frozen=True)
class AnalysisInputs:
    parcel: Parcel
    crop: Crop
    analysis_date: date
    weather: SourceResult[WeatherData]
    soil: SourceResult[SoilData]
    sentinel2: SourceResult[Sentinel2Data]
    dem: SourceResult[ElevationGrid]
    hydro: SourceResult[HydroData]
    landcover: SourceResult[LandCoverData]

    def statuses(self) -> dict[str, SourceStatus]:
        return {
            r.name: r.status
            for r in (self.weather, self.soil, self.sentinel2, self.dem, self.hydro, self.landcover)
        }


def in_vegetation_period(day: date) -> bool:
    return month_day(VEGETATION_START, day.year) <= day <= month_day(VEGETATION_END, day.year)


def computed_source(*sources: str) -> str:
    return "Obliczenia RolnikSzukaWody z danych: " + "; ".join(s for s in sources if s)


@dataclass(frozen=True)
class Context:
    inputs: AnalysisInputs
    weather: Weather | None  # None when the weather source is missing
    weather_confidence: Confidence
    soil: SoilProperties | None
    balance: RootZoneBalance | None
    history: HistoryResult | None
    terrain: TerrainResult | None
    hydro: HydroData | None
    in_vegetation: bool
    crop_on_field: bool

    @property
    def crop(self) -> Crop:
        return self.inputs.crop

    @property
    def day(self) -> date:
        return self.inputs.analysis_date

    @property
    def today(self) -> BalanceDay | None:
        return None if self.balance is None else self.balance.at(self.day)

    @property
    def weather_source(self) -> str:
        return computed_source(self.inputs.weather.source)

    @property
    def soil_source(self) -> str:
        return computed_source(self.inputs.soil.source)

    @property
    def water_source(self) -> str:
        return computed_source(self.inputs.weather.source, self.inputs.soil.source)


def build_context(inputs: AnalysisInputs) -> Context:
    weather: Weather | None = None
    if inputs.weather.data is not None:
        weather = Weather.from_daily(inputs.weather.data.daily, inputs.analysis_date)
        if not weather.dates:
            weather = None

    soil: SoilProperties | None = None
    if inputs.soil.data is not None:
        soil = soil_properties(inputs.soil.data, inputs.crop.root_depth_m)

    balance: RootZoneBalance | None = None
    history: HistoryResult | None = None
    if weather is not None:
        if soil is not None and soil.taw_mm is not None:
            balance = crop_root_zone_balance(weather, inputs.crop, soil.taw_mm)
        history = analyse_history(weather, inputs.crop, inputs.analysis_date, balance)

    terrain: TerrainResult | None = None
    if inputs.dem.data is not None:
        terrain = analyse_terrain(inputs.dem.data, parcel_shape(inputs.parcel))

    return Context(
        inputs=inputs,
        weather=weather,
        weather_confidence=inputs.weather.uncertainty.level,
        soil=soil,
        balance=balance,
        history=history,
        terrain=terrain,
        hydro=inputs.hydro.data,
        in_vegetation=in_vegetation_period(inputs.analysis_date),
        crop_on_field=inputs.crop.in_season(inputs.analysis_date),
    )
