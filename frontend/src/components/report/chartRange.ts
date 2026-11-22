import type { ChartPoint, DailyWater, SeasonChart } from '@/api/types'

// Water situation chart for a chosen time range ("Dane z ostatnich: …").
// Mirror of backend/app/report/chart_range.py (the PDF uses that one) — keep the two in sync.

export type RangeKey = '1d' | '7d' | '1m' | '6m' | '1y' | 'custom'

export const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: '1d', label: '24 h' },
  { key: '7d', label: '7 dni' },
  { key: '1m', label: 'miesiąc' },
  { key: '6m', label: '6 miesięcy' },
  { key: '1y', label: 'rok' },
  { key: 'custom', label: 'własny' },
]

const RANGE_DAYS: Record<Exclude<RangeKey, 'custom'>, number> = { '1d': 1, '7d': 7, '1m': 30, '6m': 182, '1y': 365 }
export const DEFAULT_RANGE: RangeKey = '6m'
const HISTORY_YEARS = 10
const DAILY_POINTS_MAX = 62
const STEP_DAYS = 7
const MIN_HISTORY_YEARS = 5
const DAY_MS = 86_400_000

/** ISO date → day number (UTC), so date arithmetic never depends on the viewer's time zone. */
export function dayNum(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / DAY_MS
}

export function isoDay(n: number): string {
  return new Date(n * DAY_MS).toISOString().slice(0, 10)
}

/** `iso` moved `years` back; 29 Feb becomes 28 Feb (as `same_day_in_year` in the backend). */
function yearsBack(iso: string, years: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const year = y - years
  const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
  const day = m === 2 && d === 29 && !leap ? 28 : d
  return `${String(year).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function lastDay(daily: DailyWater): string {
  return isoDay(dayNum(daily.start) + daily.precip_mm.length - 1)
}

/** First day a custom range may start: 10 years before the analysis date, within the data. */
export function earliestStart(daily: DailyWater, analysisDate: string): string {
  const tenYears = yearsBack(analysisDate, HISTORY_YEARS)
  return dayNum(tenYears) > dayNum(daily.start) ? tenYears : daily.start
}

/** [start, end] of the window, or null when a custom range is incomplete or outside the data. */
export function resolveWindow(
  daily: DailyWater,
  analysisDate: string,
  key: RangeKey,
  start?: string,
  end?: string,
): [string, string] | null {
  const lastN = Math.min(dayNum(analysisDate), dayNum(lastDay(daily)))
  if (key === 'custom') {
    if (!start || !end || dayNum(start) > dayNum(end)) return null
    if (dayNum(end) > lastN || dayNum(start) < dayNum(earliestStart(daily, analysisDate))) return null
    return [start, end]
  }
  const s = Math.max(dayNum(daily.start), lastN - RANGE_DAYS[key] + 1)
  return s <= lastN ? [isoDay(s), isoDay(lastN)] : null
}

function cumulative(values: (number | null)[], first: string, start: string, n: number): (number | null)[] | null {
  const i0 = dayNum(start) - dayNum(first)
  if (i0 < 0 || i0 + n > values.length) return null
  const out: (number | null)[] = []
  let total: number | null = 0
  for (let i = i0; i < i0 + n; i++) {
    const v = values[i]
    total = total === null || v === null ? null : total + v
    out.push(total)
  }
  return out
}

// Python's round(): halves to even, so the page and the PDF show the same whole millimetres.
function roundHalfEven(v: number): number {
  const r = Math.round(v)
  return Math.abs(v % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r
}

function r(v: number | null): number | null {
  return v === null ? null : roundHalfEven(v)
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** Cumulative rain and crop need from `start` to `end`, against the same days of the previous 10 years.
 *  The first point (the day before `start`) is 0 mm, so even a one-day window draws a line. */
export function rangeChart(daily: DailyWater, start: string, end: string): SeasonChart | null {
  const n = dayNum(end) - dayNum(start) + 1
  if (n < 1) return null
  const precip = cumulative(daily.precip_mm, daily.start, start, n)
  const need = cumulative(daily.crop_need_mm, daily.start, start, n)
  if (!precip || !need) return null
  const hist: (number | null)[][] = []
  for (let k = 1; k <= HISTORY_YEARS; k++) {
    const series = cumulative(daily.precip_mm, daily.start, yearsBack(start, k), n)
    if (series && series[n - 1] !== null) hist.push(series)
  }
  const enough = hist.length >= MIN_HISTORY_YEARS
  const offsets: number[] = []
  if (n <= DAILY_POINTS_MAX) for (let i = 0; i < n; i++) offsets.push(i)
  else {
    for (let i = 0; i < n; i += STEP_DAYS) offsets.push(i)
    if (offsets[offsets.length - 1] !== n - 1) offsets.push(n - 1)
  }
  const zero = enough ? 0 : null
  const points: ChartPoint[] = [
    {
      day: isoDay(dayNum(start) - 1),
      precip_mm: 0,
      crop_need_mm: 0,
      precip_hist_median_mm: zero,
      precip_hist_min_mm: zero,
      precip_hist_max_mm: zero,
    },
  ]
  const s0 = dayNum(start)
  for (const i of offsets) {
    const past = hist.map((s) => s[i]).filter((v): v is number => v !== null)
    const ok = enough && past.length >= MIN_HISTORY_YEARS
    points.push({
      day: isoDay(s0 + i),
      precip_mm: r(precip[i]),
      crop_need_mm: r(need[i]),
      precip_hist_median_mm: ok ? r(median(past)) : null,
      precip_hist_min_mm: ok ? r(Math.min(...past)) : null,
      precip_hist_max_mm: ok ? r(Math.max(...past)) : null,
    })
  }
  return { start, end, years: enough ? hist.length : 0, source: daily.source, points }
}
