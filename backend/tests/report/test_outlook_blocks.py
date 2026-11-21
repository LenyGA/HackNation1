"""New report blocks (tiles, heat map, trends, water plan, profile, simulator) and the stage-1 fixes."""

from app.report.pdf import render_html
from tests.recommendations.builders import LOAMY_SAND
from tests.report.builders import report_for, rich_report, two_missing_report

LOAM = (40.0, 40.0, 20.0, 15.0)


def test_rich_report_has_all_new_blocks() -> None:
    r = rich_report()
    assert [t.id for t in r.summary_tiles] == ["water_now", "action", "climate", "dry_year", "flood"]
    water = r.summary_tiles[0]
    assert water.gauge is not None and water.gauge.threshold is not None
    assert 0 <= water.gauge.value <= water.gauge.max
    assert r.stress_heatmap is not None and len(r.stress_heatmap.rows) >= 5
    assert r.trends is not None and r.trends.verdict_pl[0].startswith("Wniosek:")
    assert r.water_plan is not None and r.water_plan.text_pl
    assert r.simulation is not None and len(r.simulation.strategies) == 5
    assert all(len(s.years) == 5 for s in r.simulation.strategies)
    assert r.profile is not None and len(r.profile.points) >= 5
    # Flood not fetched in the builders: the tile says so instead of pretending "safe".
    assert r.summary_tiles[-1].status == "unknown"


def test_dry_year_never_below_typical_in_report() -> None:
    p = rich_report().water_plan
    assert p is not None and p.season_median_mm is not None and p.season_p80_mm is not None
    assert p.season_median_mm <= p.season_p80_mm
    for m in p.months:
        if m.deficit_median_mm is not None and m.deficit_p80_mm is not None:
            assert m.deficit_median_mm <= m.deficit_p80_mm


def test_no_soil_no_simulator_and_no_heatmap() -> None:
    r = two_missing_report()
    assert r.simulation is None and r.stress_heatmap is None
    assert r.water_plan is not None and r.water_plan.method == "crop_balance"
    assert r.summary_tiles[0].value_pl == "brak danych"


def _vuln_text(**kw: object) -> str:
    r = report_for(**kw)  # type: ignore[arg-type]
    return " ".join(next(s for s in r.sections if s.id == "vulnerability").paragraphs_pl)


def test_soil_retention_and_shallow_roots_are_not_contradictory() -> None:
    text = _vuln_text(crop_id="potato", texture=LOAM)
    assert "płytkich korzeni" in text
    assert "słabo magazynuje" not in text


def test_light_soil_says_so_in_both_sentences() -> None:
    text = _vuln_text(texture=LOAMY_SAND)
    assert "słabo" in text and "płytkich korzeni" not in text


def test_single_dose_rounded_once_half_up() -> None:
    irr = rich_report().irrigation
    if irr.applications and irr.applications > 1:
        assert irr.dose_mm is not None and irr.single_dose_mm is not None
        assert irr.single_dose_mm == int(irr.dose_mm / irr.applications + 0.5)
        assert f"po ok. {irr.single_dose_mm:g} mm" in irr.text_pl.replace(",", ".")


def test_pdf_has_new_charts_and_tiles() -> None:
    html = render_html(rich_report())
    assert 'class="tiles"' in html
    assert "Plan wody na sezon" in html
    assert "Porównanie strategii" in html
    assert "Przekrój terenu" in html
