"""G9 / M4.4: retention methods and the coverage card in the report, the web JSON and both PDF variants."""

from app.report.pdf import render_html
from tests.recommendations.builders import CLAY_LOAM_RICH, basin, hydro
from tests.report.builders import no_weather_report, report_for, rich_report


def test_coverage_uses_the_water_plan_values() -> None:
    r = rich_report()
    assert r.retention_plan is not None and r.water_plan is not None
    c = r.retention_plan.coverage
    assert c.full_need_m3 == r.water_plan.season_p80_m3_parcel_gross
    assert c.rescue_need_m3 == r.water_plan.critical_p80_m3_parcel_gross
    assert c.status == "ok"
    assert f"{c.full_pct:.0f} %" in c.text_pl


def test_five_methods_with_sentences() -> None:
    r = rich_report()
    assert r.retention_plan is not None
    methods = r.retention_plan.methods
    assert [m.id for m in methods] == ["pond", "weir", "rainwater", "well", "tree_belts"]
    for m in methods:
        assert m.reason_pl and m.status_pl
        assert "{{" not in m.reason_pl and "None" not in m.reason_pl


def test_no_retention_plan_without_complete_assessment() -> None:
    assert no_weather_report().retention_plan is None


def test_full_report_shows_all_methods_and_legal_basis() -> None:
    r = rich_report()
    html = render_html(r, variant="full")
    assert "Jak zatrzymać i zgromadzić wodę na tej działce" in html
    for label in ("Oczko lub staw", "Zastawka", "Deszczówka", "Studnia", "Pasy zadrzewień"):
        assert label in html
    assert "Dz.U. 2025 poz. 960" in html


def test_basic_report_shows_coverage_and_only_recommended_methods() -> None:
    r = report_for(surface=basin, texture=CLAY_LOAM_RICH, hydro_data=lambda p: hydro(p, ditch_m=200.0))
    assert r.retention_plan is not None
    html = render_html(r, variant="basic")
    assert r.retention_plan.coverage.text_pl.split(" (")[0] in html
    for m in r.retention_plan.methods:
        shown = f"<b>{m.label_pl}</b>" in html
        assert shown == (m.status == "recommended"), m.id


def test_shares_over_100_percent_read_as_all_the_water() -> None:
    from app.analysis.retention_balance import CoverageStatus, RetentionCoverage
    from app.recommendations.retention_methods import MethodAssessment, MethodStatus
    from app.report.texts import render_line

    c = RetentionCoverage(CoverageStatus.OK, 11960.0, 34900.0, 0.8, 12590.0, 840.0, 95.0, 1424.0)
    text = render_line("blocks/retention_coverage.j2", c=c)
    assert "1 424" not in text and "ok. 95 %" in text and "całą wodę na podlewanie ratunkowe" in text
    pond = MethodAssessment(
        "pond",
        MethodStatus.RECOMMENDED,
        "depression",
        {"volume_m3": 11960.0, "full_pct": 95.0, "rescue_pct": 1424.0, "sealing": "natural", "controlled": 0},
    )
    line = render_line("blocks/retention_method.j2", m=pond)
    assert "1 424" not in line and "całą na podlewanie ratunkowe" in line
