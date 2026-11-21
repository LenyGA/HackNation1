import type {
  ClimateTrends,
  SatelliteSeries,
  SlopeProfile,
  StressHeatmap,
  TrendLevel,
  TrendMetric,
  WaterPlan,
} from '@/api/types'
import { formatDateDmy, formatDatePl, formatNumberPl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { AXIS, niceStep, niceTicks, useMeasuredWidth } from './chartUtils'
import { Disclosure } from './ReportParts'
import { YAxis } from './YAxis'

// Plain-SVG charts of the report (no chart library), drawn like SeasonChartView.

function Source({ text }: { text: string }) {
  return <p className="text-xs text-muted-foreground">Źródło: {text}</p>
}

function Swatch({ color, round, dashed }: { color: string; round?: boolean; dashed?: boolean }) {
  if (dashed) return <span className="inline-block w-5" style={{ borderTop: `2px dashed ${color}` }} aria-hidden />
  return <span className={cn('inline-block size-3', round ? 'rounded-full' : 'rounded-sm')} style={{ background: color }} aria-hidden />
}

// --- satellite --------------------------------------------------------------------------------------

const SAT = { past: '#16a34a', now: '#dc2626', band: '#bbf7d0', median: '#15803d' }

export function SatelliteChart({ data, analysisDate }: { data: SatelliteSeries; analysisDate: string }) {
  const { ref, width: W } = useMeasuredWidth()
  const pts = data.points
  if (pts.length === 0) return null
  const H = W < 480 ? 200 : 240
  const PAD = { top: 24, right: 14, bottom: 26, left: 40 }
  const years = pts.map((p) => p.year)
  const y0 = Math.min(...years)
  const y1 = Math.max(...years)
  const vals = pts.map((p) => p.ndvi)
  // Water or bare soil can give a negative index: the axis goes below 0 when needed.
  const ticks = niceTicks(
    Math.max(-1, Math.min(0, Math.min(...vals, data.history_min ?? 1) - 0.05)),
    Math.min(1, Math.max(...vals, data.history_max ?? 0) + 0.05),
  )
  const lo = ticks[0]
  const hi = ticks[ticks.length - 1]
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (year: number) => PAD.left + (y1 === y0 ? innerW / 2 : (innerW * (year - y0)) / (y1 - y0))
  const y = (v: number) => PAD.top + innerH * (1 - (v - lo) / Math.max(0.01, hi - lo))
  const yearStep = W < 420 ? 2 : 1
  const current = pts.filter((p) => p.current)
  const day = formatDateDmy(analysisDate)
  const nowMedian = current.length ? current.map((p) => p.ndvi).sort((a, b) => a - b)[Math.floor(current.length / 2)] : null

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">Kondycja roślin z satelity: na dzień {day} i w tych samych tygodniach w poprzednich latach</figcaption>
      <div ref={ref} className="w-full">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="block h-auto w-full"
          role="img"
          aria-label={`Kondycja roślin na dzień ${day}: ${nowMedian !== null ? formatNumberPl(nowMedian, 2) : 'brak zdjęcia'}; zwykle w tych tygodniach: ${
            data.history_median !== null ? formatNumberPl(data.history_median, 2) : 'brak danych'
          } (0 — goła ziemia, 1 — gęste, zielone rośliny).`}
        >
          <YAxis ticks={ticks} y={y} left={PAD.left} right={W - PAD.right} unit="wskaźnik zieleni" />
          {data.history_min !== null && data.history_max !== null && (
            <rect
              x={PAD.left}
              width={innerW}
              y={y(data.history_max)}
              height={Math.max(1, y(data.history_min) - y(data.history_max))}
              fill={SAT.band}
              opacity={0.5}
            />
          )}
          {data.history_median !== null && (
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(data.history_median)}
              y2={y(data.history_median)}
              stroke={SAT.median}
              strokeDasharray="5 4"
              strokeWidth={1.5}
            />
          )}
          {Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i)
            .filter((yr) => (yr - y0) % yearStep === 0 || yr === y1)
            .map((yr) => (
              <text key={yr} x={x(yr)} y={H - 8} fontSize="11" fill={AXIS.text} textAnchor="middle">
                {yr}
              </text>
            ))}
          {pts.map((p, i) => (
            <circle
              key={`${p.day}-${i}`}
              cx={x(p.year)}
              cy={y(p.ndvi)}
              r={p.current ? 6 : 5}
              fill={p.current ? SAT.now : SAT.past}
              stroke="#fff"
              strokeWidth={1.5}
            >
              <title>{`${formatDatePl(p.day)}: ${formatNumberPl(p.ndvi, 2)}`}</title>
            </circle>
          ))}
        </svg>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <li className="flex items-center gap-2">
          <Swatch color={SAT.now} round /> Ostatnie bezchmurne zdjęcia przed {day}
        </li>
        <li className="flex items-center gap-2">
          <Swatch color={SAT.past} round /> Te same tygodnie w poprzednich latach
        </li>
        <li className="flex items-center gap-2">
          <Swatch color={SAT.median} dashed /> Zwykle (środek)
        </li>
        <li className="flex items-center gap-2">
          <Swatch color={SAT.band} /> Od najsłabszego do najlepszego roku
        </li>
      </ul>
      <p className="text-sm leading-relaxed">{data.text_pl}</p>
      <Disclosure summary="Szczegóły dla zainteresowanych">
        <p className="text-sm text-muted-foreground">
          Skala to wskaźnik NDVI z satelity Sentinel-2 (0 — goła ziemia, 1 — gęsta zielona roślinność), średnio dla działki, z
          maską chmur. Porównujemy działkę z nią samą w tych samych tygodniach poprzednich lat, nie z progiem ogólnym.
          {!data.applicable && ' W tym okresie wskaźnik nie służy do oceny suszy (uprawa nie zakryła pola).'}
        </p>
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {pts.map((p, i) => (
            <li key={`${p.day}-d-${i}`}>
              {formatDatePl(p.day)}: NDVI {formatNumberPl(p.ndvi, 2)}
              {p.ndmi !== null && `, NDMI ${formatNumberPl(p.ndmi, 2)}`}
              {p.current && ' (sezon analizy)'}
            </li>
          ))}
        </ul>
      </Disclosure>
      <Source text={data.source} />
    </figure>
  )
}

// --- stress heat map --------------------------------------------------------------------------------

function heatColor(share: number): { bg: string; fg: string } {
  if (share <= 0) return { bg: '#f0fdf4', fg: '#166534' }
  if (share < 0.2) return { bg: '#fef9c3', fg: '#713f12' }
  if (share < 1 / 3) return { bg: '#fde68a', fg: '#713f12' }
  if (share < 0.5) return { bg: '#fdba74', fg: '#7c2d12' }
  if (share < 0.75) return { bg: '#f87171', fg: '#450a0a' }
  return { bg: '#b91c1c', fg: '#ffffff' }
}

const HEAT_LEGEND: { share: number; label: string }[] = [
  { share: 0, label: 'bez stresu' },
  { share: 0.1, label: 'do 1/5 dni' },
  { share: 0.25, label: 'do 1/3 dni' },
  { share: 0.4, label: 'do połowy' },
  { share: 0.6, label: 'do 3/4' },
  { share: 0.9, label: 'prawie cały miesiąc' },
]

export function StressHeatmapView({ data }: { data: StressHeatmap }) {
  if (data.rows.length === 0) return null
  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">Ile dni w miesiącu uprawa cierpiała z braku wody — rok po roku</figcaption>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full border-collapse text-center text-sm tabular-nums" aria-label="Dni stresu wodnego uprawy w miesiącach kolejnych lat">
          <thead className="bg-muted/60">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Rok</th>
              {data.months_pl.map((m) => (
                <th key={m} className="px-1.5 py-1.5 font-medium">
                  {m.slice(0, 3)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.year} className="border-t">
                <th scope="row" className="px-2 py-1 text-left font-medium">
                  {r.year}
                </th>
                {r.stress_days.map((d, i) => {
                  const season = r.season_days[i]
                  if (d === null || season === null || season === 0) {
                    return (
                      <td key={i} className="px-1.5 py-1 text-muted-foreground">
                        –
                      </td>
                    )
                  }
                  const c = heatColor(d / season)
                  return (
                    <td
                      key={i}
                      className="min-w-9 px-1.5 py-1 font-medium"
                      style={{ background: c.bg, color: c.fg }}
                      title={`${data.months_pl[i]} ${r.year}: ${d} z ${season} dni ze stresem wodnym`}
                    >
                      {d}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {HEAT_LEGEND.map((l) => {
          const c = heatColor(l.share)
          return (
            <li key={l.label} className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-5 rounded-sm border" style={{ background: c.bg }} aria-hidden />
              {l.label}
            </li>
          )
        })}
      </ul>
      <p className="text-xs text-muted-foreground">
        Liczba w kratce to dni, w których uprawie brakowało wody w glebie (z bilansu wody w strefie korzeni). „–” — uprawy nie
        było na polu albo brak danych.
      </p>
      <Source text={data.source} />
    </figure>
  )
}

// --- trends -----------------------------------------------------------------------------------------

const LEVEL_PILL: Record<TrendLevel, string> = {
  critical: 'bg-red-600 text-white',
  worse: 'bg-amber-500 text-amber-950',
  stable: 'bg-slate-200 text-slate-900',
  better: 'bg-green-600 text-white',
  unknown: 'bg-slate-200 text-slate-700',
}

function TrendBars({ metric }: { metric: TrendMetric }) {
  const W = 240
  const H = 96
  const PAD = { top: 16, right: 4, bottom: 4, left: 30 }
  const vals = metric.values.map((v) => v.value).filter((v): v is number => v !== null)
  if (vals.length === 0) return null
  // Temperature is far from zero: the axis starts just below the coolest season so differences are visible.
  const relative = metric.key === 'tmean_c'
  const ticks = relative ? niceTicks(Math.min(...vals) - 0.5, Math.max(...vals), 3) : niceTicks(Math.min(0, ...vals), Math.max(0, ...vals), 3)
  const lo = ticks[0]
  const hi = ticks[ticks.length - 1]
  const n = metric.values.length
  const bw = (W - PAD.left - PAD.right) / n
  const y = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - (v - lo) / (hi - lo))
  const base = relative ? y(lo) : y(0)
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="block h-auto w-full"
      role="img"
      aria-label={`${metric.label_pl}: ${metric.values.map((v) => `${v.year} ${v.value === null ? 'brak danych' : formatNumberPl(v.value, 1)}`).join(', ')}`}
    >
      <YAxis ticks={ticks} y={y} left={PAD.left} right={W - PAD.right} unit={metric.unit} fontSize={10} />
      {metric.values.map((v, i) => {
        if (v.value === null) return null
        const top = Math.min(y(v.value), base)
        const h = Math.max(1, Math.abs(base - y(v.value)))
        const recent = i >= n - 2
        return (
          <rect key={v.year} x={PAD.left + i * bw + 1.5} width={Math.max(2, bw - 3)} y={top} height={h} fill={recent ? '#c2410c' : '#93c5fd'} rx={1.5}>
            <title>{`${v.year}: ${formatNumberPl(v.value, 1)} ${metric.unit}`}</title>
          </rect>
        )
      })}
      {metric.mean_all !== null && (
        <line x1={PAD.left} x2={W - PAD.right} y1={y(metric.mean_all)} y2={y(metric.mean_all)} stroke="#334155" strokeDasharray="4 3" strokeWidth={1.2} />
      )}
      {!relative && lo < 0 && <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} stroke="#64748b" />}
    </svg>
  )
}

export function TrendsView({ data }: { data: ClimateTrends }) {
  const first = data.seasons[0]
  const last = data.seasons[data.seasons.length - 1]
  return (
    <div className="space-y-3">
      <h3 className="flex flex-wrap items-center gap-2 font-semibold">
        Jak zmienia się sezon na tej działce ({first}–{last})
        <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', LEVEL_PILL[data.level])}>{data.label_pl}</span>
      </h3>
      <div className="space-y-2">
        {data.verdict_pl.map((p, i) => (
          <p key={i} className={cn('leading-relaxed', i === 0 && 'font-medium')}>
            {p}
          </p>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {data.metrics.map((m) => (
          <div key={m.key} className="rounded-md border bg-card p-2.5">
            <p className="text-sm font-medium">{m.label_pl}</p>
            <TrendBars metric={m} />
            <div className="flex justify-between pl-[12.5%] text-[11px] text-muted-foreground">
              <span>{m.values[0]?.year}</span>
              <span>{m.values[m.values.length - 1]?.year}</span>
            </div>
            <p className="mt-1 text-xs leading-snug">{m.summary_pl}</p>
          </div>
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <li className="flex items-center gap-1.5">
          <Swatch color="#93c5fd" /> wcześniejsze sezony
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch color="#c2410c" /> ostatnie 2 sezony
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch color="#334155" dashed /> średnia z {data.seasons.length} lat
        </li>
      </ul>
      <p className="text-xs text-muted-foreground">{data.uncertainty_pl}</p>
      <Source text={data.source} />
    </div>
  )
}

// --- slope profile ----------------------------------------------------------------------------------

export function ProfileChart({ data }: { data: SlopeProfile }) {
  const { ref, width: W } = useMeasuredWidth()
  const pts = data.points
  if (pts.length < 2) return null
  const H = W < 480 ? 200 : 240
  const PAD = { top: 24, right: 14, bottom: 34, left: 52 }
  const elev = pts.map((p) => p.elevation_m)
  const zmin = Math.min(...elev)
  const zmax = Math.max(...elev)
  const pad = Math.max(0.5, (zmax - zmin) * 0.15)
  const yTicks = niceTicks(zmin - pad, zmax + pad)
  const lo = yTicks[0]
  const hi = yTicks[yTicks.length - 1]
  const dmax = pts[pts.length - 1].distance_m || 1
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (d: number) => PAD.left + (innerW * d) / dmax
  const y = (z: number) => PAD.top + innerH * (1 - (z - lo) / (hi - lo))
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.distance_m).toFixed(1)},${y(p.elevation_m).toFixed(1)}`).join('')
  const area = `${line}L${x(dmax).toFixed(1)},${(PAD.top + innerH).toFixed(1)}L${x(0).toFixed(1)},${(PAD.top + innerH).toFixed(1)}Z`
  const xStep = niceStep(dmax, W < 480 ? 3 : 5)
  const xTicks: number[] = []
  for (let d = 0; d <= dmax * 0.92; d += xStep) xTicks.push(d)

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">
        Przekrój terenu działki {data.along_long_axis ? 'wzdłuż dłuższego boku' : 'wzdłuż spływu wody'}
        {data.direction_pl && ` (w stronę: ${data.direction_pl})`}
      </figcaption>
      <div ref={ref} className="w-full">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="block h-auto w-full"
          role="img"
          aria-label={`Na długości ${formatNumberPl(data.length_m)} m teren opada o ${formatNumberPl(data.drop_m, 1)} m.`}
        >
          <YAxis ticks={yTicks} y={y} left={PAD.left} right={W - PAD.right} unit="m n.p.m." />
          {xTicks.map((d) => (
            <text key={d} x={x(d)} y={PAD.top + innerH + 14} fontSize="11" fill={AXIS.text} textAnchor="middle">
              {formatNumberPl(d)}
            </text>
          ))}
          <text x={W - PAD.right} y={H - 4} fontSize="11" fill={AXIS.text} textAnchor="end">
            odległość, m
          </text>
          <path d={area} fill="#d9f99d" opacity={0.7} />
          <path d={line} fill="none" stroke="#4d7c0f" strokeWidth={2.5} />
          {pts.map((p, i) =>
            p.hollow ? <circle key={i} cx={x(p.distance_m)} cy={y(p.elevation_m)} r={4} fill="#2563eb" stroke="#fff" strokeWidth={1} /> : null,
          )}
          <text x={x(0) + 4} y={y(pts[0].elevation_m) - 8} fontSize="11" fontWeight="600" fill="#365314">
            góra pola
          </text>
          <text x={x(dmax) - 4} y={y(pts[pts.length - 1].elevation_m) - 8} fontSize="11" fontWeight="600" fill="#365314" textAnchor="end">
            dół pola
          </text>
        </svg>
      </div>
      {pts.some((p) => p.hollow) && (
        <p className="flex items-center gap-2 text-sm">
          <Swatch color="#2563eb" round /> Obniżenie, w którym zbiera się woda po deszczu
        </p>
      )}
      <p className="text-sm leading-relaxed">{data.text_pl}</p>
      <Source text={data.source} />
    </figure>
  )
}

function mmOrMissing(v: number | null): string {
  return v === null ? 'brak danych' : `${formatNumberPl(v)} mm`
}

// --- water plan -------------------------------------------------------------------------------------

const PLAN = { typical: '#93c5fd', dry: '#1d4ed8', p90: '#0f172a', critical: '#fed7aa' }

export function WaterPlanChart({ data }: { data: WaterPlan }) {
  const { ref, width: W } = useMeasuredWidth()
  const months = data.months
  if (months.length === 0) return null
  const H = W < 480 ? 210 : 250
  const PAD = { top: 22, right: 10, bottom: 30, left: 40 }
  const ticks = niceTicks(0, Math.max(10, ...months.flatMap((m) => [m.deficit_median_mm ?? 0, m.deficit_p80_mm ?? 0, m.deficit_p90_mm ?? 0])))
  const maxV = ticks[ticks.length - 1]
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const slot = innerW / months.length
  const bw = Math.min(22, slot * 0.36)
  const y = (v: number) => PAD.top + innerH * (1 - v / maxV)

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">Ile wody trzeba dodać w każdym miesiącu: rok typowy i rok suchy (mm)</figcaption>
      <div ref={ref} className="w-full">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="block h-auto w-full"
          role="img"
          aria-label={months
            .map((m) => `${m.month_pl}: typowo ${mmOrMissing(m.deficit_median_mm)}, w roku suchym ${mmOrMissing(m.deficit_p80_mm)}`)
            .join('; ')}
        >
          {months.map((m, i) =>
            m.critical ? <rect key={`c${m.month}`} x={PAD.left + i * slot} y={PAD.top} width={slot} height={innerH} fill={PLAN.critical} opacity={0.45} /> : null,
          )}
          <YAxis ticks={ticks} y={y} left={PAD.left} right={W - PAD.right} unit="mm" />
          {months.map((m, i) => {
            const cx = PAD.left + i * slot + slot / 2
            // Missing values are not drawn (never shown as 0 mm, CLAUDE.md rule 4).
            const med = m.deficit_median_mm
            const p80 = m.deficit_p80_mm
            return (
              <g key={m.month}>
                {med !== null && (
                  <rect x={cx - bw - 1} width={bw} y={y(med)} height={Math.max(0, y(0) - y(med))} fill={PLAN.typical} rx={1.5}>
                    <title>{`${m.month_pl}, rok typowy: ${formatNumberPl(med)} mm`}</title>
                  </rect>
                )}
                {p80 !== null && (
                  <rect x={cx + 1} width={bw} y={y(p80)} height={Math.max(0, y(0) - y(p80))} fill={PLAN.dry} rx={1.5}>
                    <title>{`${m.month_pl}, rok suchy (raz na 5 lat): ${formatNumberPl(p80)} mm`}</title>
                  </rect>
                )}
                {m.deficit_p90_mm !== null && m.deficit_p90_mm > 0 && (
                  <line x1={cx - 2} x2={cx + bw + 4} y1={y(m.deficit_p90_mm)} y2={y(m.deficit_p90_mm)} stroke={PLAN.p90} strokeWidth={2} />
                )}
                <text x={cx} y={H - 10} fontSize="11" fill={m.critical ? '#9a3412' : AXIS.text} fontWeight={m.critical ? 700 : 400} textAnchor="middle">
                  {m.month_pl.slice(0, 3)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <li className="flex items-center gap-2">
          <Swatch color={PLAN.typical} /> Rok typowy (środek z {data.years} lat)
        </li>
        <li className="flex items-center gap-2">
          <Swatch color={PLAN.dry} /> Rok suchy (raz na 5 lat)
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-block w-5 border-t-2" style={{ borderColor: PLAN.p90 }} aria-hidden /> Bardzo suchy (raz na 10 lat)
        </li>
        <li className="flex items-center gap-2">
          <Swatch color={PLAN.critical} /> Miesiąc, gdy uprawa najbardziej potrzebuje wody
        </li>
      </ul>
      <div className="space-y-2">
        {data.text_pl.map((p, i) => (
          <p key={i} className="leading-relaxed">
            {p}
          </p>
        ))}
      </div>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm tabular-nums">
          <thead className="bg-muted/60 text-left">
            <tr>
              <th className="px-2.5 py-1.5 font-medium">Miesiąc</th>
              <th className="px-2.5 py-1.5 text-right font-medium">Potrzeby uprawy</th>
              <th className="px-2.5 py-1.5 text-right font-medium">Deszcz</th>
              <th className="px-2.5 py-1.5 text-right font-medium">Dodać — rok typowy</th>
              <th className="px-2.5 py-1.5 text-right font-medium">Dodać — rok suchy</th>
              <th className="px-2.5 py-1.5 text-right font-medium">Rok suchy, m³/ha</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {months.map((m) => (
              <tr key={m.month} className={cn(m.critical && 'bg-orange-50')}>
                <td className="px-2.5 py-1.5 font-medium">{m.month_pl}</td>
                <td className="px-2.5 py-1.5 text-right">{mmText(m.crop_need_mm)}</td>
                <td className="px-2.5 py-1.5 text-right">{mmText(m.precip_mm)}</td>
                <td className="px-2.5 py-1.5 text-right">{mmText(m.deficit_median_mm)}</td>
                <td className="px-2.5 py-1.5 text-right font-semibold">{mmText(m.deficit_p80_mm)}</td>
                <td className="px-2.5 py-1.5 text-right">{m.deficit_p80_m3_ha === null ? 'brak danych' : formatNumberPl(m.deficit_p80_m3_ha)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Source text={data.source} />
    </figure>
  )
}

function mmText(v: number | null): string {
  return v === null ? 'brak danych' : `${formatNumberPl(v)} mm`
}
