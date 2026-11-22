"""Recommendation horizon: now vs before the next season (plan M3.5, R5)."""

from datetime import date

import pytest

from app.recommendations.models import Horizon
from tests.recommendations.builders import scenario


def _horizons(crop_id: str, day: date) -> dict[str, Horizon]:
    _, _, recs = scenario(crop_id=crop_id, day=day)
    return {r.id: r.horizon for r in recs}


@pytest.mark.parametrize("crop_id", ["rye", "winter_wheat", "spring_barley", "maize", "potato", "sugar_beet"])
@pytest.mark.parametrize("day", [date(2024, 4, 15), date(2024, 7, 22), date(2024, 9, 15)])
def test_no_main_crop_sowing_advice_now(crop_id: str, day: date) -> None:
    _, _, recs = scenario(crop_id=crop_id, day=day)
    now = [r for r in recs if r.horizon is Horizon.NOW]
    assert all(r.id != "crop_timing_variety" for r in now)
    assert all("termin siewu" not in r.title_pl for r in now)


@pytest.mark.parametrize(
    ("crop_id", "day"),
    [("maize", date(2024, 9, 15)), ("sugar_beet", date(2024, 9, 15)), ("winter_wheat", date(2024, 7, 10))],
)
def test_stubble_and_catch_crop_not_now_while_the_crop_still_ripens(crop_id: str, day: date) -> None:
    h = _horizons(crop_id, day)
    assert h.get("crop_residues", Horizon.SEASON) is Horizon.SEASON
    assert h.get("winter_cover_crop", Horizon.SEASON) is Horizon.SEASON


def test_stubble_now_in_the_last_days_before_harvest() -> None:
    assert _horizons("winter_wheat", date(2024, 7, 30))["crop_residues"] is Horizon.NOW


def test_rye_after_harvest_residues_now() -> None:
    h = _horizons("rye", date(2024, 7, 22))
    assert h["crop_residues"] is Horizon.NOW  # fires: right after harvest
    assert h["crop_timing_variety"] is Horizon.SEASON


def test_residues_not_now_while_the_crop_grows() -> None:
    h = _horizons("maize", date(2024, 7, 15))
    assert h["crop_residues"] is Horizon.SEASON  # does NOT fire: maize is still on the field
    assert h["irrigation"] is Horizon.NOW


def test_catch_crop_now_only_after_harvest_in_summer() -> None:
    assert _horizons("spring_barley", date(2024, 8, 10))["winter_cover_crop"] is Horizon.NOW
    assert _horizons("maize", date(2024, 7, 15))["winter_cover_crop"] is Horizon.SEASON


def test_nothing_is_now_for_winter_wheat_in_november_without_a_ditch() -> None:
    h = _horizons("winter_wheat", date(2024, 11, 21))  # default scenario: no ditch along the parcel
    assert "ditch_check_dam" not in h
    assert h and all(v is Horizon.SEASON for v in h.values())


def test_structures_are_always_for_the_season() -> None:
    for day in (date(2024, 4, 15), date(2024, 7, 15), date(2024, 11, 21)):
        h = _horizons("maize", day)
        for rule in ("midfield_trees", "organic_matter", "reduced_tillage_mulch"):
            if rule in h:
                assert h[rule] is Horizon.SEASON


def test_ditch_check_dam_now_only_in_the_recharge_months() -> None:
    from tests.recommendations.builders import basin, hydro

    def h(day: date) -> Horizon | None:
        _, _, recs = scenario(
            crop_id="winter_wheat", day=day, surface=basin, hydro_data=lambda p: hydro(p, ditch_m=200.0)
        )
        return next((r.horizon for r in recs if r.id == "ditch_check_dam"), None)

    assert h(date(2024, 11, 21)) is Horizon.NOW
    assert h(date(2024, 7, 15)) in (Horizon.SEASON, None)
