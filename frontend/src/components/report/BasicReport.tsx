import type { Report, ReportRecommendation } from '@/api/types'
import { Disclosure, EvidenceList, IrrigationBlock } from '@/components/report/ReportParts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDatePl } from '@/lib/format'

// Basic report (plan M3.2): the verdict of each section, actions now / before the next season, explicit missing
// data, limitations and sources. Every sentence comes ready from the backend; nothing is computed here.

const SOURCE_STATUS_PL = { ok: 'pobrano', degraded: 'z ograniczeniami', missing: 'brak danych' } as const

function ActionItem({
  rec,
  report,
  short,
  hideTitle = false,
}: {
  rec: ReportRecommendation
  report: Report
  short: boolean
  hideTitle?: boolean
}) {
  const text = short ? rec.summary_pl : rec.category === 'irrigation' ? report.irrigation.text_pl : rec.text_pl
  return (
    <li className="flex gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
        {rec.number}
      </span>
      <div className="min-w-0 space-y-1">
        {!hideTitle && <p className="font-semibold leading-snug">{rec.title_pl}</p>}
        <p className="text-sm">{text}</p>
        <Disclosure summary="Dlaczego? Dane dla tej działki" className="mt-1">
          <EvidenceList items={rec.evidence} />
        </Disclosure>
      </div>
    </li>
  )
}

export function BasicReport({ report }: { report: Report }) {
  const verdicts = report.sections.filter((s) => s.verdict_pl)
  const now = report.recommendations.filter((r) => r.horizon === 'now')
  const season = report.recommendations.filter((r) => r.horizon === 'season')
  const irrigationNow = now.some((r) => r.category === 'irrigation') && report.irrigation.applicable

  return (
    <div className="space-y-4">
      {verdicts.length > 0 && (
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-lg">Najważniejsze wnioski</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {verdicts.map((s) => (
                <li key={s.id}>
                  <span className="font-semibold">
                    {s.id === 'causes' && report.headline.level === 'none' ? 'Co może sprzyjać niedoborom wody' : s.title_pl}:
                  </span>{' '}
                  {s.verdict_pl}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {report.complete && (
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-lg">Co zrobić teraz</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {irrigationNow && <IrrigationBlock irrigation={report.irrigation} />}
            {now.length > 0 ? (
              <ol className="space-y-3">
                {now.map((r) => (
                  <ActionItem
                    key={r.number}
                    rec={r}
                    report={report}
                    short={false}
                    hideTitle={irrigationNow && r.category === 'irrigation'}
                  />
                ))}
              </ol>
            ) : (
              <p>
                Na dzień analizy dane nie wskazują pilnych działań na polu
                {season.length > 0
                  ? ' — skorzystaj z zaleceń na następny sezon.'
                  : ' ani potrzeby dodatkowych działań na tej działce.'}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {report.complete && season.length > 0 && (
        <Card className="gap-3">
          <CardHeader>
            <CardTitle className="text-lg">Przed następnym sezonem</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {season.map((r) => (
                <ActionItem key={r.number} rec={r} report={report} short />
              ))}
            </ol>
            <p className="mt-3 text-sm text-muted-foreground">
              Uzasadnienie liczbami, mapa miejsc i pełny opis każdego zalecenia są w wariancie pełnym raportu.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="gap-3">
        <CardHeader>
          <CardTitle className="text-lg">Braki danych i ograniczenia</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {report.missing_data_pl.length > 0 ? (
            <ul className="space-y-1.5">
              {report.missing_data_pl.map((line) => (
                <li key={line} className="rounded-md border border-amber-400 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-950">
                  {line}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm">Wszystkie źródła danych odpowiedziały w pełni.</p>
          )}
          <Disclosure summary={`Ograniczenia analizy (${report.limitations_pl.length})`}>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {report.limitations_pl.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Disclosure>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        <span className="font-semibold">Źródła danych</span> (pobrane na żywo, ograniczone do dnia analizy):{' '}
        {report.sources.map((s, i) => (
          <span key={s.name}>
            {s.label_pl} — {SOURCE_STATUS_PL[s.status]} {formatDatePl(s.fetched_at)}
            {i < report.sources.length - 1 ? ' · ' : '.'}
          </span>
        ))}
      </p>
    </div>
  )
}
