"""Fixes from the M1 code review: no per-decade wording or ET0 extrapolation without a significant trend,
grassland regrowth wording, the 1-in-500-year flood zone, WorldCover water wording."""

from datetime import date

import pytest

from app.analysis.simulate import simulate
from app.analysis.soil import soil_properties
from app.analysis.trends import analyse_trends
from app.analysis.water_balance import crop_root_zone_balance
from tests.analysis.builders import crop, random_precip, soil_data, soil_layers
from tests.analysis.test_outlook_modules import DAY, weather
from tests.recommendations.builders import basin, by_id, scenario
from tests.recommendations.test_rules import _flood
from tests.report.builders import report_for


@pytest.mark.parametrize("seed", range(1, 9))
def test_trend_summaries_say_per_decade_only_for_a_direction(seed: int) -> None:
    r = report_for(precip=random_precip(seed))
    assert r.trends is not None
    for m in r.trends.metrics:
        if "na dekadę" in m.summary_pl:
            assert m.direction in ("worse", "better"), (m.key, m.summary_pl)


def test_simulator_does_not_extrapolate_an_insignificant_et0_trend() -> None:
    c = crop("potato")
    w = weather()  # seasonal ET0 without a trend
    soil = soil_properties(soil_data(soil_layers(40, 40, 20, 12)), c.root_depth_m)
    t = analyse_trends(w, c, DAY, crop_root_zone_balance(w, c, soil.taw_mm))
    et0 = t.get("et0_mm")
    assert et0 is not None and not et0.significant
    sim = simulate(w, c, DAY, soil, t)
    assert sim is not None and sim.et0_change_pct_per_decade is None
    by = {(r.strategy, r.year_ahead): r for r in sim.results}
    assert by[("rescue", 1)].irrigation_mm_p80 == by[("rescue", 5)].irrigation_mm_p80


def test_grassland_before_regrowth_is_not_called_sowing() -> None:
    r = report_for(crop_id="grassland", day=date(2024, 3, 25))
    text = (
        " ".join(p for s in r.sections if s.id != "limitations" for p in s.paragraphs_pl)
        + r.irrigation.text_pl
    )
    assert "wysiana" not in text and "siew" not in text
    assert "nie ruszyły z wegetacją" in text


def test_500_year_flood_zone_alone_keeps_the_pool_advice() -> None:
    flood = _flood(False)
    flood.data.zones["q02"] = True  # type: ignore[union-attr]
    rec = by_id(scenario(surface=basin, flood=flood)[2], "depression_retention")
    assert "okresowe rozlewisko" in rec.text_pl and "kontrolowany" not in rec.text_pl


def test_worldcover_water_is_not_called_a_pond() -> None:
    from tests.recommendations.test_hydro_fallback import _landcover, _run

    _, recs, _ = _run(_landcover({"water": 90.0}))
    rec = next(r for r in recs if r.id == "protect_wetlands")
    assert "oczko, zbiornik lub ciek" in rec.text_pl
