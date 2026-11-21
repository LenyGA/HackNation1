"""Agrotechnical rules: field practices that raise soil water retention and cut losses. Pure, no I/O.

Thresholds are documented in docs/METHODOLOGY.md (section 8).
"""

from app.analysis.causes import LOW_SOC_G_PER_KG
from app.core.models import Indicator
from app.recommendations.common import (
    deficit_now,
    found,
    is_grassland,
    light_soil,
    month_indicators,
    recurring_months,
    water_need,
)
from app.recommendations.models import Category, ParamValue, Rule, RuleContext

CONTOUR_SLOPE_PCT = 3.0
# Crops that leave straw or stalks after harvest (the rest are root crops and vegetables).
STRAW_CROPS = {"winter_wheat", "rye", "spring_barley", "winter_rapeseed", "maize"}
PLANTED_CROPS = {"potato"}
SPRING_MONTHS = (4, 5)
SUMMER_MONTHS = (6, 7, 8)
GRASSLAND_MONTHS = (5, 6, 7, 8)


def _months_param(months: list[int]) -> str:
    return ",".join(str(m) for m in sorted(months))


# --- 1. low organic carbon: manure, straw, catch crops ---------------------------------------------


def _soc(ctx: RuleContext) -> float | None:
    """Topsoil organic carbon rounded as shown to the farmer, so text, evidence and condition agree."""
    soc = ctx.soil.topsoil_soc_g_per_kg if ctx.soil is not None else None
    return None if soc is None else round(soc, 1)


def _om_condition(ctx: RuleContext) -> bool:
    soc = _soc(ctx)
    return soc is not None and soc < LOW_SOC_G_PER_KG


def _om_evidence(ctx: RuleContext) -> list[Indicator]:
    return found(ctx, "soc_topsoil_g_per_kg")


def _om_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {
        "soc_g_per_kg": _soc(ctx) or 0.0,
        "threshold_g_per_kg": LOW_SOC_G_PER_KG,
        "grassland": int(is_grassland(ctx)),
    }


# --- 2. light soil + recurring spring deficits: reduced tillage and mulch --------------------------


def _mulch_condition(ctx: RuleContext) -> bool:
    return not is_grassland(ctx) and bool(light_soil(ctx)) and bool(recurring_months(ctx, SPRING_MONTHS))


def _mulch_evidence(ctx: RuleContext) -> list[Indicator]:
    return light_soil(ctx) + month_indicators(ctx, recurring_months(ctx, SPRING_MONTHS))


def _mulch_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {"months": _months_param(list(recurring_months(ctx, SPRING_MONTHS)))}


# --- 3. slope: tillage and sowing across the slope -------------------------------------------------


def _contour_condition(ctx: RuleContext) -> bool:
    t = ctx.terrain
    return not is_grassland(ctx) and t is not None and t.slope_mean_pct >= CONTOUR_SLOPE_PCT


def _contour_evidence(ctx: RuleContext) -> list[Indicator]:
    return found(ctx, "slope_mean_pct", "slope_max_pct")


def _contour_params(ctx: RuleContext) -> dict[str, ParamValue]:
    assert ctx.terrain is not None
    return {"slope_mean_pct": ctx.terrain.slope_mean_pct, "aspect": ctx.terrain.aspect or ""}


# --- 4. critical phase falls in the riskiest months: earlier variety or sowing date ----------------


def _critical_risk(ctx: RuleContext) -> list[int]:
    return list(ctx.history.critical_risk_months) if ctx.history is not None else []


def _timing_condition(ctx: RuleContext) -> bool:
    return not is_grassland(ctx) and bool(_critical_risk(ctx))


def _timing_evidence(ctx: RuleContext) -> list[Indicator]:
    months = _critical_risk(ctx)
    return month_indicators(ctx, recurring_months(ctx, tuple(months)))


def _risky_phases(ctx: RuleContext) -> str:
    """Critical phases that overlap the risky months (not every critical phase of the crop)."""
    risky = set(_critical_risk(ctx))
    crop = ctx.crop
    names = []
    for period in crop.critical_periods:
        single = crop.model_copy(update={"critical_periods": [period]})
        if single.critical_months() & risky:
            names.append(period.name_pl)
    return "; ".join(names)


def _timing_params(ctx: RuleContext) -> dict[str, ParamValue]:
    crop = ctx.crop
    timing = "winter" if crop.winter else "planted" if crop.id in PLANTED_CROPS else "sown"
    return {
        "months": _months_param(_critical_risk(ctx)),
        "phase": _risky_phases(ctx),
        "crop": crop.name_pl.lower(),
        "timing": timing,
    }


# --- 5. spring crop leaves the field bare in winter: winter catch crop ------------------------------


def _cover_condition(ctx: RuleContext) -> bool:
    if ctx.crop.winter or is_grassland(ctx):
        return False
    return bool(water_need(ctx)) or bool(light_soil(ctx))


def _cover_evidence(ctx: RuleContext) -> list[Indicator]:
    return water_need(ctx) + light_soil(ctx)


def _cover_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {"crop": ctx.crop.name_pl.lower()}


# --- 6. recurring summer deficits: keep crop residues, shallow stubble tillage ---------------------


def _residue_condition(ctx: RuleContext) -> bool:
    return not is_grassland(ctx) and bool(recurring_months(ctx, SUMMER_MONTHS))


def _residue_evidence(ctx: RuleContext) -> list[Indicator]:
    return month_indicators(ctx, recurring_months(ctx, SUMMER_MONTHS))


def _residue_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {
        "months": _months_param(list(recurring_months(ctx, SUMMER_MONTHS))),
        "straw": int(ctx.crop.id in STRAW_CROPS),
    }


# --- 7. grassland under deficit: higher cut, no cutting in drought ---------------------------------


def _grass_deficit_now(ctx: RuleContext) -> bool:
    # Off-season a "deficit" means poor winter recharge; telling the farmer about mowing then is misleading.
    return ctx.current.in_vegetation and deficit_now(ctx)


def _grass_condition(ctx: RuleContext) -> bool:
    return is_grassland(ctx) and (_grass_deficit_now(ctx) or bool(recurring_months(ctx, GRASSLAND_MONTHS)))


def _grass_evidence(ctx: RuleContext) -> list[Indicator]:
    out = water_need(ctx) if _grass_deficit_now(ctx) else []
    return out + month_indicators(ctx, recurring_months(ctx, GRASSLAND_MONTHS))


def _grass_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return {
        "months": _months_param(list(recurring_months(ctx, GRASSLAND_MONTHS))),
        "deficit_now": int(_grass_deficit_now(ctx)),
    }


AGROTECH_RULES: list[Rule] = [
    Rule("organic_matter", Category.AGROTECH, 1, _om_condition, _om_evidence, _om_params),
    Rule("reduced_tillage_mulch", Category.AGROTECH, 2, _mulch_condition, _mulch_evidence, _mulch_params),
    Rule("contour_tillage", Category.AGROTECH, 3, _contour_condition, _contour_evidence, _contour_params),
    Rule("crop_timing_variety", Category.AGROTECH, 4, _timing_condition, _timing_evidence, _timing_params),
    Rule("winter_cover_crop", Category.AGROTECH, 5, _cover_condition, _cover_evidence, _cover_params),
    Rule("crop_residues", Category.AGROTECH, 6, _residue_condition, _residue_evidence, _residue_params),
    Rule("grassland_cutting", Category.AGROTECH, 7, _grass_condition, _grass_evidence, _grass_params),
]
