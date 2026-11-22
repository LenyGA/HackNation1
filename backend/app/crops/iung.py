"""IUNG-PIB critical KBW thresholds (Dz.U. 2019 poz. 739); provenance in iung_thresholds.yaml. Pure, no I/O
beyond reading the bundled table once."""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator

from app.crops.catalog import month_day

THRESHOLDS_PATH = Path(__file__).with_name("iung_thresholds.yaml")
SOIL_CATEGORIES = ("I", "II", "III", "IV")
# SMSR publishes the six-dekad KBW after every dekad, so the latest finished period is at most one dekad old.
# A period that ended longer ago belongs to an earlier part of the season and is not a current signal.
MAX_PERIOD_AGE_DAYS = 11


class IungGroup(BaseModel):
    name_pl: str
    crops: list[str]
    kbw_critical_mm: dict[str, list[float | None]]


class IungTable(BaseModel):
    source: str
    url: str
    accessed: str
    periods: list[str]
    groups: list[IungGroup]

    @field_validator("periods")
    @classmethod
    def _check_periods(cls, value: list[str]) -> list[str]:
        for p in value:
            start, end = p.split("/")
            month_day(start, 2024)
            month_day(end, 2024)
        return value

    @model_validator(mode="after")
    def _check_shape(self) -> "IungTable":
        for g in self.groups:
            if set(g.kbw_critical_mm) != set(SOIL_CATEGORIES):
                raise ValueError(f"{g.name_pl}: soil categories must be exactly I–IV")
            for cat, values in g.kbw_critical_mm.items():
                if len(values) != len(self.periods):
                    n = len(self.periods)
                    raise ValueError(f"{g.name_pl} {cat}: {len(values)} values for {n} periods")
        return self


class IungMissing(StrEnum):
    """Why no official threshold applies (shown to the farmer)."""

    NO_SOIL_CATEGORY = "no_soil_category"
    CROP_NOT_COVERED = "crop_not_covered"  # crop absent from the regulation (e.g. grassland)
    SOIL_NOT_COVERED = "soil_not_covered"  # crop has no value for this soil category (sugar beet on cat. I)
    OUTSIDE_PERIODS = "outside_periods"  # no assessed period ended within the last dekad
    NO_WEATHER = "no_weather"  # threshold exists, but the period's weather is incomplete


@dataclass(frozen=True)
class IungThreshold:
    group_pl: str
    soil_category: str
    period_start: date
    period_end: date
    kbw_critical_mm: float
    citation: str
    url: str
    accessed: date  # when the bundled table was copied from the official text


@lru_cache
def load_iung_table() -> IungTable:
    return IungTable.model_validate(yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def _group(crop_id: str) -> IungGroup | None:
    return next((g for g in load_iung_table().groups if crop_id in g.crops), None)


def iung_lookup(crop_id: str, soil_category: str | None, day: date) -> IungThreshold | IungMissing:
    """Threshold of the latest assessed six-dekad period that ended on or before `day`, at most one dekad ago.

    The 2019 values are applied to every analysis year; the regulation replaced earlier tables (2016, 2017).
    """
    table = load_iung_table()
    if soil_category is None:
        return IungMissing.NO_SOIL_CATEGORY
    group = _group(crop_id)
    if group is None:
        return IungMissing.CROP_NOT_COVERED
    values = group.kbw_critical_mm.get(soil_category)
    if values is None or all(v is None for v in values):
        return IungMissing.SOIL_NOT_COVERED
    best: IungThreshold | None = None
    for period, value in zip(table.periods, values, strict=True):
        if value is None:
            continue
        start_s, end_s = period.split("/")
        end = month_day(end_s, day.year)
        if end > day or (day - end) > timedelta(days=MAX_PERIOD_AGE_DAYS):
            continue
        if best is None or end > best.period_end:
            best = IungThreshold(
                group_pl=group.name_pl,
                soil_category=soil_category,
                period_start=month_day(start_s, day.year),
                period_end=end,
                kbw_critical_mm=value,
                citation=table.source,
                url=table.url,
                accessed=date.fromisoformat(table.accessed),
            )
    return best if best is not None else IungMissing.OUTSIDE_PERIODS


def iung_threshold(crop_id: str, soil_category: str | None, day: date) -> IungThreshold | None:
    found = iung_lookup(crop_id, soil_category, day)
    return found if isinstance(found, IungThreshold) else None
