"""Shared types of the assessment: levels, indicators built from computed values. Pure, no I/O."""

import math
from datetime import date
from enum import StrEnum

from app.analysis.texts_pl import REASONS
from app.core.models import Confidence, Indicator, Period, Uncertainty

CONFIDENCE_ORDER = [Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]


class DeficitLevel(StrEnum):
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    SEVERE = "severe"

    @property
    def rank(self) -> int:
        return LEVEL_ORDER.index(self)

    @classmethod
    def from_rank(cls, rank: int) -> "DeficitLevel":
        return LEVEL_ORDER[max(0, min(rank, len(LEVEL_ORDER) - 1))]


LEVEL_ORDER = [DeficitLevel.NONE, DeficitLevel.LIGHT, DeficitLevel.MODERATE, DeficitLevel.SEVERE]


class Vulnerability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def confidence_from_points(points: int) -> Confidence:
    return CONFIDENCE_ORDER[max(0, min(points, 3) - 1)]


def lower(level: Confidence, steps: int = 1) -> Confidence:
    return CONFIDENCE_ORDER[max(0, CONFIDENCE_ORDER.index(level) - steps)]


def round_to(value: float | None, step: float) -> float | None:
    """Sensible rounding (CLAUDE.md rule 4): e.g. precipitation to 1 mm, NDVI to 0.01."""
    if value is None or not math.isfinite(value):
        return None
    digits = max(0, -int(f"{step:e}".split("e")[1]))
    return round(round(value / step) * step, digits)


def indicator(
    key: str,
    value: float | None,
    unit: str,
    source: str,
    *,
    level: Confidence,
    reason: str = "computed",
    step: float = 1.0,
    start: date | None = None,
    end: date | None = None,
) -> Indicator:
    period = Period(start=start, end=end) if start is not None and end is not None else None
    return Indicator(
        key=key,
        value=round_to(value, step),
        unit=unit,
        source=source,
        period=period,
        uncertainty=Uncertainty(level=level, reason_pl=REASONS[reason]),
    )


def level_from_percentile(pct: float | None) -> DeficitLevel | None:
    """Empirical percentile in the 10-year sample → deficit level.

    < 10: drier than every one of the 10 previous years; ≤ 20: 2nd–3rd driest; ≤ 30: among the 3–4 driest.
    """
    if pct is None:
        return None
    if pct < 10:
        return DeficitLevel.SEVERE
    if pct <= 20:
        return DeficitLevel.MODERATE
    if pct <= 30:
        return DeficitLevel.LIGHT
    return DeficitLevel.NONE


def level_from_ks(ks: float) -> DeficitLevel:
    """FAO-56 water stress coefficient → deficit level (ET reduced by 0, < 25 %, 25–50 %, > 50 %)."""
    if ks >= 1.0:
        return DeficitLevel.NONE
    if ks >= 0.75:
        return DeficitLevel.LIGHT
    if ks >= 0.5:
        return DeficitLevel.MODERATE
    return DeficitLevel.SEVERE


def combine(primary: DeficitLevel, secondary: DeficitLevel | None) -> DeficitLevel:
    """The secondary signal can raise the primary level by at most one step and never lowers it."""
    if secondary is None:
        return primary
    return DeficitLevel.from_rank(max(primary.rank, min(secondary.rank, primary.rank + 1)))
