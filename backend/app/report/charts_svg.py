# ruff: noqa: E501 — inline SVG markup reads better on one line per element.
"""Small inline SVG charts for the PDF / print view (no external resources, no chart library).

Same data as the online report: water plan bars, slope profile, climate trend bars, plant condition dots.
"""

from html import escape

from app.report.models import ClimateTrends, SatelliteSeries, SlopeProfile, TrendMetric, WaterPlan
from app.report.texts import num

FONT = 'font-family="DejaVu Sans, Arial, sans-serif"'
GRID = "#e5e7eb"
TEXT = "#4b5563"
BLUE = "#3b82f6"
DARK_BLUE = "#1d4ed8"
ORANGE = "#ea580c"
LIGHT_BLUE = "#bfdbfe"


def _nice_max(v: float) -> float:
    if v <= 0:
        return 10.0
    step = 10 ** len(str(int(v))) / 10
    return float(max(step, -(-v // step) * step))


def _svg(w: float, h: float, body: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="100%" role="img" '
        f'aria-label="{escape(label)}" {FONT} font-size="10">{body}</svg>'
    )


def _y_axis(
    x0: float, x1: float, y0: float, y1: float, vmax: float, vmin: float = 0.0, unit: str = ""
) -> str:
    out = ""
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = vmin + f * (vmax - vmin)
        y = y1 - f * (y1 - y0)
        out += f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>'
        out += f'<text x="{x0 - 4}" y="{y + 3:.1f}" text-anchor="end" fill="{TEXT}">{escape(num(v, 0.1 if vmax - vmin < 5 else 1))}</text>'
    if unit:
        out += f'<text x="2" y="{y0 - 6}" fill="{TEXT}">{escape(unit)}</text>'
    return out


def water_plan_svg(plan: WaterPlan) -> str:
    w, h = 640.0, 230.0
    left, right, top, bottom = 40.0, 10.0, 22.0, 40.0
    months = plan.months
    vals = [
        v for m in months for v in (m.deficit_median_mm, m.deficit_p80_mm, m.deficit_p90_mm) if v is not None
    ]
    vmax = _nice_max(max(vals, default=0.0))
    inner_w = w - left - right
    slot = inner_w / max(1, len(months))
    bar = slot * 0.32

    def y(v: float) -> float:
        return float(top + (h - top - bottom) * (1 - v / vmax))

    body = _y_axis(left, w - right, top, h - bottom, vmax, unit="mm")
    for i, m in enumerate(months):
        x = left + i * slot + slot * 0.15
        if m.critical:
            body += f'<rect x="{left + i * slot:.1f}" y="{top}" width="{slot:.1f}" height="{h - top - bottom}" fill="#fff7ed"/>'
        for j, (v, color) in enumerate(((m.deficit_median_mm, BLUE), (m.deficit_p80_mm, ORANGE))):
            if v is None:
                continue
            bx = x + j * (bar + 2)
            body += f'<rect x="{bx:.1f}" y="{y(v):.1f}" width="{bar:.1f}" height="{h - bottom - y(v):.1f}" fill="{color}"/>'
        if m.deficit_p90_mm is not None:
            px = x + bar + 2
            body += f'<line x1="{px:.1f}" x2="{px + bar:.1f}" y1="{y(m.deficit_p90_mm):.1f}" y2="{y(m.deficit_p90_mm):.1f}" stroke="#7c2d12" stroke-width="2"/>'
        body += f'<text x="{left + (i + 0.5) * slot:.1f}" y="{h - bottom + 12}" text-anchor="middle" fill="{TEXT}">{escape(m.month_pl[:3])}</text>'
    lx = left
    for color, text in (
        (BLUE, "rok typowy (mediana)"),
        (ORANGE, "rok suchy (raz na 5 lat)"),
        ("#7c2d12", "bardzo suchy (raz na 10 lat)"),
    ):
        body += f'<rect x="{lx}" y="{h - 8}" width="10" height="6" fill="{color}"/><text x="{lx + 13}" y="{h - 2}" fill="{TEXT}">{escape(text)}</text>'
        lx += 150
    body += (
        f'<text x="{w - right}" y="12" text-anchor="end" fill="{TEXT}">tło: miesiące ważne dla uprawy</text>'
    )
    return _svg(w, h, body, "Potrzeba nawadniania w kolejnych miesiącach: rok typowy i rok suchy")


def profile_svg(profile: SlopeProfile) -> str:
    w, h = 640.0, 200.0
    left, right, top, bottom = 48.0, 10.0, 18.0, 30.0
    pts = profile.points
    zs = [p.elevation_m for p in pts]
    zmin, zmax = min(zs), max(zs)
    pad = max(0.5, (zmax - zmin) * 0.15)
    lo, hi = zmin - pad, zmax + pad
    dmax = max(p.distance_m for p in pts) or 1.0

    def x(d: float) -> float:
        return float(left + (w - left - right) * d / dmax)

    def y(z: float) -> float:
        return float(top + (h - top - bottom) * (1 - (z - lo) / (hi - lo)))

    body = _y_axis(left, w - right, top, h - bottom, hi, lo, "m n.p.m.")
    line = " ".join(f"{x(p.distance_m):.1f},{y(p.elevation_m):.1f}" for p in pts)
    body += f'<polygon points="{x(0):.1f},{h - bottom} {line} {x(dmax):.1f},{h - bottom}" fill="#d9f99d" fill-opacity="0.7"/>'
    body += f'<polyline points="{line}" fill="none" stroke="#3f6212" stroke-width="2"/>'
    for p in pts:
        if p.hollow:
            body += (
                f'<circle cx="{x(p.distance_m):.1f}" cy="{y(p.elevation_m):.1f}" r="3.2" fill="{DARK_BLUE}"/>'
            )
    body += f'<text x="{left}" y="{h - 12}" fill="{TEXT}">góra pola</text>'
    body += f'<text x="{w - right}" y="{h - 12}" text-anchor="end" fill="{TEXT}">dół pola · {escape(num(dmax, 10))} m</text>'
    body += f'<text x="{(left + w - right) / 2}" y="{h - 2}" text-anchor="middle" fill="{TEXT}">odległość wzdłuż spływu, m (niebieskie punkty: obniżenia, gdzie zbiera się woda)</text>'
    return _svg(
        w, h, body, f"Przekrój terenu działki: spadek {num(profile.drop_m, 0.1)} m na {num(dmax, 10)} m"
    )


def _trend_svg(m: TrendMetric) -> str:
    w, h = 220.0, 80.0
    left, right, top, bottom = 34.0, 4.0, 10.0, 18.0
    vals = [v.value for v in m.values]
    present = [v for v in vals if v is not None]
    if not present:
        return ""
    lo = min(0.0, min(present))
    hi = max(0.0, max(present))
    if hi == lo:
        hi = lo + 1
    slot = (w - left - right) / len(vals)

    def y(v: float) -> float:
        return float(top + (h - top - bottom) * (1 - (v - lo) / (hi - lo)))

    body = f'<line x1="{left}" x2="{w - right}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{GRID}"/>'
    body += f'<text x="{left - 3}" y="{y(hi) + 3:.1f}" text-anchor="end" fill="{TEXT}">{escape(num(hi, 0.1 if hi - lo < 5 else 1))}</text>'
    body += f'<text x="{left - 3}" y="{y(lo) + 3:.1f}" text-anchor="end" fill="{TEXT}">{escape(num(lo, 0.1 if hi - lo < 5 else 1))}</text>'
    for i, tv in enumerate(m.values):
        if tv.value is None:
            continue
        recent = i >= len(vals) - 2
        top_y, base = sorted((y(tv.value), y(0)))
        color = ORANGE if recent else BLUE
        body += f'<rect x="{left + i * slot + 1:.1f}" y="{top_y:.1f}" width="{slot - 2:.1f}" height="{max(0.5, base - top_y):.1f}" fill="{color}"/>'
        if i in (0, len(vals) - 1):
            body += f'<text x="{left + (i + 0.5) * slot:.1f}" y="{h - 5}" text-anchor="middle" fill="{TEXT}" font-size="9">{tv.year}</text>'
    if m.mean_all is not None:
        body += f'<line x1="{left}" x2="{w - right}" y1="{y(m.mean_all):.1f}" y2="{y(m.mean_all):.1f}" stroke="#111827" stroke-dasharray="4 3"/>'
    return _svg(w, h, body, f"{m.label_pl}: {m.summary_pl}")


# The PDF shows the three most telling metrics (all of them are in the online report).
PDF_TREND_KEYS = ("kbw_mm", "critical_stress_days", "stress_days", "tmean_c", "hot_days")
PDF_TRENDS = 3


def trends_svgs(trends: ClimateTrends) -> list[tuple[TrendMetric, str]]:
    by_key = {m.key: m for m in trends.metrics}
    picked = [by_key[k] for k in PDF_TREND_KEYS if k in by_key]
    if "critical_stress_days" in by_key:
        picked = [m for m in picked if m.key != "stress_days"]
    return [(m, svg) for m in picked[:PDF_TRENDS] if (svg := _trend_svg(m))]


def satellite_svg(sat: SatelliteSeries) -> str:
    if not sat.points:
        return ""
    w, h = 640.0, 150.0
    left, right, top, bottom = 36.0, 10.0, 14.0, 26.0
    pts = sat.points
    n = len(pts)
    slot = (w - left - right) / n

    def y(v: float) -> float:
        return float(top + (h - top - bottom) * (1 - v))

    body = _y_axis(left, w - right, top, h - bottom, 1.0)
    if sat.history_min is not None and sat.history_max is not None:
        body += f'<rect x="{left}" y="{y(sat.history_max):.1f}" width="{w - left - right}" height="{y(sat.history_min) - y(sat.history_max):.1f}" fill="{LIGHT_BLUE}" fill-opacity="0.5"/>'
    if sat.history_median is not None:
        body += f'<line x1="{left}" x2="{w - right}" y1="{y(sat.history_median):.1f}" y2="{y(sat.history_median):.1f}" stroke="{BLUE}" stroke-dasharray="5 4"/>'
    for i, p in enumerate(pts):
        cx = left + (i + 0.5) * slot
        body += f'<circle cx="{cx:.1f}" cy="{y(min(1.0, max(0.0, p.ndvi))):.1f}" r="{5 if p.current else 3.5}" fill="{ORANGE if p.current else DARK_BLUE}"/>'
        body += f'<text x="{cx:.1f}" y="{h - 10}" text-anchor="middle" fill="{TEXT}" font-size="9">{p.year if not p.current else "teraz"}</text>'
    body += f'<text x="{left}" y="10" fill="{TEXT}">kondycja roślin (0 — brak zieleni, 1 — bujna zieleń); pas: zakres z poprzednich lat</text>'
    return _svg(w, h, body, sat.text_pl)
