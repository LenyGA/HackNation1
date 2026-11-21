"""Regressions for the M6 code review: print CSS, map frame, jargon-free labels, cause wording."""

import re

from app.report.map_svg import parcel_map_svg
from app.report.pdf import render_html
from tests.recommendations.builders import hydro
from tests.report.builders import report_for, rich_report

JARGON = re.compile(r"ndvi|ndmi|kbw|percentyl|\bTAW\b|\bRAW\b", re.IGNORECASE)


def test_print_css_is_not_html_escaped() -> None:
    html = render_html(rich_report())
    style = html[html.index("<style>") : html.index("</style>")]
    assert "&#34;" not in style and "&quot;" not in style
    assert 'content: "str. "' in style


def test_evidence_and_indicator_labels_have_no_jargon() -> None:
    r = rich_report()
    labels = [e.label_pl for rec in r.recommendations for e in rec.evidence]
    labels += [i.label_pl for s in r.sections for i in s.indicators]
    assert labels
    assert [lbl for lbl in labels if JARGON.search(lbl)] == []


def test_map_frame_includes_distant_linked_wetland() -> None:
    r = report_for(hydro_data=lambda p: hydro(p, wetland_m=250.0))
    linked = [f for f in r.map.features if f.kind == "wetland" and f.recommendation_numbers]
    assert linked, "protect_wetlands should link the wetland"
    svg = parcel_map_svg(r)
    # The wetland is drawn and its recommendation number appears as a marker.
    assert "#8fd0c8" in svg
    number = str(linked[0].recommendation_numbers[0])
    assert f">{number}</text>" in svg


def test_summary_does_not_claim_causal_link_for_vulnerability() -> None:
    summary = rich_report().sections[0].paragraphs_pl
    assert not any("sezonów, więc podatność" in p for p in summary)


def test_soil_cause_cites_only_triggered_checks() -> None:
    # Heavy soil with little organic carbon: flagged by organic carbon only.
    r = report_for(texture=(25.0, 35.0, 40.0, 5.0))
    causes = " ".join(r.sections[3].paragraphs_pl)
    assert "Gleba słabo zatrzymuje wodę" in causes
    assert "mało próchnicy" in causes
    assert "mieści tylko" not in causes
    assert "gleba ciężka" not in causes


def test_off_season_headline_from_root_zone_matches_body() -> None:
    from datetime import date

    from tests.recommendations.builders import dry

    r = report_for(day=date(2024, 11, 21), crop_id="winter_wheat", precip=dry)
    assert "odbudowuje" not in r.headline.sentence_pl
    assert "w glebie" in r.headline.sentence_pl
