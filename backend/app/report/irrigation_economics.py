"""Report block G10: irrigation technology for the parcel and whether it pays off. Pure, no I/O.

The technology is chosen first (it sets the field efficiency the seasonal water plan uses for gross water),
then the economics use the plan's typical-year need and the assessment's root-zone balance.
"""

from dataclasses import dataclass
from typing import Literal

from shapely.errors import ShapelyError

from app.analysis.assessment import Assessment
from app.analysis.common import round_to
from app.analysis.context import AnalysisInputs, computed_source
from app.analysis.economics import IrrigationEconomics, irrigation_economics
from app.analysis.parcel_shape import parcel_shape_metrics
from app.analysis.water_plan import WaterPlanResult
from app.crops.economics import load_economics
from app.recommendations.irrigation_tech import (
    REEL_HOSE_M,
    REEL_WETTED_WIDTH_M,
    SMALL_AREA_HA,
    TechChoice,
    choose_technology,
)
from app.report.models import EconomicsAssumptions, EconomicsSeason, IrrigationEconomicsView, WaterPlan
from app.report.texts import render_text
from app.sources.base import METRIC_CRS, parcel_shape, to_crs

TECH_LABELS: dict[str, str] = {
    "reel": "Deszczownia szpulowa",
    "pivot": "Deszczownia obrotowa lub liniowa",
    "drip": "Nawadnianie kroplowe",
    "none": "Bez stałej instalacji",
}
VERDICT_LABELS: dict[str, str] = {
    "profitable": "Opłacalne",
    "borderline": "Na granicy opłacalności",
    "unprofitable": "Nieopłacalne",
    "unknown": "Nie oceniono",
}
ASSUMPTIONS_PL: list[str] = [
    "Plon bez strat z suszy przyjmujemy jako średni plon w Polsce wg GUS (2024) — zmień go na plon ze "
    "swojego pola.",
    "Ceny: od przeciętnej ceny skupu do ceny targowiskowej wg GUS (grudzień 2024, bez VAT).",
    "Strata plonu w każdym sezonie z niedoboru wody na tej działce: metoda FAO-33 (współczynnik "
    "reakcji plonu na brak wody Ky), z dobowego bilansu wody w glebie bez nawadniania. Przyjmujemy, "
    "że nawadnianie usuwa całą stratę — to górna granica korzyści.",
    "Koszt instalacji, ujęcia wody i pompowania to założenia zespołu (szerokie widełki), bo nie "
    "znaleźliśmy otwartego, aktualnego cennika — wpisz ofertę z okolicy. Bez dotacji i bez podatków.",
    "Dobór maszyny według powierzchni i szerokości działki to reguła orientacyjna (progi: założenia "
    "zespołu); o ostatecznym wyborze decyduje dostęp do wody i oferta.",
    "Werdykt „opłacalne” lub „nieopłacalne” pada tylko wtedy, gdy zgadzają się z nim całe widełki cen "
    "i kosztów; w pozostałych przypadkach — „na granicy”.",
]


NEED_STEP_MM = 5.0  # = outlook.SEASON_WATER_STEP_MM (not imported: outlook imports this module)


def technology_for(inputs: AnalysisInputs, plan: WaterPlanResult | None) -> TechChoice:
    try:
        shape = parcel_shape_metrics(to_crs(parcel_shape(inputs.parcel), METRIC_CRS))
    except (ValueError, TypeError, AttributeError, ShapelyError):
        shape = None  # malformed geometry: choose by crop and area only (said in the text)
    # The rounded value the water plan prints (5 mm), so the threshold and the sentence agree with it (Q2).
    need = round_to(plan.season_p80_mm, NEED_STEP_MM) if plan is not None else None
    return choose_technology(inputs.crop, inputs.parcel.area_ha, shape, need)


def _zl(value: float | None) -> float | None:
    return round_to(value, 50.0 if value is None or value < 10_000 else 100.0)


def _area(value: float | None) -> tuple[float | None, float]:
    """Break-even area as stated: 1 ha steps from 10 ha, 0.5 ha below, 0.1 ha under 0.5 ha (never "0 ha")."""
    if value is None:
        return None, 0.5
    step = 1.0 if value >= 10 else 0.5 if value >= 0.5 else 0.1
    return max(step, round_to(value, step) or 0.0), step


Status = Literal["ok", "no_balance", "no_crop_data", "no_price", "not_needed"]


@dataclass(frozen=True)
class _Rounded:
    """Values as the report states them: the JSON fields and the sentences use the same numbers."""

    efficiency_pct: int
    length_m: float | None
    width_m: float | None
    technology_pl: str
    mean_loss_pct: float | None
    water_m3_ha: float | None
    benefit_zl_ha_low: float | None
    benefit_zl_ha_high: float | None
    cost_zl_ha_low: float | None
    cost_zl_ha_high: float | None
    break_even_area_ha: float | None
    area_step: float


def economics_view(
    choice: TechChoice,
    inputs: AnalysisInputs,
    a: Assessment,
    plan_view: WaterPlan | None,
    plan: WaterPlanResult | None,
) -> IrrigationEconomicsView | None:
    """Only after a complete assessment (rule 2)."""
    if not a.complete or a.current is None:
        return None
    catalog = load_economics()
    tech = None if choice.tech == "none" else choice.tech
    e: IrrigationEconomics = irrigation_economics(
        crop=inputs.crop,
        catalog=catalog,
        tech=tech,
        efficiency=choice.efficiency,
        area_ha=inputs.water_area_ha,
        balance=a.root_zone,
        years=plan.years if plan is not None else [],
        typical_need_mm=plan_view.season_median_mm if plan_view is not None else None,
        history=a.history,
    )
    shape = choice.shape
    total = e.costs.total if e.costs is not None else None
    break_even, area_step = _area(e.break_even_area_ha)
    v = _Rounded(
        efficiency_pct=round(100 * choice.efficiency),
        length_m=round_to(shape.length_m, 10.0) if shape is not None else None,
        width_m=round_to(shape.width_m, 10.0 if shape.width_m >= 50 else 1.0) if shape is not None else None,
        technology_pl=TECH_LABELS[choice.tech],
        mean_loss_pct=round_to(100 * e.mean_loss_share, 1.0) if e.mean_loss_share is not None else None,
        water_m3_ha=round_to(e.water_m3_ha, 10.0),
        benefit_zl_ha_low=_zl(e.benefit.low) if e.benefit is not None else None,
        benefit_zl_ha_high=_zl(e.benefit.high) if e.benefit is not None else None,
        cost_zl_ha_low=_zl(total.low) if total is not None else None,
        cost_zl_ha_high=_zl(total.high) if total is not None else None,
        break_even_area_ha=break_even,
        area_step=area_step,
    )
    crop = inputs.crop.name_pl.lower()
    tech_text, _ = render_text(
        "blocks/irrigation_tech.j2",
        t=choice,
        v=v,
        reel_width_m=REEL_WETTED_WIDTH_M,
        reel_hose_m=REEL_HOSE_M,
        small_area_ha=SMALL_AREA_HA,
    )
    econ_text, _ = render_text(
        "blocks/irrigation_economics.j2", e=e, v=v, crop=crop, farm_n=inputs.farm_parcels
    )
    ce = e.crop
    t = catalog.technologies.get(tech) if tech is not None else None
    assumptions = EconomicsAssumptions(
        yield_t_ha=ce.yield_t_ha if ce is not None else None,
        price_zl_t_low=ce.price_zl_t.low if ce is not None and ce.price_zl_t is not None else None,
        price_zl_t_high=ce.price_zl_t.high if ce is not None and ce.price_zl_t is not None else None,
        ky=ce.ky if ce is not None else None,
        capex_zl_ha_low=t.capex_zl_ha.low if t is not None else None,
        capex_zl_ha_high=t.capex_zl_ha.high if t is not None else None,
        lifetime_years=t.lifetime_years if t is not None else None,
        water_source_zl_low=catalog.water_source.capex_zl.low,
        water_source_zl_high=catalog.water_source.capex_zl.high,
        water_source_lifetime_years=catalog.water_source.lifetime_years,
        operating_zl_m3_low=catalog.operating_zl_m3.low,
        operating_zl_m3_high=catalog.operating_zl_m3.high,
    )
    assumptions_pl = list(ASSUMPTIONS_PL)
    if ce is not None and ce.ky_from is not None:
        assumptions_pl.append(
            "FAO-33 nie podaje współczynnika Ky dla tej uprawy — przyjęliśmy wartość dla "
            + ("pszenicy ozimej." if ce.ky_from == "winter_wheat" else "pszenicy jarej.")
        )
    srcs = catalog.sources
    status: Status = e.status.value
    return IrrigationEconomicsView(
        technology=choice.tech,
        technology_pl=TECH_LABELS[choice.tech],
        technology_text_pl=tech_text,
        efficiency_pct=v.efficiency_pct,
        length_m=v.length_m,
        width_m=v.width_m,
        status=status,
        verdict=e.verdict.value,
        verdict_pl=VERDICT_LABELS[e.verdict.value],
        text_pl=econ_text,
        area_ha=inputs.water_area_ha,
        mean_loss_share=round(e.mean_loss_share, 4) if e.mean_loss_share is not None else None,
        seasons=[EconomicsSeason(year=s.year, loss_pct=round(100 * s.loss_share, 1)) for s in e.seasons],
        critical_deficit_years=e.critical_deficit_years,
        years_counted=e.years_counted,
        water_m3_ha=v.water_m3_ha,
        benefit_zl_ha_low=v.benefit_zl_ha_low,
        benefit_zl_ha_high=v.benefit_zl_ha_high,
        cost_zl_ha_low=v.cost_zl_ha_low,
        cost_zl_ha_high=v.cost_zl_ha_high,
        break_even_area_ha=break_even,
        break_even_never=e.break_even_never,
        assumptions=assumptions,
        assumptions_pl=assumptions_pl,
        source="; ".join(
            [
                computed_source(inputs.weather.source, inputs.soil.source, "GUGiK ULDK (kształt działki)"),
                srcs["yields"],
                srcs["prices"],
                srcs["ky"],
                srcs["efficiency"],
                "koszty: " + srcs["costs"],
            ]
        ),
    )
