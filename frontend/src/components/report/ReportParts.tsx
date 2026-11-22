import { ChevronDown, CircleCheck, CircleHelp, OctagonAlert, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import type {
  Confidence,
  EvidenceItem,
  Headline,
  HeadlineLevel,
  MonthRisk,
  RecommendationCategory,
  ReportIrrigation,
  ReportRecommendation,
  SourceEntry,
  SourceStatus,
} from '@/api/types'
import { cn } from '@/lib/utils'
import { formatDatePl, formatDateTimePl, formatNumberPl, m3WherePl } from '@/lib/format'

// UI labels only; every sentence about the parcel comes ready from the backend (plan, decision 2).

const HEADLINE_STYLE: Record<HeadlineLevel, string> = {
  none: 'border-green-300 bg-green-50 text-green-950',
  light: 'border-amber-300 bg-amber-50 text-amber-950',
  moderate: 'border-orange-300 bg-orange-50 text-orange-950',
  severe: 'border-red-300 bg-red-50 text-red-950',
  unknown: 'border-slate-300 bg-slate-50 text-slate-900',
}
const HEADLINE_DOT: Record<HeadlineLevel, string> = {
  none: 'bg-green-600',
  light: 'bg-yellow-500',
  moderate: 'bg-orange-500',
  severe: 'bg-red-600',
  unknown: 'bg-slate-400',
}

const CONFIDENCE_PL: Record<Confidence, string> = { high: 'wysoka', medium: 'średnia', low: 'niska' }

function HeadlineIcon({ level }: { level: HeadlineLevel }) {
  const Icon = level === 'none' ? CircleCheck : level === 'unknown' ? CircleHelp : level === 'severe' ? OctagonAlert : TriangleAlert
  return (
    <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-full text-white', HEADLINE_DOT[level])} aria-hidden>
      <Icon className="size-5" />
    </span>
  )
}

export function HeadlineBanner({ headline }: { headline: Headline }) {
  return (
    <div className={cn('flex gap-3 rounded-2xl border p-4 shadow-sm', HEADLINE_STYLE[headline.level])} role="status">
      <HeadlineIcon level={headline.level} />
      <div className="min-w-0">
        <p className="text-lg leading-snug font-bold">{headline.label_pl}</p>
        <p className="mt-1 text-base">{headline.sentence_pl}</p>
        <p className="mt-2 text-sm opacity-80">{headline.confidence_pl}</p>
      </div>
    </div>
  )
}

/** Native <details>: works without JS state and is keyboard accessible. Browsers print it closed, so the report
 *  page opens every <details> before printing (see ReportPage) and print CSS keeps the content visible. */
export function Disclosure({ summary, children, className }: { summary: string; children: ReactNode; className?: string }) {
  return (
    <details className={cn('group rounded-md border bg-muted/40', className)}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-sm font-medium [&::-webkit-details-marker]:hidden">
        {summary}
        <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="border-t px-3 py-2">{children}</div>
    </details>
  )
}

function periodText(e: EvidenceItem): string | null {
  if (!e.period) return null
  return e.period.start === e.period.end
    ? formatDatePl(e.period.start)
    : `${formatDatePl(e.period.start)} – ${formatDatePl(e.period.end)}`
}

export function EvidenceList({ items }: { items: EvidenceItem[] }) {
  return (
    <ul className="divide-y">
      {items.map((e) => {
        const period = periodText(e)
        return (
          <li key={e.key} className="py-2">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm">{e.label_pl}</span>
              <span className="shrink-0 font-semibold tabular-nums">{e.value_pl}</span>
            </div>
            <p className="mt-0.5 break-words text-xs text-muted-foreground">
              {period && <>Okres: {period}. </>}
              Pewność: {CONFIDENCE_PL[e.uncertainty.level]}
              {e.uncertainty.reason_pl && <> — {e.uncertainty.reason_pl}</>}. Źródło: {e.source}
            </p>
          </li>
        )
      })}
    </ul>
  )
}

/** Paragraphs from the backend; a paragraph ending with a colon introduces the next ones. */
export function Paragraphs({ items }: { items: string[] }) {
  return (
    <div className="space-y-2.5">
      {items.map((p, i) =>
        p.trimEnd().endsWith(':') ? (
          <h3 key={i} className="pt-1 font-semibold">
            {p}
          </h3>
        ) : (
          <p key={i} className="leading-relaxed">
            {p}
          </p>
        ),
      )}
    </div>
  )
}

const CATEGORY_PL: Record<RecommendationCategory, string> = {
  retention: 'Zatrzymywanie wody',
  agrotech: 'Zabieg na polu',
  irrigation: 'Nawadnianie',
}

/** `hideText`: the section paragraphs already contain this text (irrigation), so the card shows only its numbers. */
export function RecommendationCard({ rec, hideText = false }: { rec: ReportRecommendation; hideText?: boolean }) {
  return (
    <article id={`zalecenie-${rec.number}`} className="scroll-mt-4 rounded-lg border bg-card p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground">
          {rec.number}
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{CATEGORY_PL[rec.category]}</p>
          <h3 className="font-semibold leading-snug">{rec.title_pl}</h3>
          {!hideText && <p className="leading-relaxed">{rec.text_pl}</p>}
          {rec.locations.length > 0 && (
            <p className="text-sm text-primary">Miejsce zaznaczone na mapie numerem {rec.number}.</p>
          )}
        </div>
      </div>
      <Disclosure summary="Dlaczego? Dane dla tej działki" className="mt-3">
        <EvidenceList items={rec.evidence} />
      </Disclosure>
    </article>
  )
}

export function MonthsTable({ months }: { months: MonthRisk[] }) {
  if (months.length === 0) return null
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">W których miesiącach najczęściej brakowało wody (ostatnie 10 lat)</p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-left">
            <tr>
              <th className="px-3 py-2 font-medium">Miesiąc</th>
              <th className="px-3 py-2 text-right font-medium">Lata z niedoborem</th>
              <th className="px-3 py-2 text-right font-medium">Lata z poważnym niedoborem</th>
              <th className="px-3 py-2 text-right font-medium">Średnio dni stresu</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {months.map((m) => (
              <tr key={m.month} className={cn(m.risk && 'bg-orange-50')}>
                <td className="px-3 py-2">
                  <span className="font-medium">{m.month_pl}</span>
                  <span className="mt-0.5 flex flex-wrap gap-1">
                    {m.years_with_data > 0 && m.risk && (
                      <span className="rounded bg-orange-200 px-1.5 py-0.5 text-xs font-medium text-orange-950">częsty niedobór</span>
                    )}
                    {m.critical && (
                      <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">ważny dla uprawy</span>
                    )}
                  </span>
                </td>
                <td className="px-3 py-2 text-right align-top tabular-nums">
                  {m.years_with_data === 0 ? 'brak danych' : `${m.deficit_years} z ${m.years_with_data}`}
                </td>
                <td className="px-3 py-2 text-right align-top tabular-nums">
                  {m.years_with_data === 0 ? '–' : `${m.severe_years} z ${m.years_with_data}`}
                </td>
                <td className="px-3 py-2 text-right align-top tabular-nums">
                  {m.mean_stress_days === null ? '–' : formatNumberPl(m.mean_stress_days, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        „Lata z niedoborem” — uprawie brakowało wody przez co najmniej 1/3 dni miesiąca; „poważny niedobór” — przez co
        najmniej połowę dni. „Częsty niedobór” — wody brakowało w co najmniej 3 na 10 lat. „Ważny dla uprawy” — w tym
        miesiącu uprawa najbardziej potrzebuje wody.
      </p>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-card px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

export function IrrigationBlock({ irrigation, farmCount }: { irrigation: ReportIrrigation; farmCount?: number }) {
  const stats: { label: string; value: string }[] = []
  if (irrigation.within_days === 0) stats.push({ label: 'Termin', value: 'od razu' })
  else if (irrigation.irrigate_by) stats.push({ label: 'Podlej do', value: formatDatePl(irrigation.irrigate_by) })
  if (irrigation.dose_mm !== null) stats.push({ label: 'Dawka wody', value: `${formatNumberPl(irrigation.dose_mm)} mm` })
  if (irrigation.single_dose_mm !== null && irrigation.applications !== null && irrigation.applications > 1) {
    stats.push({
      label: 'Podział dawki',
      value: `${irrigation.applications} × ok. ${formatNumberPl(irrigation.single_dose_mm)} mm`,
    })
  }
  if (irrigation.volume_m3 !== null) stats.push({ label: `Woda ${m3WherePl(farmCount, 'na całą działkę')}`, value: `ok. ${formatNumberPl(irrigation.volume_m3)} m³` })

  return (
    <div className="space-y-3">
      <p className="font-semibold">{irrigation.title_pl}</p>
      {stats.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {stats.map((s) => (
            <Stat key={s.label} {...s} />
          ))}
        </div>
      )}
      {irrigation.evidence.length > 0 && (
        <Disclosure summary="Dlaczego? Dane dla tej działki">
          <EvidenceList items={irrigation.evidence} />
        </Disclosure>
      )}
    </div>
  )
}

const STATUS_PL: Record<SourceStatus, string> = { ok: 'pobrane', degraded: 'z ograniczeniami', missing: 'brak danych' }
const STATUS_STYLE: Record<SourceStatus, string> = {
  ok: 'bg-green-100 text-green-900',
  degraded: 'bg-amber-100 text-amber-900',
  missing: 'bg-red-100 text-red-900',
}

export function SourcesList({ sources }: { sources: SourceEntry[] }) {
  return (
    <ul className="divide-y rounded-md border">
      {sources.map((s) => (
        <li key={s.name} className="space-y-1 px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{s.label_pl}</span>
            <span className={cn('rounded px-2 py-0.5 text-xs font-medium', STATUS_STYLE[s.status])}>{STATUS_PL[s.status]}</span>
          </div>
          {s.message_pl && <p className="text-sm">{s.message_pl}</p>}
          <p className="break-words text-xs text-muted-foreground">
            {s.source}. Licencja: {s.license}. Pobrano: {formatDateTimePl(s.fetched_at)}
            {s.period && <>. Zakres danych: {formatDatePl(s.period.start)} – {formatDatePl(s.period.end)}</>}.
          </p>
        </li>
      ))}
    </ul>
  )
}
