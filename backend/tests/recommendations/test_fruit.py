"""Orchards and fruit bushes (plan33 M6 = plan2 L2): rules, texts, irrigation and land cover."""

import dataclasses
import re
from datetime import date

import pytest

from app.analysis.assessment import assess
from app.analysis.context import landcover_for_crop
from app.core.models import SourceStatus
from app.crops.catalog import load_crops
from app.recommendations.irrigation import IrrigationStatus, irrigation_advice
from app.recommendations.irrigation_tech import choose_technology
from app.recommendations.texts_pl import DOSE_CAVEAT_PL, FRUIT_CAVEAT_PL, OM_ACTIONS_PL
from app.sources.landcover import LandCoverData, not_agricultural_pl
from tests.analysis.builders import ok
from tests.recommendations.builders import (
    CLAY_LOAM_RICH,
    SUMMER,
    by_id,
    dry,
    hydro,
    ids,
    scenario,
    tilted,
    valley,
    wet,
)

FRUIT = sorted(c.id for c in load_crops().values() if c.is_fruit)
ARABLE = sorted(c.id for c in load_crops().values() if c.kind == "arable")
TILLAGE_RULES = {
    "reduced_tillage_mulch",
    "contour_tillage",
    "crop_timing_variety",
    "winter_cover_crop",
    "crop_residues",
}
FIELD_WORDS = re.compile(r"\b(orka|orkę|orki|siew\w*|wysiej|międzyplon\w*|ściernisk\w*)\b", re.IGNORECASE)


def test_four_fruit_crops() -> None:
    assert FRUIT == ["berry_bushes", "orchard_cherry", "orchard_plum", "orchard_pome"]


# --- L2.2: field rules are off for fruit crops ----------------------------------------------------


@pytest.mark.parametrize("crop_id", FRUIT)
@pytest.mark.parametrize("day", [SUMMER, date(2024, 5, 15), date(2025, 11, 21), date(2026, 1, 1)])
def test_fruit_gets_no_tillage_or_sowing_rules(crop_id: str, day: date) -> None:
    _, _, recs = scenario(
        crop_id=crop_id,
        day=day,
        surface=lambda p: tilted(p, 0.08),
        hydro_data=lambda p: hydro(p, ditch_m=100),
    )
    assert not TILLAGE_RULES & set(ids(recs))
    assert "grassland_cutting" not in ids(recs)
    for r in recs:
        if r.id != "irrigation":
            assert not FIELD_WORDS.search(r.text_pl), (r.id, r.text_pl)


def test_same_dry_slope_gives_field_rules_to_a_spring_crop() -> None:
    """Control: the scenario above does fire the field rules for an arable crop."""
    _, _, recs = scenario(crop_id="spring_barley", surface=lambda p: tilted(p, 0.08))
    assert TILLAGE_RULES & set(ids(recs))


@pytest.mark.parametrize("crop_id", FRUIT)
def test_organic_matter_has_orchard_text(crop_id: str) -> None:
    _, _, recs = scenario(crop_id=crop_id)  # loamy sand: low organic carbon
    rec = by_id(recs, "organic_matter")
    assert OM_ACTIONS_PL["fruit"] in rec.text_pl
    assert "słoma" not in rec.text_pl and "międzyplon" not in rec.text_pl


# --- L2.3: orchard_mulch_sward ----------------------------------------------------------------------


@pytest.mark.parametrize("crop_id", FRUIT)
def test_orchard_mulch_fires_on_light_soil_with_dry_summers(crop_id: str) -> None:
    _, _, recs = scenario(crop_id=crop_id, precip=dry)
    rec = by_id(recs, "orchard_mulch_sward")
    assert "lekka" in rec.text_pl
    assert "ściółkę grubości 5–10 cm" in rec.text_pl
    assert "drzewom" in rec.text_pl or "krzewom" in rec.text_pl
    keys = {e.key for e in rec.evidence}
    assert keys & {"soil_category", "taw_per_m_mm"}
    assert any(k.startswith("deficit_frequency_month_") for k in keys)


def test_orchard_mulch_fires_on_heavy_soil_when_summers_are_dry() -> None:
    _, _, recs = scenario(crop_id="orchard_pome", precip=dry, texture=CLAY_LOAM_RICH)
    rec = by_id(recs, "orchard_mulch_sward")
    assert "lekka" not in rec.text_pl
    assert "wody często brakowało" in rec.text_pl


def test_orchard_mulch_names_bushes_for_berry_bushes() -> None:
    _, _, recs = scenario(crop_id="berry_bushes")
    assert "krzewom" in by_id(recs, "orchard_mulch_sward").text_pl


def test_orchard_mulch_not_on_heavy_soil_in_wet_years() -> None:
    _, _, recs = scenario(crop_id="orchard_pome", precip=wet, texture=CLAY_LOAM_RICH)
    assert "orchard_mulch_sward" not in ids(recs)


@pytest.mark.parametrize("crop_id", [*ARABLE, "grassland"])
def test_orchard_mulch_never_for_field_crops_or_grassland(crop_id: str) -> None:
    _, _, recs = scenario(crop_id=crop_id, precip=dry)
    assert "orchard_mulch_sward" not in ids(recs)


# --- L2.4: irrigation texts -------------------------------------------------------------------------


@pytest.mark.parametrize("crop_id", FRUIT)
def test_dormant_orchard_text(crop_id: str) -> None:
    # 25 March: inside the vegetation period (from 21 March), before bud break of every fruit crop
    # (1–10 April).
    a, inputs, _ = scenario(crop_id=crop_id, day=date(2024, 3, 25))
    adv = irrigation_advice(a, inputs, today=inputs.analysis_date)
    assert adv.status is IrrigationStatus.NO_CROP
    assert "spoczynku" in adv.text_pl
    assert "wysian" not in adv.text_pl and "pole" not in adv.text_pl


def test_late_stage_orchard_text() -> None:
    crop = load_crops()["berry_bushes"]
    day = date(2024, 9, 20)
    assert crop.stage(day) == "late" and crop.critical_period_at(day) is None
    a, inputs, _ = scenario(crop_id="berry_bushes", day=day)
    adv = irrigation_advice(a, inputs, today=day)
    assert adv.status is IrrigationStatus.LATE_STAGE
    assert "owoce są już zebrane" in adv.text_pl
    assert "dojrzewania" not in adv.text_pl


def test_drip_caveat_only_for_fruit_when_irrigating() -> None:
    a, inputs, _ = scenario(crop_id="orchard_pome", precip=dry)
    adv = irrigation_advice(a, inputs, today=inputs.analysis_date)
    assert adv.status in (IrrigationStatus.IRRIGATE, IrrigationStatus.IRRIGATE_SOON)
    assert FRUIT_CAVEAT_PL in adv.caveats_pl
    assert DOSE_CAVEAT_PL not in adv.caveats_pl  # sprinkler losses do not apply to drip
    a, inputs, _ = scenario(crop_id="maize", precip=dry)
    adv = irrigation_advice(a, inputs, today=inputs.analysis_date)
    assert FRUIT_CAVEAT_PL not in adv.caveats_pl
    assert DOSE_CAVEAT_PL in adv.caveats_pl


@pytest.mark.parametrize("crop_id", FRUIT)
def test_fruit_gets_drip_technology(crop_id: str) -> None:
    choice = choose_technology(load_crops()[crop_id], 30.0, None, 120.0)
    assert choice.tech == "drip"
    assert choice.reason == "fruit_rows"


def test_large_arable_field_still_gets_a_sprinkler() -> None:
    choice = choose_technology(load_crops()["maize"], 30.0, None, 120.0)
    assert choice.tech != "drip"


# --- L2.5: land cover -------------------------------------------------------------------------------


def _landcover(trees: float, crop: float = 10.0, grass: float = 5.0) -> LandCoverData:
    built = round(100 - trees - crop - grass, 1)
    return LandCoverData(
        map_year=2021,
        pixels=300,
        shares_pct={"trees": trees, "cropland": crop, "grassland": grass, "built_up": built},
        cropland_pct=crop,
        grassland_pct=grass,
        trees_pct=trees,
        built_up_pct=built,
        looks_agricultural=crop + grass >= 50,
    )


def _landcover_result(data: LandCoverData):  # type: ignore[no-untyped-def]
    r = ok("landcover", data, SourceStatus.OK if data.looks_agricultural else SourceStatus.DEGRADED)
    message = "Mapa pokrycia terenu pokazuje stan z 2021 r., nie z dnia analizy."
    if not data.looks_agricultural:
        message += " " + not_agricultural_pl(data)
    return r.model_copy(update={"message_pl": message})


def test_trees_count_as_orchard() -> None:
    raw = _landcover_result(_landcover(trees=80.0))
    adapted = landcover_for_crop(raw, load_crops()["orchard_pome"])
    assert adapted.data is not None and adapted.data.looks_agricultural
    assert adapted.status is SourceStatus.OK
    assert adapted.message_pl == "Mapa pokrycia terenu pokazuje stan z 2021 r., nie z dnia analizy."


def test_trees_still_warn_for_wheat() -> None:
    raw = _landcover_result(_landcover(trees=80.0))
    adapted = landcover_for_crop(raw, load_crops()["winter_wheat"])
    assert adapted is raw
    assert adapted.data is not None and not adapted.data.looks_agricultural


def test_built_up_orchard_still_warns() -> None:
    raw = _landcover_result(_landcover(trees=20.0, crop=5.0, grass=5.0))
    adapted = landcover_for_crop(raw, load_crops()["orchard_pome"])
    assert adapted is raw


@pytest.mark.parametrize(("crop_id", "warned"), [("orchard_pome", False), ("winter_wheat", True)])
def test_landcover_limitation_follows_crop(crop_id: str, warned: bool) -> None:
    _, inputs, _ = scenario(crop_id=crop_id, day=SUMMER, surface=valley)
    raw = _landcover_result(_landcover(trees=80.0))
    inputs = dataclasses.replace(inputs, landcover=landcover_for_crop(raw, inputs.crop))
    a = assess(inputs)
    assert ("landcover_not_agricultural" in a.limitations) is warned
    assert ("fruit_root_depth" in a.limitations) is not warned
    assert ("fruit_critical_periods" in a.limitations) is not warned


# --- whole report -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_id", ["orchard_summer", "orchard_dormant", "berry_late", "orchard_october"]
)
def test_fruit_report_has_no_sowing_or_ploughing(scenario_id: str) -> None:
    """The whole report JSON (simulation, retention plan, limitations included) — review finding of M6."""
    from tests.report.builders import SCENARIOS

    text = SCENARIOS[scenario_id]().model_dump_json()
    assert not FIELD_WORDS.search(text), FIELD_WORDS.search(text)


def test_october_orchard_headline_not_on_field() -> None:
    from tests.report.builders import SCENARIOS

    r = SCENARIOS["orchard_october"]()
    assert "na polu" not in r.headline.sentence_pl


def test_fruit_simulation_assumptions_replace_the_right_items() -> None:
    from app.report.outlook import SIM_ASSUMPTIONS, SIM_ASSUMPTIONS_FRUIT

    assert SIM_ASSUMPTIONS[2].startswith("Przyrost węgla organicznego")
    assert SIM_ASSUMPTIONS[3].startswith("Ściółka")
    assert set(SIM_ASSUMPTIONS_FRUIT) == {2, 3}
