import type { DailyWater, SeasonChart } from '@/api/types'
import { SeasonChartView } from './SeasonChartView'
import { earliestStart, lastDay, RANGE_OPTIONS, rangeChart, type RangeKey, resolveWindow } from './chartRange'

export interface ChartRange {
  key: RangeKey
  start?: string
  end?: string
}

/** Water situation chart with the time range switch ("Dane z ostatnich: …"). The chosen range also goes to
 *  the full PDF and the print view. Reports saved before the switch existed show the season chart. */
export function WaterChart({
  daily,
  fallback,
  analysisDate,
  range,
  onRangeChange,
}: {
  daily: DailyWater | null | undefined
  fallback: SeasonChart | null
  analysisDate: string
  range: ChartRange
  onRangeChange: (r: ChartRange) => void
}) {
  if (!daily) return fallback ? <SeasonChartView chart={fallback} /> : null

  const window = resolveWindow(daily, analysisDate, range.key, range.start, range.end)
  const chart = window ? rangeChart(daily, window[0], window[1]) : null
  const minDay = earliestStart(daily, analysisDate)
  const maxDay = lastDay(daily) < analysisDate ? lastDay(daily) : analysisDate

  function pick(key: RangeKey) {
    if (key !== 'custom') return onRangeChange({ key })
    // Start the custom range from the window shown now, so the inputs are never empty.
    const [start, end] = window ?? resolveWindow(daily as DailyWater, analysisDate, '1m') ?? [minDay, maxDay]
    onRangeChange({ key, start, end })
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium" id="water-range-label">
          Dane z ostatnich:
        </span>
        <div role="group" aria-labelledby="water-range-label" className="flex flex-wrap gap-1">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.key}
              type="button"
              aria-pressed={range.key === o.key}
              onClick={() => pick(o.key)}
              className={`min-h-9 rounded-md border px-3 text-sm transition-colors ${
                range.key === o.key
                  ? 'border-navy bg-navy font-semibold text-white'
                  : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      {range.key === 'custom' && (
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            od
            <input
              type="date"
              className="h-9 rounded-md border bg-background px-2"
              min={minDay}
              max={range.end ?? maxDay}
              value={range.start ?? ''}
              onChange={(e) => onRangeChange({ ...range, start: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1">
            do
            <input
              type="date"
              className="h-9 rounded-md border bg-background px-2"
              min={range.start ?? minDay}
              max={maxDay}
              value={range.end ?? ''}
              onChange={(e) => onRangeChange({ ...range, end: e.target.value })}
            />
          </label>
        </div>
      )}
      {chart ? (
        <SeasonChartView chart={chart} />
      ) : (
        <p role="status" className="text-sm text-muted-foreground">
          {range.key === 'custom'
            ? 'Wybierz daty od–do z ostatnich 10 lat, nie późniejsze niż data analizy.'
            : 'Brak danych pogodowych dla tego okresu.'}
        </p>
      )}
    </div>
  )
}
