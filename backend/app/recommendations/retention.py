"""Retention rules: keep water where it falls (NWRM), always before agrotechnics and irrigation. Pure, no I/O.

Thresholds are documented in docs/METHODOLOGY.md (section 8).
"""

from app.analysis.causes import RETENTION_RADIUS_M
from app.analysis.common import indicator
from app.analysis.context import computed_source, landcover_surroundings, surroundings_nearest_m
from app.analysis.soil import SoilCategory
from app.analysis.terrain import RetentionSite, main_depressions
from app.core.models import Confidence, Indicator
from app.recommendations.common import found, light_soil, water_need
from app.recommendations.models import Category, Location, ParamValue, Rule, RuleContext
from app.sources.hydro import BOUNDARY_BUFFER_M, HydroFeature

DITCH_MIN_LENGTH_M = 20.0
# Q6: on a heavy (category IV) soil or with a flood / groundwater-flooding hazard an uncontrolled pool after a
# wet winter waterlogs the crop; the advice becomes a controlled pond or a weir with an outlet.
HEAVY_SOIL_CATEGORIES = (SoilCategory.IV,)
FLOOD_ZONES_FOR_POND = ("q10", "q1")
FLOW_PATH_MIN_CONTRIBUTING_M2 = 5_000.0
FLOW_PATH_MIN_SLOPE_PCT = 2.0
PROTECT_RADIUS_M = 300.0
PROTECT_KINDS = ("wetland", "water_body")


def _terrain_meta(ctx: RuleContext) -> tuple[str, Confidence, str]:
    t = ctx.terrain
    assert t is not None
    nmt = t.dataset == "gugik_nmt"
    return (
        computed_source(ctx.inputs.dem.source),
        Confidence.HIGH if nmt else Confidence.MEDIUM,
        "terrain_nmt" if nmt else "terrain_cop",
    )


def _hydro_source(ctx: RuleContext) -> str:
    return computed_source(ctx.inputs.hydro.source)


# --- 1. ditch along the parcel: check dam / weir ---------------------------------------------------


def _boundary_ditches(ctx: RuleContext) -> list[HydroFeature]:
    if ctx.hydro is None:
        return []
    return [f for f in ctx.hydro.features if f.kind == "ditch" and f.distance_m <= BOUNDARY_BUFFER_M]


def _ditch_length(ctx: RuleContext) -> float:
    return ctx.hydro.ditch_length_along_boundary_m if ctx.hydro is not None else 0.0


def _ditch_condition(ctx: RuleContext) -> bool:
    return _ditch_length(ctx) >= DITCH_MIN_LENGTH_M and bool(water_need(ctx))


def _ditch_evidence(ctx: RuleContext) -> list[Indicator]:
    if ctx.hydro is None:
        return []
    ditch = indicator(
        "ditch_length_along_boundary_m",
        _ditch_length(ctx),
        "m",
        _hydro_source(ctx),
        level=Confidence.LOW,
        reason="osm",
        step=10,
    )
    return [ditch, *water_need(ctx)]


def _ditch_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {"ditch_length_m": round(_ditch_length(ctx), -1)}


def _ditch_locations(ctx: RuleContext) -> list[Location]:
    return [Location(kind="ditch", geometry=f.geometry) for f in _boundary_ditches(ctx)]


# --- 2. depression on the parcel: pond or temporary water retention --------------------------------


def _depressions(ctx: RuleContext) -> list[RetentionSite]:
    return main_depressions(ctx.terrain) if ctx.terrain is not None else []


def _depression_condition(ctx: RuleContext) -> bool:
    return bool(_depressions(ctx)) and bool(water_need(ctx))


def _heavy_soil(ctx: RuleContext) -> bool:
    return ctx.soil is not None and ctx.soil.category in HEAVY_SOIL_CATEGORIES


def _wet_hazards(ctx: RuleContext) -> tuple[bool, bool]:
    """(groundwater flooding area PIG-PIB, flood zone ISOK) at the parcel; False when not checked."""
    flood = ctx.inputs.flood.data if ctx.inputs.flood is not None else None
    if flood is None:
        return False, False
    # Zones of floods every 10 and 100 years; the 1-in-500-year zone alone does not change the advice.
    return bool(flood.groundwater_flooding), any(flood.zones.get(z, False) for z in FLOOD_ZONES_FOR_POND)


def _wet_risk_evidence(ctx: RuleContext) -> list[Indicator]:
    out: list[Indicator] = []
    if _heavy_soil(ctx):
        out += found(ctx, "soil_category")
    podt, zone = _wet_hazards(ctx)
    if (podt or zone) and ctx.inputs.flood is not None:
        src = computed_source(ctx.inputs.flood.source)
        if podt:
            out.append(indicator("groundwater_flooding_risk", 1, "", src, level=Confidence.MEDIUM))
        if zone:
            out.append(indicator("flood_zone_risk", 1, "", src, level=Confidence.MEDIUM))
    return out


def _depression_evidence(ctx: RuleContext) -> list[Indicator]:
    sites = _depressions(ctx)
    if not sites:
        return []
    src, conf, reason = _terrain_meta(ctx)
    top = sites[0]  # sorted by volume in terrain analysis
    return (
        [
            indicator("depression_count", len(sites), "szt.", src, level=conf, reason=reason),
            indicator("depression_volume_m3", top.volume_m3, "m³", src, level=conf, reason=reason, step=10),
            indicator(
                "depression_max_depth_m", top.max_depth_m, "m", src, level=conf, reason=reason, step=0.1
            ),
            indicator(
                "depression_contributing_area_m2",
                top.contributing_area_m2,
                "m²",
                src,
                level=conf,
                reason=reason,
                step=100,
            ),
        ]
        + _wet_risk_evidence(ctx)
        + water_need(ctx)
    )


def _depression_params(ctx: RuleContext) -> dict[str, ParamValue]:
    sites = _depressions(ctx)
    top = sites[0]
    params: dict[str, ParamValue] = {
        "count": len(sites),
        "contributing_ha": round(top.contributing_area_m2 / 10_000, 1),
    }
    podt, zone = _wet_hazards(ctx)
    heavy = _heavy_soil(ctx)
    params["controlled"] = int(heavy or podt or zone)
    params["heavy_soil"] = int(heavy)
    params["groundwater_flooding"] = int(podt)
    params["flood_zone"] = int(zone)
    if top.volume_m3 is not None and top.volume_m3 >= 1:
        # Never a fake "0 m³": small volumes are rounded to 1 m³, larger ones to 10 m³.
        params["volume_m3"] = round(top.volume_m3, -1 if top.volume_m3 >= 50 else 0)
    return params


def _depression_locations(ctx: RuleContext) -> list[Location]:
    return [Location(kind="depression", geometry=d.geometry) for d in _depressions(ctx)]


# --- 3. runoff leaving the parcel: buffer strip or balk across the slope at the outlet -------------


def _outlet_condition(ctx: RuleContext) -> bool:
    runoff = ctx.cause("excessive_runoff")
    return runoff is not None and runoff.flagged is True and bool(ctx.terrain and ctx.terrain.outlets)


def _outlet_evidence(ctx: RuleContext) -> list[Indicator]:
    return found(ctx, "slope_mean_pct", "slope_max_pct", "main_outlet_area_m2", "nearest_retention_element_m")


def _outlet_params(ctx: RuleContext) -> dict[str, ParamValue]:
    assert ctx.terrain is not None
    main = ctx.terrain.outlets[0]
    return {
        "direction": main.direction or "",
        "outlet_count": len(ctx.terrain.outlets),
        "slope_mean_pct": ctx.terrain.slope_mean_pct,
        "contributing_ha": round(main.contributing_area_m2 / 10_000, 1),
    }


def _outlet_locations(ctx: RuleContext) -> list[Location]:
    assert ctx.terrain is not None
    return [Location(kind="outlet", geometry=o.geometry) for o in ctx.terrain.outlets]


# --- 4. concentrated flow line across the parcel: grassed waterway --------------------------------


def _flow_paths(ctx: RuleContext) -> list[RetentionSite]:
    t = ctx.terrain
    if t is None or t.slope_mean_pct < FLOW_PATH_MIN_SLOPE_PCT:
        return []
    return [f for f in t.flow_paths if f.contributing_area_m2 >= FLOW_PATH_MIN_CONTRIBUTING_M2]


def _flow_condition(ctx: RuleContext) -> bool:
    return bool(_flow_paths(ctx)) and bool(water_need(ctx))


def _flow_evidence(ctx: RuleContext) -> list[Indicator]:
    paths = _flow_paths(ctx)
    if not paths:
        return []
    src, conf, reason = _terrain_meta(ctx)
    return [
        indicator(
            "flow_path_contributing_area_m2",
            paths[0].contributing_area_m2,
            "m²",
            src,
            level=conf,
            reason=reason,
            step=100,
        ),
        *found(ctx, "slope_mean_pct"),
        *water_need(ctx),
    ]


def _flow_params(ctx: RuleContext) -> dict[str, ParamValue]:
    paths = _flow_paths(ctx)
    return {"count": len(paths), "contributing_ha": round(paths[0].contributing_area_m2 / 10_000, 1)}


def _flow_locations(ctx: RuleContext) -> list[Location]:
    return [Location(kind="flow_path", geometry=f.geometry) for f in _flow_paths(ctx)]


# --- 5. no trees nearby + light soil: mid-field tree belt -------------------------------------------


def _nearest_trees_m(ctx: RuleContext) -> float | None:
    if ctx.hydro is not None:
        return ctx.hydro.nearest_m.get("trees")
    s = landcover_surroundings(ctx.inputs)
    return surroundings_nearest_m(s, "trees") if s is not None else None


def _trees_known(ctx: RuleContext) -> bool:
    """Trees are known from OSM, or (OSM down) from the WorldCover ring around the parcel (Q4)."""
    return ctx.hydro is not None or landcover_surroundings(ctx.inputs) is not None


def _trees_condition(ctx: RuleContext) -> bool:
    if not _trees_known(ctx):
        return False
    nearest = _nearest_trees_m(ctx)
    no_trees = nearest is None or nearest > RETENTION_RADIUS_M
    return no_trees and bool(light_soil(ctx)) and bool(water_need(ctx))


def _trees_evidence(ctx: RuleContext) -> list[Indicator]:
    nearest = _nearest_trees_m(ctx)
    if ctx.hydro is None:
        s = landcover_surroundings(ctx.inputs)
        assert s is not None
        src = computed_source(ctx.inputs.landcover.source)
        tree_ind = (
            indicator(
                "nearest_trees_m", nearest, "m", src, level=Confidence.LOW, reason="worldcover", step=10
            )
            if nearest is not None
            else indicator(
                "trees_share_surroundings_pct",
                s.shares_pct.get("trees", 0.0),
                "%",
                src,
                level=Confidence.LOW,
                reason="worldcover",
                step=0.1,
            )
        )
        return [tree_ind, *light_soil(ctx), *water_need(ctx)]
    src = _hydro_source(ctx)
    tree_ind = (
        indicator("nearest_trees_m", nearest, "m", src, level=Confidence.LOW, reason="osm", step=10)
        if nearest is not None
        else indicator(
            "trees_within_radius_count",
            ctx.hydro.counts.get("trees", 0),
            "szt.",
            src,
            level=Confidence.LOW,
            reason="osm",
        )
    )
    return [tree_ind, *light_soil(ctx), *water_need(ctx)]


def _trees_params(ctx: RuleContext) -> dict[str, ParamValue]:
    nearest = _nearest_trees_m(ctx)
    if ctx.hydro is not None:
        radius = ctx.hydro.radius_m
    else:
        s = landcover_surroundings(ctx.inputs)
        radius = int(s.radius_m) if s is not None else 0
    return {"nearest_trees_m": round(nearest, -1) if nearest is not None else 0, "radius_m": radius}


# --- 6. wetland or pond nearby: protect it, do not drain -------------------------------------------


def _protected(ctx: RuleContext) -> list[HydroFeature]:
    if ctx.hydro is None:
        return []
    return [f for f in ctx.hydro.features if f.kind in PROTECT_KINDS and f.distance_m <= PROTECT_RADIUS_M]


def _protected_landcover(ctx: RuleContext) -> tuple[str, float] | None:
    """(kind, distance) of the nearest wetland or open water in the WorldCover ring when OSM is down (Q4)."""
    s = landcover_surroundings(ctx.inputs)
    if s is None:
        return None
    near = [
        (kind, d)
        for kind in PROTECT_KINDS
        if (d := surroundings_nearest_m(s, kind)) is not None and d <= PROTECT_RADIUS_M
    ]
    return min(near, key=lambda kd: kd[1]) if near else None


def _protect_condition(ctx: RuleContext) -> bool:
    return bool(_protected(ctx)) or _protected_landcover(ctx) is not None


def _protect_evidence(ctx: RuleContext) -> list[Indicator]:
    feats = _protected(ctx)
    if not feats:
        lc = _protected_landcover(ctx)
        if lc is None:
            return []
        src = computed_source(ctx.inputs.landcover.source)
        return [
            indicator(
                "nearest_wetland_or_pond_m",
                lc[1],
                "m",
                src,
                level=Confidence.LOW,
                reason="worldcover",
                step=10,
            )
        ]
    src = _hydro_source(ctx)
    return [
        indicator(
            "nearest_wetland_or_pond_m",
            min(f.distance_m for f in feats),
            "m",
            src,
            level=Confidence.LOW,
            reason="osm",
            step=10,
        ),
        indicator("wetlands_and_ponds_count", len(feats), "szt.", src, level=Confidence.LOW, reason="osm"),
    ]


def _protect_params(ctx: RuleContext) -> dict[str, ParamValue]:
    feats = _protected(ctx)
    if not feats:
        lc = _protected_landcover(ctx)
        assert lc is not None
        kind = "open_water" if lc[0] == "water_body" else lc[0]
        return {"kind": kind, "distance_m": round(lc[1], -1), "count": 1, "radius_m": int(PROTECT_RADIUS_M)}
    nearest = min(feats, key=lambda f: f.distance_m)
    return {
        "kind": nearest.kind,
        "distance_m": round(nearest.distance_m, -1),
        "count": len(feats),
        "radius_m": int(PROTECT_RADIUS_M),
    }


def _protect_locations(ctx: RuleContext) -> list[Location]:
    return [Location(kind=f.kind, geometry=f.geometry) for f in _protected(ctx)]


RETENTION_RULES: list[Rule] = [
    Rule(
        "ditch_check_dam",
        Category.RETENTION,
        1,
        _ditch_condition,
        _ditch_evidence,
        _ditch_params,
        _ditch_locations,
    ),
    Rule(
        "depression_retention",
        Category.RETENTION,
        2,
        _depression_condition,
        _depression_evidence,
        _depression_params,
        _depression_locations,
    ),
    Rule(
        "outlet_buffer_strip",
        Category.RETENTION,
        3,
        _outlet_condition,
        _outlet_evidence,
        _outlet_params,
        _outlet_locations,
    ),
    Rule(
        "grassed_flow_path",
        Category.RETENTION,
        4,
        _flow_condition,
        _flow_evidence,
        _flow_params,
        _flow_locations,
    ),
    Rule("midfield_trees", Category.RETENTION, 5, _trees_condition, _trees_evidence, _trees_params),
    Rule(
        "protect_wetlands",
        Category.RETENTION,
        6,
        _protect_condition,
        _protect_evidence,
        _protect_params,
        _protect_locations,
    ),
]
