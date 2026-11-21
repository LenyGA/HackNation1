"""IUNG-PIB critical KBW thresholds (see iung_thresholds.yaml for the provenance rules)."""

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.crops.catalog import month_day

THRESHOLDS_PATH = Path(__file__).with_name("iung_thresholds.yaml")


class IungThreshold(BaseModel):
    crop_id: str
    soil_category: str
    period_end: str
    kbw_critical_mm: float


class IungTable(BaseModel):
    source: str | None
    thresholds: list[IungThreshold]


@lru_cache
def load_iung_table() -> IungTable:
    return IungTable.model_validate(yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def iung_threshold(crop_id: str, soil_category: str | None, day: date) -> tuple[date, float, str] | None:
    """Latest published period ending on or before `day` (same year) for the crop and soil category.

    Returns (period end date, critical KBW in mm, citation), or None when the table has no matching entry.
    """
    table = load_iung_table()
    if soil_category is None or table.source is None:
        return None
    best: tuple[date, float] | None = None
    for t in table.thresholds:
        if t.crop_id != crop_id or t.soil_category != soil_category:
            continue
        end = month_day(t.period_end, day.year)
        if end <= day and (best is None or end > best[0]):
            best = (end, t.kbw_critical_mm)
    return None if best is None else (best[0], best[1], table.source)
