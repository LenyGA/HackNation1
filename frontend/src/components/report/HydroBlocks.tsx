import type { FloodInfo, GroundwaterInfo } from '@/api/types'
import { formatDatePl, formatNumberPl } from '@/lib/format'
import { cn } from '@/lib/utils'

const FLOOD_PILL: Record<FloodInfo['level'], string> = {
  high: 'bg-red-600 text-white',
  medium: 'bg-orange-500 text-white',
  low: 'bg-amber-200 text-amber-950',
  none: 'bg-green-600 text-white',
  unknown: 'bg-slate-200 text-slate-800',
}

function hitText(hit: boolean | null): string {
  return hit === null ? 'nie sprawdzono' : hit ? 'tak' : 'nie'
}

export function FloodBlock({ flood }: { flood: FloodInfo }) {
  return (
    <div className="space-y-2 rounded-lg border bg-card p-3.5">
      <h3 className="flex flex-wrap items-center gap-2 font-semibold">
        Zagrożenie powodzią
        <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', FLOOD_PILL[flood.level])}>{flood.label_pl}</span>
      </h3>
      <p className="leading-relaxed">{flood.sentence_pl}</p>
      {flood.zones.length > 0 && (
        <ul className="divide-y rounded-md border text-sm">
          {flood.zones.map((z) => (
            <li key={z.id} className="flex items-center justify-between gap-3 px-3 py-1.5">
              <span>{z.label_pl}</span>
              <span className={cn('shrink-0 font-semibold', z.hit === true && 'text-red-700', z.hit === null && 'text-muted-foreground')}>
                {hitText(z.hit)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">Źródło: {flood.source}</p>
    </div>
  )
}

const GW_PILL: Record<NonNullable<GroundwaterInfo['trend']>, { text: string; cls: string }> = {
  falling: { text: 'spada', cls: 'bg-red-600 text-white' },
  stable: { text: 'stabilny', cls: 'bg-slate-200 text-slate-900' },
  rising: { text: 'rośnie', cls: 'bg-green-600 text-white' },
}

export function GroundwaterBlock({ gw }: { gw: GroundwaterInfo }) {
  const pill = gw.trend ? GW_PILL[gw.trend] : null
  return (
    <div className="space-y-2 rounded-lg border bg-card p-3.5">
      <h3 className="flex flex-wrap items-center gap-2 font-semibold">
        Poziom wód podziemnych w okolicy
        {pill && <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', pill.cls)}>{pill.text}</span>}
      </h3>
      <p className="leading-relaxed">{gw.sentence_pl}</p>
      {(gw.station_pl || gw.distance_km !== null || gw.period) && (
        <p className="text-sm text-muted-foreground">
          {gw.station_pl && <>Stacja: {gw.station_pl}. </>}
          {gw.distance_km !== null && <>Odległość od działki: ok. {formatNumberPl(gw.distance_km)} km. </>}
          {gw.change_m !== null && <>Zmiana poziomu: {formatNumberPl(gw.change_m, 2)} m. </>}
          {gw.period && (
            <>
              Okres: {formatDatePl(gw.period.start)} – {formatDatePl(gw.period.end)}.
            </>
          )}
        </p>
      )}
      <p className="text-xs text-muted-foreground">Źródło: {gw.source}</p>
    </div>
  )
}
