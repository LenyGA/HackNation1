"""Report data model (plan step M6.1). Served as JSON (`GET /api/reports/{id}`) and rendered to PDF.

Texts for the farmer are generated once, in the backend (plan, decision 2): the frontend and the PDF template
only lay out the sentences below. Every number shown carries its source, period and uncertainty.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.models import Confidence, Parcel, Period, SourceStatus, Uncertainty
from app.recommendations.irrigation import ForecastUse, IrrigationStatus, ProjectedDay
from app.recommendations.models import Category, Location

SectionId = Literal[
    "summary",
    "current",
    "vulnerability",
    "causes",
    "retention",
    "agrotech",
    "irrigation",
    "sources",
    "limitations",
]
# Mandatory order of the report sections (plan step M6.1, CLAUDE.md rule 2).
SECTION_ORDER: list[SectionId] = [
    "summary",
    "current",
    "vulnerability",
    "causes",
    "retention",
    "agrotech",
    "irrigation",
    "sources",
    "limitations",
]

HeadlineLevel = Literal["none", "light", "moderate", "severe", "unknown"]


class EvidenceItem(BaseModel):
    """A computed number ready to show: Polish label and formatted value, plus full provenance."""

    key: str
    label_pl: str
    value: float | None
    value_pl: str = Field(description="Value formatted for the farmer, with unit, e.g. '23 mm'.")
    unit: str
    source: str
    period: Period | None = None
    uncertainty: Uncertainty


class ReportCrop(BaseModel):
    id: str
    name_pl: str


class Headline(BaseModel):
    """Coloured status indicator at the top of the report with one sentence."""

    level: HeadlineLevel
    label_pl: str
    sentence_pl: str
    confidence: Confidence
    confidence_pl: str


class ReportSection(BaseModel):
    id: SectionId
    number: int = Field(description="1-based position in the mandatory section order.")
    title_pl: str
    paragraphs_pl: list[str]
    details_pl: list[str] = Field(
        default_factory=list, description="'Szczegóły dla zainteresowanych': technical terms allowed here."
    )
    indicators: list[EvidenceItem] = Field(default_factory=list)
    recommendation_numbers: list[int] = Field(default_factory=list)


class ReportRecommendation(BaseModel):
    number: int
    id: str
    category: Category
    title_pl: str
    text_pl: str
    evidence: list[EvidenceItem] = Field(min_length=1)
    locations: list[Location] = Field(default_factory=list)


class ReportIrrigation(BaseModel):
    status: IrrigationStatus
    applicable: bool
    title_pl: str
    text_pl: str
    caveats_pl: list[str]
    dose_mm: float | None = None
    single_dose_max_mm: float | None = None
    applications: int | None = None
    single_dose_mm: float | None = Field(
        None, description="dose_mm / applications, rounded once in the backend."
    )
    volume_m3: float | None = None
    within_days: int | None = None
    irrigate_by: date | None = None
    forecast: ForecastUse
    projection: list[ProjectedDay] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class MonthRisk(BaseModel):
    """One row of the table 'how often water was short in this month in the last 10 years'."""

    month: int
    month_pl: str
    years_with_data: int
    deficit_years: int
    frequency_pct: float | None
    risk: bool = Field(description="Deficit in at least 30 % of the years with data.")
    critical: bool = Field(description="The month overlaps a water-critical period of the crop.")
    severe_years: int = Field(0, description="Years with water stress on at least half of the days.")
    mean_stress_days: float | None = Field(None, description="Mean crop water-stress days in the month.")


class StressRow(BaseModel):
    year: int
    stress_days: list[int | None] = Field(description="Per month of StressHeatmap.months; None = no data.")
    season_days: list[int | None] = Field(description="In-season days of the crop in that month.")


class StressHeatmap(BaseModel):
    """Crop water-stress days per month and year (FAO-56 root-zone balance), the last 10 years."""

    months: list[int]
    months_pl: list[str]
    rows: list[StressRow]
    source: str


class TrendYear(BaseModel):
    year: int
    value: float | None


class TrendMetric(BaseModel):
    key: str
    label_pl: str
    unit: str
    values: list[TrendYear]
    mean_all: float | None
    mean_mid: float | None = Field(description="Mean of the last 3 seasons.")
    mean_recent: float | None = Field(description="Mean of the last 2 seasons.")
    slope_per_decade: float | None
    direction: Literal["worse", "stable", "better"] | None
    recent: Literal["critical", "worse", "typical", "better"] | None
    summary_pl: str


TrendLevel = Literal["critical", "worse", "stable", "better", "unknown"]


class ClimateTrends(BaseModel):
    """Growing season (1 April – 30 September) over the last 10 seasons: baseline vs last 3 vs last 2."""

    seasons: list[int]
    level: TrendLevel
    label_pl: str
    verdict_pl: list[str]
    metrics: list[TrendMetric]
    source: str
    uncertainty_pl: str


class WaterPlanMonth(BaseModel):
    month: int
    month_pl: str
    years: int
    crop_need_mm: float | None = Field(description="Median crop water need ETc = Kc·ET0.")
    precip_mm: float | None = Field(description="Median precipitation.")
    deficit_median_mm: float | None = Field(description="Irrigation need in a typical year (median).")
    deficit_p80_mm: float | None = Field(description="Dry year, once in 5 years (80th percentile).")
    deficit_p90_mm: float | None = Field(description="Very dry year, once in 10 years (90th percentile).")
    deficit_p80_m3_ha: float | None
    critical: bool


class WaterPlan(BaseModel):
    """Monthly water plan for the crop (FAO-56), typical year vs dry years of the last 10 years."""

    method: Literal["root_zone", "crop_balance"]
    years: int
    months: list[WaterPlanMonth]
    season_median_mm: float | None
    season_p80_mm: float | None
    season_p90_mm: float | None
    season_p80_m3_parcel: float | None = Field(description="Net water (to reach the soil) in a dry year.")
    season_p80_m3_parcel_gross: float | None = Field(
        None, description="Water to pump with a sprinkler in a dry year (net / efficiency)."
    )
    efficiency_pct: int = 75
    critical_p80_mm: float | None
    pond_side_m: float | None = Field(
        description="Side of a square pond 2 m deep holding the P80 season volume."
    )
    pond_depth_m: float
    text_pl: list[str]
    source: str


class ProfilePoint(BaseModel):
    distance_m: float
    elevation_m: float
    hollow: bool


class SlopeProfile(BaseModel):
    """Elevation along the main downslope line across the parcel."""

    points: list[ProfilePoint]
    length_m: float
    drop_m: float
    mean_slope_pct: float
    direction_pl: str | None
    along_long_axis: bool
    resolution_m: float
    text_pl: str
    source: str


class StrategyYear(BaseModel):
    year_ahead: int
    stress_days_median: float | None
    stress_days_p80: float | None
    irrigation_mm_median: float | None
    irrigation_mm_p80: float | None
    irrigation_m3_parcel_p80: float | None
    taw_mm: float
    evaporation_saved_mm_median: float | None = Field(
        default=None, description="Soil evaporation avoided by the residue mulch (retention strategies)."
    )
    evaporation_saved_m3_parcel_median: float | None = None


class Strategy(BaseModel):
    id: Literal["none", "rescue", "full", "retention", "retention_rescue"]
    label_pl: str
    description_pl: str
    years: list[StrategyYear]


class Simulation(BaseModel):
    """1–5 year comparison of strategies (no action / irrigation / soil retention) for this parcel."""

    strategies: list[Strategy]
    members: int = Field(description="Past seasons used as possible future weather.")
    et0_change_pct_per_decade: float | None
    tmean_change_c_per_decade: float | None
    taw_now_mm: float
    taw_gain_5y_mm: float
    spring_storage_none_mm: float | None
    spring_storage_full_mm: float | None
    text_pl: list[str]
    assumptions_pl: list[str]
    source: str


TileStatus = Literal["good", "warn", "bad", "unknown"]


class Gauge(BaseModel):
    value: float
    max: float
    threshold: float | None = Field(None, description="Stress threshold on the same scale.")
    unit: str


class SummaryTile(BaseModel):
    id: Literal["water_now", "flood", "climate", "action", "dry_year"]
    label_pl: str
    value_pl: str
    detail_pl: str
    status: TileStatus
    gauge: Gauge | None = None
    link_section: SectionId | None = None


class SatellitePoint(BaseModel):
    year: int
    day: date
    ndvi: float
    ndmi: float | None
    current: bool = Field(description="True for scenes of the analysed season (the latest weeks).")


class SatelliteSeries(BaseModel):
    """Plant condition (vegetation index) of this parcel: now vs the same weeks in previous years."""

    points: list[SatellitePoint]
    history_median: float | None
    history_min: float | None
    history_max: float | None
    applicable: bool = Field(
        description="False when the crop has no developed canopy (index not comparable)."
    )
    text_pl: str
    source: str


class FloodZone(BaseModel):
    id: str
    label_pl: str
    hit: bool | None = Field(description="True = parcel touches the zone; None = not checked.")


class FloodInfo(BaseModel):
    status: SourceStatus
    level: Literal["high", "medium", "low", "none", "unknown"]
    label_pl: str
    sentence_pl: str
    zones: list[FloodZone]
    wms_url: str | None = None
    wms_layers: list[str] = Field(default_factory=list)
    source: str


class GroundwaterInfo(BaseModel):
    status: SourceStatus
    station_pl: str | None = None
    distance_km: float | None = None
    trend: Literal["falling", "stable", "rising"] | None = None
    change_m: float | None = None
    period: Period | None = None
    sentence_pl: str
    source: str


class ChartPoint(BaseModel):
    day: date
    precip_mm: float | None = Field(description="Precipitation summed from the chart start to this day.")
    crop_need_mm: float | None = Field(description="Crop water need ETc = Kc·ET0 summed likewise.")
    precip_hist_median_mm: float | None
    precip_hist_min_mm: float | None
    precip_hist_max_mm: float | None


class SeasonChart(BaseModel):
    """Current season (cumulative precipitation and crop water need) against the 10 previous years."""

    start: date
    end: date
    years: int = Field(description="Previous years with complete data for the comparison band.")
    source: str
    points: list[ChartPoint]


MapFeatureKind = Literal[
    "depression", "flow_path", "outlet", "ditch", "watercourse", "water_body", "wetland", "trees"
]


class MapFeature(BaseModel):
    kind: MapFeatureKind
    label_pl: str
    geometry: dict[str, Any] = Field(description="GeoJSON geometry in EPSG:4326.")
    recommendation_numbers: list[int] = Field(default_factory=list)


class ReportMap(BaseModel):
    parcel: dict[str, Any] = Field(description="Parcel outline, GeoJSON geometry in EPSG:4326.")
    features: list[MapFeature]
    legend_pl: dict[str, str] = Field(description="Feature kind → plain-language legend entry.")


class SourceEntry(BaseModel):
    name: str
    label_pl: str
    status: SourceStatus
    source: str
    license: str
    fetched_at: datetime
    period: Period | None = None
    uncertainty: Uncertainty
    message_pl: str | None = None


class Report(BaseModel):
    id: str
    created_at: datetime
    app: str
    version: str
    parcel: Parcel
    crop: ReportCrop
    analysis_date: date
    complete: bool = Field(description="False when the water assessment could not be made (no advice).")
    headline: Headline
    sections: list[ReportSection]
    recommendations: list[ReportRecommendation]
    irrigation: ReportIrrigation
    months: list[MonthRisk]
    chart: SeasonChart | None = None
    summary_tiles: list[SummaryTile] = Field(default_factory=list)
    stress_heatmap: StressHeatmap | None = None
    trends: ClimateTrends | None = None
    water_plan: WaterPlan | None = None
    profile: SlopeProfile | None = None
    simulation: Simulation | None = None
    satellite: SatelliteSeries | None = None
    flood: FloodInfo | None = None
    groundwater: GroundwaterInfo | None = None
    map: ReportMap
    sources: list[SourceEntry]
    limitations_pl: list[str]
    missing_data_pl: list[str] = Field(description="Explicit statements of missing data, one per source.")
