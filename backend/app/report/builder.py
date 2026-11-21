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
from app.analysis.context import VEGETATION_END, VEGETATION_START, AnalysisInputs, computed_source
from app.analysis.history import RISK_FREQUENCY, HistoryMethod
from app.analysis.series import Weather, same_day_in_year
from app.core.config import APP_TITLE, APP_VERSION, HISTORY_YEARS
from app.core.models import Confidence, Indicator, SourceResult, SourceStatus, Uncertainty
from app.crops.catalog import month_day
from app.crops.iung import iung_threshold
from app.recommendations.irrigation import IrrigationAdvice
from app.recommendations.models import Category, Recommendation
from app.report import labels_pl as L
from app.report.models import (
    SECTION_ORDER,
    ChartPoint,
    EvidenceItem,
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
    SeasonChart,
    SectionId,
    SourceEntry,
)
from app.report.texts import num, render_line, render_text, years_pl
from app.sources import uldk

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


def format_value(key: str, value: float | None, unit: str) -> str:
    if value is None:
        return "brak danych"
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
    if a.current is not None and a.current.iung_threshold_used and soil is not None and soil.category:
        threshold = iung_threshold(crop.id, soil.category.value, day)
        if threshold is not None:
            iung = {"critical_mm": threshold[1], "citation": threshold[2], "period_end": threshold[0]}
    by_cat = {cat: [r for r in recs if r.category is cat] for cat in Category}
    landcover = inputs.landcover.data
    return {
        "complete": a.complete,
        "incomplete_reason": a.incomplete_reason_pl,
        "crop": crop.name_pl.lower(),
        "crop_name": crop.name_pl,
        "crop_id": crop.id,
        "grassland": crop.id == "grassland",
        "winter_crop": crop.winter,
        "root_depth_m": crop.root_depth_m,
        "day": day,
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
            "soc": soil.topsoil_soc_g_per_kg,
        },
        "terrain": None
        if terrain is None
        else {
            "slope_mean_pct": terrain.slope_mean_pct,
            "slope_max_pct": terrain.slope_max_pct,
            "aspect_pl": L.COMPASS_FROM_PL.get(terrain.aspect or ""),
            "depressions": len(terrain.depressions),
            "flow_paths": len(terrain.flow_paths),
            "fine": terrain.dataset == "gugik_nmt",
        },
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
        "recs": recs,
        "recs_retention": by_cat[Category.RETENTION],
        "recs_agrotech": by_cat[Category.AGROTECH],
        "recs_irrigation": by_cat[Category.IRRIGATION],
        "irrigation": irrigation,
        "statuses": {k: v.value for k, v in a.source_status.items()},
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
                title_pl=L.SECTION_TITLES[sid],
                paragraphs_pl=main,
                details_pl=details,
                indicators=_section_indicators(a, sid),
                recommendation_numbers=numbers.get(sid, []),
            )
        )
    return out


# --- sources, missing data, limitations ---------------------------------------------------------------


def _source_results(inputs: AnalysisInputs) -> list[SourceResult[Any]]:
    return [inputs.weather, inputs.sentinel2, inputs.soil, inputs.dem, inputs.hydro, inputs.landcover]


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


# --- map --------------------------------------------------------------------------------------------


def _map(inputs: AnalysisInputs, a: Assessment, recs: list[Recommendation]) -> ReportMap:
    features: list[MapFeature] = []

    def add(kind: MapFeatureKind, geometry: dict[str, Any]) -> None:
        features.append(MapFeature(kind=kind, label_pl=L.MAP_LEGEND[kind], geometry=geometry))

    if a.terrain is not None:
        for site in a.terrain.depressions:
            add("depression", site.geometry)
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


# --- entry point ------------------------------------------------------------------------------------


def _report_recommendation(r: Recommendation) -> ReportRecommendation:
    return ReportRecommendation(
        number=r.number,
        id=r.id,
        category=r.category,
        title_pl=r.title_pl,
        text_pl=r.text_pl,
        evidence=[evidence_item(i) for i in r.evidence],
        locations=r.locations,
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
    return Report(
        id=report_id,
        created_at=created_at,
        app=APP_TITLE,
        version=APP_VERSION,
        parcel=inputs.parcel,
        crop=ReportCrop(id=inputs.crop.id, name_pl=inputs.crop.name_pl),
        analysis_date=inputs.analysis_date,
        complete=assessment.complete,
        headline=ctx["headline"],
        sections=_sections(ctx, assessment, recs, sources, limitations, missing_data),
        recommendations=[_report_recommendation(r) for r in recs],
        irrigation=_irrigation(irrigation),
        months=_months(inputs, assessment),
        chart=_chart(inputs),
        map=_map(inputs, assessment, recs),
        sources=sources,
        limitations_pl=limitations,
        missing_data_pl=missing_data,
    )
