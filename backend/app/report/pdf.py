"""Report as print HTML and PDF (plan step M6.3). One HTML template + one stylesheet serve both the PDF
(WeasyPrint) and printing from the browser. No external resources: the map is inline SVG; its orthophoto
background is fetched by the server and embedded as a data URI.
"""

import asyncio
import base64
from collections import OrderedDict
from datetime import date
from functools import lru_cache
from typing import Any, Literal

from app.report.chart_range import DEFAULT_RANGE, RangeKey, range_chart, resolve_window
from app.report.charts_svg import profile_svg, satellite_svg, season_svg, trends_svgs, water_plan_svg
from app.report.labels_pl import CONFIDENCE_LABELS
from app.report.map_svg import STYLE, map_frame, parcel_map_svg
from app.report.models import Report, SeasonChart
from app.report.texts import TEMPLATES_DIR, html_env
from app.sources import orthophoto


@lru_cache
def _css() -> str:
    return (TEMPLATES_DIR / "report.css").read_text(encoding="utf-8")


@lru_cache
def _logo_uri() -> str:
    """Team logo for the report header (M8.5), embedded so the PDF loads nothing from outside."""
    data = (TEMPLATES_DIR / "logo.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _legend_colors() -> dict[str, str]:
    """Legend swatch colour per feature kind, taken from the SVG styles."""
    out: dict[str, str] = {}
    for kind, style in STYLE.items():
        attr = "fill" if 'fill="none"' not in style else "stroke"
        start = style.index(f'{attr}="') + len(attr) + 2
        out[kind] = style[start : style.index('"', start)]
    return out


def water_chart(report: Report, window: tuple[date, date] | None) -> SeasonChart | None:
    """Water situation chart for the window chosen on the page; older reports without daily data keep
    the season chart."""
    if report.water_daily is None:
        return report.chart
    if window is None:
        window = resolve_window(report.water_daily, report.analysis_date, DEFAULT_RANGE)
    return range_chart(report.water_daily, *window) if window else None


def chart_window(
    report: Report, key: RangeKey = DEFAULT_RANGE, start: date | None = None, end: date | None = None
) -> tuple[date, date] | None:
    """Window of the water chart for a range key from the page (None: not applicable / invalid)."""
    if report.water_daily is None:
        return None
    return resolve_window(report.water_daily, report.analysis_date, key, start, end)


def _charts(report: Report, window: tuple[date, date] | None) -> dict[str, object]:
    season = water_chart(report, window)
    return {
        "season": season_svg(season) if season and len(season.points) >= 2 else "",
        "season_chart": season,
        "water_plan": water_plan_svg(report.water_plan) if report.water_plan else "",
        "profile": profile_svg(report.profile) if report.profile and len(report.profile.points) >= 2 else "",
        "trends": trends_svgs(report.trends) if report.trends else [],
        "satellite": satellite_svg(report.satellite) if report.satellite else "",
    }


# The 1–5 year strategy simulator is hidden from the report for now (team decision 22.11); it is still
# computed and kept in the report model so it can come back.
SHOW_SIMULATION = False

# Colour of the retention method status (G9).
METHOD_PILL = {"recommended": "good", "conditional": "warn", "not_recommended": "bad", "no_data": "unknown"}

Variant = Literal["basic", "full"]
TEMPLATES: dict[Variant, str] = {"basic": "report_basic.html.j2", "full": "report.html.j2"}


def render_html(
    report: Report,
    basemap_uri: str | None = None,
    basemap_requested: bool = False,
    variant: Variant = "full",
    window: tuple[date, date] | None = None,
) -> str:
    """`basemap_requested`: the server asked Geoportal for the orthophoto (PDF). The print view does not,
    so it never claims that the service failed. The basic variant has no map, charts or tables."""
    return (
        html_env()
        .get_template(TEMPLATES[variant])
        .render(
            r=report,
            css=_css(),
            logo_uri=_logo_uri(),
            map_svg=parcel_map_svg(report, basemap_uri),
            basemap="ok" if basemap_uri is not None else ("failed" if basemap_requested else "none"),
            charts=_charts(report, window),
            recs={rec.number: rec for rec in report.recommendations},
            legend_colors=_legend_colors(),
            confidence_pl=CONFIDENCE_LABELS,
            method_pill=METHOD_PILL,
            show_simulation=SHOW_SIMULATION,
        )
    )


def _fetcher() -> Any:
    """WeasyPrint URL fetcher that allows only embedded data: URIs (the orthophoto fetched by the server).

    Every http(s)/file URL raises: the PDF must not load anything from outside."""
    from weasyprint import URLFetcher

    return URLFetcher(allowed_protocols={"data"}, fail_on_errors=False)


def _write_pdf(html: str) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is requested

    pdf: bytes = HTML(string=html, url_fetcher=_fetcher()).write_pdf()
    return pdf


# WeasyPrint is CPU- and memory-heavy; limit parallel renders on the small VPS.
_pdf_slots: asyncio.Semaphore | None = None
PDF_CONCURRENCY = 2


def _render(
    report: Report, basemap_uri: str | None, variant: Variant, window: tuple[date, date] | None
) -> bytes:
    full = variant == "full"
    html = render_html(report, basemap_uri, basemap_requested=full, variant=variant, window=window)
    return _write_pdf(html)


# Saved reports never change, so a rendered PDF is reused: repeated downloads (or a client hammering one
# link) cost no WeasyPrint work. Bounded LRU of ~300 KB files.
PDF_CACHE_SIZE = 32
_pdf_cache: OrderedDict[tuple[str, Variant, tuple[date, date] | None], bytes] = OrderedDict()


async def render_pdf(
    report: Report, variant: Variant = "full", window: tuple[date, date] | None = None
) -> bytes:
    """`window`: range of the water chart chosen on the page (full variant only; None = default range)."""
    global _pdf_slots
    if variant == "basic":
        window = None  # the basic variant has no charts
    elif window is None:
        window = chart_window(report)  # the default range shares its cache entry with an explicit one
    key = (report.id, variant, window)
    cached = _pdf_cache.get(key)
    if cached is not None:
        _pdf_cache.move_to_end(key)
        return cached
    if _pdf_slots is None:
        _pdf_slots = asyncio.Semaphore(PDF_CONCURRENCY)
    # The WMS call runs before taking a render slot, so a slow Geoportal never blocks other PDFs.
    # The basic variant has no map, so it never asks for the orthophoto.
    basemap = await orthophoto.fetch_data_uri(map_frame(report)) if variant == "full" else None
    async with _pdf_slots:
        cached = _pdf_cache.get(key)  # rendered by another request while this one waited
        if cached is not None:
            return cached
        pdf = await asyncio.to_thread(_render, report, basemap, variant, window)
    if variant == "full" and basemap is None:
        return pdf  # not cached: the next download tries the orthophoto again
    _pdf_cache[key] = pdf
    while len(_pdf_cache) > PDF_CACHE_SIZE:
        _pdf_cache.popitem(last=False)
    return pdf
