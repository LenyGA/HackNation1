"""plan2 L1.1 (Y axes with units on every PDF chart) and L1.2 ("na dzień DD.MM.YYYY" instead of "teraz")."""

import math
import re
from datetime import date

import pytest

from app.report.charts_svg import nice_ticks, profile_svg, satellite_svg, trends_svgs, water_plan_svg
from app.report.models import Report, SatellitePoint, SatelliteSeries
from app.report.pdf import render_html
from app.report.texts import date_dmy
from tests.report.builders import report_for, rich_report

HISTORIC = date(2019, 7, 15)

TICK = re.compile(r'<text class="tick"[^>]*>([^<]+)</text>')
UNIT = re.compile(r'<text class="unit"[^>]*>([^<]+)</text>')


def _axis(svg: str) -> tuple[list[str], str]:
    ticks = TICK.findall(svg)
    units = UNIT.findall(svg)
    assert len(units) == 1, "every chart has exactly one unit label on the Y axis"
    return ticks, units[0]


def test_date_dmy() -> None:
    assert date_dmy(HISTORIC) == "15.07.2019"
    assert date_dmy("2026-01-03") == "03.01.2026"
    assert date_dmy(None) == "brak daty"


@pytest.mark.parametrize(
    ("lo", "hi"),
    [(0, 7), (0, 43), (0, 380), (-112, 35), (101.3, 104.9), (0, 1), (-3.2, -0.4), (5, 5)],
)
def test_nice_ticks_are_round_and_cover_range(lo: float, hi: float) -> None:
    ticks = nice_ticks(lo, hi)
    assert 3 <= len(ticks) <= 6
    assert ticks[0] <= lo and ticks[-1] >= hi
    step = ticks[1] - ticks[0]
    mantissa = step / 10 ** math.floor(math.log10(step))
    assert round(mantissa, 6) in (1, 2, 5, 10)
    assert all(abs((b - a) - step) < 1e-9 for a, b in zip(ticks, ticks[1:], strict=False))


def test_every_pdf_chart_has_labelled_y_axis_with_unit() -> None:
    r = rich_report()
    assert r.water_plan is not None and r.profile is not None and r.trends is not None
    ticks, unit = _axis(water_plan_svg(r.water_plan))
    assert unit == "mm" and len(ticks) >= 3 and ticks[0] == "0"
    ticks, unit = _axis(profile_svg(r.profile))
    assert unit == "m n.p.m." and len(ticks) >= 3
    trends = trends_svgs(r.trends)
    assert trends
    for metric, svg in trends:
        ticks, unit = _axis(svg)
        assert unit == metric.unit and len(ticks) >= 3


def test_satellite_svg_axis_and_date_instead_of_now() -> None:
    sat = SatelliteSeries(
        points=[
            SatellitePoint(year=2017, day=date(2017, 7, 10), ndvi=0.71, ndmi=None, current=False),
            SatellitePoint(year=2018, day=date(2018, 7, 12), ndvi=0.55, ndmi=None, current=False),
            SatellitePoint(year=2019, day=date(2019, 7, 9), ndvi=0.48, ndmi=0.1, current=True),
        ],
        history_median=0.63,
        history_min=0.55,
        history_max=0.71,
        applicable=True,
        text_pl="x",
        source="Sentinel-2",
    )
    svg = satellite_svg(sat)
    ticks, unit = _axis(svg)
    assert unit == "wskaźnik zieleni"
    assert ticks == ["0", "0,25", "0,5", "0,75", "1"]
    assert "09.07" in svg
    assert "teraz" not in svg


def test_decimal_comma_on_axis() -> None:
    assert "," in "".join(TICK.findall(satellite_svg(_tiny_sat())))


def _tiny_sat() -> SatelliteSeries:
    return SatelliteSeries(
        points=[SatellitePoint(year=2019, day=date(2019, 7, 9), ndvi=0.48, ndmi=None, current=True)],
        history_median=None,
        history_min=None,
        history_max=None,
        applicable=False,
        text_pl="x",
        source="Sentinel-2",
    )


@pytest.fixture(scope="module")
def historic_report() -> Report:
    return report_for(day=HISTORIC)


def test_report_for_historic_date_says_na_dzien(historic_report: Report) -> None:
    r = historic_report
    current = next(s for s in r.sections if s.id == "current")
    assert current.title_pl == "Sytuacja wodna na dzień 15.07.2019"
    action = next(t for t in r.summary_tiles if t.id == "action")
    assert action.label_pl == "Najważniejszy ruch na dzień 15.07.2019"


def test_no_teraz_in_headers_or_legends(historic_report: Report) -> None:
    r = historic_report
    headers = [s.title_pl for s in r.sections] + [t.label_pl for t in r.summary_tiles]
    assert not [h for h in headers if "teraz" in h.lower()]
    html = render_html(r)
    for tag in ("h1", "h2", "h3", "th"):
        for text in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.S):
            assert "teraz" not in text.lower(), text
    for cap in re.findall(r'<div class="cap">(.*?)</div>', html, re.S):
        assert "teraz" not in cap.lower(), cap
    assert "15.07.2019" in html
