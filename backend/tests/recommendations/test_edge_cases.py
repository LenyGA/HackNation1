"""Edge cases of the recommendation engine: crops, dates, missing sources, odd terrain, hydro and soil."""

import dataclasses
import json
import re
from datetime import date
from typing import Any

import pytest

from app.analysis.assessment import Assessment, assess
from app.analysis.context import AnalysisInputs
from app.crops.catalog import load_crops
from app.recommendations.engine import recommend
from app.recommendations.models import Recommendation
from app.recommendations.texts_pl import SIDE_UNKNOWN_PL
from app.sources.hydro import BOUNDARY_BUFFER_M
from tests.analysis.builders import LOAMY_SAND, default_parcel, make_inputs
from tests.recommendations.builders import (
    SUMMER,
    basin,
    by_id,
    dem_result,
    dry,
    hydro,
    ids,
    scenario,
    soil_result,
    tilted,
    valley,
)

FORBIDDEN = re.compile(r"\b(NDVI|NDMI|KBW|percentyl\w*|FAO|TAW|RAW|SCL|ET0|ETc)\b", re.IGNORECASE)
CROP_IDS = sorted(load_crops())
DATES = [SUMMER, date(2024, 4, 20), date(2025, 11, 21), date(2026, 1, 1), date(2024, 2, 29)]
TILLAGE_RULES = {
    "reduced_tillage_mulch",
    "contour_tillage",
    "crop_timing_variety",
    "winter_cover_crop",
    "crop_residues",
}


def check_invariants(recs: list[Recommendation], analysis_date: date) -> None:
    for r in recs:
        assert r.evidence, r.id
        for e in r.evidence:
            assert e.value is not None and e.source, (r.id, e.key)
            assert e.period is None or e.period.end <= analysis_date, (r.id, e.key)
        for t in (r.title_pl, r.text_pl):
            assert "{" not in t and "}" not in t, (r.id, t)
            assert not FORBIDDEN.search(t), (r.id, t)
            assert not re.search(r"\d\.\d", t), (r.id, t)  # decimal comma, never "1000.0"
            assert "None" not in t and "nan" not in t, (r.id, t)
        json.loads(r.model_dump_json())


def run(
    crop_id: str,
    day: date,
    *,
    soil: bool = True,
    dem: bool = True,
    hydro_on: bool = True,
    weather: bool = True,
) -> tuple[Assessment, AnalysisInputs, list[Recommendation]]:
    parcel = default_parcel()
    inputs = make_inputs(
        day,
        crop_id,
        precip=dry,
        soil=soil_result(LOAMY_SAND) if soil else False,
        dem=dem_result(parcel, valley(parcel)) if dem else False,
        hydro=hydro(parcel, ditch_m=150, wetland_m=50, water_m=250) if hydro_on else False,
        weather=weather,
        parcel=parcel,
    )
    a = assess(inputs)
    return a, inputs, recommend(a, inputs)


# --- every crop × date × missing source -----------------------------------------------------------


@pytest.mark.parametrize("crop_id", CROP_IDS)
def test_every_crop_and_date_never_raises(crop_id: str) -> None:
    for day in DATES:
        _, _, recs = run(crop_id, day)
        check_invariants(recs, day)
        assert recs, (crop_id, day)  # dry weather + ditch + wetland always yields something


@pytest.mark.parametrize("crop_id", CROP_IDS)
def test_missing_sources_never_raise(crop_id: str) -> None:
    for kw in (
        {"soil": False},
        {"dem": False},
        {"hydro_on": False},
        {"soil": False, "dem": False, "hydro_on": False},
    ):
        _, _, recs = run(crop_id, SUMMER, **kw)
        check_invariants(recs, SUMMER)


@pytest.mark.parametrize("day", DATES)
def test_missing_weather_gives_empty_list(day: date) -> None:
    for crop_id in CROP_IDS:
        a, _, recs = run(crop_id, day, weather=False)
        assert not a.complete and recs == []


def test_missing_sources_drop_their_rules() -> None:
    assert not {"organic_matter", "midfield_trees", "reduced_tillage_mulch"} & set(
        ids(run("maize", SUMMER, soil=False)[2])
    )
    no_dem = set(ids(run("maize", SUMMER, dem=False)[2]))
    assert (
        not {"outlet_buffer_strip", "grassed_flow_path", "contour_tillage", "depression_retention"} & no_dem
    )
    no_hydro = set(ids(run("maize", SUMMER, hydro_on=False)[2]))
    assert not {"ditch_check_dam", "midfield_trees", "protect_wetlands"} & no_hydro


def test_deterministic() -> None:
    a, inputs, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=100))
    again = recommend(assess(inputs), inputs)
    assert [r.model_dump_json() for r in again] == [r.model_dump_json() for r in recs]
    assert [r.model_dump_json() for r in recommend(a, inputs)] == [r.model_dump_json() for r in recs]


def test_json_roundtrip() -> None:
    _, _, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=100))
    for r in recs:
        dumped = r.model_dump_json()
        assert Recommendation.model_validate_json(dumped).model_dump_json() == dumped


# --- hydro -------------------------------------------------------------------------------------------


def _ditch_at(distance_m: float) -> Any:
    def build(p: Any) -> Any:
        h = hydro(p, ditch_m=50)
        return h.model_copy(
            update={"features": [h.features[0].model_copy(update={"distance_m": distance_m})]}
        )

    return build


def test_ditch_exactly_at_buffer_edge_is_located() -> None:
    rec = by_id(scenario(hydro_data=_ditch_at(BOUNDARY_BUFFER_M))[2], "ditch_check_dam")
    assert len(rec.locations) == 1
    rec = by_id(scenario(hydro_data=_ditch_at(BOUNDARY_BUFFER_M + 0.01))[2], "ditch_check_dam")
    assert rec.locations == []


def test_ditch_length_threshold() -> None:
    assert "ditch_check_dam" not in ids(scenario(hydro_data=lambda p: hydro(p, ditch_m=19.9))[2])
    assert "ditch_check_dam" in ids(scenario(hydro_data=lambda p: hydro(p, ditch_m=20.0))[2])


def test_nearest_m_without_keys() -> None:
    def build(p: Any) -> Any:
        return hydro(p, ditch_m=100, wetland_m=50).model_copy(update={"nearest_m": {}, "counts": {}})

    _, _, recs = scenario(hydro_data=build)
    check_invariants(recs, SUMMER)
    trees = by_id(recs, "midfield_trees")
    assert trees.evidence[0].key == "trees_within_radius_count"


# Regression: a wetland at < 5 m used to read "W odległości ok. 0 m od działki".
@pytest.mark.parametrize("distance_m", [0.0, 4.0])
def test_wetland_on_boundary_text(distance_m: float) -> None:
    rec = by_id(scenario(hydro_data=lambda p: hydro(p, wetland_m=distance_m))[2], "protect_wetlands")
    assert "ok. 0 m" not in rec.text_pl


# --- terrain -----------------------------------------------------------------------------------------


def test_outlet_without_direction() -> None:
    a, inputs, _ = scenario(surface=lambda p: tilted(p, 0.06))
    assert a.terrain is not None and a.terrain.outlets
    terrain = dataclasses.replace(
        a.terrain,
        outlets=[dataclasses.replace(o, direction=None) for o in a.terrain.outlets],
        aspect=None,
    )
    recs = recommend(dataclasses.replace(a, terrain=terrain), inputs)
    check_invariants(recs, SUMMER)
    assert SIDE_UNKNOWN_PL in by_id(recs, "outlet_buffer_strip").text_pl
    assert "stok jest skierowany" not in by_id(recs, "contour_tillage").text_pl


def test_no_outlets_no_buffer_strip() -> None:
    a, inputs, _ = scenario(surface=lambda p: tilted(p, 0.06))
    assert a.terrain is not None
    recs = recommend(dataclasses.replace(a, terrain=dataclasses.replace(a.terrain, outlets=[])), inputs)
    assert "outlet_buffer_strip" not in ids(recs)


def _basin_with(**update: Any) -> list[Recommendation]:
    a, inputs, _ = scenario(surface=basin)
    assert a.terrain is not None and a.terrain.depressions
    deps = [dataclasses.replace(d, **update) for d in a.terrain.depressions]
    return recommend(dataclasses.replace(a, terrain=dataclasses.replace(a.terrain, depressions=deps)), inputs)


def test_depression_without_depth_still_valid() -> None:
    recs = _basin_with(max_depth_m=None)
    check_invariants(recs, SUMMER)
    rec = by_id(recs, "depression_retention")
    assert "depression_max_depth_m" not in {e.key for e in rec.evidence}


# Regression: volume None (or < 5 m³) used to read "ok. 0 m³ wody".
@pytest.mark.parametrize("volume", [None, 3.0])
def test_depression_unknown_volume_not_shown_as_zero(volume: float | None) -> None:
    rec = by_id(_basin_with(volume_m3=volume), "depression_retention")
    assert "0 m³" not in rec.text_pl


# --- crop, history, soil ----------------------------------------------------------------------------


def test_grassland_gets_no_tillage_rules() -> None:
    for day in (SUMMER, date(2025, 11, 21), date(2026, 1, 1)):
        _, _, recs = scenario(
            crop_id="grassland", day=day, surface=valley, hydro_data=lambda p: hydro(p, ditch_m=100)
        )
        check_invariants(recs, day)
        assert not TILLAGE_RULES & set(ids(recs))
        assert "grassland_cutting" in ids(recs)


def test_empty_history_months() -> None:
    a, inputs, _ = scenario(surface=valley)
    assert a.history is not None
    for history in (
        dataclasses.replace(a.history, months=[]),
        dataclasses.replace(a.history, months=[], critical_risk_months=[6, 7], risk_months=[6, 7]),
        None,
    ):
        recs = recommend(dataclasses.replace(a, history=history), inputs)
        check_invariants(recs, SUMMER)
        assert not {"reduced_tillage_mulch", "crop_timing_variety", "crop_residues"} & set(ids(recs))


def test_soil_without_taw_or_category_is_not_light() -> None:
    a, inputs, _ = scenario(surface=valley)
    assert a.soil is not None
    soil = dataclasses.replace(a.soil, taw_mm=None, category=None)
    assert soil.taw_per_m_mm is None
    recs = recommend(dataclasses.replace(a, soil=soil), inputs)
    check_invariants(recs, SUMMER)
    assert not {"midfield_trees", "reduced_tillage_mulch"} & set(ids(recs))
