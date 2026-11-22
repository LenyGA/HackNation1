"""Shared domain models. Every value shown to the farmer must carry its source, period and uncertainty."""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Self

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import HISTORY_YEARS, today_local


class SourceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"  # data present but lower quality (fallback source, partial coverage)
    MISSING = "missing"  # no data; never replaced with a default value


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Uncertainty(BaseModel):
    level: Confidence
    reason_pl: str = Field(description="Plain-language reason for this confidence level (Polish).")


class Period(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("period end must not be before start")
        return self


class SourceResult[T](BaseModel):
    """Result of fetching one external data source."""

    name: str = Field(description="Internal source id, e.g. 'open_meteo'.")
    status: SourceStatus
    source: str = Field(description="Human-readable provider and dataset name, with URL.")
    license: str
    fetched_at: datetime
    period: Period | None = None
    uncertainty: Uncertainty
    message_pl: str | None = Field(default=None, description="Message for the farmer, required when not ok.")
    data: T | None = None

    @model_validator(mode="after")
    def _status_matches_data(self) -> Self:
        if self.status is SourceStatus.MISSING and self.data is not None:
            raise ValueError("a 'missing' result must not carry data")
        if self.status is not SourceStatus.MISSING and self.data is None:
            raise ValueError(f"a '{self.status}' result must carry data")
        if self.status is not SourceStatus.OK and not self.message_pl:
            raise ValueError("a non-ok result must explain itself in message_pl")
        return self


class Indicator(BaseModel):
    """A single computed number with its provenance."""

    key: str
    value: float | None
    unit: str
    source: str
    period: Period | None = None
    uncertainty: Uncertainty


# WWPPGG_R.OOOO.NR — precinct may be followed by extra segments (e.g. AR_1); number may contain '/'.
PARCEL_ID_RE = re.compile(r"^\d{6}_\d\.\d{4}(\.[0-9A-Za-z_]+)*\.[0-9A-Za-z]+(/[0-9A-Za-z]+)*$")


def validate_parcel_id(value: str) -> str:
    value = value.strip()
    if len(value) > 64 or not PARCEL_ID_RE.match(value):
        raise ValueError(
            "Nieprawidłowy numer działki. Oczekiwany format: WWPPGG_R.OOOO.NR, np. 141201_1.0001.6509"
        )
    return value


class Parcel(BaseModel):
    id: str
    voivodeship: str | None = None
    county: str | None = None
    commune: str | None = None
    precinct: str | None = None
    number: str | None = None
    area_ha: float
    centroid_lat: float
    centroid_lon: float
    geometry: dict[str, Any] = Field(description="GeoJSON geometry in EPSG:4326.")


def analysis_date_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or today_local()
    return today - relativedelta(years=HISTORY_YEARS), today


# Farm mode (G11, plan33 M7): up to 5 more parcels within 2 km of the main one. Only the main parcel is
# analysed (weather, soil, satellite, terrain); the extra ones add their area to the water volumes.
MAX_EXTRA_PARCELS = 5
MAX_FARM_DISTANCE_M = 2000.0


class AnalysisRequest(BaseModel):
    parcel_id: str
    crop_id: str
    analysis_date: date
    extra_parcel_ids: list[str] = Field(default_factory=list)

    @field_validator("parcel_id")
    @classmethod
    def _parcel_id(cls, v: str) -> str:
        return validate_parcel_id(v)

    @field_validator("extra_parcel_ids")
    @classmethod
    def _extra_parcel_ids(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_EXTRA_PARCELS:
            raise ValueError(f"Do analizy można dodać najwyżej {MAX_EXTRA_PARCELS} działek oprócz głównej.")
        ids = [validate_parcel_id(x) for x in v]
        if len(set(ids)) != len(ids):
            raise ValueError("Ta sama działka jest dodana dwa razy.")
        return ids

    @model_validator(mode="after")
    def _extra_not_main(self) -> Self:
        if self.parcel_id in self.extra_parcel_ids:
            raise ValueError("Działka główna nie może być jednocześnie działką dodatkową.")
        return self

    @field_validator("analysis_date")
    @classmethod
    def _date_in_range(cls, v: date) -> date:
        lo, hi = analysis_date_bounds()
        if not lo <= v <= hi:
            raise ValueError(
                f"Data analizy musi być z zakresu {lo.isoformat()} – {hi.isoformat()} (ostatnie 10 lat)."
            )
        return v
