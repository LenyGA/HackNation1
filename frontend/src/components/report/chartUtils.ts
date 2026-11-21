import { useEffect, useRef, useState } from 'react'

// Shared helpers for the plain-SVG charts: the SVG is drawn in screen pixels at the measured width,
// so labels keep a readable size on a phone.

export const MIN_CHART_W = 260

export function useMeasuredWidth(initial = 640) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(initial)
  useEffect(() => {
    const box = ref.current
    if (!box) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(MIN_CHART_W, Math.round(entry.contentRect.width))))
    ro.observe(box)
    return () => ro.disconnect()
  }, [])
  return { ref, width }
}

export const AXIS = { grid: '#e5e7eb', text: '#6b7280' }

/** Step of 1, 2 or 5 × 10^k giving about `count` ticks over `span`. */
export function niceStep(span: number, count = 4): number {
  const raw = Math.max(span, 1e-9) / count
  const pow = 10 ** Math.floor(Math.log10(raw))
  const f = raw / pow
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow
}

/** 3–6 round tick values covering [lo, hi]; the first and last tick are the axis limits (mirror of `nice_ticks` in charts_svg.py). */
export function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!(hi > lo)) hi = lo + 1
  const step = niceStep(hi - lo, count)
  const start = Math.floor(lo / step + 1e-9) * step
  const end = Math.ceil(hi / step - 1e-9) * step
  const n = Math.round((end - start) / step)
  return Array.from({ length: n + 1 }, (_, i) => Number((start + i * step).toFixed(10)))
}

/** Number of decimals needed to print every tick exactly ('0', '0,25', '1'). */
export function tickDecimals(ticks: number[]): number {
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1
  for (let d = 0; d < 7; d++) if (Math.abs(Number(step.toFixed(d)) - step) < 1e-9) return d
  return 6
}
