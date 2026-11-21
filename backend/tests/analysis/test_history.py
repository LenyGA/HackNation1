from datetime import date, timedelta

import pytest

from app.analysis.history import HistoryMethod, analyse_history, empirical_percentile
from app.analysis.series import Weather
from app.analysis.water_balance import crop_root_zone_balance
from app.sources.open_meteo import DailySeries, history_start
from tests.analysis.builders import crop, daily_series

ANALYSIS_DATE = date(2024, 8, 15)
DRY_JUNE_YEARS = {2016, 2019, 2022}


def _precip(d: date) -> float:
    if d.year in DRY_JUNE_YEARS and d.month == 6:
        return 0.0
    if d.year in DRY_JUNE_YEARS and d.month == 7 and d.day == 1:
        return 150.0  # refills the root zone so July is not a deficit month
    return 4.0


def _et0(d: date) -> float:
    return 6.0 if d.year in DRY_JUNE_YEARS and d.month == 6 else 2.0


def _daily(end: date = ANALYSIS_DATE) -> DailySeries:
    return daily_series(history_start(ANALYSIS_DATE), end, _precip, _et0)


def test_three_dry_junes_in_ten_years_give_30_percent() -> None:
    maize = crop("maize")
    weather = Weather.from_daily(_daily(), ANALYSIS_DATE)
    balance = crop_root_zone_balance(weather, maize, 80.0)
    hist = analyse_history(weather, maize, ANALYSIS_DATE, balance)

    assert hist.method is HistoryMethod.ROOT_ZONE
    assert [y.year for y in hist.years] == list(range(2014, 2024))
    freq = {f.month: f for f in hist.months}
    assert freq[6].years_with_data == 10
    assert freq[6].deficit_years == 3
    assert freq[6].frequency == pytest.approx(0.3)
    assert 6 in hist.risk_months
    for m in (5, 7, 8):
        assert freq[m].frequency == 0.0, m
    assert 3 not in freq and 4 not in freq  # maize not on the field in March, only 6 days in April
    dry = [y.year for y in hist.years if 6 in y.deficit_months]
    assert set(dry) == DRY_JUNE_YEARS
    assert hist.deficit_year_share == pytest.approx(0.3)
    june_2019 = next(y for y in hist.years if y.year == 2019).months[6]
    assert june_2019.stress_days is not None and june_2019.stress_days >= 10
    # June is not a maize critical month (July–August), so it is not a critical-risk month.
    assert hist.critical_risk_months == []


def test_without_soil_frequency_is_not_determined_but_crop_balance_reported() -> None:
    """crop_balance method (no soil): history.py deliberately reports no deficit frequency, only P − ETc."""
    maize = crop("maize")
    weather = Weather.from_daily(_daily(), ANALYSIS_DATE)
    hist = analyse_history(weather, maize, ANALYSIS_DATE, None)
    assert hist.method is HistoryMethod.CROP_BALANCE
    assert hist.risk_months == []
    assert all(f.frequency is None or f.years_with_data == 0 for f in hist.months)
    june = {y.year: y.months[6].crop_balance_mm for y in hist.years}
    assert all(v is not None for v in june.values())
    dry = sorted(june, key=lambda y: june[y] or 0.0)[:3]
    assert set(dry) == DRY_JUNE_YEARS
    assert all((june[y] or 0.0) < -100 for y in DRY_JUNE_YEARS)
    assert all((june[y] or 0.0) > 0 for y in june if y not in DRY_JUNE_YEARS)


def test_poison_after_analysis_date_has_no_effect() -> None:
    maize = crop("maize")
    clean = _daily()
    poisoned_end = ANALYSIS_DATE + timedelta(days=120)
    base = daily_series(history_start(ANALYSIS_DATE), poisoned_end, _precip, _et0)
    n_clean = len(clean.dates)
    poisoned = base.model_copy(
        update={
            "precip_mm": base.precip_mm[:n_clean] + [5000.0] * (len(base.dates) - n_clean),
            "et0_mm": base.et0_mm[:n_clean] + [0.0] * (len(base.dates) - n_clean),
        }
    )
    results = []
    for daily in (clean, poisoned):
        w = Weather.from_daily(daily, ANALYSIS_DATE)
        assert w.last == ANALYSIS_DATE
        bal = crop_root_zone_balance(w, maize, 80.0)
        results.append((analyse_history(w, maize, ANALYSIS_DATE, bal), bal.days[-1]))
    assert results[0] == results[1]


def test_current_windows_and_percentiles() -> None:
    maize = crop("maize")
    weather = Weather.from_daily(_daily(), ANALYSIS_DATE)
    hist = analyse_history(weather, maize, ANALYSIS_DATE, None)
    assert hist.current.precip_30d_mm == pytest.approx(120.0)
    assert hist.current.precip_90d_mm == pytest.approx(360.0)
    assert hist.current.kbw_60d_mm == pytest.approx(120.0)
    # all years have identical 30-day windows ending 15 Aug -> ties count half
    assert hist.current.precip_30d_pct == pytest.approx(50.0)


def test_empirical_percentile() -> None:
    sample: list[float | None] = [float(v) for v in range(10)]
    assert empirical_percentile(-1.0, sample) == 0.0
    assert empirical_percentile(100.0, sample) == 100.0
    assert empirical_percentile(4.5, sample) == 50.0
    assert empirical_percentile(4.0, sample) == 45.0  # 4 below + half of 1 tie
    assert empirical_percentile(None, sample) is None
    assert empirical_percentile(1.0, [1.0, 2.0, 3.0, 4.0, None, None]) is None  # 4 values < 5
    assert empirical_percentile(3.0, [1.0, 2.0, 3.0, 4.0, 5.0, None]) == 50.0


def test_history_with_gaps_marks_months_unknown() -> None:
    maize = crop("maize")
    daily = _daily()
    p = list(daily.precip_mm)
    for i, d in enumerate(daily.dates):
        if d.year == 2019 and d.month == 6 and d.day <= 10:
            p[i] = None
    w = Weather.from_daily(daily.model_copy(update={"precip_mm": p}), ANALYSIS_DATE)
    hist = analyse_history(w, maize, ANALYSIS_DATE, crop_root_zone_balance(w, maize, 80.0))
    june = {f.month: f for f in hist.months}[6]
    assert june.years_with_data == 9
    assert june.deficit_years == 2
    assert next(y for y in hist.years if y.year == 2019).months[6].deficit is None


def test_short_weather_series_does_not_crash() -> None:
    maize = crop("maize")
    daily = daily_series(date(2023, 1, 1), ANALYSIS_DATE, _precip, _et0)
    w = Weather.from_daily(daily, ANALYSIS_DATE)
    hist = analyse_history(w, maize, ANALYSIS_DATE, crop_root_zone_balance(w, maize, 80.0))
    assert hist.years_with_data == 1
    assert hist.current.precip_30d_pct is None  # fewer than 5 past years


@pytest.mark.parametrize(
    "analysis_date", [date(2024, 2, 29), date(2024, 10, 1), date(2024, 10, 2), date(2026, 11, 21)]
)
@pytest.mark.parametrize("crop_id", ["maize", "winter_wheat", "grassland"])
def test_awkward_dates(analysis_date: date, crop_id: str) -> None:
    c = crop(crop_id)
    daily = daily_series(history_start(analysis_date), analysis_date, _precip, _et0)
    w = Weather.from_daily(daily, analysis_date)
    hist = analyse_history(w, c, analysis_date, crop_root_zone_balance(w, c, 80.0))
    assert len(hist.years) == 10
    assert hist.current.precip_90d_mm is not None
    assert hist.current.precip_90d_pct is not None
