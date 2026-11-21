"""Causes of the water deficit (CLAUDE.md, methodology): a flag and numeric evidence each. Pure, no I/O.

flagged = None means the cause could not be evaluated because its data are missing (never guessed).

Thresholds (documented in docs/METHODOLOGY.md):
- precipitation_deficit_heat: 90-day precipitation or 60-day KBW among the 3 driest of 10 years
  (percentile ≤ 30), or a 30-day mean maximum temperature ≥ HEAT_ANOMALY_C above the same window of
  previous years with KBW below the median,
- low_soil_retention: IUNG category I–II, or TAW < LOW_TAW_PER_M_MM per metre of soil, or topsoil organic
  carbon below LOW_SOC_G_PER_KG (≈ 1.7 % organic matter, lower bound of "medium humus" arable soils),
- excessive_runoff: mean slope ≥ RUNOFF_SLOPE_PCT, or a gentle slope (≥ GENTLE_SLOPE_PCT) with either no
  retention elements (ponds, wetlands, trees) within 500 m or a main outlet draining ≥ OUTLET_AREA_M2,
- crop_sensitivity: the analysis date falls in a water-critical phase while a deficit is present, or the
  critical months were deficit months in ≥ 30 % of the previous 10 years.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from statistics import mean
from typing import Literal

from app.analysis.common import DeficitLevel, indicator
from app.analysis.context import Context, computed_source
from app.analysis.series import same_day_in_year
from app.analysis.soil import SoilCategory
from app.core.config import HISTORY_YEARS
from app.core.models import Confidence, Indicator

PRECIP_DRY_PCT = 30.0
HEAT_ANOMALY_C = 1.5
HOT_DAY_C = 30.0
LOW_TAW_PER_M_MM = 100.0
LOW_SOC_G_PER_KG = 10.0
RUNOFF_SLOPE_PCT = 5.0
GENTLE_SLOPE_PCT = 2.0
OUTLET_AREA_M2 = 10_000.0
RETENTION_RADIUS_M = 500.0

CauseId = Literal["precipitation_deficit_heat", "low_soil_retention", "excessive_runoff", "crop_sensitivity"]


@dataclass(frozen=True)
class Cause:
    id: CauseId
    flagged: bool | None
    evidence: list[Indicator]
    context: dict[str, str] = field(
        default_factory=dict
    )  # non-numeric facts, e.g. name of the critical phase


def _precip_heat(ctx: Context) -> Cause:
    if ctx.weather is None or ctx.history is None:
        return Cause("precipitation_deficit_heat", None, [])
    cur = ctx.history.current
    w = ctx.weather
    src = ctx.weather_source
    lvl = ctx.weather_confidence
    start, end = w.window(ctx.day, 30)
    tmax_now = w.mean_tmax(start, end)
    hot_now = w.hot_days(start, end, HOT_DAY_C)
    past_tmax: list[float] = []
    past_hot: list[int] = []
    for k in range(1, HISTORY_YEARS + 1):
        e = same_day_in_year(ctx.day, ctx.day.year - k)
        s = e - timedelta(days=29)
        t = w.mean_tmax(s, e)
        h = w.hot_days(s, e, HOT_DAY_C)
        if t is not None:
            past_tmax.append(t)
        if h is not None:
            past_hot.append(h)
    anomaly = tmax_now - mean(past_tmax) if tmax_now is not None and past_tmax else None
    hot_mean = mean(past_hot) if past_hot else None

    evidence = [
        indicator("precip_30d_mm", cur.precip_30d_mm, "mm", src, level=lvl, start=start, end=end),
        indicator(
            "precip_90d_mm", cur.precip_90d_mm, "mm", src, level=lvl, start=end - timedelta(days=89), end=end
        ),
        indicator("precip_90d_pct", cur.precip_90d_pct, "%", src, level=lvl, reason="percentile_10y"),
        indicator(
            "kbw_60d_mm", cur.kbw_60d_mm, "mm", src, level=lvl, start=end - timedelta(days=59), end=end
        ),
        indicator("kbw_60d_pct", cur.kbw_60d_pct, "%", src, level=lvl, reason="percentile_10y"),
        indicator("tmax_30d_mean_c", tmax_now, "°C", src, level=lvl, step=0.1, start=start, end=end),
        indicator("tmax_30d_anomaly_c", anomaly, "°C", src, level=lvl, step=0.1, reason="percentile_10y"),
        indicator("hot_days_30d", hot_now, "dni", src, level=lvl, start=start, end=end),
        indicator(
            "hot_days_30d_history_mean", hot_mean, "dni", src, level=lvl, step=0.1, reason="percentile_10y"
        ),
    ]
    signals = [cur.precip_90d_pct, cur.kbw_60d_pct]
    if all(s is None for s in signals) and anomaly is None:
        return Cause("precipitation_deficit_heat", None, evidence)
    dry = any(s is not None and s <= PRECIP_DRY_PCT for s in signals)
    hot = (
        anomaly is not None
        and anomaly >= HEAT_ANOMALY_C
        and cur.kbw_60d_pct is not None
        and cur.kbw_60d_pct < 50
    )
    return Cause("precipitation_deficit_heat", dry or hot, evidence)


def _soil_retention(ctx: Context) -> Cause:
    soil = ctx.soil
    if soil is None:
        return Cause("low_soil_retention", None, [])
    src = ctx.soil_source
    evidence = [
        indicator(
            "sand_topsoil_pct", soil.topsoil_sand_pct, "%", src, level=Confidence.MEDIUM, reason="soil_map"
        ),
        indicator(
            "clay_topsoil_pct", soil.topsoil_clay_pct, "%", src, level=Confidence.MEDIUM, reason="soil_map"
        ),
        indicator(
            "soc_topsoil_g_per_kg",
            soil.topsoil_soc_g_per_kg,
            "g/kg",
            src,
            level=Confidence.MEDIUM,
            reason="soil_map",
        ),
        indicator("taw_mm", soil.taw_mm, "mm", src, level=Confidence.MEDIUM, reason="soil_map"),
        indicator("taw_per_m_mm", soil.taw_per_m_mm, "mm/m", src, level=Confidence.MEDIUM, reason="soil_map"),
    ]
    context: dict[str, str] = {}
    if soil.category is not None:
        context["soil_category"] = soil.category.value
    if soil.texture is not None:
        context["texture"] = soil.texture.value
    checks: list[bool] = []
    if soil.category is not None:
        checks.append(soil.category in (SoilCategory.I, SoilCategory.II))
    if soil.taw_per_m_mm is not None:
        checks.append(soil.taw_per_m_mm < LOW_TAW_PER_M_MM)
    if soil.topsoil_soc_g_per_kg is not None:
        checks.append(soil.topsoil_soc_g_per_kg < LOW_SOC_G_PER_KG)
    return Cause("low_soil_retention", any(checks) if checks else None, evidence, context)


def _runoff(ctx: Context) -> Cause:
    terrain = ctx.terrain
    hydro = ctx.hydro
    if terrain is None:
        return Cause("excessive_runoff", None, [])
    tsrc = computed_source(ctx.inputs.dem.source)
    tconf = Confidence.HIGH if terrain.dataset == "gugik_nmt" else Confidence.MEDIUM
    treason = "terrain_nmt" if terrain.dataset == "gugik_nmt" else "terrain_cop"
    main_outlet = terrain.outlets[0].contributing_area_m2 if terrain.outlets else None
    evidence = [
        indicator("slope_mean_pct", terrain.slope_mean_pct, "%", tsrc, level=tconf, reason=treason, step=0.1),
        indicator("slope_max_pct", terrain.slope_max_pct, "%", tsrc, level=tconf, reason=treason, step=0.1),
        indicator("main_outlet_area_m2", main_outlet, "m²", tsrc, level=tconf, reason=treason, step=100),
    ]
    no_retention: bool | None = None
    if hydro is not None:
        hsrc = computed_source(ctx.inputs.hydro.source)
        distances = [hydro.nearest_m.get(k) for k in ("water_body", "wetland", "trees")]
        present = [d for d in distances if d is not None]
        nearest = min(present) if present else None
        no_retention = nearest is None or nearest > RETENTION_RADIUS_M
        evidence += [
            indicator(
                "nearest_retention_element_m", nearest, "m", hsrc, level=Confidence.LOW, reason="osm", step=10
            ),
            indicator(
                "ditch_length_along_boundary_m",
                hydro.ditch_length_along_boundary_m,
                "m",
                hsrc,
                level=Confidence.LOW,
                reason="osm",
                step=10,
            ),
        ]
    steep = terrain.slope_mean_pct >= RUNOFF_SLOPE_PCT
    gentle = terrain.slope_mean_pct >= GENTLE_SLOPE_PCT
    concentrated = main_outlet is not None and main_outlet >= OUTLET_AREA_M2
    context = {"aspect": terrain.aspect} if terrain.aspect else {}
    return Cause(
        "excessive_runoff", steep or (gentle and (bool(no_retention) or concentrated)), evidence, context
    )


def _crop_sensitivity(ctx: Context, level: DeficitLevel) -> Cause:
    crop = ctx.crop
    period = crop.critical_period_at(ctx.day)
    context: dict[str, str] = {}
    evidence: list[Indicator] = []
    now_critical = period is not None and level.rank >= DeficitLevel.LIGHT.rank
    if period is not None:
        start = crop.season_start(ctx.day)
        assert start is not None
        lo, hi = period.range_for_season(start)
        context.update(
            critical_phase=period.name_pl, critical_start=lo.isoformat(), critical_end=hi.isoformat()
        )
    structural: bool | None = None
    if ctx.history is not None and ctx.history.months:
        crit = crop.critical_months()
        freq = {f.month: f.frequency for f in ctx.history.months}
        src = ctx.water_source if ctx.balance is not None else ctx.weather_source
        conf = Confidence.MEDIUM if ctx.balance is not None else Confidence.LOW
        reason = "root_zone" if ctx.balance is not None else "history_crop_balance"
        for m in sorted(crit):
            if freq.get(m) is not None:
                evidence.append(
                    indicator(
                        f"deficit_frequency_month_{m:02d}_pct",
                        100 * (freq[m] or 0.0),
                        "%",
                        src,
                        level=conf,
                        reason=reason,
                    )
                )
        structural = bool(ctx.history.critical_risk_months)
        context["critical_months"] = ",".join(str(m) for m in sorted(crit))
    flagged = now_critical or bool(structural)
    return Cause("crop_sensitivity", flagged, evidence, context)


def assess_causes(ctx: Context, level: DeficitLevel) -> list[Cause]:
    return [_precip_heat(ctx), _soil_retention(ctx), _runoff(ctx), _crop_sensitivity(ctx, level)]
