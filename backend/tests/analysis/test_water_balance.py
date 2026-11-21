from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from app.analysis.series import Weather, same_day_in_year
from app.analysis.water_balance import (
    BARE_SOIL_KC,
    RootZoneBalance,
    crop_root_zone_balance,
    kbw_mm,
    root_zone_balance,
    stress_coefficient,
)
from tests.analysis.builders import crop, date_range

# Hand-computed FAO-56 example (eqs. 83–85), TAW = 100 mm, p = 0.5 -> RAW = 50 mm, Dr0 = 40 mm.
#  day  P     ET0   Kc   Ks (from Dr_{i-1})              ETc = Ks·Kc·ET0    Dr_i
#  1    0     5     1.0  1 (40 ≤ 50)                     5.0                45.0
#  2    0     6     1.0  1 (45 ≤ 50)                     6.0                51.0   (crosses RAW)
#  3    0     5     1.0  (100−51)/50 = 0.98              4.9                55.9
#  4    None  5     1.0  gap                             None               55.9   (unchanged)
#  5    2     4     1.0  (100−55.9)/50 = 0.882           3.528              57.428
#  6    80    3     1.0  (100−57.428)/50 = 0.85144       2.55432            0      (−19.97 -> drains)
#  7    0     4     0.5  1                               2.0                2.0
#  8    1     None  0.5  gap                             None               2.0
#  9    0     5     0.5  1                               2.5                4.5
# 10    10    2     0.5  1                               1.0                0      (−4.5 -> drains)
P = [0, 0, 0, None, 2, 80, 0, 1, 0, 10]
ET0 = [5, 6, 5, 5, 4, 3, 4, None, 5, 2]
KC = [1.0] * 6 + [0.5] * 4
EXP_KS = [1.0, 1.0, 0.98, None, 0.882, 0.85144, 1.0, None, 1.0, 1.0]
EXP_ETC = [5.0, 6.0, 4.9, None, 3.528, 2.55432, 2.0, None, 2.5, 1.0]
EXP_DR = [45.0, 51.0, 55.9, 55.9, 57.428, 0.0, 2.0, 2.0, 4.5, 0.0]


def _balance() -> RootZoneBalance:
    days = date_range(date(2024, 6, 1), date(2024, 6, 10))
    return root_zone_balance(days, P, ET0, KC, [True] * 10, taw_mm=100.0, p=0.5, dr0_mm=40.0)


def test_hand_computed_ten_days() -> None:
    bal = _balance()
    assert bal.taw_mm == 100.0
    assert bal.raw_mm == pytest.approx(50.0)
    for i, day in enumerate(bal.days):
        assert day.dr_mm == pytest.approx(EXP_DR[i], abs=0.1), i
        if EXP_ETC[i] is None:
            assert day.etc_mm is None and day.gap
        else:
            assert day.etc_mm == pytest.approx(EXP_ETC[i], abs=0.1), i
            assert day.ks == pytest.approx(EXP_KS[i], abs=0.001), i
    assert bal.gap_days == 2
    assert [d.stressed for d in bal.days] == [False, False, True, False, True, True] + [False] * 4


def test_depletion_never_exceeds_taw_and_ks_zero_at_taw() -> None:
    days = date_range(date(2024, 6, 1), date(2024, 6, 30))
    bal = root_zone_balance(days, [0.0] * 30, [8.0] * 30, [1.2] * 30, [True] * 30, taw_mm=30.0, p=0.5)
    assert all(0.0 <= d.dr_mm <= 30.0 for d in bal.days)
    assert stress_coefficient(30.0, 30.0, 0.5) == 0.0
    assert stress_coefficient(15.0, 30.0, 0.5) == 1.0


def test_invalid_parameters() -> None:
    d = [date(2024, 1, 1)]
    with pytest.raises(ValueError):
        root_zone_balance(d, [0.0], [1.0], [1.0], [True], taw_mm=0.0, p=0.5)
    with pytest.raises(ValueError):
        root_zone_balance(d, [0.0], [1.0], [1.0], [True], taw_mm=50.0, p=1.0)
    with pytest.raises(ValueError):
        root_zone_balance(d, [0.0, 1.0], [1.0], [1.0], [True], taw_mm=50.0, p=0.5)


def _weather(days: list[date], p: Sequence[float | None], e: Sequence[float | None]) -> Weather:
    n = len(days)
    return Weather(days, list(p), list(e), [20.0] * n, [15.0] * n)


def test_kbw_60_day_sum() -> None:
    days = date_range(date(2024, 1, 1), date(2024, 6, 30))
    n = len(days)
    w = _weather(days, [2.0] * n, [3.0] * n)
    assert kbw_mm(w, date(2024, 6, 30)) == pytest.approx(-60.0)
    # Window 2 Jan .. 1 Mar = 60 days
    assert kbw_mm(w, date(2024, 3, 1)) == pytest.approx(-60.0)
    # Window would start before the series -> None (no partial sums)
    assert kbw_mm(w, date(2024, 2, 1)) is None
    assert kbw_mm(w, date(2024, 7, 5)) is None


def test_kbw_gap_handling() -> None:
    days = date_range(date(2024, 1, 1), date(2024, 6, 30))
    n = len(days)
    end = date(2024, 6, 30)
    # 6 missing days of 60 (= 10 %) -> sum scaled from the 54 present days
    p: list[float | None] = [2.0] * n
    for i in range(1, 7):
        p[-i] = None
    w = _weather(days, p, [3.0] * n)
    assert kbw_mm(w, end) == pytest.approx(-60.0)
    # 7 missing days (> 10 %) -> no value
    p[-7] = None
    w = _weather(days, p, [3.0] * n)
    assert kbw_mm(w, end) is None


def test_weather_from_daily_cuts_at_analysis_date() -> None:
    from tests.analysis.builders import daily_series

    daily = daily_series(date(2024, 1, 1), date(2024, 3, 1), lambda d: 1.0)
    w = Weather.from_daily(daily, date(2024, 2, 10))
    assert w.last == date(2024, 2, 10)
    assert w.p_et0(date(2024, 2, 11)) == (None, None)


def test_same_day_in_year_29_feb() -> None:
    assert same_day_in_year(date(2024, 2, 29), 2023) == date(2023, 2, 28)
    assert same_day_in_year(date(2024, 2, 29), 2020) == date(2020, 2, 29)


def test_crop_balance_uses_bare_soil_off_season() -> None:
    maize = crop("maize")
    days = date_range(date(2024, 3, 1), date(2024, 5, 31))
    n = len(days)
    w = _weather(days, [0.0] * n, [2.0] * n)
    bal = crop_root_zone_balance(w, maize, 120.0)
    march = bal.at(date(2024, 3, 10))
    assert march is not None and not march.in_season
    assert march.kc == BARE_SOIL_KC and march.etc_mm == pytest.approx(0.6)
    may = bal.at(date(2024, 5, 1))
    assert may is not None and may.in_season and may.kc == maize.kc_ini
    assert not march.stressed  # no crop -> never counted as crop stress
    assert bal.at(date(2024, 6, 1)) is None
    assert bal.between(date(2024, 3, 1), date(2024, 3, 31))[-1].day == date(2024, 3, 31)
    assert days[-1] - days[0] == timedelta(days=n - 1)
