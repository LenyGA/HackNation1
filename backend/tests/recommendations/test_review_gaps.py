"""Gaps found in review: missing sources keep rules silent, the trigger is always in the evidence,
every template reads well for every crop, off-season behaviour."""

from datetime import date

import pytest

from app.crops.catalog import load_crops
from app.recommendations.texts_pl import render
from tests.recommendations.builders import (
    CLAY_LOAM_RICH,
    basin,
    by_id,
    hydro,
    ids,
    scenario,
    tilted,
    valley,
)

OFF_SEASON = date(2024, 11, 21)
NEEDS_SOIL = {
    "midfield_trees",
    "organic_matter",
    "reduced_tillage_mulch",
    "crop_timing_variety",
    "crop_residues",
}
NEEDS_DEM = {"depression_retention", "outlet_buffer_strip", "grassed_flow_path", "contour_tillage"}
NEEDS_HYDRO = {"ditch_check_dam", "midfield_trees", "protect_wetlands"}

# The data value that triggers each rule must be among its evidence.
TRIGGER = {
    "ditch_check_dam": "ditch_length_along_boundary_m",
    "depression_retention": "depression_volume_m3",
    "outlet_buffer_strip": "slope_mean_pct",
    "grassed_flow_path": "flow_path_contributing_area_m2",
    "protect_wetlands": "nearest_wetland_or_pond_m",
    "organic_matter": "soc_topsoil_g_per_kg",
    "contour_tillage": "slope_mean_pct",
}


def test_missing_sources_silence_their_rules() -> None:
    assert not NEEDS_SOIL & set(ids(scenario(soil=False, surface=valley)[2]))
    assert not NEEDS_DEM & set(ids(scenario(dem=False)[2]))
    assert not NEEDS_HYDRO & set(ids(scenario(hydro_data=False)[2]))
    assert ids(scenario(soil=False, dem=False, hydro_data=False)[2]) == ["winter_cover_crop"]


def test_ditch_evidence_without_dem() -> None:
    rec = by_id(scenario(dem=False, hydro_data=lambda p: hydro(p, ditch_m=150))[2], "ditch_check_dam")
    assert rec.evidence[0].key == "ditch_length_along_boundary_m" and rec.evidence[0].value == 150


def test_trigger_is_in_evidence() -> None:
    _, _, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=50))
    recs += scenario(surface=basin)[2]
    seen = set()
    for r in recs:
        if r.id in TRIGGER:
            assert TRIGGER[r.id] in {e.key for e in r.evidence}, r.id
            seen.add(r.id)
    assert seen == set(TRIGGER)


@pytest.mark.parametrize("crop_id", sorted(load_crops()))
def test_every_template_for_every_crop(crop_id: str) -> None:
    _, _, recs = scenario(
        crop_id=crop_id, surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=50)
    )
    name = load_crops()[crop_id].name_pl.lower()
    for r in recs:
        title, text = render(r.template, r.params)
        assert text == r.text_pl and title == r.title_pl
        # No verb agreement with the crop name (plural names: ziemniaki, buraki cukrowe, warzywa polowe).
        assert f"{name} zostawia" not in text.lower() and f"{name} najbardziej" not in text.lower()
        if crop_id in {"potato", "sugar_beet", "field_vegetables"}:
            assert "słomę" not in text, r.id
        if crop_id == "grassland":
            assert "międzyplon" not in text and "przyora" not in text, r.id
    if crop_id == "potato" and "crop_timing_variety" in ids(recs):
        assert "sadzenie" in by_id(recs, "crop_timing_variety").text_pl


def test_off_season_grassland_does_not_say_deficit_now() -> None:
    a, _, recs = scenario(crop_id="grassland", day=OFF_SEASON)
    assert a.current is not None and not a.current.in_vegetation
    if "grassland_cutting" in ids(recs):
        assert "brakuje teraz" not in by_id(recs, "grassland_cutting").text_pl


def test_off_season_winter_wheat_runs() -> None:
    a, _, recs = scenario(crop_id="winter_wheat", day=OFF_SEASON, surface=lambda p: tilted(p, 0.04))
    assert a.complete and recs
    timing = [r for r in recs if r.id == "crop_timing_variety"]
    assert all("odporną na suszę" in r.text_pl for r in timing)


def test_soc_text_never_equals_threshold() -> None:
    from app.analysis.causes import LOW_SOC_G_PER_KG

    for soc in (9.94, 9.96, 10.0):
        texture = (80.0, 12.0, 8.0, soc)
        recs = scenario(texture=texture)[2]
        if soc >= 9.95:
            assert "organic_matter" not in ids(recs)
        else:
            rec = by_id(recs, "organic_matter")
            assert rec.evidence[0].value == pytest.approx(9.9)
            assert rec.params["soc_g_per_kg"] < LOW_SOC_G_PER_KG


def test_heavy_rich_soil_skips_soil_rules() -> None:
    recs = ids(scenario(texture=CLAY_LOAM_RICH)[2])
    assert "organic_matter" not in recs and "midfield_trees" not in recs


def test_month_frequencies_carry_history_period() -> None:
    rec = by_id(scenario()[2], "crop_residues")
    for e in rec.evidence:
        assert e.period is not None and e.period.end.year == 2023 and e.period.start.year == 2014
