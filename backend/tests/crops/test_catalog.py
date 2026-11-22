from datetime import date, timedelta

import pytest

from app.crops.catalog import load_crops, month_day

CROP_IDS = [
    "winter_wheat",
    "rye",
    "spring_barley",
    "winter_rapeseed",
    "maize",
    "potato",
    "sugar_beet",
    "grassland",
    "field_vegetables",
]


def test_catalog_has_the_nine_crops() -> None:
    assert sorted(load_crops()) == sorted(CROP_IDS)


@pytest.mark.parametrize("crop_id", CROP_IDS)
@pytest.mark.parametrize("year", [2023, 2024])  # normal and leap year
def test_kc_defined_for_every_day_of_the_year(crop_id: str, year: int) -> None:
    crop = load_crops()[crop_id]
    d = date(year, 1, 1)
    while d.year == year:
        kc = crop.kc(d)
        assert isinstance(kc, float)
        assert 0.0 <= kc <= 1.5
        if not crop.in_season(d):
            assert kc == crop.kc_off_season
        d += timedelta(days=1)


@pytest.mark.parametrize("day", [date(2024, 3, 1), date(2024, 3, 15), date(2024, 3, 31)])
def test_maize_in_march_is_empty_field(day: date) -> None:
    maize = load_crops()["maize"]
    assert not maize.in_season(day)
    assert maize.kc(day) == 0.0


def test_maize_curve_follows_fao56_stages() -> None:
    maize = load_crops()["maize"]
    start = date(2024, 4, 25)
    ini, dev, mid, late = maize.stages_days
    assert maize.kc(start) == maize.kc_ini
    assert maize.kc(start + timedelta(days=ini - 1)) == maize.kc_ini
    half_dev = maize.kc(start + timedelta(days=ini + dev // 2))
    assert maize.kc_ini < half_dev < maize.kc_mid
    assert maize.kc(start + timedelta(days=ini + dev)) == maize.kc_mid
    last = start + timedelta(days=maize.season_days - 1)
    assert maize.kc(last) == pytest.approx(maize.kc_end)
    assert not maize.in_season(last + timedelta(days=1))


def test_winter_wheat_season_crosses_new_year() -> None:
    wheat = load_crops()["winter_wheat"]
    assert wheat.winter
    assert wheat.season_start(date(2024, 1, 15)) == date(2023, 9, 25)
    assert wheat.in_season(date(2023, 12, 31)) and wheat.in_season(date(2024, 1, 1))
    assert wheat.kc(date(2024, 1, 15)) == wheat.kc_ini
    assert wheat.kc(date(2024, 6, 1)) == wheat.kc_mid  # mid-season in early June
    assert not wheat.in_season(date(2024, 9, 10))  # after harvest, before sowing
    assert wheat.kc(date(2024, 9, 10)) == 0.0
    assert wheat.season_start(date(2024, 9, 25)) == date(2024, 9, 25)
    assert wheat.last_season_start(date(2024, 9, 10)) == date(2023, 9, 25)


def test_critical_periods() -> None:
    crops = load_crops()
    maize = crops["maize"]
    p = maize.critical_period_at(date(2024, 7, 15))
    assert p is not None and p.name_pl
    assert maize.critical_period_at(date(2024, 5, 15)) is None
    assert maize.critical_period_at(date(2024, 3, 1)) is None  # off-season
    assert maize.critical_months() == {7, 8}

    wheat = crops["winter_wheat"]
    p = wheat.critical_period_at(date(2024, 5, 20))
    assert p is not None
    assert p.range_for_season(date(2023, 9, 25)) == (date(2024, 5, 1), date(2024, 6, 20))
    assert wheat.critical_period_at(date(2024, 1, 20)) is None
    assert wheat.critical_months() == {5, 6}


@pytest.mark.parametrize("crop_id", CROP_IDS)
def test_critical_periods_lie_inside_the_season(crop_id: str) -> None:
    crop = load_crops()[crop_id]
    start = month_day(crop.sowing, 2023)
    for period in crop.critical_periods:
        lo, hi = period.range_for_season(start)
        assert crop.in_season(lo) and crop.in_season(hi), (crop_id, lo, hi)
        assert crop.critical_period_at(lo) is not None


def test_month_day_leap_fallback() -> None:
    assert month_day("02-29", 2024) == date(2024, 2, 29)
    assert month_day("02-29", 2023) == date(2023, 2, 28)


def test_kc_on_29_february() -> None:
    for crop in load_crops().values():
        crop.kc(date(2024, 2, 29))
