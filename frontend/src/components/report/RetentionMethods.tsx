import type { RetentionMethodStatus, RetentionPlan } from '@/api/types'
import { Disclosure, EvidenceList } from '@/components/report/ReportParts'
import { cn } from '@/lib/utils'

// G9: coverage card (depression volume vs dry-year needs) and the five ways to keep or store water.
// Statuses and sentences come ready from the backend; nothing is computed here.

const STATUS_PILL: Record<RetentionMethodStatus, string> = {
  recommended: 'bg-green-600 text-white',
  conditional: 'bg-amber-200 text-amber-950',
  not_recommended: 'bg-red-100 text-red-900',
  no_data: 'bg-slate-200 text-slate-800',
}

const COVERAGE_BORDER: Record<string, string> = {
  good: 'border-l-green-600',
  warn: 'border-l-amber-500',
  unknown: 'border-l-slate-400',
}

export function CoverageCard({ plan }: { plan: RetentionPlan }) {
  const c = plan.coverage
  const tone = c.full_pct !== null && c.full_pct >= 100 ? 'good' : c.status === 'ok' ? 'warn' : 'unknown'
  return (
    <div className={cn('space-y-1 rounded-lg border border-l-4 bg-card p-3.5', COVERAGE_BORDER[tone])}>
      <h3 className="font-semibold">Ile wody da retencja na działce?</h3>
      {c.full_pct !== null && (
        <div className="flex items-center gap-3" aria-hidden>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-sky-600" style={{ width: `${Math.min(100, c.full_pct)}%` }} />
          </div>
          <span className="shrink-0 text-sm font-semibold tabular-nums">{c.full_pct >= 100 ? '100 %' : `${c.full_pct} %`}</span>
        </div>
      )}
      <p className="leading-relaxed">{c.text_pl}</p>
      <p className="break-words text-xs text-muted-foreground">Źródło: {c.source}</p>
    </div>
  )
}

export function RetentionMethods({ plan, onlyRecommended = false }: { plan: RetentionPlan; onlyRecommended?: boolean }) {
  const methods = onlyRecommended ? plan.methods.filter((m) => m.status === 'recommended') : plan.methods
  return (
    <div className="space-y-3">
      <CoverageCard plan={plan} />
      {methods.length > 0 ? (
        <ul className="divide-y rounded-lg border bg-card">
          {methods.map((m) => (
            <li key={m.id} className="space-y-1.5 p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{m.label_pl}</span>
                <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', STATUS_PILL[m.status])}>{m.status_pl}</span>
              </div>
              <p className="text-sm leading-relaxed">{m.reason_pl}</p>
              {m.legal_pl && (
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">Formalności:</span> {m.legal_pl}
                </p>
              )}
              {m.evidence.length > 0 && (
                <Disclosure summary="Dlaczego? Dane dla tej działki">
                  <EvidenceList items={m.evidence} />
                </Disclosure>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm">
          Żaden sposób gromadzenia wody nie jest dla tej działki wyraźnie polecany; ocenę wszystkich pięciu sposobów pokazuje
          wariant pełny.
        </p>
      )}
      {!onlyRecommended && (
        <p className="text-xs text-muted-foreground">
          Ocena wynika z reguł sprawdzających dane tej działki; „brak danych” oznacza, że źródło nie odpowiedziało, a nie, że
          sposób się nie nadaje. Podstawa prawna: {plan.legal_basis_pl}.
        </p>
      )}
    </div>
  )
}
