"""Does irrigation pay on this parcel? (G10, plan33 M5.3). Pure, no I/O.

Benefit = the yield the crop lost to water shortage in the last 10 seasons on THIS parcel, valued at GUS
prices. Yield loss per season from FAO-33 (Doorenbos and Kassam 1979):
    1 − Ya/Ym = Ky · (1 − ETa/ETc),
with ETa/ETc summed over the crop's days on the field in March–October from the root-zone balance without
irrigation (the same balance as the assessment). Irrigation at the management allowed depletion keeps Ks = 1,
so with irrigation the loss is taken as zero (an upper estimate of the benefit). Ym = the national average
yield (GUS 2024) — a reference, not this farm's yield; the farmer can change it in the browser.

Cost per ha and year = installation / lifetime + water source (once per farm) / lifetime / area
+ running cost per m³ × gross water of a typical year (net need / field efficiency of the chosen method).

Verdict on ranges (prices: purchase → market place; costs: wide assumptions): profitable only when even the
lowest benefit covers the highest cost, unprofitable when even the highest benefit is below the lowest cost,
otherwise borderline. Break-even area from mid values: the area from which the water source pays off.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.analysis.history import HistoryResult
from app.analysis.water_balance import RootZoneBalance
from app.crops.catalog import Crop
from app.crops.economics import CropEconomics, EconomicsCatalog, Range, TechId

MAX_GAP_SHARE = 0.1
MIN_SEASONS = 5
# Mean yield loss below this share: irrigation has nothing to save (said as "not needed", not a zero benefit).
MIN_LOSS_SHARE = 0.01


class EconomicsStatus(StrEnum):
    OK = "ok"
    NO_BALANCE = "no_balance"  # no soil data or too few seasons: losses cannot be computed
    NO_CROP_DATA = "no_crop_data"  # no Ky or yield for this crop in the sources
    NO_PRICE = "no_price"  # losses known, no published price: the farmer enters it
    NOT_NEEDED = "not_needed"  # no installation chosen (low need) or no loss to save


class Verdict(StrEnum):
    PROFITABLE = "profitable"
    BORDERLINE = "borderline"
    UNPROFITABLE = "unprofitable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SeasonLoss:
    year: int
    et_ratio: float  # ETa / ETc in the season
    loss_share: float  # 1 − Ya/Ym


@dataclass(frozen=True)
class CostParts:
    installation: Range  # zł/ha/year
    water_source: Range  # zł/ha/year at this area
    water: Range  # zł/ha/year, typical year

    @property
    def total(self) -> Range:
        parts = (self.installation, self.water_source, self.water)
        return Range(low=sum(p.low for p in parts), high=sum(p.high for p in parts))


@dataclass(frozen=True)
class IrrigationEconomics:
    status: EconomicsStatus
    verdict: Verdict
    tech: TechId | None
    area_ha: float
    seasons: list[SeasonLoss]
    mean_loss_share: float | None
    critical_deficit_years: int | None  # seasons with a water deficit in a month critical for the crop
    years_counted: int | None
    crop: CropEconomics | None
    water_m3_ha: float | None  # gross, typical year
    benefit: Range | None  # zł/ha/year
    costs: CostParts | None
    break_even_area_ha: float | None
    break_even_never: bool  # even a very large farm would not pay off (mid values)


def season_losses(balance: RootZoneBalance, years: list[int], ky: float) -> list[SeasonLoss]:
    out: list[SeasonLoss] = []
    for y in years:
        days = [b for b in balance.between(date(y, 3, 1), date(y, 10, 31)) if b.in_season]
        if not days:
            continue
        gaps = sum(1 for b in days if b.gap)
        if gaps > MAX_GAP_SHARE * len(days):
            continue
        potential = sum(b.kc * b.et0_mm for b in days if b.et0_mm is not None and b.etc_mm is not None)
        actual = sum(b.etc_mm for b in days if b.et0_mm is not None and b.etc_mm is not None)
        if potential <= 0:
            continue
        ratio = min(1.0, actual / potential)
        out.append(SeasonLoss(y, ratio, min(1.0, max(0.0, ky * (1.0 - ratio)))))
    return out


def critical_deficit_years(history: HistoryResult | None, crop: Crop) -> tuple[int | None, int | None]:
    if history is None:
        return None, None
    critical = crop.critical_months()
    counted = deficit = 0
    for y in history.years:
        outcomes = [y.months[m].deficit for m in critical if m in y.months]
        known = [o for o in outcomes if o is not None]
        if not known:
            continue
        counted += 1
        deficit += int(any(known))
    return (deficit, counted) if counted else (None, None)


def irrigation_economics(
    *,
    crop: Crop,
    catalog: EconomicsCatalog,
    tech: TechId | None,
    efficiency: float,
    area_ha: float,
    balance: RootZoneBalance | None,
    years: list[int],
    typical_need_mm: float | None,
    history: HistoryResult | None,
) -> IrrigationEconomics:
    ce = catalog.crops.get(crop.id)
    crit, counted = critical_deficit_years(history, crop)

    def result(
        status: EconomicsStatus,
        seasons: list[SeasonLoss] | None = None,
        mean: float | None = None,
        *,
        verdict: Verdict = Verdict.UNKNOWN,
        water_m3_ha: float | None = None,
        benefit: Range | None = None,
        costs: CostParts | None = None,
        break_even_area_ha: float | None = None,
        break_even_never: bool = False,
    ) -> IrrigationEconomics:
        return IrrigationEconomics(
            status=status,
            verdict=verdict,
            tech=tech,
            area_ha=area_ha,
            seasons=seasons or [],
            mean_loss_share=mean,
            critical_deficit_years=crit,
            years_counted=counted,
            crop=ce,
            water_m3_ha=water_m3_ha,
            benefit=benefit,
            costs=costs,
            break_even_area_ha=break_even_area_ha,
            break_even_never=break_even_never,
        )

    if tech is None:
        return result(EconomicsStatus.NOT_NEEDED)
    if ce is None or ce.ky is None or ce.yield_t_ha is None:
        return result(EconomicsStatus.NO_CROP_DATA)
    if balance is None:
        return result(EconomicsStatus.NO_BALANCE)
    seasons = season_losses(balance, years, ce.ky)
    if len(seasons) < MIN_SEASONS or typical_need_mm is None:
        return result(EconomicsStatus.NO_BALANCE, seasons)
    mean = sum(s.loss_share for s in seasons) / len(seasons)
    if mean < MIN_LOSS_SHARE:
        return result(EconomicsStatus.NOT_NEEDED, seasons, mean)

    water_m3_ha = typical_need_mm * 10.0 / efficiency  # 1 mm on 1 ha = 10 m³
    t = catalog.technologies[tech]
    src = catalog.water_source
    op = catalog.operating_zl_m3
    costs = CostParts(
        installation=Range(
            low=t.capex_zl_ha.low / t.lifetime_years, high=t.capex_zl_ha.high / t.lifetime_years
        ),
        water_source=Range(
            low=src.capex_zl.low / src.lifetime_years / area_ha,
            high=src.capex_zl.high / src.lifetime_years / area_ha,
        ),
        water=Range(low=op.low * water_m3_ha, high=op.high * water_m3_ha),
    )
    if ce.price_zl_t is None:
        return result(EconomicsStatus.NO_PRICE, seasons, mean, water_m3_ha=water_m3_ha, costs=costs)

    benefit = Range(
        low=ce.yield_t_ha * ce.price_zl_t.low * mean, high=ce.yield_t_ha * ce.price_zl_t.high * mean
    )
    total = costs.total
    if benefit.low >= total.high:
        verdict = Verdict.PROFITABLE
    elif benefit.high < total.low:
        verdict = Verdict.UNPROFITABLE
    else:
        verdict = Verdict.BORDERLINE
    margin = benefit.mid - costs.installation.mid - costs.water.mid
    source_per_year = src.capex_zl.mid / src.lifetime_years
    return result(
        EconomicsStatus.OK,
        seasons,
        mean,
        verdict=verdict,
        water_m3_ha=water_m3_ha,
        benefit=benefit,
        costs=costs,
        break_even_area_ha=source_per_year / margin if margin > 0 else None,
        break_even_never=margin <= 0,
    )
