"""Report assembly (plan step M6.1): assessment + recommendations + irrigation → `Report`. Pure, no I/O.

Sections come in the mandatory order (CLAUDE.md rule 2): summary · water situation now ·
10-year vulnerability · causes · retention · field practices · irrigation · data sources ·
limitations and missing data.
All nine sections are always present; without a complete assessment the recommendation sections say why
they are empty instead of disappearing.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

from app.analysis.assessment import Assessment, CurrentState, StructuralVulnerability
from app.analysis.causes import Cause
from app.analysis.context import (
    VEGETATION_END,
    VEGETATION_START,
    AnalysisInputs,
    computed_source,
    landcover_surroundings,
    surroundings_nearest_m,
)
from app.analysis.farm import distance_m
from app.analysis.history import RISK_FREQUENCY, HistoryMethod
from app.analysis.retention_balance import RetentionCoverage, retention_coverage
from app.analysis.series import Weather, same_day_in_year
from app.analysis.terrain import is_main_depression, main_depressions
from app.core.config import APP_TITLE, APP_VERSION, HISTORY_YEARS
from app.core.models import Confidence, Indicator, SourceResult, SourceStatus, Uncertainty
from app.crops.catalog import month_day, next_sowing
from app.recommendations.irrigation import IrrigationAdvice
from app.recommendations.models import Category, Recommendation, RuleContext
from app.recommendations.retention_methods import METHOD_ORDER, WATER_LAW_PL, assess_methods
from app.report import labels_pl as L
from app.report.models import (
    SECTION_ORDER,
    ChartPoint,
    DailyWater,
    EvidenceItem,
    Farm,
    FarmParcel,
    Headline,
    HeadlineLevel,
    MapFeature,
    MapFeatureKind,
    MonthRisk,
    Report,
    ReportCrop,
    ReportIrrigation,
    ReportMap,
    ReportRecommendation,
    ReportSection,
    RetentionCoverageView,
    RetentionMethodView,
    RetentionPlan,
    SeasonChart,
    SectionId,
    SourceEntry,
    WaterPlan,
)
from app.report.outlook import build_outlook, flood_info, groundwater_info
from app.report.texts import date_dmy, first_sentence, num, render_line, render_text, years_pl
from app.sources import open_meteo, uldk
from app.sources.landcover import SURROUNDINGS_RADIUS_M

# Hydro features shown on the report map (the source covers 1 km; the map focuses on the surroundings).
MAP_FEATURE_RADIUS_M = 500.0
CHART_STEP_DAYS = 7
CHART_SEASON_START = (3, 1)  # 1 March
CHART_SEASON_END = (10, 31)
CHART_MIN_DAYS = 14
ROMAN = ["I", "II", "III", "IV"]


@dataclass(frozen=True)
class ParcelSource:
    """Provenance of the parcel geometry (ULDK is fetched before the other sources)."""

    fetched_at: datetime


# --- evidence ---------------------------------------------------------------------------------------


def indicator_label(key: str) -> str:
    if key in L.INDICATOR_LABELS:
        return L.INDICATOR_LABELS[key]
    if key.startswith(L.MONTH_INDICATOR_PREFIX):
        month = int(key.removeprefix(L.MONTH_INDICATOR_PREFIX)[:2])
        return L.MONTH_INDICATOR_LABEL.format(month=L.MONTHS_PL_NOMINATIVE[month])
    return key


def _step_for(value: float) -> float:
    """Indicators are already rounded by the analysis; keep their precision when formatting."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    decimals = len(text.partition(".")[2])
    return 10.0 ** -min(decimals, 2)


# Yes/no indicators (1 = present).
FLAG_KEYS = {"groundwater_flooding_risk", "flood_zone_risk"}


def format_value(key: str, value: float | None, unit: str) -> str:
    if value is None:
        return "brak danych"
    if key in FLAG_KEYS:
        return "tak" if value >= 1 else "nie"
    if key == "soil_category":
        idx = int(value) - 1
        return f"kategoria {ROMAN[idx]}" if 0 <= idx < len(ROMAN) else "brak danych"
    if unit == "lat":
        return years_pl(int(value))
    text = num(value, _step_for(value))
    if not unit:
        return text
    if unit in ("%", "°C"):
        return f"{text} {unit}" if unit == "%" else f"{text} °C"
    return f"{text} {unit}"


def evidence_item(ind: Indicator) -> EvidenceItem:
    return EvidenceItem(
        key=ind.key,
        label_pl=indicator_label(ind.key),
        value=ind.value,
        value_pl=format_value(ind.key, ind.value, ind.unit),
        unit=ind.unit,
        source=ind.source,
        period=ind.period,
        uncertainty=ind.uncertainty,
    )


def _all_indicators(a: Assessment) -> dict[str, Indicator]:
    pools: list[list[Indicator]] = []
    if a.current is not None:
        pools.append(a.current.indicators)
        if a.current.last_season is not None:
            pools.append(a.current.last_season.indicators)
        pools.append(a.current.satellite.indicators)
    pools += [c.evidence for c in a.causes]
    if a.vulnerability is not None:
        pools += [c.indicators for c in a.vulnerability.components]
    out: dict[str, Indicator] = {}
    for pool in pools:
        for ind in pool:
            if ind.value is not None:
                out.setdefault(ind.key, ind)
    return out


def _values(a: Assessment) -> dict[str, float]:
    return {k: i.value for k, i in _all_indicators(a).items() if i.value is not None}


# --- headline and summary ---------------------------------------------------------------------------


def _confidence_pl(u: Uncertainty) -> str:
    return f"Pewność oceny: {L.CONFIDENCE_LABELS[u.level.value]}. {u.reason_pl}"


def _headline(ctx: dict[str, Any], a: Assessment) -> Headline:
    if not a.complete or a.current is None:
        level: HeadlineLevel = "unknown"
        sentence = a.incomplete_reason_pl or L.LEVEL_LABELS["unknown"]
        conf = Confidence.LOW
        conf_pl = "Pewność oceny: niska — oceny nie wykonano."
    else:
        level = a.current.level.value
        sentence = render_line("headline.j2", **ctx)
        conf = a.uncertainty.level
        conf_pl = _confidence_pl(a.uncertainty)
    return Headline(
        level=level,
        label_pl=L.LEVEL_LABELS[level],
        sentence_pl=sentence,
        confidence=conf,
        confidence_pl=conf_pl,
    )


# --- template contexts ------------------------------------------------------------------------------


def _risk_months(a: Assessment) -> list[int]:
    return list(a.history.risk_months) if a.history is not None else []


def _deficit_years(a: Assessment) -> tuple[int | None, int]:
    h = a.history
    if h is None or h.deficit_year_share is None:
        return None, 0
    n = h.years_with_data
    return round(h.deficit_year_share * n), n


def _cause_view(c: Cause) -> dict[str, Any]:
    return {
        "id": c.id,
        "flagged": c.flagged,
        "v": {i.key: i.value for i in c.evidence if i.value is not None},
        "context": dict(c.context),
    }


def _current_view(cur: CurrentState) -> dict[str, Any]:
    sat = cur.satellite
    sat_values = {i.key: i.value for i in sat.indicators if i.value is not None}
    scene = next((i for i in sat.indicators if i.key == "ndvi_current" and i.period is not None), None)
    last = cur.last_season
    recharge = next((i for i in cur.indicators if i.key == "recharge_kbw_mm" and i.period is not None), None)
    return {
        "recharge_start": recharge.period.start if recharge is not None and recharge.period else None,
        "level": cur.level.value,
        "in_vegetation": cur.in_vegetation,
        "crop_on_field": cur.crop_on_field,
        "basis": list(cur.basis),
        "root_zone": "root_zone" in cur.basis,
        "iung_used": cur.iung_threshold_used,
        "satellite": sat.status,
        "sat": sat_values,
        "sat_date": scene.period.end if scene is not None and scene.period is not None else None,
        "last_season": None
        if last is None
        else {
            "year": last.year,
            "stress_days": last.stress_days,
            "stress_pct": last.stress_days_pct,
            "deficit_months": list(last.deficit_months),
        },
    }


def _vulnerability_view(v: StructuralVulnerability) -> dict[str, Any]:
    return {
        "level": v.level.value if v.level is not None else None,
        "level_pl": L.VULNERABILITY_LABELS[v.level.value] if v.level is not None else None,
        "score": v.score,
        "max_score": v.max_score,
        "components": {c.id: c.points for c in v.components},
        "unknown": [c.id for c in v.components if c.points is None],
        "unknown_pl": [L.VULNERABILITY_COMPONENTS_PL[c.id] for c in v.components if c.points is None],
    }


def _typical(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return median(present) if len(present) >= 5 else None


def _context(
    inputs: AnalysisInputs,
    a: Assessment,
    recs: list[Recommendation],
    irrigation: IrrigationAdvice,
) -> dict[str, Any]:
    crop = inputs.crop
    day = inputs.analysis_date
    v = _values(a)
    soil = a.soil
    terrain = a.terrain
    hydro = a.hydro
    history = a.history
    deficit_years, years_with_data = _deficit_years(a)
    critical = crop.critical_period_at(day)
    typical_p30 = _typical([y.precip_30d_mm for y in history.years]) if history is not None else None
    typical_p90 = _typical([y.precip_90d_mm for y in history.years]) if history is not None else None
    iung = None
    iung_missing = None
    if a.current is not None and a.current.iung is not None:
        t = a.current.iung
        iung = {
            "critical_mm": t.kbw_critical_mm,
            "below": a.current.iung_below,
            "period_start": t.period_start,
            "period_end": t.period_end,
            "group_pl": t.group_pl.lower(),
            "category": t.soil_category,
            "citation": t.citation,
            "url": t.url,
            "accessed": t.accessed,
        }
    elif a.current is not None and a.current.iung_missing is not None:
        iung_missing = a.current.iung_missing.value
    by_cat = {cat: [r for r in recs if r.category is cat] for cat in Category}
    landcover = inputs.landcover.data
    return {
        "complete": a.complete,
        "incomplete_reason": a.incomplete_reason_pl,
        "crop": crop.name_pl.lower(),
        "crop_name": crop.name_pl,
        "crop_id": crop.id,
        "grassland": crop.is_grassland,
        "fruit": crop.is_fruit,
        "winter_crop": crop.winter,
        "root_depth_m": crop.root_depth_m,
        "day": day,
        "phase": crop.field_phase(day),
        "harvest_day": crop.season_end(day) - timedelta(days=1),
        "sowing_day": next_sowing(crop, day),
        "parcel": inputs.parcel,
        "season_start": month_day(VEGETATION_START, day.year),
        "season_end": month_day(VEGETATION_END, day.year),
        "v": v,
        "typical_p30": typical_p30,
        "typical_p90": typical_p90,
        "current": _current_view(a.current) if a.current is not None else None,
        "vuln": _vulnerability_view(a.vulnerability) if a.vulnerability is not None else None,
        "causes": [_cause_view(c) for c in a.causes],
        "soil": None
        if soil is None
        else {
            "category": soil.category.value if soil.category else None,
            "category_pl": L.SOIL_CATEGORY_PL[soil.category.value] if soil.category else None,
            "texture_pl": L.TEXTURE_PL[soil.texture.value] if soil.texture else None,
            "taw_mm": soil.taw_mm,
            "taw_per_m_mm": soil.taw_per_m_mm,
            "soc": soil.topsoil_soc_g_per_kg,
        },
        "terrain": None
        if terrain is None
        else {
            "slope_mean_pct": terrain.slope_mean_pct,
            "slope_max_pct": terrain.slope_max_pct,
            "aspect_pl": L.COMPASS_FROM_PL.get(terrain.aspect or ""),
            "depressions": len(main_depressions(terrain)),
            "depressions_minor": len(terrain.depressions) - len(main_depressions(terrain)),
            "flow_paths": len(terrain.flow_paths),
            "fine": terrain.dataset == "gugik_nmt",
        },
        "surroundings": _surroundings_view(inputs),
        "hydro": None
        if hydro is None
        else {
            "radius_m": hydro.radius_m,
            "counts": dict(hydro.counts),
            "nearest": {k: d for k, d in hydro.nearest_m.items() if d is not None},
            "ditch_boundary_m": hydro.ditch_length_along_boundary_m,
        },
        "history_method": history.method.value if history is not None else None,
        "history_root_zone": history is not None and history.method is HistoryMethod.ROOT_ZONE,
        "deficit_years": deficit_years,
        "years_with_data": years_with_data,
        "risk_months": _risk_months(a),
        "critical_risk_months": list(history.critical_risk_months) if history is not None else [],
        "critical_months": sorted(crop.critical_months()),
        "critical_now": critical.name_pl if critical is not None else None,
        "iung": iung,
        "iung_missing": iung_missing,
        "recs": recs,
        "recs_retention": by_cat[Category.RETENTION],
        "recs_agrotech": by_cat[Category.AGROTECH],
        "recs_irrigation": by_cat[Category.IRRIGATION],
        "irrigation": irrigation,
        "statuses": {k: v.value for k, v in a.source_status.items()},
        "weather_from_power": inputs.weather.data is not None
        and open_meteo.SOURCE_POWER in inputs.weather.source,
        "landcover": None
        if landcover is None
        else {
            "looks_agricultural": landcover.looks_agricultural,
            "cropland_pct": landcover.cropland_pct,
            "grassland_pct": landcover.grassland_pct,
            "trees_pct": landcover.trees_pct,
            "built_up_pct": landcover.built_up_pct,
            "map_year": landcover.map_year,
        },
        "current_confidence_level_pl": L.CONFIDENCE_LABELS[a.current.uncertainty.level.value]
        if a.current is not None
        else None,
        "current_confidence": a.current.uncertainty.reason_pl if a.current is not None else None,
        "vuln_confidence_level_pl": L.CONFIDENCE_LABELS[a.vulnerability.uncertainty.level.value]
        if a.vulnerability is not None
        else None,
        "vuln_confidence": a.vulnerability.uncertainty.reason_pl if a.vulnerability is not None else None,
        "confidence": a.uncertainty,
        "confidence_pl": L.CONFIDENCE_LABELS[a.uncertainty.level.value],
        "history_years": HISTORY_YEARS,
        "risk_threshold_pct": round(100 * RISK_FREQUENCY),
    }


# --- sections ---------------------------------------------------------------------------------------


def _section_indicators(a: Assessment, section: SectionId) -> list[EvidenceItem]:
    if section == "current" and a.current is not None:
        inds = [*a.current.indicators, *a.current.satellite.indicators]
        if a.current.last_season is not None:
            inds += a.current.last_season.indicators
    elif section == "vulnerability" and a.vulnerability is not None:
        inds = [i for c in a.vulnerability.components for i in c.indicators]
    elif section == "causes":
        inds = [i for c in a.causes if c.flagged for i in c.evidence]
    else:
        return []
    seen: set[str] = set()
    out: list[EvidenceItem] = []
    for ind in inds:
        if ind.value is not None and ind.key not in seen:
            seen.add(ind.key)
            out.append(evidence_item(ind))
    return out


# Sections with a one-sentence verdict in the basic report (plan M3.2). The water situation itself is the
# headline above them, so "current" has none (its first paragraph is often an intro about the season).
VERDICT_SECTIONS = ("vulnerability", "causes")
LEAD_CLAUSE_MAX_CHARS = 70


def _verdict(sid: str, main: list[str], complete: bool, flagged_causes: int) -> str | None:
    if sid not in VERDICT_SECTIONS or not main or not complete:
        return None
    if sid == "causes" and flagged_causes:
        # The first paragraphs are the flagged causes, each starting with its lead clause ("Mało deszczu: …").
        leads = [
            p.split(": ", 1)[0] for p in main[:flagged_causes] if 0 < p.find(": ") <= LEAD_CLAUSE_MAX_CHARS
        ]
        if leads:
            joined = "; ".join([leads[0]] + [x[:1].lower() + x[1:] for x in leads[1:]])
            return f"{joined}."
    return first_sentence(main[0])


def _sections(
    ctx: dict[str, Any],
    a: Assessment,
    recs: list[Recommendation],
    sources: list[SourceEntry],
    limitations: list[str],
    missing_data: list[str],
) -> list[ReportSection]:
    out: list[ReportSection] = []
    numbers = {
        "retention": [r.number for r in recs if r.category is Category.RETENTION],
        "agrotech": [r.number for r in recs if r.category is Category.AGROTECH],
        "irrigation": [r.number for r in recs if r.category is Category.IRRIGATION],
    }
    for n, sid in enumerate(SECTION_ORDER, start=1):
        if sid == "sources":
            main, details = render_text("sections/sources.j2", sources=sources, **ctx)
        elif sid == "limitations":
            main, details = render_text(
                "sections/limitations.j2", limitations=limitations, missing_data=missing_data, **ctx
            )
        else:
            main, details = render_text(f"sections/{sid}.j2", **ctx)
        out.append(
            ReportSection(
                id=sid,
                number=n,
                title_pl=L.SECTION_TITLES[sid].format(date=date_dmy(ctx["day"])),
                paragraphs_pl=main,
                verdict_pl=_verdict(sid, main, ctx["complete"], sum(1 for c in a.causes if c.flagged)),
                details_pl=details,
                indicators=_section_indicators(a, sid),
                recommendation_numbers=numbers.get(sid, []),
            )
        )
    return out


# --- sources, missing data, limitations ---------------------------------------------------------------


def _source_results(inputs: AnalysisInputs) -> list[SourceResult[Any]]:
    out: list[SourceResult[Any]] = [
        inputs.weather,
        inputs.sentinel2,
        inputs.soil,
        inputs.dem,
        inputs.hydro,
        inputs.landcover,
    ]
    return out + [r for r in (inputs.flood, inputs.groundwater) if r is not None]


def _sources(inputs: AnalysisInputs, parcel_source: ParcelSource) -> list[SourceEntry]:
    entries = [
        SourceEntry(
            name=uldk.NAME,
            label_pl=L.SOURCE_LABELS[uldk.NAME],
            status=SourceStatus.OK,
            source=uldk.SOURCE,
            license=uldk.LICENSE,
            fetched_at=parcel_source.fetched_at,
            uncertainty=Uncertainty(
                level=Confidence.HIGH, reason_pl="Granice i powierzchnia działki z ewidencji gruntów."
            ),
        )
    ]
    for r in _source_results(inputs):
        entries.append(
            SourceEntry(
                name=r.name,
                label_pl=L.SOURCE_LABELS.get(r.name, r.name),
                status=r.status,
                source=r.source,
                license=r.license,
                fetched_at=r.fetched_at,
                period=r.period,
                uncertainty=r.uncertainty,
                message_pl=r.message_pl,
            )
        )
    return entries


def _surroundings_view(inputs: AnalysisInputs) -> dict[str, Any] | None:
    """WorldCover ring used in place of the OSM map (only when OSM is missing, Q4)."""
    s = landcover_surroundings(inputs)
    if s is None:
        return None
    return {
        "radius_m": s.radius_m,
        "nearest": {k: surroundings_nearest_m(s, k) for k in ("water_body", "wetland", "trees")},
        "trees_pct": s.shares_pct.get("trees", 0.0),
    }


def _missing_data(inputs: AnalysisInputs) -> list[str]:
    out: list[str] = []
    for r in _source_results(inputs):
        if r.status is SourceStatus.OK:
            continue
        line = render_line(
            f"missing/{r.name}.j2",
            status=r.status.value,
            message=r.message_pl or "",
            label=L.SOURCE_LABELS.get(r.name, r.name),
            landcover_fallback=r.name == "hydro" and landcover_surroundings(inputs) is not None,
            radius_m=SURROUNDINGS_RADIUS_M,
        )
        if line:
            out.append(line)
    return out


# Codes already explained per source in "missing data" (no duplicate sentence).
_COVERED_BY_MISSING = {
    "soil_missing",
    "satellite_missing",
    "terrain_missing",
    "hydro_missing",
    "landcover_missing",
    "weather_degraded",
    "satellite_degraded",
}


def _limitations(a: Assessment, ctx: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for code in a.limitations:
        if code in _COVERED_BY_MISSING:
            continue
        line = render_line("limitations.j2", code=code, **ctx)
        if line and line not in out:
            out.append(line)
    return out


# --- months table and chart -------------------------------------------------------------------------


def _months(inputs: AnalysisInputs, a: Assessment) -> list[MonthRisk]:
    h = a.history
    if h is None:
        return []
    critical = inputs.crop.critical_months()
    return [
        MonthRisk(
            month=f.month,
            month_pl=L.MONTHS_PL_NOMINATIVE[f.month].capitalize(),
            years_with_data=f.years_with_data,
            deficit_years=f.deficit_years,
            frequency_pct=None if f.frequency is None else round(100 * f.frequency),
            risk=f.frequency is not None and f.frequency >= RISK_FREQUENCY,
            critical=f.month in critical,
            severe_years=f.severe_years,
            mean_stress_days=None if f.mean_stress_days is None else round(f.mean_stress_days, 1),
        )
        for f in h.months
    ]


def _cumulative(
    weather: Weather, start: date, end: date, kc: Any
) -> tuple[list[float | None], list[float | None]]:
    """Running sums of P and Kc·ET0; a missing day ends the series (no gap filling)."""
    precip: list[float | None] = []
    need: list[float | None] = []
    p_sum: float | None = 0.0
    e_sum: float | None = 0.0
    d = start
    while d <= end:
        p, e = weather.p_et0(d)
        p_sum = None if p_sum is None or p is None else p_sum + p
        e_sum = None if e_sum is None or e is None else e_sum + kc(d) * e
        precip.append(p_sum)
        need.append(e_sum)
        d += timedelta(days=1)
    return precip, need


def _chart(inputs: AnalysisInputs) -> SeasonChart | None:
    data = inputs.weather.data
    if data is None:
        return None
    day = inputs.analysis_date
    weather = Weather.from_daily(data.daily, day)
    if not weather.dates:
        return None
    year = day.year if day.month >= CHART_SEASON_START[0] else day.year - 1
    start = date(year, *CHART_SEASON_START)
    end = min(day, date(year, *CHART_SEASON_END))
    if (end - start).days + 1 < CHART_MIN_DAYS or not weather.covers(start, end):
        return None
    crop = inputs.crop
    precip, need = _cumulative(weather, start, end, crop.kc)
    hist: list[list[float | None]] = []
    for k in range(1, HISTORY_YEARS + 1):
        s = same_day_in_year(start, year - k)
        e = same_day_in_year(end, year - k)
        if not weather.covers(s, e):
            continue
        series, _ = _cumulative(weather, s, e, crop.kc)
        if series and series[-1] is not None:
            hist.append(series)
    n = (end - start).days + 1
    offsets = sorted({*range(0, n, CHART_STEP_DAYS), n - 1})
    points: list[ChartPoint] = []
    for i in offsets:
        past = [s[i] for s in hist if i < len(s) and s[i] is not None]
        enough = len(past) >= 5
        points.append(
            ChartPoint(
                day=start + timedelta(days=i),
                precip_mm=_r(precip[i]),
                crop_need_mm=_r(need[i]),
                precip_hist_median_mm=_r(median(past)) if enough else None,
                precip_hist_min_mm=_r(min(past)) if enough else None,
                precip_hist_max_mm=_r(max(past)) if enough else None,
            )
        )
    return SeasonChart(
        start=start,
        end=end,
        years=len(hist),
        source=computed_source(inputs.weather.source),
        points=points,
    )


def _r(value: float | None) -> float | None:
    return None if value is None else round(value)


def _water_daily(inputs: AnalysisInputs) -> DailyWater | None:
    """Daily rain and ETc for the range-selectable water chart (0.1 mm: sums stay exact to 1 mm)."""
    data = inputs.weather.data
    if data is None:
        return None
    weather = Weather.from_daily(data.daily, inputs.analysis_date)
    if not weather.dates:
        return None
    precip: list[float | None] = []
    need: list[float | None] = []
    d = weather.first
    while d <= weather.last:
        p, e = weather.p_et0(d)
        precip.append(None if p is None else round(p, 1))
        need.append(None if e is None else round(inputs.crop.kc(d) * e, 1))
        d += timedelta(days=1)
    # Trailing days without rain data (e.g. recent days the forecast did not deliver) are cut, so the
    # ranges ending "now" end on the last day with data instead of showing no line at all.
    while precip and precip[-1] is None:
        precip.pop()
        need.pop()
    if not precip:
        return None
    source = computed_source(inputs.weather.source)
    return DailyWater(start=weather.first, precip_mm=precip, crop_need_mm=need, source=source)


# --- map --------------------------------------------------------------------------------------------


def _map(inputs: AnalysisInputs, a: Assessment, recs: list[Recommendation]) -> ReportMap:
    features: list[MapFeature] = []

    def add(kind: MapFeatureKind, geometry: dict[str, Any]) -> None:
        features.append(MapFeature(kind=kind, label_pl=L.MAP_LEGEND[kind], geometry=geometry))

    if a.terrain is not None:
        for site in a.terrain.depressions:
            add("depression" if is_main_depression(site) else "depression_minor", site.geometry)
        for site in a.terrain.flow_paths:
            add("flow_path", site.geometry)
        for outlet in a.terrain.outlets:
            add("outlet", outlet.geometry)
    if a.hydro is not None:
        for f in a.hydro.features:
            if f.distance_m <= MAP_FEATURE_RADIUS_M:
                add(f.kind, f.geometry)
    # Link every recommendation location to its map feature (plan step M7.4); add it when not listed yet.
    for rec in recs:
        for loc in rec.locations:
            match = next((f for f in features if f.kind == loc.kind and f.geometry == loc.geometry), None)
            if match is None:
                add(loc.kind, loc.geometry)
                match = features[-1]
            if rec.number not in match.recommendation_numbers:
                match.recommendation_numbers.append(rec.number)
    kinds = {f.kind for f in features}
    legend = {k: v for k, v in L.MAP_LEGEND.items() if k in kinds}
    return ReportMap(parcel=inputs.parcel.geometry, features=features, legend_pl=legend)


# --- retention methods (G9) -------------------------------------------------------------------------


def _coverage_view(c: RetentionCoverage, inputs: AnalysisInputs, drip: bool = False) -> RetentionCoverageView:
    return RetentionCoverageView(
        status=c.status.value,
        volume_m3=c.volume_m3,
        full_need_m3=c.full_need_m3,
        rescue_need_m3=c.rescue_need_m3,
        full_pct=c.full_pct,
        rescue_pct=c.rescue_pct,
        text_pl=render_line("blocks/retention_coverage.j2", c=c, drip=drip, farm_n=inputs.farm_parcels),
        source=computed_source(inputs.dem.source, inputs.weather.source, inputs.soil.source),
    )


def _retention_plan(
    inputs: AnalysisInputs, assessment: Assessment, plan: WaterPlan | None
) -> RetentionPlan | None:
    """Coverage card and the five methods; only after a complete assessment (rule 2)."""
    if not assessment.complete or assessment.current is None:
        return None
    full = plan.season_p80_m3_parcel_gross if plan is not None else None
    if plan is not None and plan.season_p80_mm is not None and plan.season_p80_mm < 1:
        full = 0.0  # the plan says no irrigation needed even in a dry year
    rescue = plan.critical_p80_m3_parcel_gross if plan is not None else None
    coverage = retention_coverage(assessment.terrain, full, rescue)
    methods = assess_methods(RuleContext(assessment=assessment, inputs=inputs), coverage)
    order = {mid: i for i, mid in enumerate(METHOD_ORDER)}
    views = [
        RetentionMethodView(
            id=m.id,
            label_pl=L.RETENTION_METHOD_LABELS[m.id],
            status=m.status.value,
            status_pl=L.RETENTION_STATUS_LABELS[m.status.value],
            reason_pl=render_line("blocks/retention_method.j2", m=m, farm_n=inputs.farm_parcels),
            legal_pl=render_line("blocks/retention_permit.j2", m=m, farm_n=inputs.farm_parcels) or None,
            evidence=[evidence_item(i) for i in m.evidence],
        )
        for m in sorted(methods, key=lambda m: order[m.id])
    ]
    return RetentionPlan(
        coverage=_coverage_view(coverage, inputs, drip=plan is not None and plan.technology == "drip"),
        methods=views,
        legal_basis_pl=WATER_LAW_PL,
    )


# --- farm mode (G11) --------------------------------------------------------------------------------


def _farm(inputs: AnalysisInputs) -> Farm | None:
    """None for a single parcel, so a one-parcel report is exactly what it was before G11."""
    if not inputs.extra_parcels:
        return None
    n = inputs.farm_parcels
    total = inputs.water_area_ha
    main, _ = render_text("blocks/farm.j2", n=n, total_ha=total, main_ha=inputs.parcel.area_ha)
    return Farm(
        count=n,
        total_area_ha=round(total, 4),
        parcels=[
            FarmParcel(
                id=p.id,
                number=p.number,
                precinct=p.precinct,
                commune=p.commune,
                area_ha=p.area_ha,
                distance_m=_r_distance(distance_m(inputs.parcel, p)),
                geometry=p.geometry,
            )
            for p in inputs.extra_parcels
        ],
        text_pl=main,
        source=uldk.SOURCE,
    )


def _r_distance(d: float | None) -> float | None:
    if d is None:
        return None
    return 0.0 if d < 1 else float(round(d, -1 if d >= 100 else 0))


# --- entry point ------------------------------------------------------------------------------------


def _report_recommendation(r: Recommendation) -> ReportRecommendation:
    return ReportRecommendation(
        number=r.number,
        id=r.id,
        category=r.category,
        title_pl=r.title_pl,
        text_pl=r.text_pl,
        summary_pl=first_sentence(r.text_pl),
        evidence=[evidence_item(i) for i in r.evidence],
        locations=r.locations,
        horizon=r.horizon,
    )


def _irrigation(advice: IrrigationAdvice) -> ReportIrrigation:
    return ReportIrrigation(
        status=advice.status,
        applicable=advice.applicable,
        title_pl=advice.title_pl,
        text_pl=advice.text_pl,
        caveats_pl=advice.caveats_pl,
        dose_mm=advice.dose_mm,
        single_dose_max_mm=advice.single_dose_max_mm,
        applications=advice.applications,
        single_dose_mm=advice.single_dose_mm,
        volume_m3=advice.volume_m3,
        within_days=advice.within_days,
        irrigate_by=advice.irrigate_by,
        forecast=advice.forecast,
        projection=advice.projection,
        evidence=[evidence_item(i) for i in advice.evidence if i.value is not None],
    )


def build_report(
    *,
    report_id: str,
    created_at: datetime,
    inputs: AnalysisInputs,
    assessment: Assessment,
    recommendations: list[Recommendation],
    irrigation: IrrigationAdvice,
    parcel_source: ParcelSource,
) -> Report:
    # Rule 2: no recommendations without a complete assessment, whatever the caller passed.
    recs = recommendations if assessment.complete and assessment.current is not None else []
    ctx = _context(inputs, assessment, recs, irrigation)
    sources = _sources(inputs, parcel_source)
    missing_data = _missing_data(inputs)
    limitations = _limitations(assessment, ctx)
    ctx["headline"] = _headline(ctx, assessment)
    ctx["created_at"] = created_at
    flood = flood_info(inputs.flood, inputs.parcel.geometry)
    outlook = build_outlook(inputs, assessment, recs, irrigation, flood)
    ctx["outlook"] = outlook
    return Report(
        id=report_id,
        created_at=created_at,
        app=APP_TITLE,
        version=APP_VERSION,
        parcel=inputs.parcel,
        farm=_farm(inputs),
        crop=ReportCrop(id=inputs.crop.id, name_pl=inputs.crop.name_pl),
        analysis_date=inputs.analysis_date,
        complete=assessment.complete,
        headline=ctx["headline"],
        sections=_sections(ctx, assessment, recs, sources, limitations, missing_data),
        recommendations=[_report_recommendation(r) for r in recs],
        irrigation=_irrigation(irrigation),
        months=_months(inputs, assessment),
        chart=_chart(inputs),
        water_daily=_water_daily(inputs),
        summary_tiles=outlook.tiles if assessment.complete else [],
        stress_heatmap=outlook.heatmap,
        trends=outlook.trends,
        water_plan=outlook.water_plan if assessment.complete else None,
        retention_plan=_retention_plan(inputs, assessment, outlook.water_plan),
        irrigation_economics=outlook.irrigation_economics if assessment.complete else None,
        profile=outlook.profile,
        simulation=outlook.simulation if assessment.complete else None,
        satellite=outlook.satellite,
        flood=flood,
        groundwater=groundwater_info(inputs.groundwater),
        map=_map(inputs, assessment, recs),
        sources=sources,
        limitations_pl=limitations,
        missing_data_pl=missing_data,
    )
