"""Trends, seasonal water plan, strategy simulator and slope profile (pure functions, synthetic data)."""

from datetime import date

import pytest

from app.analysis.history import analyse_history
from app.analysis.profile import slope_profile
from app.analysis.series import Weather
from app.analysis.simulate import extra_soc_after, simulate
from app.analysis.soil import soil_properties
from app.analysis.trends import Direction, RecentChange, analyse_trends, completed_seasons, theil_sen_slope
from app.analysis.water_balance import crop_root_zone_balance, root_zone_balance
from app.analysis.water_plan import percentile, water_plan
from app.sources.base import parcel_shape
from app.sources.open_meteo import history_start
from tests.analysis.builders import (
    crop,
    daily_series,
    default_parcel,
    grid_around,
    random_precip,
    seasonal_et0,
    seasonal_t,
    soil_data,
    soil_layers,
    tilted_grid,
)

DAY = date(2025, 7, 20)


def weather(precip=None, tmean=seasonal_t, et0=seasonal_et0, day: date = DAY) -> Weather:
    daily = daily_series(history_start(day), day, precip or random_precip(3), et0=et0, tmean=tmean)
    return Weather.from_daily(daily, day)


def loam(soc: float = 12.0):
    return soil_properties(soil_data(soil_layers(40, 40, 20, soc)), crop("potato").root_depth_m)


# --- water balance with irrigation ---------------------------------------------------------------


def test_irrigation_refills_to_field_capacity_above_raw() -> None:
    days = [date(2025, 7, d) for d in range(1, 11)]
    out = root_zone_balance(
        days, [0.0] * 10, [5.0] * 10, [1.0] * 10, [True] * 10, 50.0, 0.5, irrigate=[True] * 10
    )
    assert sum(d.irrigation_mm for d in out.days) > 0
    assert all(not d.stressed for d in out.days)  # never below RAW at the start of a day
    assert max(d.dr_mm for d in out.days) <= 25.0 + 5.0


def test_no_irrigation_by_default_and_et0_factor_scales_use() -> None:
    days = [date(2025, 7, d) for d in range(1, 4)]
    base = root_zone_balance(days, [0.0] * 3, [2.0] * 3, [1.0] * 3, [True] * 3, 100.0, 0.5)
    hot = root_zone_balance(days, [0.0] * 3, [2.0] * 3, [1.0] * 3, [True] * 3, 100.0, 0.5, et0_factor=1.5)
    assert all(d.irrigation_mm == 0 for d in base.days)
    assert hot.days[-1].dr_mm == pytest.approx(1.5 * base.days[-1].dr_mm)


# --- trends --------------------------------------------------------------------------------------


def test_theil_sen_is_robust_to_one_outlier() -> None:
    xs = [float(x) for x in range(10)]
    ys = [2.0 * x for x in xs]
    ys[4] = 500.0
    assert theil_sen_slope(xs, ys) == pytest.approx(2.0)


def test_completed_seasons_exclude_the_running_season() -> None:
    w = weather()
    assert completed_seasons(w, DAY)[-1] == 2024
    autumn = weather(day=date(2025, 11, 1))
    assert completed_seasons(autumn, date(2025, 11, 1))[-1] == 2025


def test_warming_and_drying_trend_detected() -> None:
    def tmean(d: date) -> float:
        return seasonal_t(d) + 0.1 * (d.year - 2014)  # +1 °C per decade

    def et0(d: date) -> float:
        return seasonal_et0(d) * (1 + 0.03 * (d.year - 2014))

    w = weather(precip=random_precip(5), tmean=tmean, et0=et0)
    t = analyse_trends(w, crop("potato"), DAY, None)
    assert t is not None
    temp = t.get("tmean_c")
    assert temp is not None and temp.slope_per_decade == pytest.approx(1.0, abs=0.05)
    assert temp.direction is Direction.WORSE
    kbw = t.get("kbw_mm")
    assert kbw is not None and kbw.direction is Direction.WORSE
    assert t.get("stress_days") is not None and t.get("stress_days").mean_all is None  # no soil → no stress


def test_flat_climate_is_stable_and_typical() -> None:
    w = weather(precip=lambda d: 1.5)
    t = analyse_trends(w, crop("potato"), DAY, None)
    assert t is not None
    for key in ("tmean_c", "kbw_mm", "et0_mm"):
        m = t.get(key)
        assert m is not None and m.direction is Direction.STABLE
        assert m.recent is RecentChange.TYPICAL


def test_recent_dry_seasons_flagged() -> None:
    def precip(d: date) -> float:
        return 0.2 if d.year >= 2023 else 2.5

    w = weather(precip=precip)
    t = analyse_trends(w, crop("potato"), DAY, None)
    assert t is not None
    kbw = t.get("kbw_mm")
    assert kbw is not None and kbw.recent is RecentChange.CRITICAL


def test_too_short_series_gives_no_trend() -> None:
    daily = daily_series(date(2022, 1, 1), DAY, random_precip(1))
    assert analyse_trends(Weather.from_daily(daily, DAY), crop("potato"), DAY, None) is None


# --- water plan ----------------------------------------------------------------------------------


def test_percentile_needs_enough_years() -> None:
    assert percentile([1.0, 2.0, 3.0], 80) is None
    assert percentile([float(v) for v in range(1, 11)], 50) == pytest.approx(5.5)


def test_dry_year_need_not_below_typical() -> None:
    w = weather()
    soil = loam()
    plan = water_plan(w, crop("potato"), DAY, soil.taw_mm)
    assert plan is not None and plan.method.value == "root_zone"
    assert (
        plan.season_median_mm is not None
        and plan.season_p80_mm is not None
        and plan.season_p90_mm is not None
    )
    assert plan.season_median_mm <= plan.season_p80_mm <= plan.season_p90_mm
    for m in plan.months:
        if m.need_median_mm is not None:
            assert m.need_median_mm <= (m.need_p80_mm or 0) <= (m.need_p90_mm or 0)
    # Off-season months of a potato crop need no irrigation.
    march = next(m for m in plan.months if m.month == 3)
    assert march.need_p90_mm == 0
    assert plan.critical_p80_mm is not None and plan.critical_p80_mm <= plan.season_p80_mm + 1e-9


def test_wet_climate_needs_no_irrigation() -> None:
    plan = water_plan(weather(precip=lambda d: 8.0), crop("potato"), DAY, loam().taw_mm)
    assert plan is not None and plan.season_p90_mm == pytest.approx(0.0)


def test_plan_without_soil_uses_crop_balance() -> None:
    plan = water_plan(weather(), crop("potato"), DAY, None)
    assert plan is not None and plan.method.value == "crop_balance"


# --- simulator -----------------------------------------------------------------------------------


def test_cover_crop_carbon_gives_small_capacity_gain() -> None:
    assert extra_soc_after(5) == pytest.approx(0.381, abs=0.01)  # g C / kg over 0–30 cm
    w = weather()
    soil = loam()
    t = analyse_trends(w, crop("potato"), DAY, crop_root_zone_balance(w, crop("potato"), soil.taw_mm))
    sim = simulate(w, crop("potato"), DAY, soil, t)
    assert sim is not None
    assert 0 <= sim.taw_gain_5y_mm < 2  # Minasny & McBratney 2018: limited effect


def test_strategies_order_is_physical() -> None:
    w = weather()
    soil = loam()
    sim = simulate(w, crop("potato"), DAY, soil, None)
    assert sim is not None
    by = {(r.strategy, r.year_ahead): r for r in sim.results}
    for k in range(1, 6):
        none, rescue, full = by[("none", k)], by[("rescue", k)], by[("full", k)]
        assert full.stress_days_median <= rescue.stress_days_median <= none.stress_days_median
        assert none.irrigation_mm_median == 0
        assert (rescue.irrigation_mm_p80 or 0) <= (full.irrigation_mm_p80 or 0)
        assert by[("retention", k)].stress_days_median <= none.stress_days_median


def test_irrigation_does_not_carry_over_after_wet_winters() -> None:
    def precip(d: date) -> float:
        return 4.0 if d.month in (10, 11, 12, 1, 2, 3) else 0.5

    sim = simulate(weather(precip=precip), crop("potato"), DAY, loam(), None)
    assert sim is not None
    assert sim.spring_storage_none_mm == pytest.approx(sim.spring_storage_full_mm, abs=1.0)


def test_simulator_needs_soil() -> None:
    assert simulate(weather(), crop("potato"), DAY, None, None) is None


# --- history: severe months ----------------------------------------------------------------------


def test_severe_months_counted_and_mean_stress_reported() -> None:
    w = weather(precip=lambda d: 0.0)
    soil = loam()
    balance = crop_root_zone_balance(w, crop("potato"), soil.taw_mm)
    h = analyse_history(w, crop("potato"), DAY, balance)
    july = next(f for f in h.months if f.month == 7)
    assert july.severe_years == july.deficit_years == july.years_with_data
    assert july.mean_stress_days is not None and july.mean_stress_days > 15


# --- slope profile -------------------------------------------------------------------------------


def test_profile_runs_downhill() -> None:
    parcel = default_parcel()
    prof = slope_profile(tilted_grid(parcel, slope=0.04), parcel_shape(parcel))
    assert prof is not None and not prof.along_long_axis
    assert prof.points[0].elevation_m > prof.points[-1].elevation_m
    assert prof.mean_slope_pct == pytest.approx(4.0, abs=0.6)
    assert prof.direction is not None


def test_flat_profile_uses_long_axis_and_marks_hollow() -> None:
    parcel = default_parcel()

    def bowl(x, y):  # flat with a 0.5 m deep pit in the middle
        cx, cy = x.mean(), y.mean()
        return 100.0 - 0.5 * ((abs(x - cx) < 25) & (abs(y - cy) < 25))

    prof = slope_profile(grid_around(parcel_shape(parcel), bowl), parcel_shape(parcel))
    assert prof is not None and prof.along_long_axis
    assert any(p.hollow for p in prof.points)
