"""Shared conditions and evidence of the recommendation rules. Pure, no I/O."""

from datetime import date

from app.analysis.causes import LOW_TAW_PER_M_MM
from app.analysis.common import DeficitLevel, indicator
from app.analysis.context import computed_source
from app.analysis.history import RISK_FREQUENCY
from app.analysis.soil import SoilCategory
from app.core.models import Confidence, Indicator, Period
from app.recommendations.models import RuleContext

# Deficits are "recurring" when at least half of the 10 previous years had a deficit month. A lower share
# (≥ 30 %) would hold almost everywhere in Poland with the root-zone method and keep every rule open.
RECURRING_SHARE = 0.5
LIGHT_SOIL_CATEGORIES = (SoilCategory.I, SoilCategory.II)
# Indicators that show the current deficit, per signal that set the level (CurrentState.basis).
BASIS_KEYS: dict[str, tuple[str, ...]] = {
    "root_zone": ("root_zone_depletion_pct",),
    "kbw_percentile": ("kbw_60d_mm", "kbw_60d_pct"),
    "precip_percentile": ("precip_30d_mm", "precip_30d_pct"),
    "recharge_percentile": ("recharge_kbw_mm", "recharge_kbw_pct"),
    "iung": ("kbw_iung_period_mm",),
}


def find_indicator(ctx: RuleContext, key: str) -> Indicator | None:
    """An indicator already computed by the assessment (same value, source and period as in the report)."""
    a = ctx.assessment
    pools: list[list[Indicator]] = [ctx.current.indicators]
    pools += [c.evidence for c in a.causes]
    if a.vulnerability is not None:
        pools += [c.indicators for c in a.vulnerability.components]
    for pool in pools:
        for ind in pool:
            if ind.key == key and ind.value is not None:
                return ind
    return None


def found(ctx: RuleContext, *keys: str) -> list[Indicator]:
    return [i for k in keys if (i := find_indicator(ctx, k)) is not None]


def deficit_now(ctx: RuleContext) -> bool:
    return ctx.current.level.rank >= DeficitLevel.LIGHT.rank


def recurring_deficit(ctx: RuleContext) -> bool:
    share = ctx.history.deficit_year_share if ctx.history is not None else None
    return share is not None and share >= RECURRING_SHARE


def water_need(ctx: RuleContext) -> list[Indicator]:
    """Evidence that the parcel needs more water kept on it: a deficit now or deficits in ≥ half of 10 years.

    Empty list = no need shown by the data.
    """
    out: list[Indicator] = []
    if deficit_now(ctx):
        for basis in ctx.current.basis:
            out += found(ctx, *BASIS_KEYS.get(basis, ()))
    if recurring_deficit(ctx):
        out += found(ctx, "deficit_year_share_pct")
    return out


def light_soil(ctx: RuleContext) -> list[Indicator]:
    """Evidence of a light soil that holds little water (IUNG category I–II or TAW < 100 mm per metre)."""
    soil = ctx.soil
    if soil is None:
        return []
    out: list[Indicator] = []
    if soil.category in LIGHT_SOIL_CATEGORIES:
        out += found(ctx, "soil_category")
    if soil.taw_per_m_mm is not None and soil.taw_per_m_mm < LOW_TAW_PER_M_MM:
        out += found(ctx, "taw_per_m_mm")
    return out


def month_frequencies(ctx: RuleContext, months: list[int] | tuple[int, ...]) -> dict[int, float]:
    """Share of the 10 previous years with a deficit in each of the given months (only months with data)."""
    if ctx.history is None:
        return {}
    out: dict[int, float] = {}
    for f in ctx.history.months:
        if f.month in months and f.frequency is not None:
            out[f.month] = f.frequency
    return out


def recurring_months(ctx: RuleContext, months: list[int] | tuple[int, ...]) -> dict[int, float]:
    return {m: f for m, f in month_frequencies(ctx, months).items() if f >= RISK_FREQUENCY}


def month_indicators(ctx: RuleContext, freqs: dict[int, float]) -> list[Indicator]:
    """Deficit frequency per month; reuses the assessment's indicator when it already exists.

    Monthly deficits exist only with the root-zone balance (weather + soil), hence source and confidence.
    """
    src = computed_source(ctx.inputs.weather.source, ctx.inputs.soil.source)
    years = [y.year for y in ctx.history.years] if ctx.history is not None else []
    period = Period(start=date(min(years), 1, 1), end=date(max(years), 12, 31)) if years else None
    out: list[Indicator] = []
    for m, f in sorted(freqs.items()):
        key = f"deficit_frequency_month_{m:02d}_pct"
        ind = find_indicator(ctx, key) or indicator(
            key, 100 * f, "%", src, level=Confidence.MEDIUM, reason="root_zone"
        )
        # The frequency covers the 10 previous calendar years (CLAUDE.md rule 5: every number has a date).
        out.append(ind if ind.period is not None else ind.model_copy(update={"period": period}))
    return out


def is_grassland(ctx: RuleContext) -> bool:
    return ctx.crop.id == "grassland"
