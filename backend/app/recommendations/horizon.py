"""When to act on a recommendation: now (from the analysis date) or before the next season (plan M3.5, R5).

Pure, no I/O. Decided from the analysis date, the vegetation period and the crop's field phase on that date
(typical crop calendar), never from the text. Main-crop sowing advice is never "now": in July it would be too
late, and the only sowing that fits after harvest is a catch crop, which is a separate rule named as such.
"""

from datetime import date

from app.recommendations.models import Horizon, RuleContext

# Catch crops (międzyplon ścierniskowy) are sown from the harvest of the main crop until early September;
# winter catch crops (żyto, wyka ozima) until the end of September (typical Polish practice).
CATCH_CROP_MONTHS = (7, 8, 9)
# Check dams hold the winter and spring recharge (snowmelt, low evaporation): October to March.
DITCH_HOLD_MONTHS = (10, 11, 12, 1, 2, 3)
# Stubble tillage and leaving residues right after the harvest (until the autumn tillage).
RESIDUE_MONTHS = (7, 8, 9, 10)

# Field works or structures prepared for the next growing season, whatever the date.
SEASON_RULES = frozenset(
    {
        "depression_retention",
        "outlet_buffer_strip",
        "grassed_flow_path",
        "midfield_trees",
        "organic_matter",
        "reduced_tillage_mulch",
        "contour_tillage",
        "crop_timing_variety",  # variety or main-crop sowing date: only for the next sowing
    }
)


# Ripening counts as "after harvest" only in its last days, when stubble works can be prepared.
HARVEST_LEAD_DAYS = 10


def _after_harvest(ctx: RuleContext, day: date) -> bool:
    phase = ctx.crop.field_phase(day)
    if phase == "after_harvest":
        return True
    return phase == "ripening" and (ctx.crop.season_end(day) - day).days <= HARVEST_LEAD_DAYS


def horizon(rule_id: str, ctx: RuleContext) -> Horizon:
    day = ctx.inputs.analysis_date
    current = ctx.assessment.current
    in_season_on_field = current is not None and current.in_vegetation and current.crop_on_field
    if rule_id in SEASON_RULES:
        return Horizon.SEASON
    if rule_id == "protect_wetlands":
        return Horizon.NOW  # do not drain or plough the wetland: applies at any time
    if rule_id == "ditch_check_dam":
        return Horizon.NOW if day.month in DITCH_HOLD_MONTHS else Horizon.SEASON
    if rule_id == "winter_cover_crop":
        return Horizon.NOW if day.month in CATCH_CROP_MONTHS and _after_harvest(ctx, day) else Horizon.SEASON
    if rule_id == "crop_residues":
        return Horizon.NOW if day.month in RESIDUE_MONTHS and _after_harvest(ctx, day) else Horizon.SEASON
    if rule_id in ("grassland_cutting", "irrigation"):
        return Horizon.NOW if in_season_on_field else Horizon.SEASON
    return Horizon.SEASON
