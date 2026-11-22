"""Report as print HTML and PDF (plan step M6.3). One HTML template + one stylesheet serve both the PDF
(WeasyPrint) and printing from the browser. No external resources: the map is inline SVG; its orthophoto
background is fetched by the server and embedded as a data URI.
"""

import asyncio
from collections import OrderedDict
from functools import lru_cache
from typing import Any

from app.report.charts_svg import profile_svg, satellite_svg, trends_svgs, water_plan_svg
from app.report.labels_pl import CONFIDENCE_LABELS
from app.report.map_svg import STYLE, map_frame, parcel_map_svg
from app.report.models import Report
from app.report.texts import TEMPLATES_DIR, html_env
from app.sources import orthophoto


@lru_cache
def _css() -> str:
    return (TEMPLATES_DIR / "report.css").read_text(encoding="utf-8")


def _legend_colors() -> dict[str, str]:
    """Legend swatch colour per feature kind, taken from the SVG styles."""
    out: dict[str, str] = {}
    for kind, style in STYLE.items():
        attr = "fill" if 'fill="none"' not in style else "stroke"
        start = style.index(f'{attr}="') + len(attr) + 2
        out[kind] = style[start : style.index('"', start)]
    return out


def _charts(report: Report) -> dict[str, object]:
    return {
        "water_plan": water_plan_svg(report.water_plan) if report.water_plan else "",
        "profile": profile_svg(report.profile) if report.profile and len(report.profile.points) >= 2 else "",
        "trends": trends_svgs(report.trends) if report.trends else [],
        "satellite": satellite_svg(report.satellite) if report.satellite else "",
    }


def render_html(report: Report, basemap_uri: str | None = None, basemap_requested: bool = False) -> str:
    """`basemap_requested`: the server asked Geoportal for the orthophoto (PDF). The print view does not,
    so it never claims that the service failed."""
    return (
        html_env()
        .get_template("report.html.j2")
        .render(
            r=report,
            css=_css(),
            map_svg=parcel_map_svg(report, basemap_uri),
            basemap="ok" if basemap_uri is not None else ("failed" if basemap_requested else "none"),
            charts=_charts(report),
            recs={rec.number: rec for rec in report.recommendations},
            legend_colors=_legend_colors(),
            confidence_pl=CONFIDENCE_LABELS,
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


def _render(report: Report, basemap_uri: str | None = None) -> bytes:
    return _write_pdf(render_html(report, basemap_uri, basemap_requested=True))


# Saved reports never change, so a rendered PDF is reused: repeated downloads (or a client hammering one
# link) cost no WeasyPrint work. Bounded LRU of ~300 KB files.
PDF_CACHE_SIZE = 32
_pdf_cache: OrderedDict[str, bytes] = OrderedDict()


async def render_pdf(report: Report) -> bytes:
    global _pdf_slots
    cached = _pdf_cache.get(report.id)
    if cached is not None:
        _pdf_cache.move_to_end(report.id)
        return cached
    if _pdf_slots is None:
        _pdf_slots = asyncio.Semaphore(PDF_CONCURRENCY)
    # The WMS call runs before taking a render slot, so a slow Geoportal never blocks other PDFs.
    basemap = await orthophoto.fetch_data_uri(map_frame(report))
    async with _pdf_slots:
        cached = _pdf_cache.get(report.id)  # rendered by another request while this one waited
        if cached is not None:
            return cached
        pdf = await asyncio.to_thread(_render, report, basemap)
    if basemap is None:
        return pdf  # not cached: the next download tries the orthophoto again
    _pdf_cache[report.id] = pdf
    while len(_pdf_cache) > PDF_CACHE_SIZE:
        _pdf_cache.popitem(last=False)
    return pdf
