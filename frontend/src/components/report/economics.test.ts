import { describe, expect, it } from 'vitest'
import { computeEconomics, defaultInputs, roundZl, type EconomicsInputs } from './economics'
import type { EconomicsAssumptions } from '@/api/types'

const ASSUMPTIONS: EconomicsAssumptions = {
  yield_t_ha: 30.2,
  price_zl_t_low: 1082.5,
  price_zl_t_high: 2095.2,
  ky: 1.1,
  capex_zl_ha_low: 3000,
  capex_zl_ha_high: 8000,
  lifetime_years: 12,
  water_source_zl_low: 40000,
  water_source_zl_high: 120000,
  water_source_lifetime_years: 25,
  operating_zl_m3_low: 0.5,
  operating_zl_m3_high: 1.5,
}

describe('computeEconomics', () => {
  it('uses the middle of each range by default', () => {
    const inp = defaultInputs(ASSUMPTIONS) as EconomicsInputs
    expect(inp.priceZlT).toBeCloseTo(1588.85)
    expect(inp.capexZlHa).toBe(5500)
    expect(inp.operatingZlM3).toBe(1)
  })

  it('potato with a 16.5 % loss pays off, rye does not', () => {
    const potato = computeEconomics(defaultInputs(ASSUMPTIONS) as EconomicsInputs, 0.165, 2000, 7.6)
    expect(potato?.verdict).toBe('profitable')
    const rye = computeEconomics({ ...(defaultInputs(ASSUMPTIONS) as EconomicsInputs), yieldTHa: 3.57, priceZlT: 770 }, 0.1575, 2000, 7.6)
    expect(rye?.verdict).toBe('unprofitable')
    expect(rye?.breakEvenAreaHa).toBeNull()
  })

  it('is borderline within ±20 %', () => {
    const inp: EconomicsInputs = {
      yieldTHa: 10, priceZlT: 100, capexZlHa: 0, lifetimeYears: 10, waterSourceZl: 0, waterSourceLifetimeYears: 10, operatingZlM3: 0.5,
    }
    // benefit 10 × 100 × 0.1 = 100 zł, cost 0.5 × 200 = 100 zł
    expect(computeEconomics(inp, 0.1, 200, 5)?.verdict).toBe('borderline')
  })

  it('needs a price', () => {
    expect(computeEconomics({ ...(defaultInputs(ASSUMPTIONS) as EconomicsInputs), priceZlT: 0 }, 0.2, 2000, 7.6)).toBeNull()
  })

  it('rounds money like the report', () => {
    expect(roundZl(1234)).toBe(1250)
    expect(roundZl(12_340)).toBe(12_300)
  })
})
