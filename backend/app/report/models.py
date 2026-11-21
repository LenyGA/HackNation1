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
    map: ReportMap
    sources: list[SourceEntry]
    limitations_pl: list[str]
    missing_data_pl: list[str] = Field(description="Explicit statements of missing data, one per source.")
