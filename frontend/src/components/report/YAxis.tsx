import { formatNumberPl } from '@/lib/format'
import { AXIS, tickDecimals } from './chartUtils'

// Y axis of the plain-SVG charts (plan2 L1.1): grid lines, round tick values with a Polish decimal comma and the unit
// above the axis. `y` maps a value to the SVG y coordinate.
export function YAxis({
  ticks,
  y,
  left,
  right,
  unit,
  fontSize = 11,
}: {
  ticks: number[]
  y: (v: number) => number
  left: number
  right: number
  unit: string
  fontSize?: number
}) {
  const digits = tickDecimals(ticks)
  return (
    <g data-axis="y">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={right} y1={y(t)} y2={y(t)} stroke={AXIS.grid} />
          <text x={left - 5} y={y(t) + fontSize * 0.35} textAnchor="end" fontSize={fontSize} fill={AXIS.text}>
            {formatNumberPl(t, digits)}
          </text>
        </g>
      ))}
      <text x={2} y={y(ticks[ticks.length - 1]) - fontSize * 0.7} fontSize={fontSize} fill={AXIS.text}>
        {unit}
      </text>
    </g>
  )
}
