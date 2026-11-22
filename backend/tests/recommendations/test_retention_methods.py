"""G9 / M4.3: five retention methods, each with a status computed from the parcel's data.

Every method has a "recommended" (or conditional) case, a "not recommended" case and a missing-source case
that gives "no data", never "not recommended" (CLAUDE.md rule 4)."""

import dataclasses
from typing import Any

from app.analysis.retention_balance import CoverageStatus, RetentionCoverage, retention_coverage
from app.recommendations.models import RuleContext
from app.recommendations.retention_methods import (
    MethodAssessment,
    MethodStatus,
    Permit,
    assess_methods,
)
from app.sources.landcover import LandCoverData, Surroundings
from tests.analysis.builders import ok
from tests.recommendations.builders import CLAY_LOAM_RICH, basin, flat, hydro, scenario, tilted, wet
from tests.recommendations.test_rules import _flood

NEED_FULL = 12090.0
NEED_RESCUE = 7600.0


def _landcover(
    *, trees_pct: float = 0.0, built_m: float | None = None, on_parcel_built: float = 0.0
) -> LandCoverData:
    return LandCoverData(
        map_year=2021,
        pixels=500,
        shares_pct={"cropland": 100.0},
        cropland_pct=100.0,
        grassland_pct=0.0,
        trees_pct=0.0,
        built_up_pct=on_parcel_built,
        looks_agricultural=True,
        surroundings=Surroundings(
            radius_m=500,
            pixels=9000,
            shares_pct={
                "trees": trees_pct,
                "water": 0.0,
                "wetland": 0.0,
                "built_up": 1.0 if built_m else 0.0,
            },
            nearest_m={"trees": None, "water": None, "wetland": None, "built_up": built_m},
        ),
    )


def _methods(
    *,
    full: float | None = NEED_FULL,
    rescue: float | None = NEED_RESCUE,
    landcover: LandCoverData | None = None,
    groundwater: Any = None,
    coverage: RetentionCoverage | None = None,
    **kw: Any,
) -> dict[str, MethodAssessment]:
    a, inputs, _ = scenario(**kw)
    if landcover is not None:
        inputs = dataclasses.replace(inputs, landcover=ok("landcover", landcover))
    if groundwater is not None:
        inputs = dataclasses.replace(inputs, groundwater=groundwater)
    cov = coverage or retention_coverage(a.terrain, full, rescue)
    return {m.id: m for m in assess_methods(RuleContext(assessment=a, inputs=inputs), cov)}


def _cov(volume: float | None, full: float | None = NEED_FULL, **kw: Any) -> RetentionCoverage:
    base: dict[str, Any] = {
        "status": CoverageStatus.OK if volume is not None else CoverageStatus.NO_DEPRESSION,
        "volume_m3": volume,
        "area_m2": 1200.0,
        "max_depth_m": 0.8,
        "full_need_m3": full,
        "rescue_need_m3": NEED_RESCUE,
        "full_pct": None,
        "rescue_pct": None,
    }
    return RetentionCoverage(**{**base, **kw})


def _groundwater() -> Any:
    from datetime import date

    from app.sources.groundwater import GroundwaterData

    return ok(
        "groundwater",
        GroundwaterData(
            station_id=1,
            station_name="Test",
            distance_km=12.3,
            depth_now_m=19.5,
            depth_before_m=19.0,
            years_compared=3,
            change_m=-0.5,
            trend="falling",
            window_start=date(2024, 6, 15),
            window_end=date(2024, 7, 15),
        ),
    )


# --- every method carries numbers or says "no data" --------------------------------------------------


def test_all_five_methods_in_order_with_evidence() -> None:
    ms = _methods(surface=basin, landcover=_landcover(), hydro_data=lambda p: hydro(p, ditch_m=200.0))
    assert list(ms) == ["pond", "weir", "rainwater", "well", "tree_belts"]
    for m in ms.values():
        assert m.status is MethodStatus.NO_DATA or m.evidence, m.id


# --- 1. pond ----------------------------------------------------------------------------------------


def test_pond_recommended_on_heavy_soil_without_liner() -> None:
    m = _methods(surface=basin, texture=CLAY_LOAM_RICH)["pond"]
    assert m.status is MethodStatus.RECOMMENDED
    assert m.params["sealing"] == "natural"
    assert m.params["controlled"] == 1  # Q6: heavy soil → controlled pond with an outlet
    assert m.permit in (Permit.NOTIFICATION, Permit.PERMIT)
    assert {"depression_volume_m3", "retention_coverage_full_pct"} <= {e.key for e in m.evidence}


def test_pond_on_light_soil_needs_liner_conditional() -> None:
    m = _methods(surface=basin)["pond"]
    assert m.status is MethodStatus.CONDITIONAL
    assert m.params["sealing"] == "liner"


def test_pond_not_recommended_without_depression() -> None:
    assert _methods(surface=flat)["pond"].status is MethodStatus.NOT_RECOMMENDED


def test_pond_not_recommended_when_too_small() -> None:
    m = _methods(surface=basin, coverage=_cov(150.0))["pond"]
    assert m.status is MethodStatus.NOT_RECOMMENDED
    assert m.reason == "small"


def test_pond_no_data_without_terrain() -> None:
    assert _methods(dem=False)["pond"].status is MethodStatus.NO_DATA


def test_pond_over_5000_m2_needs_permit_below_notification() -> None:
    big = _methods(surface=basin, texture=CLAY_LOAM_RICH, coverage=_cov(2320.0, area_m2=6084.0))["pond"]
    assert big.permit is Permit.PERMIT
    deep = _methods(surface=basin, texture=CLAY_LOAM_RICH, coverage=_cov(2320.0, max_depth_m=3.4))["pond"]
    assert deep.permit is Permit.PERMIT
    small = _methods(surface=basin, texture=CLAY_LOAM_RICH, coverage=_cov(2320.0, area_m2=4000.0))["pond"]
    assert small.permit is Permit.NOTIFICATION


# --- 2. weir / controlled drainage ------------------------------------------------------------------


def test_weir_recommended_with_ditch_at_the_parcel() -> None:
    m = _methods(hydro_data=lambda p: hydro(p, ditch_m=200.0))["weir"]
    assert m.status is MethodStatus.RECOMMENDED
    assert m.reason == "ditch_near"
    assert m.permit is Permit.CHECK


def test_weir_recommended_on_flat_ground_with_groundwater_flooding_even_without_osm() -> None:
    m = _methods(surface=flat, hydro_data=False, flood=_flood(True))["weir"]
    assert m.status is MethodStatus.RECOMMENDED
    assert m.reason == "flat_wet"
    assert "groundwater_flooding_risk" in {e.key for e in m.evidence}


def test_weir_not_recommended_without_ditch_on_slope() -> None:
    m = _methods(surface=lambda p: tilted(p, 0.04), hydro_data=lambda p: hydro(p))["weir"]
    assert m.status is MethodStatus.NOT_RECOMMENDED
    assert m.evidence


def test_weir_no_data_without_osm() -> None:
    assert (
        _methods(surface=lambda p: tilted(p, 0.04), hydro_data=False)["weir"].status is MethodStatus.NO_DATA
    )


# --- 3. rainwater from roofs ------------------------------------------------------------------------


def test_rainwater_too_small_for_thousands_of_m3() -> None:
    m = _methods(landcover=_landcover(built_m=50.0))["rainwater"]
    assert m.status is MethodStatus.CONDITIONAL
    assert m.reason == "too_small"


def test_rainwater_recommended_for_small_need() -> None:
    m = _methods(landcover=_landcover(built_m=50.0), full=600.0, rescue=300.0)["rainwater"]
    assert m.status is MethodStatus.RECOMMENDED


def test_rainwater_not_recommended_without_roofs() -> None:
    m = _methods(landcover=_landcover(built_m=400.0))["rainwater"]
    assert m.status is MethodStatus.NOT_RECOMMENDED
    assert m.reason == "no_roofs"


def test_rainwater_no_data_without_landcover() -> None:
    assert _methods()["rainwater"].status is MethodStatus.NO_DATA


# --- 4. well ----------------------------------------------------------------------------------------


def test_well_fills_the_gap_and_needs_permit_above_5_m3_per_day() -> None:
    m = _methods(surface=flat, groundwater=_groundwater())["well"]
    assert m.status is MethodStatus.CONDITIONAL
    assert m.permit is Permit.PERMIT  # no depression: even rescue 7 600 m³ / 365 ≈ 20.8 m³ per day
    assert m.params["per_day_m3"] == round(NEED_FULL / 365, 1)
    assert m.params["per_day_rescue_m3"] == round(NEED_RESCUE / 365, 1)
    assert {"groundwater_depth_m", "groundwater_station_km"} <= {e.key for e in m.evidence}


def test_well_abstraction_is_only_the_gap_left_by_the_depression() -> None:
    # Live heavy_soil case: depression 11 960 m³, full 12 590 m³, rescue 840 m³ → the well gives 630 m³.
    m = _methods(coverage=_cov(11960.0, full=12590.0, rescue_need_m3=840.0))["well"]
    assert m.params["gap_m3"] == 630
    assert m.params["gap_rescue_m3"] == 0
    assert m.permit is Permit.ORDINARY_USE  # 630 / 365 ≈ 1.7 m³ per day


def test_well_rescue_within_ordinary_use_full_needs_permit() -> None:
    m = _methods(coverage=_cov(None, full=12590.0, rescue_need_m3=1500.0))["well"]
    assert m.permit is Permit.PERMIT_FULL_ONLY  # 1 500 / 365 ≈ 4.1 ≤ 5 < 12 590 / 365 ≈ 34.5


def test_well_small_need_within_ordinary_use() -> None:
    m = _methods(surface=flat, full=1500.0, rescue=1000.0)["well"]
    assert m.permit is Permit.ORDINARY_USE  # 1 500 m³ / 365 ≈ 4.1 m³ per day


def test_well_not_recommended_when_retention_covers_need() -> None:
    m = _methods(coverage=_cov(13000.0))["well"]
    assert m.status is MethodStatus.NOT_RECOMMENDED
    assert m.reason == "retention_covers"


def test_well_not_recommended_without_need() -> None:
    assert _methods(full=0.0, rescue=0.0)["well"].status is MethodStatus.NOT_RECOMMENDED


def test_well_no_data_without_plan() -> None:
    assert _methods(full=None, rescue=None)["well"].status is MethodStatus.NO_DATA


# --- 5. tree belts ----------------------------------------------------------------------------------


def test_trees_recommended_in_open_landscape_with_outlet() -> None:
    m = _methods(surface=lambda p: tilted(p, 0.04), landcover=_landcover(trees_pct=1.0))["tree_belts"]
    assert m.status is MethodStatus.RECOMMENDED
    assert m.reason == "open_outlet"


def test_trees_not_recommended_with_enough_trees() -> None:
    m = _methods(landcover=_landcover(trees_pct=20.0))["tree_belts"]
    assert m.status is MethodStatus.NOT_RECOMMENDED


def test_trees_no_data_without_landcover() -> None:
    assert _methods()["tree_belts"].status is MethodStatus.NO_DATA


# --- no water need ------------------------------------------------------------------------------------


def test_without_water_need_nothing_is_recommended() -> None:
    ms = _methods(
        precip=wet,
        surface=basin,
        texture=CLAY_LOAM_RICH,
        hydro_data=lambda p: hydro(p, ditch_m=200.0),
    )
    assert all(m.status is not MethodStatus.RECOMMENDED for m in ms.values())
    assert ms["weir"].params.get("no_need") == 1
