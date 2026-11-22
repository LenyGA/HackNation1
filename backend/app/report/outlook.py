"""Report blocks beyond the nine sections (pure, no I/O): summary tiles, stress heat map, climate trends,
seasonal water plan, slope profile and the 1–5 year strategy simulator. Texts come from templates/blocks/.
"""

import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from shapely.geometry import Point, shape

from app.analysis.assessment import Assessment
from app.analysis.context import AnalysisInputs, computed_source
from app.analysis.history import MIN_YEARS_FOR_PERCENTILE, TABLE_MONTHS, HistoryMethod
from app.analysis.profile import ProfilePoint as ProfileResultPoint
from app.analysis.profile import SlopeProfile as ProfileResult
from app.analysis.profile import slope_profile
from app.analysis.series import Weather
from app.analysis.simulate import SimulationResult, simulate
from app.analysis.terrain import TerrainResult, main_depressions
from app.analysis.trends import Direction, RecentChange, TrendResult, analyse_trends
from app.analysis.water_plan import WaterPlanResult, water_plan
from app.core.models import Period, SourceResult
from app.recommendations.irrigation import IrrigationAdvice, single_dose_max_mm
from app.recommendations.irrigation_tech import TechChoice
from app.recommendations.models import Category, Horizon, Recommendation
from app.recommendations.retention_methods import POND_NOTIFICATION_MAX_AREA_M2
from app.recommendations.texts_pl import farm_where_pl
from app.report import labels_pl as L
from app.report.irrigation_economics import economics_view, technology_for
from app.report.models import (
    ClimateTrends,
    FloodInfo,
    FloodZone,
    Gauge,
    GroundwaterInfo,
    IrrigationEconomicsView,
    ProfilePoint,
    SatellitePoint,
    SatelliteSeries,
    Simulation,
    SlopeProfile,
    Strategy,
    StrategyYear,
    StressHeatmap,
    StressRow,
    SummaryTile,
    TileStatus,
    TrendLevel,
    TrendMetric,
    TrendYear,
    WaterPlan,
    WaterPlanMonth,
)
from app.report.texts import date_dmy, num, plural, render_line, render_text
from app.sources.base import METRIC_CRS, parcel_shape, to_crs
from app.sources.flood import MZP_LAYER, MZP_WMS, FloodData
from app.sources.groundwater import GroundwaterData

POND_DEPTH_M = 2.0
# Field application efficiency of sprinkler irrigation ≈ 75 % (Brouwer et al. 1989, FAO Irrigation Water
# Management Training Manual 4): gross water = net need / 0.75 (wind drift, evaporation, uneven spread).
# Used when no technology was chosen; otherwise the chosen method's efficiency (G10, irrigation_tech.py).
SPRINKLER_EFFICIENCY = 0.75
TREND_LABELS: dict[str, str] = {
    "kbw_mm": "Opad minus parowanie w sezonie",
    "critical_stress_days": "Dni stresu wodnego w miesiącach ważnych dla uprawy",
    "stress_days": "Dni stresu wodnego uprawy w sezonie",
    "tmean_c": "Średnia temperatura sezonu",
    "hot_days": "Dni upalne (≥ 30 °C)",
    "et0_mm": "Parowanie w sezonie",
}
TREND_LEVEL_LABELS: dict[TrendLevel, str] = {
    "critical": "Ostatnie lata wyraźnie gorsze",
    "worse": "Sytuacja się pogarsza",
    "stable": "Bez wyraźnej zmiany",
    "better": "Sytuacja się poprawia",
    "unknown": "Brak danych",
}
STRATEGY_TEXTS: dict[str, tuple[str, str]] = {
    "none": ("Bez działań", "Bez nawadniania i bez zmian w uprawie."),
    "rescue": (
        "Podlewanie ratunkowe",
        "Woda tylko w okresach, gdy uprawa najbardziej jej potrzebuje, i tylko gdy gleba przeschła.",
    ),
    "full": (
        "Pełne nawadnianie",
        "Podlewanie przez cały sezon, gdy tylko gleba przeschnie — pod maksymalny plon.",
    ),
    "retention": (
        "Budowanie retencji gleby",
        "Międzyplony, resztki pożniwne jako ściółka i mniej orki — bez nawadniania.",
    ),
    "retention_rescue": (
        "Retencja + podlewanie ratunkowe",
        "Budowanie retencji gleby i woda tylko w okresach krytycznych.",
    ),
}
# Orchards and fruit bushes (plan33 M6): same model, practices named for an orchard
# (no catch crops or ploughing).
STRATEGY_TEXTS_FRUIT: dict[str, str] = {
    "none": "Bez nawadniania i bez zmian w pielęgnacji sadu.",
    "retention": (
        "Ściółka w pasie rzędów, kompost pod rzędy i zwarta murawa w międzyrzędziach — bez nawadniania."
    ),
}
SIM_ASSUMPTIONS_FRUIT: dict[int, str] = {
    2: (
        "Przyrost węgla organicznego z kompostu i ściółki przyjęto taki jak dla roślin okrywowych "
        "na gruntach ornych: 0,32 t C/ha rocznie (Poeplau i Don 2015) — dla sadu to przybliżenie. "
        "Przeliczamy go na zapas wody tymi samymi wzorami co ocena gleby (Saxton i Rawls 2006). "
        "Wpływ próchnicy na zapas wody jest niewielki (Minasny i McBratney 2018)."
    ),
    3: (
        "Ściółka w pasie rzędów na ok. połowie powierzchni ogranicza parowanie z gleby o ok. 25 % "
        "(FAO-56, rozdz. 11): w pełni przed rozwojem liści, coraz mniej w miarę rozwoju koron, a wcale "
        "przy pełnym ulistnieniu. To szacunek z typowego kalendarza sadu, nie z pomiaru."
    ),
}
SIM_ASSUMPTIONS: list[str] = [
    "Możliwa pogoda w kolejnych latach to pogoda z ostatnich 10 sezonów tej działki, z parowaniem zmienionym "
    "zgodnie z trendem z tych lat; opadów nie zmieniamy, bo 10 lat to za mało na wiarygodny trend deszczu.",
    "Każdy symulowany sezon zaczyna się 1 października od takiego zapasu wody w glebie, "
    "jaki był wtedy naprawdę w danym roku — także po suchych jesieniach, "
    "gdy zima nie uzupełniła gleby do pełna.",
    "Przyrost węgla organicznego z międzyplonów: 0,32 t C/ha rocznie (Poeplau i Don 2015), przeliczony na "
    "zapas wody tymi samymi wzorami co ocena gleby (Saxton i Rawls 2006). Wpływ próchnicy na zapas wody jest "
    "niewielki (Minasny i McBratney 2018).",
    "Ściółka z resztek na ok. połowie powierzchni ogranicza parowanie z gleby o ok. 25 % "
    "(FAO-56, rozdz. 11): w pełni, gdy gleba jest odkryta, coraz mniej w miarę zakrywania pola przez uprawę, "
    "a wcale pod pełnym łanem. To szacunek: pokrycie pola wyznaczamy z krzywej rozwoju uprawy, "
    "nie z pomiaru.",
    "„Retencja + podlewanie ratunkowe” podlewa w te same dni co samo podlewanie ratunkowe, ale każda dawka "
    "jest mniejsza o wodę, którą zatrzymała gleba — dołożenie retencji nigdy nie pogarsza wyniku.",
    "„Rok suchy” to sezon, który wśród 10 symulowanych jest gorszy od 8 z nich "
    "(zdarza się mniej więcej raz na 5 lat).",
    "To porównanie strategii, a nie prognoza pogody: pokazuje kierunek i skalę różnic.",
]


@dataclass(frozen=True)
class Outlook:
    tiles: list[SummaryTile]
    heatmap: StressHeatmap | None
    trends: ClimateTrends | None
    water_plan: WaterPlan | None
    profile: SlopeProfile | None
    simulation: Simulation | None
    satellite: SatelliteSeries | None
    irrigation_economics: IrrigationEconomicsView | None = None


# Seasonal water amounts (plan, simulator, tiles) are rounded once, here, to this step (Q2/T3): the page, the
# PDF and every sentence then show the same number. Single irrigation doses keep 1 mm (irrigation.py).
SEASON_WATER_STEP_MM = 5.0


def _r(value: float | None, step: float = 1.0) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(round(value / step) * step, 2)


# --- heat map ---------------------------------------------------------------------------------------


def _heatmap(a: Assessment, source: str) -> StressHeatmap | None:
    h = a.history
    if h is None or h.method is not HistoryMethod.ROOT_ZONE:
        return None
    months = [m for m in TABLE_MONTHS if any(m in y.months for y in h.years)]
    if not months:
        return None
    rows: list[StressRow] = []
    for y in h.years:
        if not any(o.stress_days is not None for o in y.months.values()):
            continue
        rows.append(
            StressRow(
                year=y.year,
                stress_days=[y.months[m].stress_days if m in y.months else None for m in months],
                season_days=[y.months[m].in_season_days if m in y.months else None for m in months],
            )
        )
    if not rows:
        return None
    return StressHeatmap(
        months=months,
        months_pl=[L.MONTHS_PL_NOMINATIVE[m].capitalize() for m in months],
        rows=rows,
        source=source,
    )


# --- trends -----------------------------------------------------------------------------------------


def _metric_view(t: TrendResult, key: str) -> dict[str, Any] | None:
    m = t.get(key)
    if m is None or m.mean_all is None:
        return None
    return {
        "slope": m.slope_per_decade,
        "direction": m.direction.value if m.direction else None,
        "recent": m.recent.value if m.recent else None,
        "mean_all": m.mean_all,
        "mean_mid": m.mean_mid,
        "mean_recent": m.mean_recent,
    }


# The verdict follows one water metric, named in the text: crop stress days when soil data exist (they combine
# rain, evaporation and the soil's store), otherwise the climatic water balance.
PRIMARY_TREND_KEYS = ("critical_stress_days", "stress_days", "kbw_mm")
PRIMARY_TREND_NAMES = {
    "critical_stress_days": "liczba dni, gdy uprawie brakowało wody w miesiącach dla niej ważnych",
    "stress_days": "liczba dni, gdy uprawie brakowało wody",
    "kbw_mm": "bilans deszczu i parowania w sezonie",
}


def _trend_level(t: TrendResult) -> tuple[TrendLevel, str | None, str | None, bool, str | None]:
    """(level, long-term direction, recent change, recent worse?, key) of the primary metric."""
    primary = next(
        (k for k in PRIMARY_TREND_KEYS if (m := t.get(k)) is not None and m.mean_all is not None), None
    )
    if primary is None:
        return "unknown", None, None, False, None
    m = t.get(primary)
    assert m is not None
    long_dir = m.direction.value if m.direction is not None else None
    recent = m.recent.value if m.recent is not None else None
    recent_worse = m.recent in (RecentChange.WORSE, RecentChange.CRITICAL)
    level: TrendLevel
    if m.recent is RecentChange.CRITICAL:
        level = "critical"
    elif m.direction is Direction.WORSE or recent_worse:
        level = "worse"
    elif m.direction is Direction.BETTER:
        level = "better"
    else:
        level = "stable"
    return level, long_dir, recent, recent_worse, primary


def _trend_summary(key: str, values: dict[str, Any]) -> str:
    unit = {"tmean_c": "°C", "hot_days": "dni", "stress_days": "dni", "critical_stress_days": "dni"}.get(
        key, "mm"
    )
    step = 0.1 if key == "tmean_c" else 1.0
    parts = [
        f"średnio {num(values['mean_all'], step)} {unit}",
        f"ostatnie 3 lata {num(values['mean_mid'], step)} {unit}",
        f"ostatnie 2 lata {num(values['mean_recent'], step)} {unit}",
    ]
    if values["slope"] is not None and values["direction"] in ("worse", "better"):
        sign = "+" if values["slope"] > 0 else "−" if values["slope"] < 0 else ""
        parts.append(f"trend {sign}{num(abs(values['slope']), step)} {unit} na dekadę")
    return "; ".join(parts)


def _trends(t: TrendResult | None, inputs: AnalysisInputs) -> ClimateTrends | None:
    if t is None:
        return None
    views = {k: v for k in TREND_LABELS if (v := _metric_view(t, k)) is not None}
    if not views:
        return None
    level, long_dir, crit_recent, recent_worse, primary = _trend_level(t)
    crop = inputs.crop
    main, _ = render_text(
        "blocks/trends.j2",
        m=views,
        n=len(t.seasons),
        crop=crop.name_pl.lower(),
        critical_months=sorted(crop.critical_months() & set(range(4, 10))),
        level=level,
        water_direction=long_dir,
        crit_recent=crit_recent,
        recent_worse=recent_worse,
        primary_pl=PRIMARY_TREND_NAMES.get(primary or "", ""),
        primary_is_crit=primary == "critical_stress_days",
    )
    metrics: list[TrendMetric] = []
    for key, label in TREND_LABELS.items():
        m = t.get(key)
        if m is None or key not in views:
            continue
        step = 0.1 if key == "tmean_c" else 1.0
        metrics.append(
            TrendMetric(
                key=key,
                label_pl=label,
                unit=m.unit,
                values=[TrendYear(year=y, value=_r(v, step)) for y, v in zip(m.years, m.values, strict=True)],
                mean_all=_r(m.mean_all, step),
                mean_mid=_r(m.mean_mid, step),
                mean_recent=_r(m.mean_recent, step),
                slope_per_decade=_r(m.slope_per_decade, step),
                direction=m.direction.value if m.direction else None,
                recent=m.recent.value if m.recent else None,
                summary_pl=_trend_summary(key, views[key]),
            )
        )
    sources = [inputs.weather.source] + ([inputs.soil.source] if "stress_days" in views else [])
    return ClimateTrends(
        seasons=t.seasons,
        level=level,
        label_pl=TREND_LEVEL_LABELS[level],
        verdict_pl=main,
        metrics=metrics,
        source=computed_source(*sources),
        uncertainty_pl=(
            f"Trend z {len(t.seasons)} sezonów jest orientacyjny — jeden skrajny rok mocno go zmienia. "
            "Liczymy go metodą odporną na pojedyncze skrajne lata (mediana nachyleń, Theil–Sen); "
            "„ostatnie lata gorsze” oznacza odchylenie od średniej o co najmniej pół (wyraźnie: jedno) "
            "odchylenie standardowe z tych lat."
        ),
    )


# --- water plan -------------------------------------------------------------------------------------


def _water_plan(
    p: WaterPlanResult | None, inputs: AnalysisInputs, tech: TechChoice | None = None
) -> WaterPlan | None:
    if p is None or p.season_median_mm is None:
        return None
    efficiency = tech.efficiency if tech is not None else SPRINKLER_EFFICIENCY
    area = inputs.water_area_ha
    season_p80 = _r(p.season_p80_mm, SEASON_WATER_STEP_MM)
    p80_m3 = _r(season_p80 * area * 10, 10) if season_p80 is not None and area else None
    gross_m3 = _r(p80_m3 / efficiency, 10) if p80_m3 is not None else None
    # Rescue irrigation (critical periods only), rounded the same way as the full need (Q2, G9).
    critical = _r(p.critical_p80_mm, SEASON_WATER_STEP_MM)
    critical_m3 = _r(critical * area * 10, 10) if critical is not None and area else None
    critical_gross = _r(critical_m3 / efficiency, 10) if critical_m3 is not None else None
    pond = None
    if gross_m3 is not None and gross_m3 >= 50:
        pond = _r(math.sqrt(gross_m3 / POND_DEPTH_M), 1)
    months = [
        WaterPlanMonth(
            month=m.month,
            month_pl=L.MONTHS_PL_NOMINATIVE[m.month].capitalize(),
            years=m.years,
            crop_need_mm=_r(m.etc_median_mm),
            precip_mm=_r(m.precip_median_mm),
            deficit_median_mm=_r(m.need_median_mm),
            deficit_p80_mm=_r(m.need_p80_mm),
            deficit_p90_mm=_r(m.need_p90_mm),
            deficit_p80_m3_ha=_r(m.need_p80_mm * 10, 10) if m.need_p80_mm is not None else None,
            critical=m.critical,
        )
        for m in p.months
    ]
    ranked = sorted(
        (m for m in months if (m.deficit_p80_mm or 0) >= 5), key=lambda m: -(m.deficit_p80_mm or 0)
    )
    top = sorted(m.month for m in ranked[:3])
    view = WaterPlan(
        method=p.method.value,
        years=len(p.years),
        months=months,
        season_median_mm=_r(p.season_median_mm, SEASON_WATER_STEP_MM),
        season_p80_mm=_r(p.season_p80_mm, SEASON_WATER_STEP_MM),
        season_p90_mm=_r(p.season_p90_mm, SEASON_WATER_STEP_MM),
        season_p80_m3_parcel=p80_m3,
        season_p80_m3_parcel_gross=gross_m3,
        efficiency_pct=round(100 * efficiency),
        technology=tech.tech if tech is not None else "reel",
        critical_p80_mm=critical,
        critical_p80_m3_parcel_gross=critical_gross,
        pond_side_m=pond,
        pond_depth_m=POND_DEPTH_M,
        text_pl=[],
        source=computed_source(inputs.weather.source, inputs.soil.source)
        if p.method.value == "root_zone"
        else computed_source(inputs.weather.source),
    )
    main, _ = render_text(
        "blocks/water_plan.j2",
        farm_n=inputs.farm_parcels,
        p=view,
        crop=inputs.crop.name_pl.lower(),
        area_ha=area,
        top_months=top,
        pond_max_area_m2=POND_NOTIFICATION_MAX_AREA_M2,
        drip=tech is not None and tech.tech == "drip",
    )
    return view.model_copy(update={"text_pl": main})


# --- slope profile ----------------------------------------------------------------------------------


def _hollow_runs(pr: ProfileResult) -> list[list[ProfileResultPoint]]:
    runs: list[list[ProfileResultPoint]] = []
    prev = False
    for p in pr.points:
        if p.hollow:
            if not prev:
                runs.append([])
            runs[-1].append(p)
        prev = p.hollow
    return runs


def _profile(
    pr: ProfileResult | None, inputs: AnalysisInputs, terrain: TerrainResult | None = None
) -> SlopeProfile | None:
    if pr is None:
        return None
    runs = _hollow_runs(pr)
    hollows = len(runs)
    # Q7: name which hollows lie in the main depression of the parcel (the one in the text and on the map).
    mains = [to_crs(shape(d.geometry), METRIC_CRS) for d in main_depressions(terrain)] if terrain else []
    in_main = sum(
        1 for run in runs if any(m.buffer(1.0).contains(Point(p.x_m, p.y_m)) for p in run for m in mains)
    )
    direction_pl = L.COMPASS_FROM_PL.get(pr.direction or "")
    view = SlopeProfile(
        points=[
            ProfilePoint(distance_m=p.distance_m, elevation_m=p.elevation_m, hollow=p.hollow)
            for p in pr.points
        ],
        length_m=pr.length_m,
        drop_m=pr.drop_m,
        mean_slope_pct=pr.mean_slope_pct,
        direction_pl=direction_pl,
        along_long_axis=pr.along_long_axis,
        resolution_m=pr.resolution_m,
        text_pl="",
        source=computed_source(inputs.dem.source),
    )
    main, _ = render_text(
        "blocks/profile.j2",
        pr=view,
        hollows=hollows,
        hollows_main=in_main,
        main_depressions=len(mains),
        direction_pl=direction_pl,
    )
    return view.model_copy(update={"text_pl": " ".join(main)})


# --- simulator --------------------------------------------------------------------------------------


def _simulation(
    s: SimulationResult | None, inputs: AnalysisInputs, plan: WaterPlan | None = None
) -> Simulation | None:
    if s is None:
        return None
    area = inputs.water_area_ha
    fruit = inputs.crop.is_fruit
    strategies: list[Strategy] = []
    for sid, (label, desc) in STRATEGY_TEXTS.items():
        if fruit:
            desc = STRATEGY_TEXTS_FRUIT.get(sid, desc)
        years = [
            StrategyYear(
                year_ahead=r.year_ahead,
                stress_days_median=_r(r.stress_days_median),
                stress_days_p80=_r(r.stress_days_p80),
                irrigation_mm_median=_r(r.irrigation_mm_median, SEASON_WATER_STEP_MM),
                irrigation_mm_p80=_r(r.irrigation_mm_p80, SEASON_WATER_STEP_MM),
                irrigation_m3_parcel_p80=_r(
                    (_r(r.irrigation_mm_p80, SEASON_WATER_STEP_MM) or 0.0) * area * 10, 10
                )
                if r.irrigation_mm_p80 is not None and area
                else None,
                taw_mm=round(r.taw_mm, 1),
                evaporation_saved_mm_median=_r(r.evaporation_saved_mm_median),
                evaporation_saved_m3_parcel_median=_r(r.evaporation_saved_mm_median * area * 10, 10)
                if r.evaporation_saved_mm_median is not None and area
                else None,
            )
            for r in s.results
            if r.strategy == sid
        ]
        strategies.append(Strategy(id=sid, label_pl=label, description_pl=desc, years=years))
    by = {st.id: {y.year_ahead: y for y in st.years} for st in strategies}
    view = Simulation(
        strategies=strategies,
        members=s.members,
        et0_change_pct_per_decade=_r(s.et0_change_pct_per_decade, 0.1),
        tmean_change_c_per_decade=_r(s.tmean_change_c_per_decade, 0.1),
        taw_now_mm=round(s.taw_now_mm, 1),
        taw_gain_5y_mm=round(s.taw_gain_5y_mm, 1),
        spring_storage_none_mm=_r(s.spring_storage_none_mm),
        spring_storage_full_mm=_r(s.spring_storage_full_mm),
        text_pl=[],
        assumptions_pl=[
            SIM_ASSUMPTIONS_FRUIT.get(i, a) if fruit else a for i, a in enumerate(SIM_ASSUMPTIONS)
        ],
        source=computed_source(inputs.weather.source, inputs.soil.source),
    )
    main, _ = render_text(
        "blocks/simulation.j2",
        farm_n=inputs.farm_parcels,
        s=view,
        none_y1=by["none"].get(1),
        none_y5=by["none"].get(5),
        full_y1=by["full"].get(1),
        rescue_y1=by["rescue"].get(1),
        ret_y5=by["retention"].get(5),
        both_y1=by["retention_rescue"].get(1),
        plan=plan,
        fruit=fruit,
    )
    return view.model_copy(update={"text_pl": main})


# --- satellite ------------------------------------------------------------------------------------


def _satellite(inputs: AnalysisInputs, a: Assessment) -> SatelliteSeries | None:
    data = inputs.sentinel2.data
    if data is None:
        return None
    day = inputs.analysis_date
    current = [s for s in data.current if s.date <= day]
    history = [s for s in data.history if s.date < day]
    if not current and not history:
        return None
    points = [
        SatellitePoint(
            year=s.date.year,
            day=s.date,
            ndvi=round(s.ndvi_mean, 2),
            ndmi=_r(s.ndmi_mean, 0.01),
            current=False,
        )
        for s in sorted(history, key=lambda s: s.date)
    ] + [
        SatellitePoint(
            year=s.date.year, day=s.date, ndvi=round(s.ndvi_mean, 2), ndmi=_r(s.ndmi_mean, 0.01), current=True
        )
        for s in sorted(current, key=lambda s: s.date)
    ]
    hist = sorted(s.ndvi_mean for s in history)
    check = a.current.satellite.status if a.current is not None else "missing"
    applicable = check in ("agrees", "disagrees")
    last = max(current, key=lambda s: s.date) if current else None
    band = None
    # The band is named only when there are enough past scenes to compare with (as in the assessment).
    if last is not None and len(hist) >= MIN_YEARS_FOR_PERCENTILE:
        lo, hi = round(hist[0], 2), round(hist[-1], 2)
        v = round(last.ndvi_mean, 2)
        band = "above" if v > hi else "below" if v < lo else "inside"
    main, _ = render_text(
        "blocks/satellite.j2",
        check=check,
        day=day,
        now=median(s.ndvi_mean for s in current) if current else None,
        hist_median=median(hist) if hist else None,
        hist_min=hist[0] if hist else None,
        hist_max=hist[-1] if hist else None,
        years=len(hist),
        crop=inputs.crop.name_pl.lower(),
        level=a.current.level.value if a.current is not None else None,
        phase=inputs.crop.field_phase(day),
        fruit=inputs.crop.is_fruit,
        last_day=last.date if last is not None else None,
        last_ndvi=last.ndvi_mean if last is not None else None,
        days_since_last=(day - last.date).days if last is not None else None,
        band=band,
    )
    return SatelliteSeries(
        points=points,
        history_median=_r(median(hist), 0.01) if hist else None,
        history_min=_r(hist[0], 0.01) if hist else None,
        history_max=_r(hist[-1], 0.01) if hist else None,
        applicable=applicable,
        text_pl=" ".join(main),
        source=computed_source(inputs.sentinel2.source),
    )


# --- summary tiles ----------------------------------------------------------------------------------


def _water_tile(a: Assessment) -> SummaryTile:
    rz = a.root_zone
    today = rz.at(a.analysis_date) if rz is not None else None
    if rz is None or today is None or today.gap:
        return SummaryTile(
            id="water_now",
            label_pl="Zapas wody w glebie",
            value_pl="brak danych",
            detail_pl="Bez danych o glebie lub pogodzie nie liczymy zapasu wody.",
            status="unknown",
            link_section="current",
        )
    available = max(0.0, rz.taw_mm - today.dr_mm)
    threshold = rz.taw_mm - rz.raw_mm  # below this the crop is under water stress
    status: TileStatus = (
        "good" if available > threshold + 0.25 * rz.raw_mm else "warn" if available > threshold else "bad"
    )
    detail = (
        f"Uprawa zaczyna cierpieć, gdy zostaje mniej niż {num(threshold)} mm."
        if status != "bad"
        else f"Poniżej progu stresu ({num(threshold)} mm) — uprawa już cierpi z braku wody."
    )
    return SummaryTile(
        id="water_now",
        label_pl="Zapas wody w glebie",
        value_pl=f"{num(available)} z {num(rz.taw_mm)} mm",
        detail_pl=detail,
        status=status,
        gauge=Gauge(
            value=round(available, 1), max=round(rz.taw_mm, 1), threshold=round(threshold, 1), unit="mm"
        ),
        link_section="current",
    )


def _flood_tile(flood: FloodInfo | None) -> SummaryTile:
    if flood is None or flood.level == "unknown":
        return SummaryTile(
            id="flood",
            label_pl="Zagrożenie powodzią",
            value_pl="brak danych",
            detail_pl=flood.sentence_pl
            if flood is not None
            else "Nie sprawdzono map zagrożenia powodziowego.",
            status="unknown",
            link_section="retention",
        )
    status: TileStatus = {"high": "bad", "medium": "warn", "low": "warn", "none": "good"}[flood.level]  # type: ignore[assignment]
    return SummaryTile(
        id="flood",
        label_pl="Zagrożenie powodzią",
        value_pl=flood.label_pl,
        detail_pl=flood.sentence_pl,
        status=status,
        link_section="retention",
    )


# The tile shows the number of the same metric the verdict is computed from (Q5): crop stress days (with soil
# data) or the season water balance, never the season temperature (it stays in the trends block details).
TILE_TREND_KEYS = PRIMARY_TREND_KEYS
TILE_TREND_NAMES = {
    "critical_stress_days": "Dni stresu wodnego w ważnych miesiącach",
    "stress_days": "Dni stresu wodnego w sezonie",
    "kbw_mm": "Bilans deszczu i parowania w sezonie",
}


def _tile_metric(t: ClimateTrends) -> TrendMetric | None:
    """The verdict's own metric: the first of PRIMARY_TREND_KEYS with data, as in _trend_level."""
    by = {m.key: m for m in t.metrics}
    for key in TILE_TREND_KEYS:
        m = by.get(key)
        if m is not None and m.mean_all is not None:
            return m
    return None


def _climate_tile_detail(t: ClimateTrends) -> str:
    """Numbers for the tile; the Polish sentence lives in blocks/climate_tile.j2."""
    m = _tile_metric(t)
    recent = m.mean_recent if m is not None else None
    against = recent is None
    if m is not None and recent is not None and m.mean_all is not None:
        recent_worse = (recent - m.mean_all) * (1 if m.key != "kbw_mm" else -1) > 0
        # The recent comparison is shown unless it points against the verdict.
        against = (t.level in ("worse", "critical") and not recent_worse and recent != m.mean_all) or (
            t.level == "better" and recent_worse
        )
    return render_line(
        "blocks/climate_tile.j2",
        m=m,
        name=TILE_TREND_NAMES[m.key] if m is not None else "",
        show_recent=not against,
        show_slope=m is not None and m.direction in ("worse", "better") and m.slope_per_decade is not None,
        n=len(t.seasons),
    )


def _climate_tile(t: ClimateTrends | None) -> SummaryTile:
    if t is None:
        return SummaryTile(
            id="climate",
            label_pl="Zmiana klimatu na działce",
            value_pl="brak danych",
            detail_pl="Za mało pełnych sezonów, by porównać ostatnie lata z dekadą.",
            status="unknown",
            link_section="vulnerability",
        )
    status: TileStatus = {
        "critical": "bad",
        "worse": "warn",
        "stable": "good",
        "better": "good",
        "unknown": "unknown",
    }[t.level]  # type: ignore[assignment]
    detail = _climate_tile_detail(t)
    return SummaryTile(
        id="climate",
        label_pl=f"Zmiana klimatu na działce ({len(t.seasons)} lat → 2 lata)",
        value_pl=t.label_pl,
        detail_pl=detail[:1].upper() + detail[1:],
        status=status,
        link_section="vulnerability",
    )


def _action_tile(
    a: Assessment, recs: list[Recommendation], irrigation: IrrigationAdvice, day: date
) -> SummaryTile:
    label = f"Najważniejszy ruch na dzień {date_dmy(day)}"
    urgent_irrigation = (
        irrigation.applicable
        and irrigation.dose_mm is not None
        and irrigation.within_days is not None
        and irrigation.within_days <= 3
    )
    if urgent_irrigation and a.current is not None and a.current.level.value in ("moderate", "severe"):
        n = irrigation.applications or 1
        single = irrigation.single_dose_mm
        value = f"Podlej: {num(irrigation.dose_mm)} mm" + (
            f" ({n} × {num(single)} mm)" if n > 1 and single else ""
        )
        return SummaryTile(
            id="action",
            label_pl=label,
            value_pl=value,
            detail_pl=irrigation.title_pl,
            status="bad",
            link_section="irrigation",
        )
    if recs:
        # The first action to take now (M3.5); else the first in the mandatory order (retention first).
        first = next((r for r in recs if r.horizon is Horizon.NOW), recs[0])
        when = "teraz" if first.horizon is Horizon.NOW else "przed następnym sezonem"
        section = {
            Category.RETENTION: "retention",
            Category.AGROTECH: "agrotech",
            Category.IRRIGATION: "irrigation",
        }
        return SummaryTile(
            id="action",
            label_pl=label,
            value_pl=first.title_pl,
            detail_pl=f"Zalecenie nr {first.number} ({when})"
            + (
                f" — w sumie {len(recs)} {plural(len(recs), 'zalecenie', 'zalecenia', 'zaleceń')} w raporcie."
                if len(recs) > 1
                else "."
            ),
            status="warn",
            link_section=section[first.category],
        )
    return SummaryTile(
        id="action",
        label_pl=label,
        value_pl="Bez pilnych działań",
        detail_pl="Dane nie wskazują dziś potrzeby dodatkowych działań na tej działce.",
        status="good" if a.complete else "unknown",
        link_section="summary",
    )


def _dry_year_tile(plan: WaterPlan | None, farm_n: int = 1) -> SummaryTile:
    if plan is None or plan.season_p80_mm is None:
        return SummaryTile(
            id="dry_year",
            label_pl="Woda na rok suchy",
            value_pl="brak danych",
            detail_pl="Za mało danych, by policzyć zapotrzebowanie w roku suchym.",
            status="unknown",
            link_section="irrigation",
        )
    if plan.season_p80_mm < 1:
        return SummaryTile(
            id="dry_year",
            label_pl="Woda na rok suchy",
            value_pl="nie trzeba",
            detail_pl="Nawet w roku suchym (raz na 5 lat) deszcz i gleba pokrywały potrzeby uprawy.",
            status="good",
            link_section="irrigation",
        )
    where = f" {farm_where_pl(farm_n)}" if farm_n > 1 else ""
    p80_m3 = plan.season_p80_m3_parcel
    m3 = f" · ok. {num(p80_m3, 10)} m³{where}" if p80_m3 is not None else ""
    return SummaryTile(
        id="dry_year",
        label_pl="Woda dla roślin na rok suchy (raz na 5 lat)",
        value_pl=f"ok. {num(plan.season_p80_mm, 5)} mm{m3}",
        detail_pl=f"W typowym roku ok. {num(plan.season_median_mm or 0, 5)} mm. "
        + (
            f"Z instalacji trzeba podać ok. {num(plan.season_p80_m3_parcel_gross, 10)} m³{where} "
            "(część wody się traci). "
            if plan.season_p80_m3_parcel_gross is not None
            else ""
        )
        + "Planuj zapas na rok suchy, nie na średni.",
        status="warn" if plan.season_p80_mm >= 25 else "good",
        link_section="irrigation",
    )


# --- entry point ------------------------------------------------------------------------------------


def build_outlook(
    inputs: AnalysisInputs,
    a: Assessment,
    recs: list[Recommendation],
    irrigation: IrrigationAdvice,
    flood: FloodInfo | None,
) -> Outlook:
    weather: Weather | None = None
    if inputs.weather.data is not None:
        weather = Weather.from_daily(inputs.weather.data.daily, inputs.analysis_date)
        if not weather.dates:
            weather = None
    trends_r: TrendResult | None = None
    plan_r: WaterPlanResult | None = None
    sim_r: SimulationResult | None = None
    if weather is not None:
        trends_r = analyse_trends(weather, inputs.crop, inputs.analysis_date, a.root_zone)
        taw = a.soil.taw_mm if a.soil is not None else None
        cap = single_dose_max_mm(a.soil.category if a.soil is not None else None)
        plan_r = water_plan(weather, inputs.crop, inputs.analysis_date, taw, cap)
        sim_r = simulate(weather, inputs.crop, inputs.analysis_date, a.soil, trends_r, cap)
    profile_r = (
        slope_profile(inputs.dem.data, parcel_shape(inputs.parcel)) if inputs.dem.data is not None else None
    )

    stress_source = computed_source(inputs.weather.source, inputs.soil.source)
    trends = _trends(trends_r, inputs)
    tech = technology_for(inputs, plan_r)
    plan = _water_plan(plan_r, inputs, tech)
    tiles = [
        _water_tile(a),
        _action_tile(a, recs, irrigation, inputs.analysis_date),
        _climate_tile(trends),
        _dry_year_tile(plan, inputs.farm_parcels),
        _flood_tile(flood),
    ]
    return Outlook(
        tiles=tiles,
        heatmap=_heatmap(a, stress_source),
        trends=trends,
        water_plan=plan,
        profile=_profile(profile_r, inputs, a.terrain),
        simulation=_simulation(sim_r, inputs, plan),
        satellite=_satellite(inputs, a),
        irrigation_economics=economics_view(tech, inputs, a, plan, plan_r),
    )


# --- flood and groundwater --------------------------------------------------------------------------

FLOOD_LABELS = {
    "high": "Wysokie",
    "medium": "Średnie",
    "low": "Niskie",
    "none": "Poza strefami",
    "unknown": "Nie sprawdzono",
}
ZONE_LABELS = {
    "q10": "Woda raz na 10 lat (zalewa często)",
    "q1": "Woda stuletnia (raz na 100 lat)",
    "q02": "Woda raz na 500 lat (skrajna powódź)",
}


def flood_info(r: SourceResult[FloodData] | None) -> FloodInfo | None:
    if r is None:
        return None
    d = r.data
    if d is None:
        return FloodInfo(
            status=r.status,
            level="unknown",
            label_pl=FLOOD_LABELS["unknown"],
            sentence_pl=r.message_pl or "Nie udało się sprawdzić map zagrożenia powodziowego.",
            zones=[FloodZone(id=z, label_pl=t, hit=None) for z, t in ZONE_LABELS.items()],
            source=r.source,
        )
    level = (
        "high"
        if d.zones.get("q10")
        else "medium"
        if d.zones.get("q1")
        else "low"
        if d.zones.get("q02")
        else "none"
    )
    partial = d.points_checked < max(d.points_total, 1)
    if level == "none" and partial:
        level = "unknown"  # some points did not answer: "no zone found" would be false certainty
    label = FLOOD_LABELS[level]
    if level == "none" and d.groundwater_flooding:
        level, label = "low", "Możliwe podtopienia"  # outside river zones, but in a groundwater-flooding area
    zones = [FloodZone(id=z, label_pl=t, hit=d.zones.get(z)) for z, t in ZONE_LABELS.items()]
    zones.append(
        FloodZone(id="historical", label_pl="Powodzie historyczne (mapa Wód Polskich)", hit=d.historical)
    )
    zones.append(
        FloodZone(
            id="groundwater",
            label_pl="Obszar podtopień od wód gruntowych (PIG-PIB)",
            hit=d.groundwater_flooding,
        )
    )
    main, _ = render_text("blocks/flood.j2", level=level, d=d, partial=partial)
    return FloodInfo(
        status=r.status,
        level=level,
        label_pl=label,
        sentence_pl=" ".join(main),
        zones=zones,
        wms_url=MZP_WMS,
        wms_layers=[MZP_LAYER],
        source=r.source,
    )


def groundwater_info(r: SourceResult[GroundwaterData] | None) -> GroundwaterInfo | None:
    if r is None:
        return None
    d = r.data
    if d is None:
        return GroundwaterInfo(
            status=r.status, sentence_pl=r.message_pl or "Brak danych o wodach podziemnych.", source=r.source
        )
    main, _ = render_text("blocks/groundwater.j2", d=d)
    return GroundwaterInfo(
        status=r.status,
        station_pl=d.station_name,
        distance_km=d.distance_km,
        trend=d.trend,
        change_m=d.change_m,
        period=Period(start=d.window_start, end=d.window_end),
        sentence_pl=" ".join(main),
        source=r.source,
    )
