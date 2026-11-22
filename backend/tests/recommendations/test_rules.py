"""Every rule: a case where it fires and a case where it does not (CLAUDE.md, Testy)."""

from datetime import date

from tests.recommendations.builders import (
    CLAY_LOAM_RICH,
    basin,
    by_id,
    hydro,
    ids,
    scenario,
    tilted,
    valley,
    wet,
)

SPRING = date(2024, 5, 20)

# --- retention ------------------------------------------------------------------------------------


def test_ditch_check_dam_fires_with_ditch_and_deficit() -> None:
    _, _, recs = scenario(hydro_data=lambda p: hydro(p, ditch_m=150))
    rec = by_id(recs, "ditch_check_dam")
    assert {e.key for e in rec.evidence} >= {"ditch_length_along_boundary_m", "deficit_year_share_pct"}
    assert rec.params["ditch_length_m"] == 150
    assert [loc.kind for loc in rec.locations] == ["ditch"]


def test_ditch_check_dam_not_without_ditch_or_without_need() -> None:
    assert "ditch_check_dam" not in ids(scenario()[2])
    assert "ditch_check_dam" not in ids(scenario(hydro_data=lambda p: hydro(p, ditch_m=10))[2])
    assert "ditch_check_dam" not in ids(scenario(precip=wet, hydro_data=lambda p: hydro(p, ditch_m=150))[2])


def test_depression_retention_fires_on_basin() -> None:
    _, _, recs = scenario(surface=basin)
    rec = by_id(recs, "depression_retention")
    keys = {e.key for e in rec.evidence}
    assert {"depression_volume_m3", "depression_contributing_area_m2"} <= keys
    assert rec.locations and rec.locations[0].kind == "depression"
    assert "zagłębienie" in rec.text_pl


def test_depression_retention_not_on_flat_or_wet() -> None:
    assert "depression_retention" not in ids(scenario()[2])
    assert "depression_retention" not in ids(scenario(surface=basin, precip=wet)[2])


def test_outlet_buffer_strip_fires_on_steep_slope() -> None:
    a, _, recs = scenario(surface=lambda p: tilted(p, 0.06))
    rec = by_id(recs, "outlet_buffer_strip")
    assert a.terrain is not None and len(rec.locations) == len(a.terrain.outlets)
    assert all(loc.kind == "outlet" for loc in rec.locations)
    assert rec.params["direction"] in {"E", "NE", "SE"}
    assert "wschodniej" in rec.text_pl


def test_outlet_buffer_strip_not_on_flat() -> None:
    assert "outlet_buffer_strip" not in ids(scenario()[2])
    assert "outlet_buffer_strip" not in ids(scenario(dem=False)[2])


def test_grassed_flow_path_fires_in_valley() -> None:
    _, _, recs = scenario(surface=valley)
    rec = by_id(recs, "grassed_flow_path")
    assert rec.evidence[0].key == "flow_path_contributing_area_m2"
    assert rec.locations and rec.locations[0].kind == "flow_path"


def test_grassed_flow_path_not_on_plane_or_wet() -> None:
    assert "grassed_flow_path" not in ids(scenario(surface=lambda p: tilted(p, 0.04))[2])
    assert "grassed_flow_path" not in ids(scenario(surface=valley, precip=wet)[2])


def test_midfield_trees_fires_without_trees_on_light_soil() -> None:
    _, _, recs = scenario()
    rec = by_id(recs, "midfield_trees")
    keys = {e.key for e in rec.evidence}
    assert "trees_within_radius_count" in keys and "taw_per_m_mm" in keys
    assert "W promieniu 1000 m" in rec.text_pl


def test_midfield_trees_not_with_trees_nearby_or_heavy_soil_or_no_osm() -> None:
    assert "midfield_trees" not in ids(scenario(hydro_data=lambda p: hydro(p, trees_m=200))[2])
    assert "midfield_trees" not in ids(scenario(texture=CLAY_LOAM_RICH)[2])
    # Trees beyond 500 m still count as "missing nearby", reported with the distance.
    rec = by_id(scenario(hydro_data=lambda p: hydro(p, trees_m=700))[2], "midfield_trees")
    assert rec.evidence[0].key == "nearest_trees_m" and rec.evidence[0].value == 700


def test_protect_wetlands_fires_when_close() -> None:
    _, _, recs = scenario(precip=wet, hydro_data=lambda p: hydro(p, wetland_m=100, water_m=250))
    rec = by_id(recs, "protect_wetlands")
    assert rec.params["kind"] == "wetland" and rec.params["distance_m"] == 100
    assert {loc.kind for loc in rec.locations} == {"wetland", "water_body"}
    assert "mokradło" in rec.text_pl


def test_protect_wetlands_not_when_far() -> None:
    assert "protect_wetlands" not in ids(scenario(hydro_data=lambda p: hydro(p, wetland_m=600))[2])


# --- agrotechnics ---------------------------------------------------------------------------------


def test_organic_matter_fires_on_low_carbon() -> None:
    rec = by_id(scenario()[2], "organic_matter")
    assert rec.evidence[0].key == "soc_topsoil_g_per_kg" and rec.evidence[0].value == 8


def test_organic_matter_not_on_rich_soil_or_without_soil() -> None:
    assert "organic_matter" not in ids(scenario(texture=CLAY_LOAM_RICH)[2])
    assert "organic_matter" not in ids(scenario(soil=False)[2])


def test_reduced_tillage_fires_on_light_soil_with_spring_deficits() -> None:
    rec = by_id(scenario(crop_id="winter_wheat", day=SPRING)[2], "reduced_tillage_mulch")
    assert any(e.key.startswith("deficit_frequency_month_0") for e in rec.evidence)
    assert "maj" in rec.text_pl


def test_reduced_tillage_not_on_heavy_soil_or_wet() -> None:
    assert "reduced_tillage_mulch" not in ids(
        scenario(crop_id="winter_wheat", day=SPRING, texture=CLAY_LOAM_RICH)[2]
    )
    assert "reduced_tillage_mulch" not in ids(scenario(crop_id="winter_wheat", day=SPRING, precip=wet)[2])


def test_contour_tillage_fires_on_slope() -> None:
    rec = by_id(scenario(surface=lambda p: tilted(p, 0.04))[2], "contour_tillage")
    assert rec.params["aspect"] == "E" and "wschód" in rec.text_pl


def test_contour_tillage_not_on_flat_or_grassland() -> None:
    assert "contour_tillage" not in ids(scenario()[2])
    assert "contour_tillage" not in ids(scenario(crop_id="grassland", surface=lambda p: tilted(p, 0.04))[2])


def test_crop_timing_fires_when_critical_months_are_risky() -> None:
    a, _, recs = scenario()
    rec = by_id(recs, "crop_timing_variety")
    assert a.history is not None and a.history.critical_risk_months
    months = {int(m) for m in str(rec.params["months"]).split(",")}
    assert months == set(a.history.critical_risk_months)
    assert "kukurydza" in rec.text_pl


def test_crop_timing_not_when_wet_or_grassland() -> None:
    assert "crop_timing_variety" not in ids(scenario(precip=wet)[2])
    assert "crop_timing_variety" not in ids(scenario(crop_id="grassland")[2])


def test_winter_cover_crop_fires_for_spring_crop() -> None:
    rec = by_id(scenario()[2], "winter_cover_crop")
    assert "uprawy jarej (kukurydza)" in rec.text_pl


def test_winter_cover_crop_not_for_winter_crop_or_without_need() -> None:
    assert "winter_cover_crop" not in ids(scenario(crop_id="winter_wheat", day=SPRING)[2])
    assert "winter_cover_crop" not in ids(scenario(precip=wet, texture=CLAY_LOAM_RICH)[2])


def test_crop_residues_fires_on_summer_deficits() -> None:
    rec = by_id(scenario()[2], "crop_residues")
    assert rec.evidence and all(e.key.startswith("deficit_frequency_month_") for e in rec.evidence)


def test_crop_residues_not_when_wet() -> None:
    assert "crop_residues" not in ids(scenario(precip=wet)[2])


def test_grassland_cutting_fires_for_dry_grassland() -> None:
    rec = by_id(scenario(crop_id="grassland")[2], "grassland_cutting")
    assert rec.params["deficit_now"] == 1
    assert rec.text_pl.startswith("Na łące brakuje teraz wody.")


def test_grassland_cutting_not_for_other_crops_or_wet() -> None:
    assert "grassland_cutting" not in ids(scenario()[2])
    assert "grassland_cutting" not in ids(scenario(crop_id="grassland", precip=wet)[2])


# --- Q6: depression on heavy soil or with a flood hazard -> controlled pond / weir ---------------------


def _flood(podt: bool, zone: bool = False):
    from app.sources.flood import FloodData
    from tests.analysis.builders import ok

    return ok(
        "flood",
        FloodData(
            zones={"q10": zone, "q1": zone, "q02": zone},
            points_checked=9,
            points_total=9,
            historical=False,
            groundwater_flooding=podt,
            groundwater_flooding_name="obszar zagrożenia" if podt else None,
        ),
    )


def test_depression_on_heavy_soil_with_groundwater_flooding_is_controlled() -> None:
    from tests.recommendations.builders import CLAY_LOAM_RICH

    recs = scenario(surface=basin, texture=CLAY_LOAM_RICH, flood=_flood(True))[2]
    rec = by_id(recs, "depression_retention")
    assert "kontrolowany staw lub zastawka z odpływem" in rec.text_pl
    assert "wymakaniem" in rec.text_pl and "PIG-PIB" in rec.text_pl and "ciężka" in rec.text_pl
    assert "okresowe rozlewisko" not in rec.text_pl
    keys = {e.key for e in rec.evidence}
    assert {"soil_category", "groundwater_flooding_risk"} <= keys


def test_depression_flood_zone_alone_is_controlled() -> None:
    rec = by_id(scenario(surface=basin, flood=_flood(False, zone=True))[2], "depression_retention")
    assert "ISOK" in rec.text_pl and "kontrolowany staw" in rec.text_pl


def test_depression_on_light_soil_without_hazard_keeps_pool_advice() -> None:
    for flood in (None, _flood(False)):
        rec = by_id(scenario(surface=basin, flood=flood)[2], "depression_retention")
        assert "okresowe rozlewisko lub oczko wodne" in rec.text_pl
        assert "kontrolowany" not in rec.text_pl
