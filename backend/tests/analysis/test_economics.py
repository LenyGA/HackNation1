"""G10 / M5.3: irrigation economics from this parcel's yield losses (FAO-33), GUS prices and cost ranges."""

from datetime import date, timedelta

import pytest

from app.analysis.economics import (
    EconomicsStatus,
    Verdict,
    irrigation_economics,
    season_losses,
)
from app.analysis.water_balance import BalanceDay, RootZoneBalance
from app.crops.catalog import load_crops
from app.crops.economics import load_economics

CROPS = load_crops()
YEARS = list(range(2015, 2025))


def balance(et_ratio: float, years: list[int] = YEARS, gap_every: int = 0) -> RootZoneBalance:
    """Every in-season day: ET0 4 mm, Kc 1, actual ET = ratio · 4 mm."""
    days: list[BalanceDay] = []
    for y in years:
        d = date(y, 3, 1)
        i = 0
        while d <= date(y, 10, 31):
            gap = gap_every > 0 and i % gap_every == 0
            days.append(
                BalanceDay(
                    d,
                    None if gap else 0.0,
                    None if gap else 4.0,
                    1.0,
                    True,
                    et_ratio,
                    None if gap else 4.0 * et_ratio,
                    50.0,
                )
            )
            d += timedelta(days=1)
            i += 1
    return RootZoneBalance(taw_mm=100, raw_mm=50, p=0.5, days=days)


def econ(
    crop_id: str,
    et_ratio: float = 0.85,
    area_ha: float = 7.6,
    need_mm: float | None = 150.0,
    tech: str | None = "reel",
    bal: RootZoneBalance | None = None,
):  # type: ignore[no-untyped-def]
    return irrigation_economics(
        crop=CROPS[crop_id],
        catalog=load_economics(),
        tech=tech,  # type: ignore[arg-type]
        efficiency=0.75,
        area_ha=area_ha,
        balance=bal if bal is not None else balance(et_ratio),
        years=YEARS,
        typical_need_mm=need_mm,
        history=None,
    )


def test_season_loss_follows_fao33() -> None:
    losses = season_losses(balance(0.8), YEARS, ky=1.25)
    assert len(losses) == 10
    assert losses[0].et_ratio == pytest.approx(0.8)
    assert losses[0].loss_share == pytest.approx(0.25)


def test_no_stress_no_loss() -> None:
    assert all(s.loss_share == 0 for s in season_losses(balance(1.0), YEARS, ky=1.1))


def test_seasons_with_too_many_gaps_are_skipped() -> None:
    assert season_losses(balance(0.8, gap_every=5), YEARS, ky=1.0) == []


def test_rye_on_7_6_ha_is_unprofitable() -> None:
    e = econ("rye")
    assert e.status is EconomicsStatus.OK
    assert e.verdict is Verdict.UNPROFITABLE
    assert e.benefit is not None and e.costs is not None
    assert e.benefit.high < e.costs.total.low


def test_potatoes_on_the_same_field_get_another_verdict() -> None:
    e = econ("potato")
    assert e.status is EconomicsStatus.OK
    assert e.verdict is Verdict.PROFITABLE
    assert e.break_even_area_ha is not None and e.break_even_area_ha < 7.6


def test_borderline_when_ranges_overlap() -> None:
    # Maize with a moderate loss: benefit and cost ranges overlap.
    e = econ("maize", et_ratio=0.75, need_mm=150.0)
    assert e.benefit is not None and e.costs is not None
    assert e.benefit.low < e.costs.total.high and e.benefit.high >= e.costs.total.low
    assert e.verdict is Verdict.BORDERLINE


def test_cost_per_ha_falls_with_area() -> None:
    small, large = econ("potato", area_ha=2.0), econ("potato", area_ha=40.0)
    assert small.costs is not None and large.costs is not None
    assert large.costs.total.low < small.costs.total.low
    assert large.costs.installation == small.costs.installation


def test_drip_efficiency_means_less_water() -> None:
    a = econ("potato")
    b = irrigation_economics(
        crop=CROPS["potato"],
        catalog=load_economics(),
        tech="drip",
        efficiency=0.9,
        area_ha=7.6,
        balance=balance(0.85),
        years=YEARS,
        typical_need_mm=150.0,
        history=None,
    )
    assert a.water_m3_ha == pytest.approx(2000) and b.water_m3_ha == pytest.approx(1500 / 0.9)


def test_no_loss_means_not_needed() -> None:
    e = econ("potato", et_ratio=1.0)
    assert e.status is EconomicsStatus.NOT_NEEDED and e.verdict is Verdict.UNKNOWN


def test_no_installation_means_not_needed() -> None:
    assert econ("potato", tech=None).status is EconomicsStatus.NOT_NEEDED


def test_crop_without_ky_has_no_economics() -> None:
    for crop_id in ("winter_rapeseed", "grassland", "field_vegetables"):
        assert econ(crop_id).status is EconomicsStatus.NO_CROP_DATA


def test_crop_without_price_keeps_losses_and_costs() -> None:
    e = econ("sugar_beet")
    assert e.status is EconomicsStatus.NO_PRICE
    assert e.mean_loss_share is not None and e.costs is not None and e.benefit is None


def test_missing_soil_balance() -> None:
    e = irrigation_economics(
        crop=CROPS["potato"],
        catalog=load_economics(),
        tech="reel",
        efficiency=0.75,
        area_ha=7.6,
        balance=None,
        years=YEARS,
        typical_need_mm=150.0,
        history=None,
    )
    assert e.status is EconomicsStatus.NO_BALANCE and e.benefit is None


def test_missing_plan_need() -> None:
    assert econ("potato", need_mm=None).status is EconomicsStatus.NO_BALANCE


def test_too_few_seasons() -> None:
    e = econ("potato", bal=balance(0.8, years=YEARS[:3]))
    assert e.status is EconomicsStatus.NO_BALANCE
