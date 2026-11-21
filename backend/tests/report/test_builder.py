"""Report assembly (plan M6.1/M6.2): section order, plain language, explicit missing data, evidence."""

import re
from collections.abc import Callable
from datetime import date

import pytest
from shapely.geometry import shape

from app.report.models import SECTION_ORDER, Report
from tests.recommendations.builders import tilted
from tests.report.builders import (
    SCENARIOS,
    no_weather_report,
    off_season_report,
    report_for,
    rich_report,
    two_missing_report,
)

JARGON = re.compile(r"NDVI|NDMI|KBW|percentyl", re.IGNORECASE)
LEFTOVERS = re.compile(r"\{\{|\}\}|\{%|%\}|\bNone\b|\bnan\b|\binf\b|\bTrue\b|\bFalse\b", re.IGNORECASE)
SCENARIO_IDS = list(SCENARIOS)


@pytest.fixture(scope="module", params=SCENARIO_IDS)
def report(request: pytest.FixtureRequest) -> Report:
    factory: Callable[[], Report] = SCENARIOS[request.param]
    return factory()


def main_texts(r: Report) -> list[str]:
    return [r.headline.sentence_pl, *(p for s in r.sections for p in s.paragraphs_pl)]


def all_texts(r: Report) -> list[str]:
    out = main_texts(r) + [d for s in r.sections for d in s.details_pl]
    out += [r.headline.label_pl, r.headline.confidence_pl, *r.missing_data_pl, *r.limitations_pl]
    out += [r.irrigation.title_pl, r.irrigation.text_pl, *r.irrigation.caveats_pl]
    out += [t for rec in r.recommendations for t in (rec.title_pl, rec.text_pl)]
    return out


# --- 1. sections --------------------------------------------------------------------------------------


def test_all_nine_sections_in_order(report: Report) -> None:
    assert [s.id for s in report.sections] == SECTION_ORDER
    assert [s.number for s in report.sections] == list(range(1, 10))
    for s in report.sections:
        assert s.title_pl
        assert s.paragraphs_pl, f"section {s.id} has no text"


def test_no_weather_is_incomplete_and_sections_explain_why() -> None:
    r = no_weather_report()
    assert not r.complete
    assert r.recommendations == []
    assert r.headline.level == "unknown"
    for sid in ("retention", "agrotech", "irrigation"):
        s = next(s for s in r.sections if s.id == sid)
        assert s.recommendation_numbers == []
        assert any("Bez pełnej oceny" in p for p in s.paragraphs_pl), s.paragraphs_pl
    assert r.irrigation.dose_mm is None
    assert r.chart is None


def test_off_season_report_complete_with_sections() -> None:
    r = off_season_report()
    assert [s.id for s in r.sections] == SECTION_ORDER
    assert r.analysis_date == date(2024, 11, 21)
    assert r.crop.id == "winter_wheat"
    irr = next(s for s in r.sections if s.id == "irrigation")
    assert irr.paragraphs_pl
    assert not r.irrigation.applicable
    assert r.irrigation.dose_mm is None


# --- 2. plain language and clean text -----------------------------------------------------------------


def test_main_text_has_no_jargon(report: Report) -> None:
    bad = [t for t in main_texts(report) if JARGON.search(t)]
    assert not bad, bad


def test_jargon_is_allowed_in_details_of_rich_report() -> None:
    details = " ".join(d for s in rich_report().sections for d in s.details_pl)
    assert JARGON.search(details)


def test_no_template_leftovers(report: Report) -> None:
    for text in all_texts(report):
        assert not LEFTOVERS.search(text), text


def test_punctuation_is_clean(report: Report) -> None:
    for text in main_texts(report) + [d for s in report.sections for d in s.details_pl]:
        assert ".." not in text.replace("...", "…"), text
        assert not re.search(r"\s[.,;:)]", text), text
        assert text == text.strip()
        assert "  " not in text, text


def test_sentences_start_upper_and_end_with_punctuation(report: Report) -> None:
    for s in report.sections:
        for p in s.paragraphs_pl:
            assert p[0].isupper() or p[0].isdigit(), (s.id, p)
            assert p[-1] in ".:!?", (s.id, p)


# --- 3. missing data and sources ----------------------------------------------------------------------


def test_each_missing_or_degraded_source_in_missing_data(report: Report) -> None:
    not_ok = [e for e in report.sources if e.status.value != "ok"]
    assert len(report.missing_data_pl) == len(not_ok)
    for entry in not_ok:
        assert any(line.startswith(entry.label_pl) for line in report.missing_data_pl), entry.name
    limitations = next(s for s in report.sections if s.id == "limitations")
    for line in report.missing_data_pl:
        assert line in limitations.paragraphs_pl


def test_two_missing_sources_named_explicitly() -> None:
    r = two_missing_report()
    status = {e.name: e.status.value for e in r.sources}
    assert status["soilgrids"] == "missing"
    assert status["dem"] == "missing"
    text = " ".join(r.missing_data_pl)
    assert "Gleba" in text
    assert "Ukształtowanie terenu" in text


def test_sources_section_lists_every_source_with_date(report: Report) -> None:
    names = [e.name for e in report.sources]
    assert names == ["uldk", "open_meteo", "sentinel2", "soilgrids", "dem", "hydro", "landcover"]
    sec = next(s for s in report.sections if s.id == "sources")
    for e in report.sources:
        line = next((p for p in sec.paragraphs_pl if p.startswith(e.label_pl)), None)
        assert line is not None, e.name
        assert "Pobrano 21 listopada 2026" in line
        assert e.fetched_at is not None


def test_sources_section_states_analysis_date_cut_off(report: Report) -> None:
    from app.report.texts import date_pl

    sec = next(s for s in report.sections if s.id == "sources")
    assert any(date_pl(report.analysis_date) in p for p in sec.paragraphs_pl)


# --- 4. recommendations, evidence, map ----------------------------------------------------------------


def test_every_recommendation_has_full_evidence(report: Report) -> None:
    for rec in report.recommendations:
        assert rec.evidence, rec.id
        for e in rec.evidence:
            assert e.label_pl and e.label_pl != e.key, (rec.id, e.key)
            assert e.value_pl and e.value_pl != "brak danych", (rec.id, e.key)
            assert e.source
            assert e.uncertainty.level is not None
            assert e.uncertainty.reason_pl


def test_recommendation_numbers_match_sections(report: Report) -> None:
    numbers = [r.number for r in report.recommendations]
    assert numbers == list(range(1, len(numbers) + 1))
    in_sections = [n for s in report.sections for n in s.recommendation_numbers]
    assert sorted(in_sections) == numbers
    by_number = {r.number: r for r in report.recommendations}
    for s in report.sections:
        for n in s.recommendation_numbers:
            assert by_number[n].category.value == s.id


def test_rich_report_has_recommendations_in_three_sections() -> None:
    r = rich_report()
    assert r.complete
    filled = {s.id for s in r.sections if s.recommendation_numbers}
    assert {"retention", "agrotech"} <= filled
    assert r.chart is not None and r.chart.points
    assert len(r.months) == 12 or r.months


def test_map_features_linked_to_recommendation_locations(report: Report) -> None:
    numbers = {r.number for r in report.recommendations}
    for f in report.map.features:
        assert set(f.recommendation_numbers) <= numbers
        assert f.kind in report.map.legend_pl
        assert shape(f.geometry).is_valid or shape(f.geometry).length > 0
    for rec in report.recommendations:
        for loc in rec.locations:
            linked = [f for f in report.map.features if f.kind == loc.kind and f.geometry == loc.geometry]
            assert linked, (rec.id, loc.kind)
            assert all(rec.number in f.recommendation_numbers for f in linked)


def test_rich_report_map_has_linked_feature() -> None:
    r = rich_report()
    assert any(f.recommendation_numbers for f in r.map.features)


# --- 5. different scenarios -> different results ------------------------------------------------------


def test_different_scenarios_give_different_recommendations() -> None:
    a = [rec.id for rec in rich_report().recommendations]
    b = [
        rec.id
        for rec in report_for(
            texture=(25.0, 35.0, 40.0, 20.0), surface=lambda p: tilted(p, 0.08)
        ).recommendations
    ]
    assert a and b
    assert a != b


def test_wet_scenario_differs_from_dry() -> None:
    from tests.recommendations.builders import wet

    dry_r = rich_report()
    wet_r = report_for(precip=wet)
    assert dry_r.headline.level != wet_r.headline.level
    assert [r.id for r in dry_r.recommendations] != [r.id for r in wet_r.recommendations]


def test_report_json_round_trip(report: Report) -> None:
    again = Report.model_validate_json(report.model_dump_json())
    assert again.model_dump_json() == report.model_dump_json()
