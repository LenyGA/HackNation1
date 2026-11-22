"""Water situation chart for a chosen time range ("Dane z ostatnich: 24 h / 7 dni / … / własny").

Pure functions, no I/O. The report keeps the daily rain and crop water need for the whole fetched period
(`DailyWater`); the chart for any range ending at or before the analysis date is computed from it, the same
way in the browser (`frontend/src/components/report/chartRange.ts`, keep the two in sync) and here
for the PDF.
"""

from datetime import date, timedelta
from statistics import median
from typing import Literal, get_args

from app.analysis.series import same_day_in_year
from app.core.config import HISTORY_YEARS
from app.report.models import ChartPoint, DailyWater, SeasonChart

RangeKey = Literal["1d", "7d", "1m", "6m", "1y", "custom"]
RANGE_KEYS: tuple[str, ...] = get_args(RangeKey)
# Window length in days, ending on the analysis date ("1d" = the analysis day itself: data are daily).
RANGE_DAYS: dict[str, int] = {"1d": 1, "7d": 7, "1m": 30, "6m": 182, "1y": 365}
DEFAULT_RANGE: RangeKey = "6m"
# Up to this many days every day is a point; longer windows get a point every STEP_DAYS and the last day.
DAILY_POINTS_MAX = 62
STEP_DAYS = 7
# The band of previous years is shown only with at least this many complete years (as the season chart).
MIN_HISTORY_YEARS = 5


def resolve_window(
    daily: DailyWater,
    analysis_date: date,
    key: RangeKey,
    start: date | None = None,
    end: date | None = None,
) -> tuple[date, date] | None:
    """(start, end) of the window, or None when a custom range is incomplete or outside the data.

    Preset ranges end on the analysis date (or the last day with data, if earlier) and are cut to the data."""
    last = min(analysis_date, daily.last)
    if key == "custom":
        if start is None or end is None or start > end:
            return None
        if end > analysis_date or start < earliest_start(daily, analysis_date) or end > daily.last:
            return None
        return start, end
    s = max(daily.start, last - timedelta(days=RANGE_DAYS[key] - 1))
    return (s, last) if s <= last else None


def earliest_start(daily: DailyWater, analysis_date: date) -> date:
    """First day a custom range may start: 10 years before the analysis date, within the data."""
    return max(daily.start, same_day_in_year(analysis_date, analysis_date.year - HISTORY_YEARS))


def _cumulative(values: list[float | None], first: date, start: date, n: int) -> list[float | None] | None:
    """Running sum over n days from `start`; a missing day ends the series (no gap filling)."""
    i0 = (start - first).days
    if i0 < 0 or i0 + n > len(values):
        return None
    out: list[float | None] = []
    total: float | None = 0.0
    for v in values[i0 : i0 + n]:
        total = None if total is None or v is None else total + v
        out.append(total)
    return out


def _r(value: float | None) -> float | None:
    return None if value is None else float(round(value))


def range_chart(daily: DailyWater, start: date, end: date) -> SeasonChart | None:
    """Cumulative rain and crop need from `start` to `end`, against the same days of the previous 10 years.

    The first point (the day before `start`) is 0 mm, so even a one-day window draws a line."""
    n = (end - start).days + 1
    if n < 1:
        return None
    precip = _cumulative(daily.precip_mm, daily.start, start, n)
    need = _cumulative(daily.crop_need_mm, daily.start, start, n)
    if precip is None or need is None:
        return None
    hist: list[list[float | None]] = []
    for k in range(1, HISTORY_YEARS + 1):
        series = _cumulative(daily.precip_mm, daily.start, same_day_in_year(start, start.year - k), n)
        if series is not None and series[-1] is not None:
            hist.append(series)
    enough = len(hist) >= MIN_HISTORY_YEARS
    offsets = list(range(n)) if n <= DAILY_POINTS_MAX else sorted({*range(0, n, STEP_DAYS), n - 1})
    points = [
        ChartPoint(
            day=start - timedelta(days=1),
            precip_mm=0.0,
            crop_need_mm=0.0,
            precip_hist_median_mm=0.0 if enough else None,
            precip_hist_min_mm=0.0 if enough else None,
            precip_hist_max_mm=0.0 if enough else None,
        )
    ]
    for i in offsets:
        past = [v for s in hist if (v := s[i]) is not None]
        ok = enough and len(past) >= MIN_HISTORY_YEARS
        points.append(
            ChartPoint(
                day=start + timedelta(days=i),
                precip_mm=_r(precip[i]),
                crop_need_mm=_r(need[i]),
                precip_hist_median_mm=_r(median(past)) if ok else None,
                precip_hist_min_mm=_r(min(past)) if ok else None,
                precip_hist_max_mm=_r(max(past)) if ok else None,
            )
        )
    years = len(hist) if enough else 0
    return SeasonChart(start=start, end=end, years=years, source=daily.source, points=points)
