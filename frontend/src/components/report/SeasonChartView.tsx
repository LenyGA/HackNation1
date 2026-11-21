import { type PointerEvent, useEffect, useRef, useState } from 'react'
import type { ChartPoint, SeasonChart } from '@/api/types'
import { formatDatePl, formatMonthPl, formatNumberPl, formatShortDatePl } from '@/lib/format'
import { niceTicks } from './chartUtils'
import { YAxis } from './YAxis'

// Plain SVG chart (no chart library): cumulative rain this season against the range of the previous years,
// and the cumulative water need of the crop.

// The SVG is drawn in screen pixels at the measured width, so text keeps a readable size on a phone.
const DEFAULT_W = 640
const MIN_W = 260
const PAD = { top: 22, right: 12, bottom: 28, left: 44 }
const COLORS = {
  band: '#bfdbfe',
  median: '#3b82f6',
  precip: '#1d4ed8',
  need: '#ea580c',
}

type Key = 'precip_mm' | 'crop_need_mm' | 'precip_hist_median_mm'

function linePath(points: ChartPoint[], key: Key, x: (i: number) => number, y: (v: number) => number): string {
  let d = ''
  let pen = false
  points.forEach((p, i) => {
    const v = p[key]
    if (v === null) {
      pen = false
      return
    }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
    pen = true
  })
  return d
}

function bandPath(points: ChartPoint[], x: (i: number) => number, y: (v: number) => number): string {
  const idx = points.map((_, i) => i).filter((i) => points[i].precip_hist_min_mm !== null && points[i].precip_hist_max_mm !== null)
  if (idx.length < 2) return ''
  const top = idx.map((i) => `${x(i).toFixed(1)},${y(points[i].precip_hist_max_mm as number).toFixed(1)}`)
  const bottom = [...idx].reverse().map((i) => `${x(i).toFixed(1)},${y(points[i].precip_hist_min_mm as number).toFixed(1)}`)
  return `M${top.join('L')}L${bottom.join('L')}Z`
}

const DAY_MS = 86_400_000

function dayNumber(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / DAY_MS
}

function mm(v: number | null): string {
  return v === null ? 'brak danych' : `${formatNumberPl(v)} mm`
}

export function SeasonChartView({ chart }: { chart: SeasonChart }) {
  const pts = chart.points
  const [hover, setHover] = useState<number | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const [W, setW] = useState(DEFAULT_W)

  useEffect(() => {
    const box = boxRef.current
    if (!box) return
    const ro = new ResizeObserver(([entry]) => setW(Math.max(MIN_W, Math.round(entry.contentRect.width))))
    ro.observe(box)
    return () => ro.disconnect()
  }, [])

  if (pts.length < 2) return null
  const H = W < 480 ? 220 : 280

  const values = pts.flatMap((p) => [p.precip_mm, p.crop_need_mm, p.precip_hist_max_mm]).filter((v): v is number => v !== null)
  const yTicks = niceTicks(0, Math.max(10, ...values))
  const yMax = yTicks[yTicks.length - 1]
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  // Points are not evenly spaced in time (weekly, then the analysis day), so x follows the date.
  const d0 = dayNumber(pts[0].day)
  const span = Math.max(1, dayNumber(pts[pts.length - 1].day) - d0)
  const xs = pts.map((p) => PAD.left + (innerW * (dayNumber(p.day) - d0)) / span)
  const x = (i: number) => xs[i]
  const y = (v: number) => PAD.top + innerH * (1 - v / yMax)
  // A tick at the first point of every month, skipping ticks that would overlap on a narrow screen.
  const minGap = 46
  const xTicks: { i: number; day: string }[] = []
  pts.forEach((p, i) => {
    const newMonth = i === 0 || p.day.slice(5, 7) !== pts[i - 1].day.slice(5, 7)
    const prev = xTicks[xTicks.length - 1]
    if (newMonth && (!prev || xs[i] - xs[prev.i] >= minGap) && xs[i] <= W - PAD.right - minGap / 2) xTicks.push({ i, day: p.day })
  })

  const last = pts[pts.length - 1]
  const shown = hover === null ? last : pts[hover]
  const hasBand = chart.years > 0 && pts.some((p) => p.precip_hist_max_mm !== null)

  function onMove(e: PointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    let best = 0
    xs.forEach((v, i) => {
      if (Math.abs(v - px) < Math.abs(xs[best] - px)) best = i
    })
    setHover(best)
  }

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">
        Deszcz i potrzeby uprawy od {formatDatePl(chart.start)} do {formatDatePl(chart.end)} (narastająco)
      </figcaption>
      <div ref={boxRef} className="w-full">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="block h-auto w-full touch-pan-y select-none"
          role="img"
          aria-label={`Do ${formatDatePl(last.day)} spadło ${mm(last.precip_mm)} deszczu, uprawa potrzebowała ${mm(last.crop_need_mm)}${hasBand ? `, zwykle w tym okresie spadało ${mm(last.precip_hist_median_mm)}` : ''}.`}
          onPointerDown={onMove}
          onPointerMove={onMove}
          // On touch the chosen day stays shown after the finger lifts; with a mouse it resets on leaving.
          onPointerLeave={(e) => e.pointerType === 'mouse' && setHover(null)}
        >
          <YAxis ticks={yTicks} y={y} left={PAD.left} right={W - PAD.right} unit="mm" />
          {xTicks.map(({ i, day }) => (
            <text key={day} x={x(i)} y={H - 8} fontSize="11" fill="#6b7280" textAnchor={i === 0 ? 'start' : 'middle'}>
              {i === 0 ? formatShortDatePl(day) : formatMonthPl(day)}
            </text>
          ))}
          {hasBand && <path d={bandPath(pts, x, y)} fill={COLORS.band} opacity={0.6} />}
          {hasBand && (
            <path d={linePath(pts, 'precip_hist_median_mm', x, y)} fill="none" stroke={COLORS.median} strokeWidth={1.5} strokeDasharray="5 4" />
          )}
          <path d={linePath(pts, 'crop_need_mm', x, y)} fill="none" stroke={COLORS.need} strokeWidth={2.5} />
          <path d={linePath(pts, 'precip_mm', x, y)} fill="none" stroke={COLORS.precip} strokeWidth={2.5} />
          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="#9ca3af" strokeDasharray="3 3" />
          )}
        </svg>
      </div>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        <div className="col-span-full text-xs text-muted-foreground">
          {hover === null ? 'Stan na dzień analizy' : `Stan na ${formatDatePl(shown.day)}`} · dotknij wykresu lub najedź kursorem, aby zobaczyć inny dzień
        </div>
        <LegendRow color={COLORS.precip} label="Deszcz w tym sezonie" value={mm(shown.precip_mm)} />
        <LegendRow color={COLORS.need} label="Potrzeby wodne uprawy" value={mm(shown.crop_need_mm)} />
        {hasBand && (
          <>
            <LegendRow color={COLORS.median} dashed label={`Zwykle (środek z ${chart.years} lat)`} value={mm(shown.precip_hist_median_mm)} />
            <LegendRow
              color={COLORS.band}
              band
              label="Najsuchszy i najmokrzejszy rok"
              value={
                shown.precip_hist_min_mm === null || shown.precip_hist_max_mm === null
                  ? 'brak danych'
                  : `${formatNumberPl(shown.precip_hist_min_mm)}–${formatNumberPl(shown.precip_hist_max_mm)} mm`
              }
            />
          </>
        )}
      </dl>
      <p className="text-xs text-muted-foreground">Źródło: {chart.source}</p>
    </figure>
  )
}

function LegendRow({
  color,
  label,
  value,
  dashed,
  band,
}: {
  color: string
  label: string
  value: string
  dashed?: boolean
  band?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="flex items-center gap-2">
        {band ? (
          <span className="inline-block h-3 w-5 rounded-sm" style={{ background: color }} />
        ) : (
          <span
            className="inline-block w-5"
            style={{ borderTop: `${dashed ? 2 : 3}px ${dashed ? 'dashed' : 'solid'} ${color}` }}
          />
        )}
        {label}
      </dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  )
}
