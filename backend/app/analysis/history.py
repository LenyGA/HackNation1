"""Ten-year context: how often each month of the crop season had a water deficit, and where the current values
fall in the distribution of the same windows in previous years. Pure, no I/O.

10 values are too few for a fitted SPI, so we report an empirical percentile (plan, decision 4).

A month of a given year counts as a deficit month:
- with soil data ("root_zone" method): when the crop was under water stress (FAO-56 Ks < 1) on at least
  STRESS_SHARE of its in-season days that month,
- without soil data ("crop_balance" method): not determined. In Polish summers P − ETc is negative even in
  normal years, so a fixed threshold would mark almost every month as a deficit, and a relative one would
  give ~30 % by construction. The crop balance per month is still reported, the frequency is missing.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.analysis.series import Weather, same_day_in_year
from app.analysis.water_balance import KBW_WINDOW_DAYS, RootZoneBalance
from app.core.config import HISTORY_YEARS
from app.crops.catalog import Crop

TABLE_MONTHS = range(3, 11)  # March–October: the months shown to the farmer
MIN_SEASON_DAYS_IN_MONTH = 7
STRESS_SHARE = 1 / 3
RISK_FREQUENCY = 0.3
MIN_YEARS_FOR_PERCENTILE = 5
MAX_GAP_SHARE = 0.1


class HistoryMethod(StrEnum):
    ROOT_ZONE = "root_zone"
    CROP_BALANCE = "crop_balance"


@dataclass(frozen=True)
class MonthOutcome:
    in_season_days: int
    stress_days: int | None  # root-zone method only
    crop_balance_mm: float | None  # P − ETc
    deficit: bool | None  # None = not enough data / crop not on the field


@dataclass(frozen=True)
class YearStat:
    year: int
    months: dict[int, MonthOutcome]
    season_stress_days: int | None  # March–October, root-zone method only
    precip_30d_mm: float | None  # same windows as the current values
    precip_90d_mm: float | None
    kbw_60d_mm: float | None

    @property
    def deficit_months(self) -> list[int]:
        return [m for m, o in self.months.items() if o.deficit]


@dataclass(frozen=True)
class MonthFrequency:
    month: int
    years_with_data: int
    deficit_years: int

    @property
    def frequency(self) -> float | None:
        return self.deficit_years / self.years_with_data if self.years_with_data else None


@dataclass(frozen=True)
class CurrentWindows:
    precip_30d_mm: float | None
    precip_90d_mm: float | None
    kbw_60d_mm: float | None
    precip_30d_pct: float | None
    precip_90d_pct: float | None
    kbw_60d_pct: float | None


@dataclass(frozen=True)
class HistoryResult:
    method: HistoryMethod
    years: list[YearStat]  # previous HISTORY_YEARS calendar years, oldest first
    months: list[MonthFrequency]  # in-season months of TABLE_MONTHS
    risk_months: list[int]  # months with frequency ≥ RISK_FREQUENCY, most frequent first
    critical_risk_months: list[int]  # risk months that overlap the crop's water-critical periods
    deficit_year_share: float | None  # share of years with at least one deficit month
    current: CurrentWindows

    @property
    def years_with_data(self) -> int:
        return sum(1 for y in self.years if any(o.deficit is not None for o in y.months.values()))


def empirical_percentile(value: float | None, sample: list[float | None]) -> float | None:
    """Share (0–100) of past values below `value`, ties counted half. None with too few values."""
    values = [v for v in sample if v is not None]
    if value is None or len(values) < MIN_YEARS_FOR_PERCENTILE:
        return None
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return 100 * (below + 0.5 * equal) / len(values)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, nxt - timedelta(days=1)


def _month_outcome(
    weather: Weather, crop: Crop, balance: RootZoneBalance | None, year: int, month: int
) -> MonthOutcome | None:
    start, end = _month_bounds(year, month)
    if not weather.covers(start, end):
        return None
    season_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    season_days = [d for d in season_days if crop.in_season(d)]
    n = len(season_days)
    if n < MIN_SEASON_DAYS_IN_MONTH:
        return MonthOutcome(n, None, None, None)

    stress: int | None = None
    deficit: bool | None = None
    if balance is not None:
        days = [b for b in (balance.at(d) for d in season_days) if b is not None]
        gaps = sum(1 for b in days if b.gap) + (n - len(days))
        if gaps <= MAX_GAP_SHARE * n:
            stress = sum(1 for b in days if b.stressed)
            deficit = stress >= STRESS_SHARE * n

    # Crop water balance P − Kc·ET0 over the in-season days (reported with both methods).
    total = 0.0
    gaps = 0
    for d in season_days:
        p, e = weather.p_et0(d)
        if p is None or e is None:
            gaps += 1
            continue
        total += p - crop.kc(d) * e
    crop_balance = total * n / (n - gaps) if gaps <= MAX_GAP_SHARE * n and n > gaps else None
    return MonthOutcome(n, stress, crop_balance, deficit)


def _windows(weather: Weather, end: date) -> tuple[float | None, float | None, float | None]:
    p30 = weather.precip_sum(*weather.window(end, 30))
    p90 = weather.precip_sum(*weather.window(end, 90))
    kbw = weather.kbw_sum(*weather.window(end, KBW_WINDOW_DAYS))
    return p30, p90, kbw


def season_stress_days(
    balance: RootZoneBalance, crop: Crop, year: int, until: date | None = None
) -> int | None:
    """Stress days in March–October of `year` (up to `until`), None when gaps exceed MAX_GAP_SHARE."""
    start, end = date(year, 3, 1), date(year, 10, 31)
    if until is not None:
        end = min(end, until)
    days = [b for b in balance.between(start, end) if crop.in_season(b.day)]
    expected = sum(1 for i in range((end - start).days + 1) if crop.in_season(start + timedelta(days=i)))
    if not expected:
        return None
    gaps = sum(1 for b in days if b.gap) + (expected - len(days))
    if gaps > MAX_GAP_SHARE * expected:
        return None
    return sum(1 for b in days if b.stressed)


def year_stat(
    weather: Weather, crop: Crop, balance: RootZoneBalance | None, year: int, analysis_date: date
) -> YearStat:
    """Statistics of one calendar year; windows end on the same day of the year as `analysis_date`."""
    months: dict[int, MonthOutcome] = {}
    for m in TABLE_MONTHS:
        outcome = _month_outcome(weather, crop, balance, year, m)
        if outcome is not None and outcome.in_season_days >= MIN_SEASON_DAYS_IN_MONTH:
            months[m] = outcome
    p30, p90, kbw = _windows(weather, same_day_in_year(analysis_date, year))
    return YearStat(
        year=year,
        months=months,
        season_stress_days=season_stress_days(balance, crop, year) if balance is not None else None,
        precip_30d_mm=p30,
        precip_90d_mm=p90,
        kbw_60d_mm=kbw,
    )


def analyse_history(
    weather: Weather, crop: Crop, analysis_date: date, balance: RootZoneBalance | None
) -> HistoryResult:
    method = HistoryMethod.ROOT_ZONE if balance is not None else HistoryMethod.CROP_BALANCE
    years = [
        year_stat(weather, crop, balance, analysis_date.year - offset, analysis_date)
        for offset in range(HISTORY_YEARS, 0, -1)
    ]

    freqs: list[MonthFrequency] = []
    for m in TABLE_MONTHS:
        outcomes = [y.months[m] for y in years if m in y.months and y.months[m].deficit is not None]
        if outcomes:
            freqs.append(MonthFrequency(m, len(outcomes), sum(1 for o in outcomes if o.deficit)))

    risk = sorted(
        (f for f in freqs if f.frequency is not None and f.frequency >= RISK_FREQUENCY),
        key=lambda f: (-(f.frequency or 0.0), f.month),
    )
    risk_months = [f.month for f in risk]
    critical = crop.critical_months()

    counted = [y for y in years if any(o.deficit is not None for o in y.months.values())]
    share = sum(1 for y in counted if y.deficit_months) / len(counted) if counted else None

    p30, p90, kbw = _windows(weather, analysis_date)
    current = CurrentWindows(
        precip_30d_mm=p30,
        precip_90d_mm=p90,
        kbw_60d_mm=kbw,
        precip_30d_pct=empirical_percentile(p30, [y.precip_30d_mm for y in years]),
        precip_90d_pct=empirical_percentile(p90, [y.precip_90d_mm for y in years]),
        kbw_60d_pct=empirical_percentile(kbw, [y.kbw_60d_mm for y in years]),
    )
    return HistoryResult(
        method=method,
        years=years,
        months=freqs,
        risk_months=risk_months,
        critical_risk_months=[m for m in risk_months if m in critical],
        deficit_year_share=share,
        current=current,
    )
