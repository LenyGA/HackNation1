"""Official IUNG-PIB critical KBW (Dz.U. 2019 poz. 739): table integrity and period lookup."""

from datetime import date

import pytest

from app.crops.catalog import load_crops
from app.crops.iung import IungMissing, IungThreshold, iung_lookup, iung_threshold, load_iung_table


def _found(crop: str, cat: str | None, day: date) -> IungThreshold:
    t = iung_lookup(crop, cat, day)
    assert isinstance(t, IungThreshold), t
    return t


def test_table_has_citation_and_only_catalogue_crops() -> None:
    table = load_iung_table()
    assert "Dz. U. 2019 poz. 739" in table.source
    assert table.url.startswith("https://")
    assert len(table.periods) == 14
    catalogue = set(load_crops())
    listed = [c for g in table.groups for c in g.crops]
    assert len(listed) == len(set(listed))
    assert set(listed) <= catalogue
    assert catalogue - set(listed) == {"grassland"}


def test_spot_values_from_the_regulation() -> None:
    # Annex: winter cereals, category III, period 5 (1 V – 30 VI) = −213; maize, cat. I, period 14 = −164.
    t = _found("winter_wheat", "III", date(2024, 6, 30))
    assert (t.period_start, t.period_end, t.kbw_critical_mm) == (date(2024, 5, 1), date(2024, 6, 30), -213)
    assert _found("rye", "III", date(2024, 6, 30)).kbw_critical_mm == -213  # same group
    assert _found("maize", "I", date(2024, 9, 30)).kbw_critical_mm == -164
    assert _found("sugar_beet", "IV", date(2024, 5, 20)).kbw_critical_mm == -296


def test_latest_finished_period_is_used() -> None:
    # 15 July: periods ending 10 VII (no. 6) is the latest finished one.
    t = _found("spring_barley", "II", date(2024, 7, 15))
    assert t.period_end == date(2024, 7, 10) and t.kbw_critical_mm == -172
    assert _found("spring_barley", "II", date(2024, 7, 20)).period_end == date(2024, 7, 20)


def test_rapeseed_gap_in_summer_and_autumn_periods() -> None:
    assert iung_lookup("winter_rapeseed", "III", date(2024, 8, 5)) is IungMissing.OUTSIDE_PERIODS
    assert _found("winter_rapeseed", "III", date(2024, 9, 25)).period_end == date(2024, 9, 20)


@pytest.mark.parametrize("day", [date(2024, 3, 1), date(2024, 5, 19), date(2024, 11, 22)])
def test_outside_assessed_periods(day: date) -> None:
    assert iung_lookup("winter_wheat", "II", day) is IungMissing.OUTSIDE_PERIODS


def test_stale_period_is_not_used() -> None:
    # Winter cereals end at 10 VIII; on 25 VIII that is more than a dekad old.
    assert _found("winter_wheat", "I", date(2024, 8, 20)).period_end == date(2024, 8, 10)
    assert iung_lookup("winter_wheat", "I", date(2024, 8, 25)) is IungMissing.OUTSIDE_PERIODS


def test_missing_reasons() -> None:
    day = date(2024, 7, 1)
    assert iung_lookup("grassland", "II", day) is IungMissing.CROP_NOT_COVERED
    assert iung_lookup("sugar_beet", "I", day) is IungMissing.SOIL_NOT_COVERED
    assert iung_lookup("maize", None, day) is IungMissing.NO_SOIL_CATEGORY
    assert iung_threshold("grassland", "II", day) is None
