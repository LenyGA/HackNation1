import type { Gauge, ReportSection, SummaryTile, TileStatus } from '@/api/types'
import { formatNumberPl } from '@/lib/format'
import { cn } from '@/lib/utils'

const TILE_STYLE: Record<TileStatus, string> = {
  good: 'border-green-600 bg-green-50 text-green-950',
  warn: 'border-amber-500 bg-amber-50 text-amber-950',
  bad: 'border-red-600 bg-red-50 text-red-950',
  unknown: 'border-slate-300 bg-slate-50 text-slate-900',
}
// Screen readers do not see the colour: the status is read out as text.
const STATUS_PL: Record<TileStatus, string> = { good: 'dobrze', warn: 'uwaga', bad: 'źle', unknown: 'brak danych' }

const DOT: Record<TileStatus, string> = {
  good: 'bg-green-600',
  warn: 'bg-amber-500',
  bad: 'bg-red-600',
  unknown: 'bg-slate-400',
}
const FILL: Record<TileStatus, string> = {
  good: 'bg-green-600',
  warn: 'bg-amber-500',
  bad: 'bg-red-600',
  unknown: 'bg-slate-400',
}

/** "Battery" of water in the root zone: filled share, with a marker at the crop stress threshold. */
function Battery({ gauge, status }: { gauge: Gauge; status: TileStatus }) {
  const max = gauge.max > 0 ? gauge.max : 1
  const share = Math.min(1, Math.max(0, gauge.value / max))
  const thr = gauge.threshold !== null ? Math.min(1, Math.max(0, gauge.threshold / max)) : null
  return (
    <div className="mt-2">
      <div
        className="relative h-5 w-full overflow-hidden rounded-md border-2 border-current/40 bg-white"
        role="img"
        aria-label={`Zapas wody: ${formatNumberPl(gauge.value)} z ${formatNumberPl(gauge.max)} ${gauge.unit}${
          gauge.threshold !== null ? `, próg stresu ${formatNumberPl(gauge.threshold)} ${gauge.unit}` : ''
        }`}
      >
        <div className={cn('h-full', FILL[status])} style={{ width: `${share * 100}%` }} />
        {thr !== null && <div className="absolute inset-y-0 w-0.5 bg-slate-900" style={{ left: `${thr * 100}%` }} />}
      </div>
      {thr !== null && gauge.threshold !== null && (
        <div className="relative mt-0.5 h-4 text-[11px] opacity-80">
          <span
            className="absolute whitespace-nowrap"
            style={{ left: `${thr * 100}%`, transform: `translateX(${thr > 0.7 ? '-100%' : thr < 0.15 ? '0' : '-50%'})` }}
          >
            próg stresu: {formatNumberPl(gauge.threshold)} {gauge.unit}
          </span>
        </div>
      )}
    </div>
  )
}

export function SummaryTiles({ tiles, sections }: { tiles: SummaryTile[]; sections: ReportSection[] }) {
  if (tiles.length === 0) return null
  const numberOf = (id: string | null) => sections.find((s) => s.id === id)?.number
  return (
    <section aria-label="W skrócie" className="space-y-2">
      <h2 className="text-lg font-bold">W skrócie</h2>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((t) => {
          const n = numberOf(t.link_section)
          const body = (
            <>
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide opacity-80">
                <span className={cn('inline-block size-2.5 rounded-full', DOT[t.status])} aria-hidden />
                {t.label_pl}
                <span className="sr-only">, stan: {STATUS_PL[t.status]}</span>
              </p>
              <p className="mt-1 text-xl font-bold leading-tight">{t.value_pl}</p>
              {t.gauge && <Battery gauge={t.gauge} status={t.status} />}
              {n !== undefined && <p className="mt-auto pt-1.5 text-xs font-medium underline-offset-2 group-hover:underline">Więcej <span aria-hidden>→</span></p>}
            </>
          )
          const cls = cn('group flex flex-col rounded-lg border-l-4 p-3.5 shadow-sm', TILE_STYLE[t.status])
          return n !== undefined ? (
            <a key={t.id} href={`#sekcja-${n}`} className={cls}>
              {body}
            </a>
          ) : (
            <div key={t.id} className={cls}>
              {body}
            </div>
          )
        })}
      </div>
    </section>
  )
}
