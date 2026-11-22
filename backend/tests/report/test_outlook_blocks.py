"""New report blocks (tiles, heat map, trends, water plan, profile, simulator) and the stage-1 fixes."""

import pytest

from app.report import pdf
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
    assert "Przekrój terenu" in html
    assert "Deszcz i potrzeby wodne uprawy od" in html  # water chart with the default range (6 months)
    # The 1–5 year simulator is hidden for now (pdf.SHOW_SIMULATION), although it is still computed.
    assert "Porównanie strategii" not in html


def test_pdf_shows_simulator_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "SHOW_SIMULATION", True)
    assert "Porównanie strategii" in render_html(rich_report())


def test_rescue_irrigation_in_a_dry_year_has_one_value_everywhere() -> None:
    """Q2/T3: the plan, the simulator text and the PDF quote one rescue amount, rounded once."""
    import re

    from app.report.texts import num

    r = rich_report()
    p = r.water_plan
    assert p is not None and p.critical_p80_mm is not None and p.season_p80_mm is not None
    assert p.critical_p80_mm % 5 == 0 and p.season_p80_mm % 5 == 0
    rescue = f"ok. {num(p.critical_p80_mm)} mm"
    sim_text = " ".join(r.simulation.text_pl) if r.simulation else ""
    plan_text = " ".join(p.text_pl)
    html = render_html(r)
    for text in (sim_text, plan_text, html):
        quoted = re.findall(r"(?:ratunkow\w*|ratowanie plonu)[^.]*?ok\. ([\d ]+) mm", text)
        assert quoted, text[:200]
        assert {f"ok. {q} mm" for q in quoted} == {rescue}, quoted
    # Simulator year 1 starts from the same seasons as the plan: only the ET0 trend may move it.
    sim = r.simulation
    assert sim is not None
    rescue_y1 = next(s for s in sim.strategies if s.id == "rescue").years[0].irrigation_mm_p80
    assert rescue_y1 is not None and abs(rescue_y1 - p.critical_p80_mm) <= max(10.0, 0.15 * p.critical_p80_mm)
    for st in sim.strategies:
        for y in st.years:
            assert y.irrigation_mm_p80 is None or y.irrigation_mm_p80 % 5 == 0
