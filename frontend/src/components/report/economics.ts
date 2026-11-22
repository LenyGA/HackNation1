// G10: the browser recomputes irrigation economics when the farmer changes the assumptions.
// Same formula as backend/app/analysis/economics.py, on single values (the backend uses low–high ranges):
//   benefit / ha / year = yield × price × mean yield loss share (FAO-33, from this parcel's 10 seasons)
//   cost / ha / year    = installation / lifetime + water source / lifetime / area + running cost × m³ per ha

import type { EconomicsAssumptions, EconomicsVerdict, IrrigationEconomics } from '@/api/types'

// With single values the result is "borderline" when benefit and cost differ by less than this share.
export const BORDERLINE_BAND = 0.2

export interface EconomicsInputs {
  yieldTHa: number
  priceZlT: number
  capexZlHa: number
  lifetimeYears: number
  waterSourceZl: number
  waterSourceLifetimeYears: number
  operatingZlM3: number
}

export interface EconomicsResult {
  benefitZlHa: number
  costZlHa: number
  verdict: EconomicsVerdict
  breakEvenAreaHa: number | null // null: never pays off
}

const mid = (lo: number | null, hi: number | null): number | null =>
  lo === null || hi === null ? null : (lo + hi) / 2

/** Middle of each range; price may be missing (the farmer enters it). */
export function defaultInputs(a: EconomicsAssumptions): EconomicsInputs | null {
  const capex = mid(a.capex_zl_ha_low, a.capex_zl_ha_high)
  if (a.yield_t_ha === null || capex === null || a.lifetime_years === null) return null
  return {
    yieldTHa: a.yield_t_ha,
    priceZlT: mid(a.price_zl_t_low, a.price_zl_t_high) ?? 0,
    capexZlHa: capex,
    lifetimeYears: a.lifetime_years,
    waterSourceZl: (a.water_source_zl_low + a.water_source_zl_high) / 2,
    waterSourceLifetimeYears: a.water_source_lifetime_years,
    operatingZlM3: (a.operating_zl_m3_low + a.operating_zl_m3_high) / 2,
  }
}

export function canRecompute(e: IrrigationEconomics): boolean {
  return (
    e.technology !== 'none' &&
    e.mean_loss_share !== null &&
    e.water_m3_ha !== null &&
    e.area_ha > 0 &&
    defaultInputs(e.assumptions) !== null
  )
}

/** Which fields block the computation (empty, negative, or zero where zero makes no sense). */
export function invalidFields(inp: Partial<Record<keyof EconomicsInputs, number>>): (keyof EconomicsInputs)[] {
  const positive: (keyof EconomicsInputs)[] = ['priceZlT', 'yieldTHa', 'lifetimeYears', 'waterSourceLifetimeYears']
  return (Object.keys(inp) as (keyof EconomicsInputs)[]).filter((k) => {
    const v = inp[k]
    return v === undefined || !Number.isFinite(v) || v < 0 || (positive.includes(k) && v === 0)
  })
}

export function computeEconomics(
  inp: EconomicsInputs,
  meanLossShare: number,
  waterM3Ha: number,
  areaHa: number,
): EconomicsResult | null {
  if (inp.lifetimeYears <= 0 || inp.waterSourceLifetimeYears <= 0 || areaHa <= 0 || inp.priceZlT <= 0) return null
  const benefit = inp.yieldTHa * inp.priceZlT * meanLossShare
  const installation = inp.capexZlHa / inp.lifetimeYears
  const water = inp.operatingZlM3 * waterM3Ha
  const sourcePerYear = inp.waterSourceZl / inp.waterSourceLifetimeYears
  const cost = installation + sourcePerYear / areaHa + water
  const verdict: EconomicsVerdict =
    benefit >= cost * (1 + BORDERLINE_BAND) ? 'profitable' : benefit < cost * (1 - BORDERLINE_BAND) ? 'unprofitable' : 'borderline'
  const margin = benefit - installation - water
  return { benefitZlHa: benefit, costZlHa: cost, verdict, breakEvenAreaHa: margin > 0 ? sourcePerYear / margin : null }
}

/** Money as the report states it: never to the złoty (50 zł steps, 100 zł above 10 000 zł). */
export function roundZl(value: number): number {
  const step = value < 10_000 ? 50 : 100
  return Math.round(value / step) * step
}
