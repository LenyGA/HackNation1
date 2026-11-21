"""Crop catalogue with FAO-56 parameters (values and their sources live in catalog.yaml)."""

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


def month_day(value: str, year: int) -> date:
    """'MM-DD' in a given year; 29 Feb falls back to 28 Feb in non-leap years."""
    month, day = (int(part) for part in value.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, day - 1)


def _check_month_day(value: str) -> str:
    month_day(value, 2024)  # raises on malformed input
    return value


class CriticalPeriod(BaseModel):
    start: str
    end: str
    name_pl: str

    _start = field_validator("start", "end")(_check_month_day)

    def range_for_season(self, season_start: date) -> tuple[date, date]:
        """Concrete dates of this period inside the season that starts on `season_start`."""
        start = month_day(self.start, season_start.year)
        if start < season_start:
            start = month_day(self.start, season_start.year + 1)
        end = month_day(self.end, start.year)
        if end < start:
            end = month_day(self.end, start.year + 1)
        return start, end


class Crop(BaseModel):
    id: str
    name_pl: str
    winter: bool
    sowing: str
    stages_days: list[int] = Field(min_length=4, max_length=4)
    kc_ini: float = Field(ge=0, le=1.5)
    kc_mid: float = Field(ge=0, le=1.5)
    kc_end: float = Field(ge=0, le=1.5)
    kc_off_season: float = Field(ge=0, le=1.5)
    root_depth_m: float = Field(gt=0, le=3)
    p: float = Field(gt=0, lt=1)
    critical_periods: list[CriticalPeriod]

    _sowing = field_validator("sowing")(_check_month_day)

    @model_validator(mode="after")
    def _season_shorter_than_year(self) -> Self:
        if any(d <= 0 for d in self.stages_days) or self.season_days >= 365:
            raise ValueError(f"{self.id}: stage lengths must be positive and sum to less than a year")
        return self

    @property
    def season_days(self) -> int:
        return sum(self.stages_days)

    def season_start(self, day: date) -> date | None:
        """Start (sowing / regrowth) of the season containing `day`, or None when the field has no crop."""
        for year in (day.year, day.year - 1):
            start = month_day(self.sowing, year)
            if start <= day < start + timedelta(days=self.season_days):
                return start
        return None

    def last_season_start(self, day: date) -> date:
        """Start of the season containing `day`, or of the most recent season that started before it."""
        start = month_day(self.sowing, day.year)
        return start if start <= day else month_day(self.sowing, day.year - 1)

    def in_season(self, day: date) -> bool:
        return self.season_start(day) is not None

    def kc(self, day: date) -> float:
        """FAO-56 single crop coefficient for a calendar day (piecewise linear curve, FAO-56 Fig. 25)."""
        start = self.season_start(day)
        if start is None:
            return self.kc_off_season
        t = (day - start).days
        ini, dev, mid, late = self.stages_days
        if t < ini:
            return self.kc_ini
        t -= ini
        if t < dev:
            return self.kc_ini + (self.kc_mid - self.kc_ini) * t / dev
        t -= dev
        if t < mid:
            return self.kc_mid
        t -= mid
        return self.kc_mid + (self.kc_end - self.kc_mid) * (t + 1) / late

    def critical_period_at(self, day: date) -> CriticalPeriod | None:
        start = self.season_start(day)
        if start is None:
            return None
        for period in self.critical_periods:
            lo, hi = period.range_for_season(start)
            if lo <= day <= hi:
                return period
        return None

    def critical_months(self) -> set[int]:
        """Calendar months touched by any critical period."""
        months: set[int] = set()
        for period in self.critical_periods:
            lo, hi = period.range_for_season(month_day(self.sowing, 2023))
            d = lo
            while d <= hi:
                months.add(d.month)
                d += timedelta(days=1)
        return months


@lru_cache
def load_crops() -> dict[str, Crop]:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    return {c["id"]: Crop.model_validate(c) for c in raw["crops"]}


def get_crop(crop_id: str) -> Crop | None:
    return load_crops().get(crop_id)
