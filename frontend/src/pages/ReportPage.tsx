import { Check, Download, Link2, Loader2, Printer, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, ApiRequestError } from '@/api/client'
import type { Farm, Report, ReportSection, ReportVariant } from '@/api/types'
import { ReportMapView } from '@/components/map/ReportMapView'
import {
  Disclosure,
  EvidenceList,
  HeadlineBanner,
  IrrigationBlock,
  MonthsTable,
  Paragraphs,
  RecommendationCard,
  SourcesList,
} from '@/components/report/ReportParts'
import { IrrigationEconomicsBlock } from '@/components/report/IrrigationEconomics'
import { RetentionMethods } from '@/components/report/RetentionMethods'
import { ProfileChart, SatelliteChart, StressHeatmapView, TrendsView, WaterPlanChart } from '@/components/report/Charts'
import { FloodBlock, GroundwaterBlock } from '@/components/report/HydroBlocks'
import { BasicReport } from '@/components/report/BasicReport'
import { SeasonChartView } from '@/components/report/SeasonChartView'
import { Simulator } from '@/components/report/Simulator'
import { SummaryTiles } from '@/components/report/SummaryTiles'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatAreaHa, formatDatePl, formatDateTimePl, parcelsPl } from '@/lib/format'

/** ULDK names sometimes already carry the prefix ("powiat miński"); never write it twice. */
function withPrefix(prefix: string, name: string | null): string | null {
  if (!name) return null
  return name.toLowerCase().startsWith(prefix.replace('.', '')) ? name : `${prefix} ${name}`
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Clipboard API needs HTTPS or localhost; fall back to a hidden text area.
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}

function Actions({ report, variant }: { report: Report; variant: ReportVariant }) {
  const [copied, setCopied] = useState(false)
  const [printing, setPrinting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const frameRef = useRef<HTMLIFrameElement | null>(null)

  useEffect(() => () => frameRef.current?.remove(), [])

  function print() {
    const url = api.reportPrintUrl(report.id, variant)
    // iOS Safari ignores print() inside a frame and prints the parent page: open the print view instead.
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))
    if (ios) {
      window.open(url, '_blank', 'noopener')
      return
    }
    // Elsewhere print the print view (same HTML and stylesheet as the PDF) from a hidden frame.
    frameRef.current?.remove()
    const frame = document.createElement('iframe')
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
    frame.src = url
    setPrinting(true)
    setActionError(null)
    frame.onload = () => {
      setPrinting(false)
      try {
        // An error response (JSON) must not be printed.
        if (frame.contentDocument?.contentType !== 'text/html') {
          setActionError('Nie udało się przygotować wydruku. Spróbuj ponownie albo pobierz PDF.')
          return
        }
        frame.contentWindow?.focus()
        frame.contentWindow?.print()
      } catch {
        window.open(url, '_blank', 'noopener')
      }
    }
    document.body.appendChild(frame)
    frameRef.current = frame
  }

  async function copy() {
    const link = `${window.location.origin}${window.location.pathname}${window.location.search}`
    if (await copyText(link)) {
      setActionError(null)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } else {
      setActionError(`Nie udało się skopiować. Zapisz ten adres: ${link}`)
    }
  }

  return (
    <div className="space-y-2">
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      <Button asChild size="lg" className="h-12">
        <a href={api.reportPdfUrl(report.id, variant)} download>
          <Download /> Pobierz PDF {variant === 'basic' ? '(podstawowy)' : '(pełny)'}
        </a>
      </Button>
      <Button type="button" variant="outline" size="lg" className="h-12" onClick={print} disabled={printing}>
        {printing ? <Loader2 className="animate-spin" /> : <Printer />} Drukuj
      </Button>
      <Button type="button" variant="outline" size="lg" className="h-12" onClick={() => void copy()}>
        {copied ? <Check /> : <Link2 />} {copied ? 'Skopiowano' : 'Kopiuj link do raportu'}
      </Button>
    </div>
    {actionError && (
      <p role="alert" className="break-words text-sm text-destructive">
        {actionError}
      </p>
    )}
    </div>
  )
}

function VariantSwitch({ variant, onChange }: { variant: ReportVariant; onChange: (v: ReportVariant) => void }) {
  const options: { value: ReportVariant; label: string; hint: string }[] = [
    { value: 'basic', label: 'Podstawowy', hint: 'najważniejsze wnioski i działania, 1–2 strony' },
    { value: 'full', label: 'Pełny', hint: 'wszystkie sekcje z wykresami, mapą i liczbami' },
  ]
  return (
    <div
      id="wariant"
      role="group"
      aria-label="Wariant raportu"
      className="grid scroll-mt-4 grid-cols-2 gap-1 rounded-lg border bg-muted/50 p-1"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={variant === o.value}
          onClick={() => {
            onChange(o.value)
            // The other view has a different length: show its top instead of a random place mid-page.
            document.getElementById('wariant')?.scrollIntoView()
          }}
          className={`min-h-11 rounded-md px-3 py-1.5 text-left transition-colors ${
            variant === o.value ? 'bg-background font-semibold shadow-sm' : 'text-muted-foreground hover:bg-background/60'
          }`}
        >
          <span className="block">Raport {o.label.toLowerCase()}</span>
          <span className="block text-xs font-normal text-muted-foreground">{o.hint}</span>
        </button>
      ))}
    </div>
  )
}

function SectionExtras({ section, report }: { section: ReportSection; report: Report }) {
  const recs = report.recommendations.filter((r) => section.recommendation_numbers.includes(r.number))
  const cards = (hideIrrigationText = false) =>
    recs.map((r) => <RecommendationCard key={r.number} rec={r} hideText={hideIrrigationText && r.category === 'irrigation'} />)
  switch (section.id) {
    case 'current':
      return (
        <>
          {report.chart && <SeasonChartView chart={report.chart} />}
          {report.satellite && <SatelliteChart data={report.satellite} analysisDate={report.analysis_date} />}
        </>
      )
    case 'vulnerability':
      return (
        <>
          <MonthsTable months={report.months} />
          {report.stress_heatmap && <StressHeatmapView data={report.stress_heatmap} />}
          {report.trends && <TrendsView data={report.trends} />}
        </>
      )
    case 'causes':
      return (
        <>
          {report.groundwater && <GroundwaterBlock gw={report.groundwater} />}
          {cards()}
        </>
      )
    case 'retention':
      return (
        <>
          <ReportMapView map={report.map} flood={report.flood} />
          {report.flood && <FloodBlock flood={report.flood} />}
          {report.profile && <ProfileChart data={report.profile} />}
          {report.retention_plan && (
            <div className="space-y-2">
              <h3 className="text-base font-semibold">Jak zatrzymać i zgromadzić wodę na tej działce</h3>
              <RetentionMethods plan={report.retention_plan} />
            </div>
          )}
          {cards()}
        </>
      )
    case 'agrotech':
      return <>{cards()}</>
    case 'irrigation':
      return (
        <>
          {/* The irrigation text is already in the section paragraphs: the card shows only its evidence. */}
          {cards(true)}
          {report.water_plan && <WaterPlanChart data={report.water_plan} />}
          {report.irrigation_economics && <IrrigationEconomicsBlock e={report.irrigation_economics} />}
          {report.simulation && <Simulator sim={report.simulation} farmCount={report.farm?.count} />}
        </>
      )
    case 'sources':
      return <SourcesList sources={report.sources} />
    default:
      return recs.length > 0 ? <>{cards()}</> : null
  }
}

function sectionParagraphs(section: ReportSection, report: Report): string[] {
  // The sources section lists each source as structured rows below; keep only the general sentences.
  if (section.id !== 'sources') return section.paragraphs_pl
  const labels = report.sources.map((s) => `${s.label_pl}:`)
  return section.paragraphs_pl.filter((p) => !labels.some((l) => p.startsWith(l)))
}

function SectionCard({ section, report }: { section: ReportSection; report: Report }) {
  return (
    <Card id={`sekcja-${section.number}`} className="scroll-mt-4 gap-4">
      <CardHeader>
        <CardTitle className="flex items-baseline gap-2 text-lg">
          <span className="text-muted-foreground">{section.number}.</span>
          {section.title_pl}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {section.id === 'irrigation' && report.irrigation.applicable && <IrrigationBlock irrigation={report.irrigation} farmCount={report.farm?.count} />}
        <Paragraphs items={sectionParagraphs(section, report)} />
        <SectionExtras section={section} report={report} />
        {section.indicators.length > 0 && (
          <Disclosure summary="Liczby, na których opiera się ocena">
            <EvidenceList items={section.indicators} />
          </Disclosure>
        )}
        {section.details_pl.length > 0 && (
          <Disclosure summary="Szczegóły dla zainteresowanych">
            <div className="space-y-2 text-sm text-muted-foreground">
              {section.details_pl.map((d, i) => (
                <p key={i}>{d}</p>
              ))}
            </div>
          </Disclosure>
        )}
      </CardContent>
    </Card>
  )
}

/** Farm mode (G11): which results are sums over all parcels and which describe the main parcel only. */
function FarmNote({ farm }: { farm: Farm }) {
  return (
    <div className="space-y-1.5 rounded-md border border-sky-400/50 bg-sky-50 px-3 py-2 text-sm dark:bg-sky-950/30">
      <p className="font-semibold">
        Gospodarstwo: {farm.count} {parcelsPl(farm.count)}, {formatAreaHa(farm.total_area_ha)}
      </p>
      {farm.text_pl.map((t) => (
        <p key={t}>{t}</p>
      ))}
      <ul className="text-xs text-muted-foreground">
        {farm.parcels.map((fp) => (
          <li key={fp.id}>
            Działka {fp.number ? `${fp.number} (${fp.id})` : fp.id} · {formatAreaHa(fp.area_ha)}
            {fp.distance_m !== null &&
              (fp.distance_m === 0 ? ' · przylega do głównej' : ` · ok. ${Math.round(fp.distance_m)} m od głównej`)}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ReportPage() {
  const { id = '' } = useParams()
  // The variant lives in the URL (?variant=full), so a shared link opens the same view; basic is the default.
  const location = useLocation()
  const navigate = useNavigate()
  const variant: ReportVariant = new URLSearchParams(location.search).get('variant') === 'full' ? 'full' : 'basic'
  const setVariant = (v: ReportVariant) => {
    const next = new URLSearchParams(location.search)
    if (v === 'basic') next.delete('variant')
    else next.set('variant', v)
    const search = next.toString()
    // Keep the #sekcja-N hash when opening the full view (a deep link still scrolls there); drop it for the basic
    // view, which has no sections, otherwise the deep-link effect below would switch straight back to full.
    navigate({ search: search ? `?${search}` : '', hash: v === 'full' ? window.location.hash : '' }, { replace: true })
  }
  // Result tagged with the id it belongs to, so a stale report is never shown after navigating to another one.
  const [loaded, setLoaded] = useState<{ id: string; report?: Report; error?: string } | null>(null)
  const report = loaded?.id === id ? (loaded.report ?? null) : null
  const error = loaded?.id === id ? (loaded.error ?? null) : null

  useEffect(() => {
    let alive = true
    api
      .report(id)
      .then((r) => alive && setLoaded({ id, report: r }))
      .catch((err: unknown) => {
        if (alive) {
          setLoaded({ id, error: err instanceof ApiRequestError ? err.message : 'Nie udało się wczytać raportu.' })
        }
      })
    return () => {
      alive = false
    }
  }, [id])

  // Browsers print closed <details> without their content: open all of them for printing, then restore.
  useEffect(() => {
    let opened: HTMLDetailsElement[] = []
    const before = () => {
      opened = Array.from(document.querySelectorAll('details:not([open])'))
      opened.forEach((d) => (d.open = true))
    }
    const after = () => {
      opened.forEach((d) => (d.open = false))
      opened = []
    }
    window.addEventListener('beforeprint', before)
    window.addEventListener('afterprint', after)
    return () => {
      window.removeEventListener('beforeprint', before)
      window.removeEventListener('afterprint', after)
    }
  }, [])

  useEffect(() => {
    if (!report) return
    const previous = document.title
    document.title = `Raport: działka ${report.parcel.number ?? report.parcel.id} · ${report.app}`
    return () => {
      document.title = previous
    }
  }, [report])

  // Sections and recommendation cards exist only in the full view: a link to one of them (a summary tile or a
  // shared #sekcja-N link) switches to the full report, then scrolls there once it is rendered.
  useEffect(() => {
    const isDeepLink = () => /^#(sekcja|zalecenie)-\d+$/.test(window.location.hash)
    const onHash = () => {
      if (isDeepLink() && variant === 'basic') setVariant('full')
      else if (window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView()
    }
    if (report) onHash()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setVariant is recreated each render
  }, [report, variant])

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Nie udało się wczytać raportu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>{error}</p>
          <Button asChild size="lg">
            <Link to="/">Sprawdź działkę od nowa</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }
  if (!report) {
    return (
      <p className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Wczytuję raport…
      </p>
    )
  }

  const p = report.parcel
  const place = [withPrefix('gmina', p.commune), withPrefix('powiat', p.county), withPrefix('woj.', p.voivodeship)]
    .filter(Boolean)
    .join(', ')

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold leading-tight">Raport wodny działki nr {p.number ?? p.id}</h1>
        <p className="text-muted-foreground">
          {place && <>{place} · </>}
          {formatAreaHa(p.area_ha)} · {report.crop.name_pl} · stan na {formatDatePl(report.analysis_date)}
        </p>
        <p className="text-xs text-muted-foreground">
          Numer działki: {p.id} · raport przygotowano {formatDateTimePl(report.created_at)}
        </p>
      </div>
      {report.farm && <FarmNote farm={report.farm} />}

      <HeadlineBanner headline={report.headline} />
      <SummaryTiles tiles={report.summary_tiles} sections={report.sections} />
      {!report.complete && (
        <p className="rounded-md border border-amber-400 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Nie udało się w pełni ocenić sytuacji wodnej, dlatego raport nie podaje zaleceń. Sprawdź część o brakach danych i
          ograniczeniach analizy.
        </p>
      )}
      <VariantSwitch variant={variant} onChange={setVariant} />
      <Actions report={report} variant={variant} />

      {variant === 'basic' ? (
        <BasicReport report={report} />
      ) : (
        <>
          <nav aria-label="Spis treści" className="rounded-md border bg-card px-4 py-3 text-sm">
            <p className="mb-1.5 font-semibold">Spis treści</p>
            <ol className="space-y-1">
              {report.sections.map((s) => (
                <li key={s.id}>
                  <a className="text-primary underline-offset-2 hover:underline" href={`#sekcja-${s.number}`}>
                    {s.number}. {s.title_pl}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          {report.sections.map((s) => (
            <SectionCard key={s.id} section={s} report={report} />
          ))}
        </>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild variant="secondary" size="lg" className="h-12">
          <Link to="/">
            <RotateCcw /> Sprawdź inną działkę lub datę
          </Link>
        </Button>
      </div>
    </div>
  )
}
