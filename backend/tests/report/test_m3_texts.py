"""Texts reworked in plan M3.4 (team review notes): analysis-date lead, value with a verdict, rainfall
against the usual amount, satellite condition with the scene date, no-hazard flood in one sentence,
soil vs root depth."""

import re
from datetime import date

from app.analysis.assessment import assess
from app.recommendations.engine import recommend
from app.recommendations.irrigation import irrigation_advice
from app.report.builder import ParcelSource, build_report
from app.report.models import Report
from app.report.storage import new_report_id
from tests.analysis.builders import make_inputs, ok, random_precip, sentinel_data
from tests.recommendations.test_rules import _flood
from tests.report.builders import CREATED, report_for

SUMMER = date(2024, 7, 15)


def _main(r: Report, sid: str) -> str:
    return "\n".join(next(s for s in r.sections if s.id == sid).paragraphs_pl)


def _report_with_satellite(ndvi_now: float) -> Report:
    rp = random_precip()
    inputs = make_inputs(
        SUMMER, precip=lambda d: rp(d) * 2, sentinel2=ok("sentinel2", sentinel_data(SUMMER, ndvi_now))
    )
    a = assess(inputs)
    recs = recommend(a, inputs)
    return build_report(
        report_id=new_report_id(),
        created_at=CREATED,
        inputs=inputs,
        assessment=a,
        recommendations=recs,
        irrigation=irrigation_advice(a, inputs, today=SUMMER),
        parcel_source=ParcelSource(fetched_at=CREATED),
    )


def test_summary_starts_with_the_analysis_date_without_parcel_data() -> None:
    r = report_for()
    first = next(s for s in r.sections if s.id == "summary").paragraphs_pl[0]
    assert first.startswith("Na dzień 15.07.2024 ")
    assert r.parcel.id not in first and "gmina" not in first


def test_root_zone_value_comes_with_a_verdict() -> None:
    current = _main(report_for(), "current")
    assert re.search(r"Na dzień 15\.07\.2024 w strefie korzeni .* — to (mało|zapas w normie|dużo)", current)


def test_main_text_never_says_typical_condition() -> None:
    for ndvi in (0.3, 0.7, 0.8):
        assert "typowa" not in _main(_report_with_satellite(ndvi), "current")


def test_satellite_condition_with_percent_and_scene_date() -> None:
    weak = _main(_report_with_satellite(0.4), "current")
    assert "na zdjęciu z 12.07.2024" in weak and "słabsza niż zwykle o ok." in weak
    good = _main(_report_with_satellite(0.71), "current")
    assert "jest dobra — podobna jak zwykle" in good


def test_rainfall_against_the_usual_amount() -> None:
    wet = _main(report_for(precip=lambda d: 6.0 if (SUMMER - d).days < 30 else 1.0), "current")
    assert re.search(r"W ostatnich 30 dniach spadło \d+ mm deszczu \(o \d+ mm więcej niż zwykle\)", wet)
    dry = _main(report_for(precip=lambda d: 0.0 if (SUMMER - d).days < 30 else 3.0), "current")
    assert re.search(r"spadło 0 mm deszczu \(o \d+ mm mniej niż zwykle\)", dry)


def test_no_flood_hazard_is_one_sentence() -> None:
    r = report_for(flood=_flood(False))
    assert r.flood is not None and r.flood.level == "none"
    assert r.flood.sentence_pl.count(".") == 1
    assert "nie stwierdzono stref zagrożenia powodziowego" in r.flood.sentence_pl
    assert "stan na dziś" in r.flood.sentence_pl  # maps describe today, not the analysis date


def test_flood_with_groundwater_hazard_keeps_the_caveats() -> None:
    r = report_for(flood=_flood(True))
    assert r.flood is not None and "podtopieniami" in r.flood.sentence_pl


def test_shallow_roots_explain_the_small_reserve() -> None:
    current = _main(report_for(crop_id="potato"), "current")
    assert "Sama gleba mieści ok." in current and "korzenie uprawy (ziemniaki) sięgają tylko ok." in current
    assert "Sama gleba mieści" not in _main(report_for(), "current")  # maize roots reach 1 m


def test_rainfall_difference_hidden_when_the_percentile_says_usual() -> None:
    current = _main(report_for(), "current")
    assert "mniej więcej tyle, ile zwykle" in current
    assert not re.search(r"\(o \d+ mm (więcej|mniej) niż zwykle\) — mniej więcej tyle, ile zwykle", current)


def test_basic_verdicts_list_every_flagged_cause_and_no_intro() -> None:
    from tests.report.builders import off_season_report, rich_report

    r = rich_report()
    verdicts = {s.id: s.verdict_pl for s in r.sections if s.verdict_pl}
    assert set(verdicts) == {"vulnerability", "causes"}
    flagged = [c for c in r.sections if c.id == "causes"]
    assert verdicts["causes"].count(";") >= 1 and "Nie stwierdzono" not in verdicts["causes"]
    assert flagged
    off = {s.id: s.verdict_pl for s in off_season_report().sections if s.verdict_pl}
    assert "Dzień analizy" not in " ".join(off.values())


def test_off_season_headline_has_a_soil_verdict_and_good_grammar() -> None:
    from tests.report.builders import off_season_report

    r = off_season_report()
    s = r.headline.sentence_pl
    assert "zaczyna jej brakować wody" not in s and "brakuje jej wody" not in s
    assert re.search(r"— (to mało|zapas jest prawie pełny|zapas jest w normie)", s)


def test_irrigation_text_does_not_point_to_earlier_points() -> None:
    r = report_for()
    irr = next(rec for rec in r.recommendations if rec.category.value == "irrigation")
    assert "wcześniejszych punktów" not in irr.text_pl


def test_weather_grid_matches_the_source_used() -> None:
    from app.sources import open_meteo

    r = report_for()
    assert any("10 km" in line for line in r.limitations_pl)
    assert open_meteo.SOURCE_POWER not in next(s.source for s in r.sources if s.name == "open_meteo")
