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

export function niceMax(v: number): number {
  if (v <= 0) return 10
  const step = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / step) * step
}

export const AXIS = { grid: '#e5e7eb', text: '#6b7280' }

/** Step of 1, 2 or 5 × 10^k giving about `count` ticks over `span`. */
export function niceStep(span: number, count = 4): number {
  const raw = Math.max(span, 1e-9) / count
  const pow = 10 ** Math.floor(Math.log10(raw))
  const f = raw / pow
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow
}
