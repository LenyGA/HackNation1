"""Engine-level guarantees: gate on a complete assessment, order, evidence, texts, no future data."""

import re

from app.core.models import Confidence, Indicator, Uncertainty
from app.recommendations.engine import ALL_RULES, recommend
from app.recommendations.models import CATEGORY_ORDER, Category, Rule
from app.recommendations.texts_pl import TEXTS, TITLES, fmt
from tests.recommendations.builders import (
    CLAY_LOAM_RICH,
    SUMMER,
    basin,
    hydro,
    ids,
    scenario,
    valley,
    wet,
)

FORBIDDEN = re.compile(r"\b(NDVI|NDMI|KBW|percentyl\w*|FAO|TAW|RAW|SCL)\b", re.IGNORECASE)


def test_no_recommendations_without_complete_assessment() -> None:
    a, inputs, recs = scenario(weather=False)
    assert not a.complete
    assert recs == []
    assert recommend(a, inputs) == []


def test_order_numbering_and_evidence() -> None:
    _, _, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=100))
    assert len(recs) >= 8
    assert [r.number for r in recs] == list(range(1, len(recs) + 1))
    order = [(CATEGORY_ORDER.index(r.category), r.priority) for r in recs]
    assert order == sorted(order)
    assert recs[0].category is Category.RETENTION
    assert recs[-1].category is Category.AGROTECH
    for r in recs:
        assert r.evidence, r.id
        assert all(e.value is not None and e.source and e.uncertainty.reason_pl for e in r.evidence)
        assert len({e.key for e in r.evidence}) == len(r.evidence)


def test_two_parcels_get_different_lists() -> None:
    light_dry = ids(scenario(surface=basin)[2])
    heavy_wet = ids(
        scenario(
            precip=wet, texture=CLAY_LOAM_RICH, surface=valley, hydro_data=lambda p: hydro(p, wetland_m=50)
        )[2]
    )
    assert light_dry != heavy_wet
    assert "depression_retention" in light_dry and "depression_retention" not in heavy_wet
    assert "protect_wetlands" in heavy_wet and "protect_wetlands" not in light_dry


def test_texts_are_filled_and_plain() -> None:
    _, _, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150, wetland_m=100))
    for crop in ("grassland", "winter_wheat"):
        recs += scenario(crop_id=crop, surface=basin)[2]
    assert recs
    for r in recs:
        assert "{" not in r.text_pl and "}" not in r.text_pl, r.id
        assert not FORBIDDEN.search(r.text_pl + r.title_pl), r.id
        assert ".0 " not in r.text_pl, r.id


def test_every_rule_has_texts() -> None:
    for rule in ALL_RULES:
        assert rule.template_key in TITLES and rule.template_key in TEXTS
    assert len({r.id for r in ALL_RULES}) == len(ALL_RULES)
    assert sum(r.category is Category.RETENTION for r in ALL_RULES) >= 6
    assert sum(r.category is Category.AGROTECH for r in ALL_RULES) >= 7


def test_evidence_never_after_analysis_date() -> None:
    _, _, recs = scenario(surface=valley, hydro_data=lambda p: hydro(p, ditch_m=150))
    for r in recs:
        for e in r.evidence:
            if e.period is not None:
                assert e.period.end <= SUMMER, (r.id, e.key)


def test_rule_without_numeric_evidence_is_dropped() -> None:
    a, inputs, _ = scenario()
    empty = Indicator(
        key="x",
        value=None,
        unit="",
        source="test",
        uncertainty=Uncertainty(level=Confidence.LOW, reason_pl="test"),
    )
    rule = Rule("organic_matter", Category.AGROTECH, 1, lambda _: True, lambda _: [empty])
    assert recommend(a, inputs, [rule]) == []


def test_fmt_polish_numbers() -> None:
    assert fmt(4.0) == "4"
    assert fmt(5.6) == "5,6"
    assert fmt(12) == "12"
