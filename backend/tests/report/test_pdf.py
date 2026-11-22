"""Print HTML + PDF (plan M6.3): valid PDF on 2–4 A4 pages, no external resources, autoescaping."""

import asyncio
import re
from collections.abc import Callable

import pytest
from weasyprint import HTML

from app.report.models import Report
from app.report.pdf import render_html, render_pdf
from tests.report.builders import SCENARIOS, rich_report, two_missing_report

JARGON = re.compile(r"NDVI|NDMI|KBW|percentyl", re.IGNORECASE)


def pages(r: Report) -> int:
    return len(HTML(string=render_html(r)).render().pages)


def test_render_pdf_returns_pdf_bytes() -> None:
    pdf = asyncio.run(render_pdf(rich_report()))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5_000


@pytest.mark.parametrize("factory", [rich_report, two_missing_report], ids=["rich", "two_missing"])
def test_pdf_fits_on_2_to_7_pages(factory: Callable[[], Report]) -> None:
    # 9 sections + summary tiles, 10-year heat map and trends, seasonal water plan and the strategy table.
    r = factory()
    assert 2 <= pages(r) <= 7


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_every_scenario_renders(name: str) -> None:
    r = SCENARIOS[name]()
    html = render_html(r)
    assert html.startswith("<!doctype html>")
    for s in r.sections:
        assert f"{s.number}. {s.title_pl}" in html
    assert 1 <= pages(r) <= 7


def test_html_is_autoescaped() -> None:
    r = rich_report()
    r.parcel.commune = "<script>alert(1)</script>"
    r.parcel.county = '"><img src=x onerror=alert(1)>'
    html = render_html(r)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html


def test_html_has_no_external_resources() -> None:
    html = render_html(rich_report())
    assert not re.search(r'(src|href)="https?://', html)
    assert "<svg" in html


def test_map_svg_in_retention_section() -> None:
    r = rich_report()
    html = render_html(r)
    retention = html.split('class="section-retention')[1].split("<section")[0]
    assert "<svg" in retention


def _main_html_text(html: str) -> str:
    body = re.sub(r'<div class="details">.*?</div>', "", html, flags=re.S)
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    return re.sub(r"<[^>]+>", " ", body)


def test_print_html_main_text_has_no_jargon() -> None:
    text = _main_html_text(render_html(rich_report()))
    assert not JARGON.search(text), JARGON.findall(text)


def test_pdf_lists_all_evidence_and_one_county_prefix() -> None:
    """Q7: no '… i 1 inna wartość' in the PDF, and no 'pow. powiat …' in the header."""
    r = rich_report()
    html = render_html(r)
    assert "inna wartość w raporcie online" not in html and "inne wartości w raporcie online" not in html
    for rec in r.recommendations:
        for e in rec.evidence:
            assert e.label_pl in html
    assert "pow. powiat" not in html


def test_main_depression_is_one_definition_for_text_map_and_profile() -> None:
    """Q7: the recommendation, the map and the slope profile describe the same main depression."""
    r = rich_report()
    rec = next(x for x in r.recommendations if x.id == "depression_retention")
    main_on_map = [f for f in r.map.features if f.kind == "depression"]
    count = next(e.value for e in rec.evidence if e.key == "depression_count")
    assert count == len(main_on_map)
    assert all(rec.number in f.recommendation_numbers for f in main_on_map)
    assert all(f.recommendation_numbers == [] for f in r.map.features if f.kind == "depression_minor")
    if r.profile is not None and "obniż" in r.profile.text_pl:
        assert "zagłębieni" in r.profile.text_pl
