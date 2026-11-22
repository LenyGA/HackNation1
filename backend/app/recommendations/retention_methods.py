"""Overview of the five ways to keep or store water on this parcel (G9, plan M4.3). Pure, no I/O.

Every method gets a status computed from the parcel's data — recommended / conditional / not recommended — or
"no data" when the source it depends on did not answer (never "not recommended" for a missing source, rule 4),
one reason with the numbers behind it, and the formal requirement under the Water Law.

Water Law (Prawo wodne, Dz.U. 2025 poz. 960, tekst jednolity; checked 22.11.2026):
- art. 394 ust. 1 pkt 9: a pond up to 5000 m² and 3 m deep (from the natural ground level), filled only
  with rain, snowmelt or groundwater, needs a water-law notification (zgłoszenie wodnoprawne); a larger or
  deeper one needs a water-law permit (pozwolenie wodnoprawne),
- art. 33 ust. 4 pkt 1: ordinary use of water (zwykłe korzystanie z wód, no permit) is abstraction of up to
  5 m³ per day on average over the year; irrigation above it is special use and needs a permit.
Thresholds without a published source are the team's stated assumptions (docs/METHODOLOGY.md, section 8a).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from app.analysis.common import indicator
from app.analysis.context import computed_source
from app.analysis.retention_balance import CoverageStatus, RetentionCoverage
from app.analysis.soil import SoilCategory
from app.core.models import Confidence, Indicator
from app.recommendations.common import LIGHT_SOIL_CATEGORIES, found, water_need
from app.recommendations.models import ParamValue, RuleContext
from app.recommendations.retention import FLOOD_ZONES_FOR_POND

# Water Law (see module docstring).
POND_NOTIFICATION_MAX_AREA_M2 = 5000.0
POND_NOTIFICATION_MAX_DEPTH_M = 3.0
ORDINARY_USE_MAX_M3_PER_DAY = 5.0
WATER_LAW_PL = "Prawo wodne (tekst jednolity Dz.U. 2025 poz. 960), stan sprawdzony 22.11.2026"

# Team assumptions (docs/METHODOLOGY.md, section 8a).
POND_MIN_VOLUME_M3 = 200.0  # smaller hollows hold too little to be worth digging out
SEALED_SOIL_CATEGORIES = (SoilCategory.III, SoilCategory.IV)  # loam and clay hold water without a liner
WEIR_MAX_DISTANCE_M = 150.0  # ditch or stream close enough to raise the water table under the parcel
FLAT_SLOPE_PCT = 2.0
ROOF_MAX_DISTANCE_M = 100.0
ROOF_MAIN_SOURCE_MAX_M3 = 1000.0  # needs in thousands of m³ are beyond what roofs nearby can collect
LOW_TREE_SHARE_PCT = 5.0  # open landscape: under 1/20 of the 500 m ring is trees
DAYS_PER_YEAR = 365

MethodId = Literal["pond", "weir", "rainwater", "well", "tree_belts"]
METHOD_ORDER: tuple[MethodId, ...] = ("pond", "weir", "rainwater", "well", "tree_belts")


class MethodStatus(StrEnum):
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    NOT_RECOMMENDED = "not_recommended"
    NO_DATA = "no_data"


class Permit(StrEnum):
    NONE = "none"  # nothing formal to say
    NOTIFICATION = "notification"  # zgłoszenie wodnoprawne
    PERMIT = "permit"  # pozwolenie wodnoprawne
    PERMIT_FULL_ONLY = (
        "permit_full_only"  # rescue irrigation within ordinary use, full irrigation needs a permit
    )
    ORDINARY_USE = "ordinary_use"  # within ordinary use of water, no permit
    CHECK = "check"  # depends on the structure: ask Wody Polskie and the ditch owner


@dataclass(frozen=True)
class MethodAssessment:
    id: MethodId
    status: MethodStatus
    reason: str  # key of the sentence in templates/blocks/retention_method.j2
    params: dict[str, ParamValue] = field(default_factory=dict)
    evidence: list[Indicator] = field(default_factory=list)
    permit: Permit = Permit.NONE


def _coverage_evidence(ctx: RuleContext, cov: RetentionCoverage) -> list[Indicator]:
    if cov.full_need_m3 is None:
        return []
    src = computed_source(ctx.inputs.dem.source, ctx.inputs.weather.source, ctx.inputs.soil.source)
    out = [
        indicator(
            "irrigation_need_dry_year_m3",
            cov.full_need_m3,
            "m³",
            src,
            level=Confidence.MEDIUM,
            reason="retention_balance",
            step=10,
        )
    ]
    if cov.full_pct is not None:
        out.append(
            indicator(
                "retention_coverage_full_pct",
                cov.full_pct,
                "%",
                src,
                level=Confidence.MEDIUM,
                reason="retention_balance",
            )
        )
    return out


def _wet_hazard(ctx: RuleContext) -> bool | None:
    """Groundwater flooding area or a 10/100-year flood zone at the parcel; None when not checked."""
    flood = ctx.inputs.flood.data if ctx.inputs.flood is not None else None
    if flood is None:
        return None
    return bool(flood.groundwater_flooding) or any(flood.zones.get(z, False) for z in FLOOD_ZONES_FOR_POND)


# --- 1. pond in the depression --------------------------------------------------------------------


def _pond(ctx: RuleContext, cov: RetentionCoverage) -> MethodAssessment:
    if cov.status is CoverageStatus.NO_TERRAIN:
        return MethodAssessment("pond", MethodStatus.NO_DATA, "no_terrain")
    if cov.volume_m3 is None:
        return MethodAssessment("pond", MethodStatus.NOT_RECOMMENDED, "no_depression")
    t = ctx.terrain
    assert t is not None
    nmt = t.dataset == "gugik_nmt"
    src = computed_source(ctx.inputs.dem.source)
    conf, why = (Confidence.HIGH, "terrain_nmt") if nmt else (Confidence.MEDIUM, "terrain_cop")
    evidence = [indicator("depression_volume_m3", cov.volume_m3, "m³", src, level=conf, reason=why, step=10)]
    params: dict[str, ParamValue] = {"volume_m3": cov.volume_m3, "min_volume_m3": POND_MIN_VOLUME_M3}
    if cov.volume_m3 < POND_MIN_VOLUME_M3:
        return MethodAssessment("pond", MethodStatus.NOT_RECOMMENDED, "small", params, evidence)

    area = cov.area_m2 or 0.0
    depth = cov.max_depth_m or 0.0
    evidence.append(indicator("depression_area_m2", area, "m²", src, level=conf, reason=why, step=10))
    if cov.max_depth_m is not None:
        evidence.append(
            indicator("depression_max_depth_m", depth, "m", src, level=conf, reason=why, step=0.1)
        )
    evidence += _coverage_evidence(ctx, cov)
    soil = ctx.soil.category if ctx.soil is not None else None
    sealing = (
        "natural" if soil in SEALED_SOIL_CATEGORIES else "liner" if soil in LIGHT_SOIL_CATEGORIES else ""
    )
    if soil is not None:
        evidence += found(ctx, "soil_category")
    wet = _wet_hazard(ctx)
    params.update(
        {
            "area_m2": area,
            "depth_m": round(depth, 1),
            "sealing": sealing,
            "controlled": int(bool(wet) or soil is SoilCategory.IV),
            "full_pct": cov.full_pct if cov.full_pct is not None else "",
            "rescue_pct": cov.rescue_pct if cov.rescue_pct is not None else "",
            "max_area_m2": POND_NOTIFICATION_MAX_AREA_M2,
            "max_depth_m": POND_NOTIFICATION_MAX_DEPTH_M,
        }
    )
    over = area > POND_NOTIFICATION_MAX_AREA_M2 or depth > POND_NOTIFICATION_MAX_DEPTH_M
    permit = Permit.PERMIT if over else Permit.NOTIFICATION
    status = MethodStatus.RECOMMENDED if sealing == "natural" else MethodStatus.CONDITIONAL
    return MethodAssessment("pond", status, "depression", params, evidence, permit)


# --- 2. weir on a ditch / controlled drainage -----------------------------------------------------


def _nearest_ditch_m(ctx: RuleContext) -> float | None:
    if ctx.hydro is None:
        return None
    found_m = [d for k in ("ditch", "watercourse") if (d := ctx.hydro.nearest_m.get(k)) is not None]
    return min(found_m) if found_m else None


def _weir(ctx: RuleContext) -> MethodAssessment:
    near = _nearest_ditch_m(ctx)
    t = ctx.terrain
    wet = _wet_hazard(ctx)
    flat_wet = t is not None and t.slope_mean_pct < FLAT_SLOPE_PCT and wet is True
    params: dict[str, ParamValue] = {"max_distance_m": WEIR_MAX_DISTANCE_M, "flat_slope_pct": FLAT_SLOPE_PCT}
    evidence: list[Indicator] = []
    if near is not None:
        evidence.append(
            indicator(
                "nearest_ditch_or_stream_m",
                near,
                "m",
                computed_source(ctx.inputs.hydro.source),
                level=Confidence.LOW,
                reason="osm",
                step=10,
            )
        )
        params["distance_m"] = round(near, -1)
    if near is not None and near <= WEIR_MAX_DISTANCE_M:
        return MethodAssessment(
            "weir", MethodStatus.RECOMMENDED, "ditch_near", params, evidence, Permit.CHECK
        )
    if flat_wet:
        assert t is not None
        params["slope_mean_pct"] = t.slope_mean_pct
        evidence += found(ctx, "slope_mean_pct")
        evidence += _wet_evidence(ctx)
        return MethodAssessment("weir", MethodStatus.RECOMMENDED, "flat_wet", params, evidence, Permit.CHECK)
    if ctx.hydro is None:
        return MethodAssessment("weir", MethodStatus.NO_DATA, "no_hydro", params)
    params["radius_m"] = ctx.hydro.radius_m
    if not evidence:
        # No ditch on the map within the searched radius: the evidence is the (empty) count.
        evidence.append(
            indicator(
                "ditches_within_radius_count",
                ctx.hydro.counts.get("ditch", 0) + ctx.hydro.counts.get("watercourse", 0),
                "szt.",
                computed_source(ctx.inputs.hydro.source),
                level=Confidence.LOW,
                reason="osm",
            )
        )
    return MethodAssessment("weir", MethodStatus.NOT_RECOMMENDED, "no_ditch", params, evidence)


def _wet_evidence(ctx: RuleContext) -> list[Indicator]:
    flood = ctx.inputs.flood
    if flood is None or flood.data is None:
        return []
    src = computed_source(flood.source)
    out: list[Indicator] = []
    if flood.data.groundwater_flooding:
        out.append(indicator("groundwater_flooding_risk", 1, "", src, level=Confidence.MEDIUM))
    if any(flood.data.zones.get(z, False) for z in FLOOD_ZONES_FOR_POND):
        out.append(indicator("flood_zone_risk", 1, "", src, level=Confidence.MEDIUM))
    return out


# --- 3. rainwater from roofs ----------------------------------------------------------------------


def _rainwater(ctx: RuleContext, cov: RetentionCoverage) -> MethodAssessment:
    lc = ctx.inputs.landcover.data
    if lc is None:
        return MethodAssessment("rainwater", MethodStatus.NO_DATA, "no_landcover")
    ring = lc.surroundings
    on_parcel = lc.built_up_pct > 0
    nearest = 0.0 if on_parcel else (ring.nearest_m.get("built_up") if ring is not None else None)
    if ring is None and not on_parcel:
        return MethodAssessment("rainwater", MethodStatus.NO_DATA, "no_landcover")
    src = computed_source(ctx.inputs.landcover.source)
    params: dict[str, ParamValue] = {
        "max_distance_m": ROOF_MAX_DISTANCE_M,
        "main_source_max_m3": ROOF_MAIN_SOURCE_MAX_M3,
        "radius_m": ring.radius_m if ring is not None else 0,
    }
    if nearest is None or nearest > ROOF_MAX_DISTANCE_M:
        evidence = (
            [
                indicator(
                    "nearest_built_up_m",
                    nearest,
                    "m",
                    src,
                    level=Confidence.LOW,
                    reason="worldcover_ring",
                    step=10,
                )
            ]
            if nearest is not None
            else [
                indicator(
                    "built_up_share_surroundings_pct",
                    ring.shares_pct.get("built_up", 0.0) if ring is not None else 0.0,
                    "%",
                    src,
                    level=Confidence.LOW,
                    reason="worldcover_ring",
                    step=0.1,
                )
            ]
        )
        if nearest is not None:
            params["distance_m"] = round(nearest, -1)
        return MethodAssessment("rainwater", MethodStatus.NOT_RECOMMENDED, "no_roofs", params, evidence)
    params["distance_m"] = round(nearest, -1)
    params["on_parcel"] = int(on_parcel)
    evidence = [
        indicator(
            "nearest_built_up_m", nearest, "m", src, level=Confidence.LOW, reason="worldcover_ring", step=10
        )
    ]
    evidence += _coverage_evidence(ctx, cov)
    need = cov.full_need_m3
    if need is not None and need >= ROOF_MAIN_SOURCE_MAX_M3:
        params["need_m3"] = need
        return MethodAssessment("rainwater", MethodStatus.CONDITIONAL, "too_small", params, evidence)
    if need is not None and need >= 1:
        params["need_m3"] = need
        return MethodAssessment("rainwater", MethodStatus.RECOMMENDED, "small_need", params, evidence)
    return MethodAssessment("rainwater", MethodStatus.CONDITIONAL, "auxiliary", params, evidence)


# --- 4. well --------------------------------------------------------------------------------------


def _groundwater_evidence(ctx: RuleContext) -> tuple[list[Indicator], dict[str, ParamValue]]:
    gw = ctx.inputs.groundwater
    if gw is None or gw.data is None:
        return [], {}
    src = computed_source(gw.source)
    d = gw.data
    return (
        [
            indicator(
                "groundwater_depth_m",
                d.depth_now_m,
                "m",
                src,
                level=Confidence.LOW,
                reason="groundwater_station",
                step=0.1,
                start=d.window_start,
                end=d.window_end,
            ),
            indicator(
                "groundwater_station_km",
                d.distance_km,
                "km",
                src,
                level=Confidence.LOW,
                reason="groundwater_station",
                step=1,
            ),
        ],
        {"gw_depth_m": round(d.depth_now_m, 1), "gw_station_km": round(d.distance_km)},
    )


def _well(ctx: RuleContext, cov: RetentionCoverage) -> MethodAssessment:
    if cov.status is CoverageStatus.NO_PLAN or cov.full_need_m3 is None:
        return MethodAssessment("well", MethodStatus.NO_DATA, "no_plan")
    gw_evidence, params = _groundwater_evidence(ctx)
    params["max_m3_day"] = ORDINARY_USE_MAX_M3_PER_DAY
    if cov.status is CoverageStatus.NO_NEED:
        return MethodAssessment(
            "well", MethodStatus.NOT_RECOMMENDED, "no_need", params, _coverage_evidence(ctx, cov)
        )
    kept = cov.volume_m3 or 0.0
    if kept >= cov.full_need_m3:
        return MethodAssessment(
            "well", MethodStatus.NOT_RECOMMENDED, "retention_covers", params, _coverage_evidence(ctx, cov)
        )
    # The well supplies only what the depression does not hold; ordinary use is judged on that abstraction,
    # for full irrigation and for rescue irrigation (which the depression may already cover).
    gap_full = cov.full_need_m3 - kept
    gap_rescue = max(0.0, cov.rescue_need_m3 - kept) if cov.rescue_need_m3 is not None else None
    per_day = gap_full / DAYS_PER_YEAR
    per_day_rescue = gap_rescue / DAYS_PER_YEAR if gap_rescue is not None else None
    params.update(
        {
            "gap_m3": round(gap_full, -1),
            "per_day_m3": round(per_day, 1),
            "gap_rescue_m3": round(gap_rescue, -1) if gap_rescue is not None else "",
            "per_day_rescue_m3": round(per_day_rescue, 1) if per_day_rescue is not None else "",
        }
    )
    src = computed_source(ctx.inputs.weather.source, ctx.inputs.soil.source, ctx.inputs.dem.source)
    evidence = [
        *_coverage_evidence(ctx, cov),
        indicator(
            "irrigation_avg_m3_per_day",
            per_day,
            "m³",
            src,
            level=Confidence.MEDIUM,
            reason="retention_balance",
            step=0.1,
        ),
        *gw_evidence,
    ]
    if per_day <= ORDINARY_USE_MAX_M3_PER_DAY:
        permit = Permit.ORDINARY_USE
    elif per_day_rescue is not None and per_day_rescue <= ORDINARY_USE_MAX_M3_PER_DAY:
        permit = Permit.PERMIT_FULL_ONLY
    else:
        permit = Permit.PERMIT
    return MethodAssessment("well", MethodStatus.CONDITIONAL, "gap", params, evidence, permit)


# --- 5. mid-field tree belts and buffer strips ----------------------------------------------------


def _tree_belts(ctx: RuleContext) -> MethodAssessment:
    lc = ctx.inputs.landcover.data
    ring = lc.surroundings if lc is not None else None
    if ring is None:
        return MethodAssessment("tree_belts", MethodStatus.NO_DATA, "no_landcover")
    share = ring.shares_pct.get("trees", 0.0)
    src = computed_source(ctx.inputs.landcover.source)
    evidence = [
        indicator(
            "trees_share_surroundings_pct",
            share,
            "%",
            src,
            level=Confidence.LOW,
            reason="worldcover_ring",
            step=0.1,
        )
    ]
    params: dict[str, ParamValue] = {
        "share_pct": round(share, 1),
        "radius_m": ring.radius_m,
        "low_share_pct": LOW_TREE_SHARE_PCT,
    }
    if share >= LOW_TREE_SHARE_PCT:
        return MethodAssessment("tree_belts", MethodStatus.NOT_RECOMMENDED, "enough_trees", params, evidence)
    t = ctx.terrain
    if t is not None and t.outlets:
        params["outlets"] = len(t.outlets)
        evidence += found(ctx, "main_outlet_area_m2")
        return MethodAssessment("tree_belts", MethodStatus.RECOMMENDED, "open_outlet", params, evidence)
    return MethodAssessment(
        "tree_belts",
        MethodStatus.CONDITIONAL,
        "open_no_terrain" if t is None else "open_no_outlet",
        params,
        evidence,
    )


# --- entry point ----------------------------------------------------------------------------------


def _without_need(m: MethodAssessment) -> MethodAssessment:
    """Without a water need shown by the data a recommended method becomes conditional (rule 1)."""
    if m.status is not MethodStatus.RECOMMENDED:
        return m
    return MethodAssessment(
        m.id, MethodStatus.CONDITIONAL, m.reason, {**m.params, "no_need": 1}, m.evidence, m.permit
    )


def assess_methods(ctx: RuleContext, coverage: RetentionCoverage) -> list[MethodAssessment]:
    methods = [
        _pond(ctx, coverage),
        _weir(ctx),
        _rainwater(ctx, coverage),
        _well(ctx, coverage),
        _tree_belts(ctx),
    ]
    need = water_need(ctx)
    if not need:
        methods = [_without_need(m) for m in methods]
    out: list[MethodAssessment] = []
    for m in methods:
        unique: list[Indicator] = []
        for i in m.evidence:
            if i.value is not None and all(u.key != i.key for u in unique):
                unique.append(i)
        if m.status is not MethodStatus.NO_DATA and not unique:
            # Rule 1: a status must rest on at least one number from this parcel.
            unique = need[:1]
        out.append(MethodAssessment(m.id, m.status, m.reason, m.params, unique, m.permit))
    return out
