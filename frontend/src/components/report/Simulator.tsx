import { useState } from 'react'
import type { Simulation, StrategyId } from '@/api/types'
import { formatNumberPl, m3WherePl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { AXIS, niceTicks, useMeasuredWidth } from './chartUtils'
import { Disclosure } from './ReportParts'
import { YAxis } from './YAxis'

const COLORS: Record<StrategyId, string> = {
  none: '#64748b',
  rescue: '#0ea5e9',
  full: '#1d4ed8',
  retention: '#16a34a',
  retention_rescue: '#a16207',
}

function val(v: number | null, unit: string, step = 0): string {
  return v === null ? 'brak danych' : `${formatNumberPl(v, step)} ${unit}`
}

function StressLines({ sim, chosen, year }: { sim: Simulation; chosen: StrategyId; year: number }) {
  const { ref, width: W } = useMeasuredWidth()
  const H = W < 480 ? 190 : 220
  const PAD = { top: 22, right: 12, bottom: 28, left: 40 }
  const all = sim.strategies.flatMap((s) => s.years.map((y) => y.stress_days_median ?? 0))
  const ticks = niceTicks(0, Math.max(5, ...all))
  const maxV = ticks[ticks.length - 1]
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (k: number) => PAD.left + (innerW * (k - 1)) / 4
  const y = (v: number) => PAD.top + innerH * (1 - v / maxV)
  const ordered = [...sim.strategies].sort((a, b) => (a.id === chosen ? 1 : 0) - (b.id === chosen ? 1 : 0))
  return (
    <div ref={ref} className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block h-auto w-full"
        role="img"
        aria-label={`Dni stresu wodnego w kolejnych latach: ${sim.strategies
          .map((s) => `${s.label_pl}: ${s.years.map((y) => (y.stress_days_median === null ? 'brak danych' : formatNumberPl(y.stress_days_median))).join(', ')}`)
          .join('; ')}`}
      >
        <YAxis ticks={ticks} y={y} left={PAD.left} right={W - PAD.right} unit="dni" />
        <line x1={x(year)} x2={x(year)} y1={PAD.top} y2={PAD.top + innerH} stroke="#cbd5e1" strokeDasharray="3 3" />
        {[1, 2, 3, 4, 5].map((k) => (
          <text key={k} x={x(k)} y={H - 8} fontSize="11" fill={k === year ? '#0f172a' : AXIS.text} fontWeight={k === year ? 700 : 400} textAnchor="middle">
            za {k} {k === 1 ? 'rok' : k < 5 ? 'lata' : 'lat'}
          </text>
        ))}
        {ordered.map((s) => {
          const pts = s.years.filter((p) => p.stress_days_median !== null)
          const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.year_ahead).toFixed(1)},${y(p.stress_days_median ?? 0).toFixed(1)}`).join('')
          const on = s.id === chosen
          return (
            <g key={s.id} opacity={on ? 1 : 0.45}>
              <path d={d} fill="none" stroke={COLORS[s.id]} strokeWidth={on ? 3 : 1.6} />
              {pts.map((p) => (
                <circle key={p.year_ahead} cx={x(p.year_ahead)} cy={y(p.stress_days_median ?? 0)} r={on ? 4 : 2.5} fill={COLORS[s.id]} />
              ))}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export function Simulator({ sim, farmCount }: { sim: Simulation; farmCount?: number }) {
  const [chosen, setChosen] = useState<StrategyId>(sim.strategies[0]?.id ?? 'none')
  const [year, setYear] = useState(1)
  const strategy = sim.strategies.find((s) => s.id === chosen) ?? sim.strategies[0]
  if (!strategy) return null
  const row = strategy.years.find((y) => y.year_ahead === year) ?? null
  const base = sim.strategies.find((s) => s.id === 'none')?.years.find((y) => y.year_ahead === year) ?? null
  const saved =
    row && base && row.stress_days_median !== null && base.stress_days_median !== null && chosen !== 'none'
      ? base.stress_days_median - row.stress_days_median
      : null

  return (
    <section className="space-y-3 rounded-lg border bg-card p-3.5" aria-label="Porównanie strategii na 1–5 lat">
      <h3 className="text-base font-semibold">Co dalej? Porównanie strategii na 1–5 lat</h3>
      <div
        role="radiogroup"
        aria-label="Strategia"
        className="flex flex-wrap gap-1.5"
        onKeyDown={(e) => {
          // Radio-group keyboard pattern: arrows move the choice, only the chosen option is in the tab order.
          const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
          if (!step) return
          e.preventDefault()
          const ids = sim.strategies.map((s) => s.id)
          const next = ids[(ids.indexOf(chosen) + step + ids.length) % ids.length]
          setChosen(next)
          const buttons = e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]')
          buttons[ids.indexOf(next)]?.focus()
        }}
      >
        {sim.strategies.map((s) => (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={s.id === chosen}
            tabIndex={s.id === chosen ? 0 : -1}
            onClick={() => setChosen(s.id)}
            className={cn(
              'min-h-11 rounded-md border px-3 py-1.5 text-left text-sm font-medium transition-colors',
              s.id === chosen ? 'border-transparent text-white' : 'bg-background hover:bg-muted',
            )}
            style={s.id === chosen ? { background: COLORS[s.id] } : undefined}
          >
            {s.label_pl}
          </button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">{strategy.description_pl}</p>
      <label className="block space-y-1">
        <span className="text-sm font-medium">
          Za ile lat: <b>{year}</b>
        </span>
        <input
          type="range"
          min={1}
          max={5}
          step={1}
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="h-11 w-full accent-primary"
          aria-valuetext={`za ${year} ${year === 1 ? 'rok' : year < 5 ? 'lata' : 'lat'}`}
        />
      </label>
      {row && (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div className="rounded-md border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">Dni stresu wodnego w sezonie</dt>
            <dd className="text-lg font-semibold tabular-nums">{val(row.stress_days_median, 'dni')}</dd>
            {saved !== null && saved >= 1 && <dd className="text-xs text-green-700">o {formatNumberPl(saved)} mniej niż bez działań</dd>}
          </div>
          <div className="rounded-md border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">W roku suchym</dt>
            <dd className="text-lg font-semibold tabular-nums">{val(row.stress_days_p80, 'dni')}</dd>
          </div>
          <div className="rounded-md border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">Woda do podlewania (rok suchy)</dt>
            <dd className="text-lg font-semibold tabular-nums">{val(row.irrigation_mm_p80, 'mm')}</dd>
            {row.irrigation_m3_parcel_p80 !== null && row.irrigation_m3_parcel_p80 > 0 && (
              <dd className="text-xs text-muted-foreground">ok. {formatNumberPl(row.irrigation_m3_parcel_p80)} m³ {m3WherePl(farmCount)}</dd>
            )}
          </div>
          <div className="rounded-md border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">Zapas wody w glebie (pełna)</dt>
            <dd className="text-lg font-semibold tabular-nums">{val(row.taw_mm, 'mm', 1)}</dd>
            {row.evaporation_saved_mm_median !== null && row.evaporation_saved_mm_median >= 1 && (
              <dd className="text-xs text-green-700">
                ściółka zatrzymuje ok. {formatNumberPl(row.evaporation_saved_mm_median)} mm w sezonie
                {row.evaporation_saved_m3_parcel_median !== null && row.evaporation_saved_m3_parcel_median >= 10
                  ? ` (ok. ${formatNumberPl(row.evaporation_saved_m3_parcel_median)} m³)`
                  : ''}
              </dd>
            )}
          </div>
        </dl>
      )}
      <figure className="space-y-1.5">
        <figcaption className="text-sm font-medium">Dni stresu wodnego w sezonie (typowy rok) — wszystkie strategie</figcaption>
        <StressLines sim={sim} chosen={chosen} year={year} />
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {sim.strategies.map((s) => (
            <li key={s.id} className="flex items-center gap-1.5">
              <span className="inline-block w-4" style={{ borderTop: `3px solid ${COLORS[s.id]}` }} aria-hidden />
              {s.label_pl}
            </li>
          ))}
        </ul>
      </figure>
      <div className="space-y-2">
        {sim.text_pl.map((p, i) => (
          <p key={i} className="leading-relaxed">
            {p}
          </p>
        ))}
      </div>
      <Disclosure summary="Założenia symulacji">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {sim.assumptions_pl.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </Disclosure>
      <p className="text-xs text-muted-foreground">Źródło: {sim.source}</p>
    </section>
  )
}
