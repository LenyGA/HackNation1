"""Seasonal water plan for the chosen crop: how much water the crop needs per month (March–October), how
much rain
covers and how much irrigation would have been needed — in a typical year and in a dry year. Pure, no I/O.

Method (FAO-56, Allen et al. 1998):
- crop water need ETc = Kc · ET0 with the crop's Kc curve (catalog.yaml, FAO-56 Tables 11–12) and ET0 of this
  parcel's weather for each of the last 10 calendar years;
- with soil data: net irrigation requirement from the daily root-zone balance with irrigation at the
  management
  allowed depletion (Dr > RAW → refill to field capacity, FAO-56 ch. 8). This counts rain stored in the soil;
- without soil data: the crop balance max(0, ETc − P) per month (cruder: it ignores the water stored in the
  soil, so it overstates the need in spring and understates it after a dry spell).
- Precautionary values (not only the average): the 80th and 90th percentile over the 10 years (a dry year that
  happens about once in 5 and once in 10 years), next to the median ("a typical year").
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

import numpy as np

from app.analysis.series import Weather
from app.analysis.water_balance import RootZoneBalance, crop_calendar, root_zone_balance
from app.core.config import HISTORY_YEARS
from app.crops.catalog import Crop

PLAN_MONTHS = range(3, 11)  # March–October
MIN_YEARS = 5
MAX_GAP_SHARE = 0.1


class PlanMethod(StrEnum):
    ROOT_ZONE = "root_zone"
    CROP_BALANCE = "crop_balance"


@dataclass(frozen=True)
class PlanMonth:
    month: int
    years: int
    etc_median_mm: float | None
    precip_median_mm: float | None
    need_median_mm: float | None
    need_p80_mm: float | None
    need_p90_mm: float | None
    critical: bool


@dataclass(frozen=True)
class WaterPlanResult:
    method: PlanMethod
    years: list[int]
    months: list[PlanMonth]
    season_median_mm: float | None
    season_p80_mm: float | None
    season_p90_mm: float | None
    critical_p80_mm: float | None  # need in the crop's critical months only (a "rescue" strategy)


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile (numpy default, Hyndman & Fan type 7); None for too few values."""
    if len(values) < MIN_YEARS:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q))


def irrigated_balance(
    weather: Weather,
    crop: Crop,
    taw_mm: float,
    *,
    only_critical: bool = False,
    kc: list[float] | None = None,
    et0_factor: float = 1.0,
    dr0_mm: float = 0.0,
    dose_cap_mm: float | None = None,
) -> RootZoneBalance:
    """Root-zone balance with irrigation on in-season days (or only in the crop's critical periods).

    `kc`: a crop-coefficient curve to use instead of the crop's own (e.g. lowered by a mulch)."""
    base_kc, season = crop_calendar(weather, crop)
    if kc is None:
        kc = base_kc
    if only_critical:
        allowed = [
            s and crop.critical_period_at(d) is not None for d, s in zip(weather.dates, season, strict=True)
        ]
    else:
        allowed = list(season)
    return root_zone_balance(
        weather.dates,
        weather.precip_mm,
        weather.et0_mm,
        kc,
        season,
        taw_mm,
        crop.p,
        dr0_mm=dr0_mm,
        dose_cap_mm=dose_cap_mm,
        irrigate=allowed,
        et0_factor=et0_factor,
    )


def _month_days(year: int, month: int) -> list[date]:
    start = date(year, month, 1)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return [start + timedelta(days=i) for i in range((nxt - start).days)]


def plan_years(weather: Weather, analysis_date: date) -> list[int]:
    """Last HISTORY_YEARS seasons (March–October) that ended on or before the analysis date and are covered.

    The current year counts once its October is over (a jury date in November includes this summer's drought).
    """
    last = analysis_date.year if analysis_date >= date(analysis_date.year, 10, 31) else analysis_date.year - 1
    years = range(last - HISTORY_YEARS + 1, last + 1)
    return [y for y in years if weather.covers(date(y, 3, 1), date(y, 10, 31))]


def _month_values(
    weather: Weather, crop: Crop, balance: RootZoneBalance | None, year: int, month: int
) -> tuple[float, float, float] | None:
    """(ETc, P, need) for one month; None when too many days are missing."""
    days = _month_days(year, month)
    etc = precip = irrigation = 0.0
    gaps = 0
    for d in days:
        if balance is not None:
            b = balance.at(d)
            if b is not None:
                irrigation += b.irrigation_mm  # applied at the start of the day, also on a day without data
        p, e = weather.p_et0(d)
        if p is None or e is None:
            gaps += 1
            continue
        precip += p
        if crop.in_season(d):
            etc += crop.kc(d) * e
    if gaps > MAX_GAP_SHARE * len(days):
        return None
    scale = len(days) / (len(days) - gaps) if gaps else 1.0
    etc, precip = etc * scale, precip * scale
    need = irrigation if balance is not None else max(0.0, etc - precip)
    return etc, precip, need


def water_plan(
    weather: Weather, crop: Crop, analysis_date: date, taw_mm: float | None, dose_cap_mm: float | None = None
) -> WaterPlanResult | None:
    """`dose_cap_mm`: largest single sprinkler dose for the soil; irrigation then follows the weather in small
    doses instead of one refill of the whole root zone (which made every year need about the same water)."""
    years = plan_years(weather, analysis_date)
    if len(years) < MIN_YEARS:
        return None
    balance = (
        irrigated_balance(weather, crop, taw_mm, dose_cap_mm=dose_cap_mm) if taw_mm is not None else None
    )
    rescue = (
        irrigated_balance(weather, crop, taw_mm, only_critical=True, dose_cap_mm=dose_cap_mm)
        if taw_mm is not None
        else None
    )
    method = PlanMethod.ROOT_ZONE if balance is not None else PlanMethod.CROP_BALANCE
    critical = crop.critical_months()

    months: list[PlanMonth] = []
    season_totals: dict[int, float] = dict.fromkeys(years, 0.0)
    complete: set[int] = set(years)
    for m in PLAN_MONTHS:
        rows = {y: _month_values(weather, crop, balance, y, m) for y in years}
        for y, row in rows.items():
            if row is None:
                complete.discard(y)
            else:
                season_totals[y] += row[2]
        ok = [r for r in rows.values() if r is not None]
        etc = [r[0] for r in ok]
        precip = [r[1] for r in ok]
        need = [r[2] for r in ok]
        months.append(
            PlanMonth(
                month=m,
                years=len(ok),
                etc_median_mm=percentile(etc, 50),
                precip_median_mm=percentile(precip, 50),
                need_median_mm=percentile(need, 50),
                need_p80_mm=percentile(need, 80),
                need_p90_mm=percentile(need, 90),
                critical=m in critical,
            )
        )
    totals = [season_totals[y] for y in years if y in complete]
    critical_need: list[float] = []
    if rescue is not None:
        for y in years:
            if y not in complete:
                continue
            critical_need.append(sum(b.irrigation_mm for b in rescue.between(date(y, 3, 1), date(y, 10, 31))))
    else:
        for y in years:
            if y not in complete:
                continue
            vals = [_month_values(weather, crop, None, y, m) for m in PLAN_MONTHS if m in critical]
            critical_need.append(sum(v[2] for v in vals if v is not None))
    return WaterPlanResult(
        method=method,
        years=years,
        months=months,
        season_median_mm=percentile(totals, 50),
        season_p80_mm=percentile(totals, 80),
        season_p90_mm=percentile(totals, 90),
        critical_p80_mm=percentile(critical_need, 80),
    )
