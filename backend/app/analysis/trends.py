"""How the growing season changed over the last 10 years: 10-year baseline vs the last 3 and the last 2
seasons,
with a robust trend per decade. Pure, no I/O.

- Season: 1 April – 30 September (growing season in Poland). A season counts only when it has ended on or
  before
  the analysis date (no partial current season) and the weather series covers it.
- Metrics per season: mean daily temperature, hot days (Tmax ≥ 30 °C), reference evapotranspiration ET0,
  climatic water balance KBW = P − ET0, and with soil data the crop water-stress days (FAO-56 Ks < 1), in
  total
  and in the months that are critical for the crop.
- Trend: Theil–Sen slope (median of pairwise slopes; Sen 1968, J. Am. Stat. Assoc. 63:1379–1389), robust to a
  single extreme year, expressed per decade. With ≤ 10 points it is indicative only and the report says so.
- Significance: two-sided Mann–Kendall test (Mann 1945, Econometrica 13:245–259; Kendall 1975, Rank
  Correlation Methods), normal approximation with the ties correction. A direction ("worse"/"better", and any
  "per decade" wording) is reported only when p < MK_ALPHA; otherwise the metric is "stable" and the report
  compares the last 2 seasons with the 10-year mean without extrapolating (Q5, uwaga K5).
- "Recent" change: mean of the last 2 seasons against the mean of the whole window, in units of the
  between-year standard deviation (how unusual the last two seasons are for this parcel).
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from statistics import mean, pstdev

from app.analysis.series import Weather
from app.analysis.water_balance import RootZoneBalance
from app.core.config import HISTORY_YEARS
from app.crops.catalog import Crop

SEASON_START = (4, 1)
SEASON_END = (9, 30)
MIN_SEASONS = 6
MAX_GAP_SHARE = 0.1
HOT_DAY_C = 30.0
RECENT_SEASONS = 2
MID_SEASONS = 3

# |Theil–Sen slope| per decade below which a metric is called stable (orders of magnitude of year-to-year
# noise
# of seasonal sums in Poland; the trend is "indicative", see module docstring).
STABLE_PER_DECADE: dict[str, float] = {
    "tmean_c": 0.3,
    "hot_days": 3.0,
    "et0_mm": 20.0,
    "kbw_mm": 40.0,
    "stress_days": 8.0,
    "critical_stress_days": 5.0,
}
# Which direction is worse for the water situation of the crop.
WORSE_IF_UP: dict[str, bool] = {
    "tmean_c": True,
    "hot_days": True,
    "et0_mm": True,
    "kbw_mm": False,
    "stress_days": True,
    "critical_stress_days": True,
}
UNITS: dict[str, str] = {
    "tmean_c": "°C",
    "hot_days": "dni",
    "et0_mm": "mm",
    "kbw_mm": "mm",
    "stress_days": "dni",
    "critical_stress_days": "dni",
}
# Smallest difference between the last seasons and the 10-year mean that is worth a word (below: "typical").
MIN_RECENT_DIFF: dict[str, float] = {
    "tmean_c": 0.2,
    "hot_days": 1.0,
    "et0_mm": 10.0,
    "kbw_mm": 20.0,
    "stress_days": 3.0,
    "critical_stress_days": 2.0,
}
# Recent seasons this many between-year SDs worse than the 10-year mean: "much worse" / "critical".
RECENT_WORSE_SD = 0.5
RECENT_CRITICAL_SD = 1.0
# 10 % two-sided: with ≤ 10 seasons the test has little power, and the wording stays "indicative".
MK_ALPHA = 0.10


class Direction(StrEnum):
    WORSE = "worse"
    STABLE = "stable"
    BETTER = "better"


class RecentChange(StrEnum):
    CRITICAL = "critical"  # last seasons ≥ 1 SD worse than the 10-year mean
    WORSE = "worse"
    TYPICAL = "typical"
    BETTER = "better"


@dataclass(frozen=True)
class MetricTrend:
    key: str
    unit: str
    years: list[int]
    values: list[float | None]
    mean_all: float | None
    mean_mid: float | None  # last MID_SEASONS seasons
    mean_recent: float | None  # last RECENT_SEASONS seasons
    slope_per_decade: float | None
    direction: Direction | None
    recent: RecentChange | None
    recent_sd: float | None  # (mean_recent − mean_all) / SD, signed so that > 0 is worse
    mk_p: float | None = None  # Mann–Kendall two-sided p-value of the trend
    significant: bool = False  # mk_p < MK_ALPHA


@dataclass(frozen=True)
class TrendResult:
    seasons: list[int]
    metrics: dict[str, MetricTrend] = field(default_factory=dict)

    def get(self, key: str) -> MetricTrend | None:
        return self.metrics.get(key)


def theil_sen_slope(xs: list[float], ys: list[float]) -> float | None:
    slopes = [
        (ys[j] - ys[i]) / (xs[j] - xs[i])
        for i in range(len(xs))
        for j in range(i + 1, len(xs))
        if xs[j] != xs[i]
    ]
    if not slopes:
        return None
    slopes.sort()
    n = len(slopes)
    return slopes[n // 2] if n % 2 else (slopes[n // 2 - 1] + slopes[n // 2]) / 2


def mann_kendall_p(values: list[float]) -> float | None:
    """Two-sided p-value of the Mann–Kendall trend test (normal approximation, ties corrected)."""
    n = len(values)
    if n < 3:
        return None
    s = sum((values[j] > values[i]) - (values[j] < values[i]) for i in range(n - 1) for j in range(i + 1, n))
    ties = sum(t * (t - 1) * (2 * t + 5) for t in Counter(values).values() if t > 1)
    var = (n * (n - 1) * (2 * n + 5) - ties) / 18
    if var <= 0:
        return 1.0
    z = (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var) if s < 0 else 0.0
    return math.erfc(abs(z) / math.sqrt(2))


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _season_values(
    weather: Weather, balance: RootZoneBalance | None, crop: Crop, year: int
) -> dict[str, float | None]:
    start, end = date(year, *SEASON_START), date(year, *SEASON_END)
    out: dict[str, float | None] = dict.fromkeys(STABLE_PER_DECADE)
    if not weather.covers(start, end):
        return out
    days = _days(start, end)
    out["tmean_c"] = weather.mean_tmean(start, end)
    hot = weather.hot_days(start, end, HOT_DAY_C)
    out["hot_days"] = float(hot) if hot is not None else None
    kbw = weather.kbw_sum(start, end)
    precip = weather.precip_sum(start, end)
    out["kbw_mm"] = kbw
    out["et0_mm"] = precip - kbw if precip is not None and kbw is not None else None
    if balance is not None:
        bdays = [b for b in balance.between(start, end) if b.in_season]
        expected = sum(1 for d in days if crop.in_season(d))
        gaps = sum(1 for b in bdays if b.gap) + (expected - len(bdays))
        if expected and gaps <= MAX_GAP_SHARE * expected:
            out["stress_days"] = float(sum(1 for b in bdays if b.stressed))
            critical = crop.critical_months()
            out["critical_stress_days"] = float(
                sum(1 for b in bdays if b.stressed and b.day.month in critical)
            )
    return out


def _metric(key: str, years: list[int], values: list[float | None]) -> MetricTrend:
    pairs = [(y, v) for y, v in zip(years, values, strict=True) if v is not None]
    unit = UNITS[key]
    if len(pairs) < MIN_SEASONS:
        return MetricTrend(key, unit, years, values, None, None, None, None, None, None, None)
    vals = [v for _, v in pairs]
    mean_all = mean(vals)
    # "Last 3 / last 2 seasons" are the last seasons by calendar (a season with a gap is skipped, not replaced
    # by an older one), so the text and the bar chart describe the same years.
    mid_vals = [v for v in values[-MID_SEASONS:] if v is not None]
    recent_vals = [v for v in values[-RECENT_SEASONS:] if v is not None]
    if not recent_vals:
        return MetricTrend(key, unit, years, values, mean_all, None, None, None, None, None, None)
    mean_mid = mean(mid_vals)
    mean_recent = mean(recent_vals)
    slope = theil_sen_slope([float(y) for y, _ in pairs], vals)
    slope_dec = None if slope is None else slope * 10
    up_worse = WORSE_IF_UP[key]
    mk_p = mann_kendall_p(vals)
    significant = mk_p is not None and mk_p < MK_ALPHA
    direction: Direction | None = None
    if slope_dec is not None:
        if abs(slope_dec) < STABLE_PER_DECADE[key] or not significant:
            direction = Direction.STABLE
        else:
            direction = Direction.WORSE if (slope_dec > 0) == up_worse else Direction.BETTER
    sd = pstdev(vals)
    recent_sd: float | None = None
    recent: RecentChange | None = None
    if sd > 0 and abs(mean_recent - mean_all) >= MIN_RECENT_DIFF[key]:
        recent_sd = (mean_recent - mean_all) / sd * (1 if up_worse else -1)
        if recent_sd >= RECENT_CRITICAL_SD:
            recent = RecentChange.CRITICAL
        elif recent_sd >= RECENT_WORSE_SD:
            recent = RecentChange.WORSE
        elif recent_sd <= -RECENT_WORSE_SD:
            recent = RecentChange.BETTER
        else:
            recent = RecentChange.TYPICAL
    else:
        recent, recent_sd = RecentChange.TYPICAL, 0.0
    return MetricTrend(
        key,
        unit,
        years,
        values,
        mean_all,
        mean_mid,
        mean_recent,
        slope_dec,
        direction,
        recent,
        recent_sd,
        mk_p=mk_p,
        significant=significant,
    )


def completed_seasons(weather: Weather, analysis_date: date) -> list[int]:
    """Last HISTORY_YEARS growing seasons that ended on or before the analysis date, oldest first."""
    last = (
        analysis_date.year
        if analysis_date >= date(analysis_date.year, *SEASON_END)
        else analysis_date.year - 1
    )
    years = list(range(last - HISTORY_YEARS + 1, last + 1))
    return [y for y in years if weather.covers(date(y, *SEASON_START), date(y, *SEASON_END))]


def analyse_trends(
    weather: Weather, crop: Crop, analysis_date: date, balance: RootZoneBalance | None
) -> TrendResult | None:
    seasons = completed_seasons(weather, analysis_date)
    if len(seasons) < MIN_SEASONS:
        return None
    per_year = {y: _season_values(weather, balance, crop, y) for y in seasons}
    metrics = {key: _metric(key, seasons, [per_year[y][key] for y in seasons]) for key in STABLE_PER_DECADE}
    return TrendResult(seasons=seasons, metrics=metrics)
