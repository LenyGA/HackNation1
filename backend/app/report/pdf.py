"""Report as print HTML and PDF (plan step M6.3). One HTML template + one stylesheet serve both the PDF
(WeasyPrint) and printing from the browser. No external resources: the map is inline SVG.
"""

import asyncio
from functools import lru_cache

from app.report.labels_pl import CONFIDENCE_LABELS
from app.report.map_svg import STYLE, parcel_map_svg
from app.report.models import Report
from app.report.texts import TEMPLATES_DIR, html_env

# Numbers listed under each recommendation in the PDF (all of them are in the online report).
MAX_EVIDENCE_PDF = 4


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


def render_html(report: Report) -> str:
    return (
        html_env()
        .get_template("report.html.j2")
        .render(
            r=report,
            css=_css(),
            map_svg=parcel_map_svg(report),
            recs={rec.number: rec for rec in report.recommendations},
            legend_colors=_legend_colors(),
            confidence_pl=CONFIDENCE_LABELS,
            max_evidence=MAX_EVIDENCE_PDF,
        )
    )


def _no_fetch(url: str, *args: object, **kwargs: object) -> dict[str, object]:
    """WeasyPrint URL fetcher that refuses every request: the PDF must not load anything from outside."""
    raise ValueError(f"external resource blocked: {url}")


def _write_pdf(html: str) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is requested

    pdf: bytes = HTML(string=html, url_fetcher=_no_fetch).write_pdf()
    return pdf


# WeasyPrint is CPU- and memory-heavy; limit parallel renders on the small VPS.
_pdf_slots: asyncio.Semaphore | None = None
PDF_CONCURRENCY = 2


def _render(report: Report) -> bytes:
    return _write_pdf(render_html(report))


async def render_pdf(report: Report) -> bytes:
    global _pdf_slots
    if _pdf_slots is None:
        _pdf_slots = asyncio.Semaphore(PDF_CONCURRENCY)
    async with _pdf_slots:
        return await asyncio.to_thread(_render, report)
