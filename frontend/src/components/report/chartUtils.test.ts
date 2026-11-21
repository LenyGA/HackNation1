import { describe, expect, it } from 'vitest'
import { formatDateDmy } from '@/lib/format'
import { niceTicks, tickDecimals } from './chartUtils'

describe('niceTicks', () => {
  it.each([
    [0, 7],
    [0, 43],
    [0, 380],
    [-112, 35],
    [101.3, 104.9],
    [0, 1],
    [-3.2, -0.4],
    [5, 5],
  ])('[%d, %d] → 3–6 round ticks covering the range', (lo, hi) => {
    const t = niceTicks(lo, hi)
    expect(t.length).toBeGreaterThanOrEqual(3)
    expect(t.length).toBeLessThanOrEqual(6)
    expect(t[0]).toBeLessThanOrEqual(lo)
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(hi)
    const step = t[1] - t[0]
    const mantissa = step / 10 ** Math.floor(Math.log10(step))
    expect([1, 2, 5, 10]).toContain(Math.round(mantissa * 1e6) / 1e6)
  })

  it('decimals follow the step', () => {
    expect(tickDecimals([0, 100, 200])).toBe(0)
    expect(tickDecimals([0, 0.25, 0.5])).toBe(2)
    expect(tickDecimals(niceTicks(0, 1))).toBe(1)
  })
})

describe('formatDateDmy', () => {
  it('uses the analysis date in DD.MM.YYYY', () => {
    expect(formatDateDmy('2019-07-15')).toBe('15.07.2019')
    expect(formatDateDmy('2026-01-03T00:00:00')).toBe('03.01.2026')
  })
})
