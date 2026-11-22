"""Official IUNG-PIB critical KBW (Dz.U. 2019 poz. 739): table integrity and period lookup."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.crops.catalog import load_crops
from app.crops.iung import IungMissing, IungTable, IungThreshold, iung_lookup, load_iung_table


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


def _table_dict() -> dict:
    return load_iung_table().model_dump()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["groups"][0]["kbw_critical_mm"]["I"].__setitem__(0, 12.0),  # positive value
        lambda d: d["periods"].__setitem__(1, "03-01/03-10"),  # not six dekads
        lambda d: d["periods"].reverse(),  # out of order
        lambda d: d["groups"][0]["kbw_critical_mm"]["I"].pop(),  # wrong length
        lambda d: d.update(extra_key=1),  # unknown key
    ],
)
def test_table_validation_rejects_broken_tables(mutate) -> None:  # type: ignore[no-untyped-def]
    d = _table_dict()
    mutate(d)
    with pytest.raises(ValidationError):
        IungTable.model_validate(d)
