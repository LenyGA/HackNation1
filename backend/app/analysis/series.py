"""Indexed daily weather series with gap-aware window sums. Pure, no I/O."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.sources.open_meteo import DailySeries

# A window with more missing days than this share has no value (no false precision).
MAX_GAP_SHARE = 0.1


def same_day_in_year(day: date, year: int) -> date:
    """`day` moved to another year; 29 Feb becomes 28 Feb."""
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


@dataclass(frozen=True)
class Weather:
    """Daily weather indexed by date. Values are None for missing days."""

    dates: list[date]
    precip_mm: list[float | None]
    et0_mm: list[float | None]
    tmax_c: list[float | None]
    tmean_c: list[float | None]
    _index: dict[date, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        n = len(self.dates)
        if not all(len(s) == n for s in (self.precip_mm, self.et0_mm, self.tmax_c, self.tmean_c)):
            raise ValueError("all weather series must have the same length")
        object.__setattr__(self, "_index", {d: i for i, d in enumerate(self.dates)})

    @classmethod
    def from_daily(cls, daily: DailySeries, until: date) -> "Weather":
        """Series cut at `until` (analysis_date): later records never enter the analysis."""
        keep = [i for i, d in enumerate(daily.dates) if d <= until]
        return cls(
            dates=[daily.dates[i] for i in keep],
            precip_mm=[daily.precip_mm[i] for i in keep],
            et0_mm=[daily.et0_mm[i] for i in keep],
            tmax_c=[daily.tmax_c[i] for i in keep],
            tmean_c=[daily.tmean_c[i] for i in keep],
        )

    @property
    def first(self) -> date:
        return self.dates[0]

    @property
    def last(self) -> date:
        return self.dates[-1]

    def p_et0(self, day: date) -> tuple[float | None, float | None]:
        """Precipitation and ET0 on one day; (None, None) outside the series."""
        i = self._index.get(day)
        return (None, None) if i is None else (self.precip_mm[i], self.et0_mm[i])

    def covers(self, start: date, end: date) -> bool:
        return bool(self.dates) and self.first <= start and end <= self.last

    def _values(self, series: Sequence[float | None], start: date, end: date) -> list[float | None] | None:
        if end < start or not self.covers(start, end):
            return None
        i, j = self._index.get(start), self._index.get(end)
        if i is None or j is None:
            return None
        return list(series[i : j + 1])

    def window(self, end: date, days: int) -> tuple[date, date]:
        return end - timedelta(days=days - 1), end

    def precip_sum(self, start: date, end: date) -> float | None:
        return _gap_aware_sum(self._values(self.precip_mm, start, end))

    def kbw_sum(self, start: date, end: date) -> float | None:
        """Climatic water balance P − ET0 (mm) over [start, end]."""
        p = self._values(self.precip_mm, start, end)
        e = self._values(self.et0_mm, start, end)
        if p is None or e is None:
            return None
        diffs = [None if a is None or b is None else a - b for a, b in zip(p, e, strict=True)]
        return _gap_aware_sum(diffs)

    def mean_tmax(self, start: date, end: date) -> float | None:
        values = self._values(self.tmax_c, start, end)
        if values is None:
            return None
        present = [v for v in values if v is not None]
        if not present or len(values) - len(present) > MAX_GAP_SHARE * len(values):
            return None
        return sum(present) / len(present)

    def hot_days(self, start: date, end: date, threshold_c: float) -> int | None:
        values = self._values(self.tmax_c, start, end)
        if values is None:
            return None
        present = [v for v in values if v is not None]
        if len(values) - len(present) > MAX_GAP_SHARE * len(values):
            return None
        return sum(1 for v in present if v >= threshold_c)


def _gap_aware_sum(values: list[float | None] | None) -> float | None:
    """Sum scaled up for a few missing days; None when too many are missing."""
    if not values:
        return None
    present = [v for v in values if v is not None]
    if len(values) - len(present) > MAX_GAP_SHARE * len(values) or not present:
        return None
    return sum(present) * len(values) / len(present)
