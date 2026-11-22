import { type CSSProperties, type Dispatch, memo, type SetStateAction, useRef, useState } from 'react'
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

function yearsPl(k: number): string {
  return `za ${k} ${k === 1 ? 'rok' : k < 5 ? 'lata' : 'lat'}`
}

/** Redrawn only when the strategy or the whole year changes. The cursor line follows the slider through the
 *  CSS variable --sim-pos set on a parent, so dragging does not re-render the chart. */
const StressLines = memo(function StressLines({
  sim,
  chosen,
  year,
}: {
  sim: Simulation
  chosen: StrategyId
  year: number
}) {
  const { ref, width: W } = useMeasuredWidth()
  const H = W < 480 ? 190 : 220
  const PAD = { top: 22, right: 26, bottom: 28, left: 40 }
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
        <line
          x1={x(1)}
          x2={x(1)}
          y1={PAD.top}
          y2={PAD.top + innerH}
          stroke="#94a3b8"
          strokeWidth={1.5}
          strokeDasharray="3 3"
          style={{ transform: `translateX(calc((var(--sim-pos, 1) - 1) * ${(innerW / 4).toFixed(2)}px))` }}
        />
        {[1, 2, 3, 4, 5].map((k) => (
          <text key={k} x={x(k)} y={H - 8} fontSize="11" fill={k === year ? '#0f172a' : AXIS.text} fontWeight={k === year ? 700 : 400} textAnchor="middle">
            {yearsPl(k)}
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
})

/** Years slider: the thumb glides with the finger, the values switch at the nearest whole year and the thumb
 *  snaps there on release. Arrow keys move one whole year. */
function YearSlider({ pos, onChange }: { pos: number; onChange: Dispatch<SetStateAction<number>> }) {
  const year = Math.round(pos)
  const dragging = useRef(false)
  // Functional update: snap to the year of the latest position, not of the last render.
  const snap = () => {
    dragging.current = false
    onChange((p) => Math.round(p))
  }
  const fill = ((pos - 1) / 4) * 100
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span id="sim-years" className="text-sm font-medium">
          Za ile lat
        </span>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-sm font-semibold text-primary tabular-nums">
          {yearsPl(year)}
        </span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        step={0.01}
        value={pos}
        onPointerDown={() => (dragging.current = true)}
        onChange={(e) => {
          const v = Number(e.target.value)
          // While a finger or mouse drags, the thumb glides. Any other change (screen-reader swipe, which
          // moves by one tiny step) jumps a whole year in that direction.
          if (dragging.current) onChange(v)
          else onChange(v > year ? Math.min(5, year + 1) : v < year ? Math.max(1, year - 1) : year)
        }}
        onPointerUp={snap}
        onPointerCancel={snap}
        onTouchEnd={snap}
        onBlur={snap}
        onKeyDown={(e) => {
          const step =
            e.key === 'ArrowRight' || e.key === 'ArrowUp' || e.key === 'PageUp'
              ? 1
              : e.key === 'ArrowLeft' || e.key === 'ArrowDown' || e.key === 'PageDown'
                ? -1
                : 0
          const to = e.key === 'Home' ? 1 : e.key === 'End' ? 5 : step ? Math.min(5, Math.max(1, year + step)) : null
          if (to === null) return
          e.preventDefault()
          onChange(to)
        }}
        className="sim-range w-full"
        style={{ '--fill': `${fill}%` } as CSSProperties}
        aria-labelledby="sim-years"
        aria-valuetext={yearsPl(year)}
      />
      <div className="flex justify-between px-[11px] text-xs text-muted-foreground" aria-hidden>
        {[1, 2, 3, 4, 5].map((k) => (
          <button
            key={k}
            type="button"
            tabIndex={-1}
            onClick={() => onChange(k)}
            className={cn('w-0 whitespace-nowrap text-center tabular-nums', k === year && 'font-semibold text-foreground')}
          >
            <span className="-ml-2 inline-block w-4">{k}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export function Simulator({ sim, farmCount }: { sim: Simulation; farmCount?: number }) {
  const [chosen, setChosen] = useState<StrategyId>(sim.strategies[0]?.id ?? 'none')
  // Slider position (continuous while dragging); the data shown is for the nearest whole year.
  const [pos, setPos] = useState(1)
  const year = Math.round(pos)
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
      <YearSlider pos={pos} onChange={setPos} />
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
        <div style={{ '--sim-pos': pos } as CSSProperties}>
          <StressLines sim={sim} chosen={chosen} year={year} />
        </div>
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
