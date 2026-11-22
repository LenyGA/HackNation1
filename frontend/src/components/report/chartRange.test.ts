import { describe, expect, it } from 'vitest'
import type { DailyWater } from '@/api/types'
import { dayNum, isoDay, rangeChart, resolveWindow } from './chartRange'

// Same cases as backend/tests/report/test_chart_range.py: the page and the PDF must draw the same chart.
const START = '2015-10-01'
const ANALYSIS = '2026-07-15'

function daily(precip = 2, need = 3, until = ANALYSIS, start = START): DailyWater {
  const n = dayNum(until) - dayNum(start) + 1
  return { start, precip_mm: Array(n).fill(precip), crop_need_mm: Array(n).fill(need), source: 'test' }
}

const minus = (iso: string, days: number) => isoDay(dayNum(iso) - days)

describe('resolveWindow', () => {
  it.each([
    ['1d', 1],
    ['7d', 7],
    ['1m', 30],
    ['6m', 182],
    ['1y', 365],
  ] as const)('%s ends on the analysis date', (key, days) => {
    expect(resolveWindow(daily(), ANALYSIS, key)).toEqual([minus(ANALYSIS, days - 1), ANALYSIS])
  })

  it('validates a custom range', () => {
    const d = daily()
    expect(resolveWindow(d, ANALYSIS, 'custom', '2020-05-01', '2020-08-31')).toEqual(['2020-05-01', '2020-08-31'])
    expect(resolveWindow(d, ANALYSIS, 'custom', undefined, '2020-08-31')).toBeNull()
    expect(resolveWindow(d, ANALYSIS, 'custom', '2020-09-01', '2020-08-31')).toBeNull()
    expect(resolveWindow(d, ANALYSIS, 'custom', '2026-07-01', '2026-07-16')).toBeNull()
    expect(resolveWindow(d, ANALYSIS, 'custom', '2016-01-01', '2016-02-01')).toBeNull()
  })

  it('cuts a preset range to the available data', () => {
    expect(resolveWindow(daily(2, 3, minus(ANALYSIS, 3)), ANALYSIS, '7d')).toEqual([minus(ANALYSIS, 9), minus(ANALYSIS, 3)])
  })
})

describe('rangeChart', () => {
  it('draws a one-day window from zero', () => {
    const c = rangeChart(daily(), ANALYSIS, ANALYSIS)!
    expect(c.points.map((p) => p.precip_mm)).toEqual([0, 2])
    expect(c.points.map((p) => p.crop_need_mm)).toEqual([0, 3])
    expect(c.points[0].day).toBe(minus(ANALYSIS, 1))
    expect(c.years).toBe(10)
  })

  it('sums cumulatively with a band of previous years', () => {
    const c = rangeChart(daily(), minus(ANALYSIS, 6), ANALYSIS)!
    const last = c.points[c.points.length - 1]
    expect([last.precip_mm, last.crop_need_mm]).toEqual([14, 21])
    expect([last.precip_hist_min_mm, last.precip_hist_median_mm, last.precip_hist_max_mm]).toEqual([14, 14, 14])
    expect(c.points).toHaveLength(8)
  })

  it('uses weekly points for a year and keeps the last day', () => {
    const [s, e] = resolveWindow(daily(), ANALYSIS, '1y')!
    const c = rangeChart(daily(), s, e)!
    expect(c.points[c.points.length - 1].day).toBe(ANALYSIS)
    expect(c.points.length).toBeLessThan(60)
  })

  it('hides the band without 5 previous years', () => {
    const c = rangeChart(daily(1, 1, ANALYSIS, '2023-01-01'), minus(ANALYSIS, 29), ANALYSIS)!
    expect(c.years).toBe(0)
    expect(c.points.every((p) => p.precip_hist_median_mm === null)).toBe(true)
  })

  it('ends the rain line at a missing day', () => {
    const d = daily()
    d.precip_mm[dayNum(ANALYSIS) - dayNum(START) - 1] = null
    const c = rangeChart(d, minus(ANALYSIS, 6), ANALYSIS)!
    expect(c.points[c.points.length - 1].precip_mm).toBeNull()
    expect(c.points[c.points.length - 1].crop_need_mm).toBe(21)
  })
})
