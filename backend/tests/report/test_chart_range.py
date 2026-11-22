"""Water chart for a chosen time range (report/chart_range.py)."""

from datetime import date, timedelta

import pytest

from app.report.chart_range import RANGE_DAYS, range_chart, resolve_window
from app.report.charts_svg import season_svg
from app.report.models import DailyWater

START = date(2015, 10, 1)
ANALYSIS = date(2026, 7, 15)


def _daily(precip: float = 2.0, need: float = 3.0, until: date = ANALYSIS) -> DailyWater:
    n = (until - START).days + 1
    return DailyWater(start=START, precip_mm=[precip] * n, crop_need_mm=[need] * n, source="test")


@pytest.mark.parametrize("key", list(RANGE_DAYS))
def test_preset_windows_end_on_analysis_date(key: str) -> None:
    window = resolve_window(_daily(), ANALYSIS, key)  # type: ignore[arg-type]
    assert window == (ANALYSIS - timedelta(days=RANGE_DAYS[key] - 1), ANALYSIS)


def test_one_day_window_draws_a_line_from_zero() -> None:
    chart = range_chart(_daily(), ANALYSIS, ANALYSIS)
    assert chart is not None
    assert [p.precip_mm for p in chart.points] == [0.0, 2.0]
    assert [p.crop_need_mm for p in chart.points] == [0.0, 3.0]
    assert chart.points[0].day == ANALYSIS - timedelta(days=1)
    assert chart.years == 10


def test_cumulative_sums_and_history_band() -> None:
    chart = range_chart(_daily(), ANALYSIS - timedelta(days=6), ANALYSIS)
    assert chart is not None
    last = chart.points[-1]
    assert (last.precip_mm, last.crop_need_mm) == (14.0, 21.0)
    assert (last.precip_hist_min_mm, last.precip_hist_median_mm, last.precip_hist_max_mm) == (
        14.0,
        14.0,
        14.0,
    )
    assert len(chart.points) == 8  # zero point + 7 days


def test_long_window_uses_weekly_points_and_keeps_last_day() -> None:
    start, end = resolve_window(_daily(), ANALYSIS, "1y") or (None, None)
    assert start and end
    chart = range_chart(_daily(), start, end)
    assert chart is not None
    assert chart.points[-1].day == ANALYSIS
    assert len(chart.points) < 60


def test_band_hidden_without_enough_previous_years() -> None:
    # Data start only 3 years before the window: fewer than 5 comparison years.
    daily = DailyWater(start=date(2023, 1, 1), precip_mm=[1.0] * 1292, crop_need_mm=[1.0] * 1292, source="t")
    chart = range_chart(daily, ANALYSIS - timedelta(days=29), ANALYSIS)
    assert chart is not None
    assert chart.years == 0
    assert all(p.precip_hist_median_mm is None for p in chart.points)


def test_missing_day_ends_the_cumulative_line() -> None:
    daily = _daily()
    daily.precip_mm[(ANALYSIS - START).days - 1] = None
    chart = range_chart(daily, ANALYSIS - timedelta(days=6), ANALYSIS)
    assert chart is not None
    assert chart.points[-1].precip_mm is None
    assert chart.points[-1].crop_need_mm == 21.0


def test_custom_window_validation() -> None:
    daily = _daily()
    ok = resolve_window(daily, ANALYSIS, "custom", date(2020, 5, 1), date(2020, 8, 31))
    assert ok == (date(2020, 5, 1), date(2020, 8, 31))
    assert resolve_window(daily, ANALYSIS, "custom", None, date(2020, 8, 31)) is None
    assert resolve_window(daily, ANALYSIS, "custom", date(2020, 9, 1), date(2020, 8, 31)) is None  # reversed
    assert resolve_window(daily, ANALYSIS, "custom", date(2026, 7, 1), date(2026, 7, 16)) is None  # future
    assert resolve_window(daily, ANALYSIS, "custom", date(2016, 1, 1), date(2016, 2, 1)) is None  # > 10 years


def test_preset_window_is_cut_to_available_data() -> None:
    daily = _daily(until=ANALYSIS - timedelta(days=3))  # last days not available yet
    assert resolve_window(daily, ANALYSIS, "7d") == (
        ANALYSIS - timedelta(days=9),
        ANALYSIS - timedelta(days=3),
    )


def test_season_svg_renders_lines_and_band() -> None:
    chart = range_chart(_daily(), ANALYSIS - timedelta(days=181), ANALYSIS)
    assert chart is not None
    svg = season_svg(chart)
    assert svg.startswith("<svg") and svg.count("<path") == 4  # band, median, need, rain
    assert "15.07" in svg


def test_season_svg_says_missing_instead_of_zero() -> None:
    daily = _daily()
    daily.precip_mm[(ANALYSIS - START).days - 1] = None
    chart = range_chart(daily, ANALYSIS - timedelta(days=6), ANALYSIS)
    assert chart is not None
    assert "spadło brak danych deszczu" in season_svg(chart)


def test_report_water_daily_ends_on_the_last_day_with_rain_data() -> None:
    from tests.report.builders import rich_report

    daily = rich_report().water_daily
    assert daily is not None
    assert daily.precip_mm[-1] is not None
    assert len(daily.precip_mm) == len(daily.crop_need_mm)
