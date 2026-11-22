import { useId, useMemo, useState } from 'react'
import type { EconomicsVerdict, IrrigationEconomics as Economics } from '@/api/types'
import { Disclosure } from '@/components/report/ReportParts'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatNumberPl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { canRecompute, computeEconomics, defaultInputs, invalidFields, roundZl, type EconomicsInputs } from './economics'

// G10: irrigation technology for the parcel and whether it pays off. Sentences and the default verdict come
// from the backend; the farmer can change the assumptions and the browser recomputes the result.

const VERDICT_PILL: Record<EconomicsVerdict, string> = {
  profitable: 'bg-green-600 text-white',
  borderline: 'bg-amber-200 text-amber-950',
  unprofitable: 'bg-red-100 text-red-900',
  unknown: 'bg-slate-200 text-slate-800',
}
const VERDICT_BORDER: Record<EconomicsVerdict, string> = {
  profitable: 'border-l-green-600',
  borderline: 'border-l-amber-500',
  unprofitable: 'border-l-red-600',
  unknown: 'border-l-slate-400',
}
const VERDICT_LABEL: Record<EconomicsVerdict, string> = {
  profitable: 'Opłacalne',
  borderline: 'Na granicy opłacalności',
  unprofitable: 'Nieopłacalne',
  unknown: 'Nie oceniono',
}

const zl = (v: number) => `${formatNumberPl(roundZl(v))} zł`

function VerdictPill({ verdict, label }: { verdict: EconomicsVerdict; label: string }) {
  return <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', VERDICT_PILL[verdict])}>{label}</span>
}

interface FieldDef {
  key: keyof EconomicsInputs
  label: string
  unit: string
  step: number
}

const FIELDS: FieldDef[] = [
  { key: 'yieldTHa', label: 'Plon bez strat z suszy', unit: 't/ha', step: 0.1 },
  { key: 'priceZlT', label: 'Cena sprzedaży', unit: 'zł/t', step: 10 },
  { key: 'capexZlHa', label: 'Koszt instalacji', unit: 'zł/ha', step: 100 },
  { key: 'lifetimeYears', label: 'Instalacja posłuży', unit: 'lat', step: 1 },
  { key: 'waterSourceZl', label: 'Ujęcie wody (studnia, pompa)', unit: 'zł', step: 1000 },
  { key: 'waterSourceLifetimeYears', label: 'Ujęcie posłuży', unit: 'lat', step: 1 },
  { key: 'operatingZlM3', label: 'Pompowanie, energia, praca', unit: 'zł/m³', step: 0.1 },
]

const toText = (v: number) => (v ? String(Math.round(v * 100) / 100).replace('.', ',') : '')
const parse = (v: string) => (v.trim() === '' ? Number.NaN : Number(v.trim().replace(/\s/g, '').replace(',', '.')))

function Calculator({ e }: { e: Economics }) {
  const id = useId()
  const defaults = useMemo(() => defaultInputs(e.assumptions), [e.assumptions])
  const initial = useMemo(
    () =>
      Object.fromEntries(FIELDS.map((f) => [f.key, toText((defaults as EconomicsInputs)[f.key])])) as Record<
        keyof EconomicsInputs,
        string
      >,
    [defaults],
  )
  const [values, setValues] = useState(initial)
  const edited = FIELDS.some((f) => values[f.key] !== initial[f.key])
  const parsed = Object.fromEntries(FIELDS.map((f) => [f.key, parse(values[f.key])])) as unknown as EconomicsInputs
  const invalid = invalidFields(parsed)
  const result =
    invalid.length === 0 && e.mean_loss_share !== null && e.water_m3_ha !== null
      ? computeEconomics(parsed, e.mean_loss_share, e.water_m3_ha, e.area_ha)
      : null

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Startujemy od środka widełek. Zmień liczby na swoje — strata plonu z suszy (średnio{' '}
        {formatNumberPl(100 * (e.mean_loss_share ?? 0))} %) i ilość wody (ok. {formatNumberPl(e.water_m3_ha ?? 0)} m³/ha w typowym
        roku) zostają z danych tej działki.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key} className="space-y-1">
            <Label htmlFor={`${id}-${f.key}`}>
              {f.label} <span className="font-normal text-muted-foreground">({f.unit})</span>
            </Label>
            {/* type="text": a number input drops the Polish decimal comma in Firefox and iOS Safari. */}
            <Input
              id={`${id}-${f.key}`}
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={values[f.key]}
              aria-invalid={invalid.includes(f.key)}
              onChange={(ev) => setValues((v) => ({ ...v, [f.key]: ev.target.value }))}
            />
          </div>
        ))}
      </div>
      <div className="rounded-md border bg-card p-3" aria-live="polite">
        {!edited ? (
          <p className="text-sm">
            Przy wartościach domyślnych obowiązuje ocena z raportu ({e.verdict_pl.toLowerCase()}), liczona na całych widełkach cen
            i kosztów. Zmień którąś liczbę, a przeliczymy wynik dla Twoich wartości.
          </p>
        ) : result ? (
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">Twój wynik:</span>
              <VerdictPill verdict={result.verdict} label={VERDICT_LABEL[result.verdict]} />
            </div>
            <p className="text-sm">
              Uratowany plon ok. {zl(result.benefitZlHa)}/ha rocznie, koszt nawadniania ok. {zl(result.costZlHa)}/ha rocznie.{' '}
              {result.breakEvenAreaHa === null
                ? 'Przy tych liczbach nawadnianie nie zwraca się przy żadnym areale.'
                : `Ujęcie wody zwraca się od ok. ${formatNumberPl(result.breakEvenAreaHa, result.breakEvenAreaHa < 10 ? 1 : 0)} ha nawadnianych upraw.`}{' '}
              Przy jednej wartości zamiast widełek „na granicy” oznacza różnicę mniejszą niż 20 %.
            </p>
          </div>
        ) : (
          <p className="text-sm">
            Popraw pola: {FIELDS.filter((f) => invalid.includes(f.key)).map((f) => f.label.toLowerCase()).join(', ')} (liczba
            większa od zera; przecinek lub kropka).
          </p>
        )}
      </div>
    </div>
  )
}

export function IrrigationEconomicsBlock({ e, short = false }: { e: Economics; short?: boolean }) {
  const showTable = !short && (e.status === 'ok' || e.status === 'no_price') && e.cost_zl_ha_low !== null
  return (
    <div className={cn('space-y-3 rounded-lg border border-l-4 bg-card p-3.5', VERDICT_BORDER[e.verdict])}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold">{short ? 'Nawadnianie: jaka instalacja i czy się opłaca' : 'Jaka instalacja i czy nawadnianie się opłaca'}</h4>
        <VerdictPill verdict={e.verdict} label={e.verdict_pl} />
      </div>
      <div className="space-y-1">
        <p className="font-medium">{e.technology_pl}</p>
        {(short ? e.technology_text_pl.slice(0, 1) : e.technology_text_pl).map((t) => (
          <p key={t} className="text-sm leading-relaxed">
            {t}
          </p>
        ))}
      </div>
      {(short ? e.text_pl.slice(0, 1) : e.text_pl).map((t) => (
        <p key={t} className="leading-relaxed">
          {t}
        </p>
      ))}
      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 pr-2 font-medium">Na 1 ha rocznie</th>
                <th className="py-1 pr-2 text-right font-medium">od</th>
                <th className="py-1 text-right font-medium">do</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {e.benefit_zl_ha_low !== null && e.benefit_zl_ha_high !== null && (
                <tr>
                  <td className="py-1.5 pr-2">Wartość plonu, który zabierała susza</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{zl(e.benefit_zl_ha_low)}</td>
                  <td className="py-1.5 text-right tabular-nums">{zl(e.benefit_zl_ha_high)}</td>
                </tr>
              )}
              <tr>
                <td className="py-1.5 pr-2">Koszt nawadniania</td>
                <td className="py-1.5 pr-2 text-right tabular-nums">{zl(e.cost_zl_ha_low as number)}</td>
                <td className="py-1.5 text-right tabular-nums">{zl(e.cost_zl_ha_high as number)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {!short && canRecompute(e) && (
        <Disclosure summary="Przelicz z własnymi cenami i kosztami">
          <Calculator e={e} />
        </Disclosure>
      )}
      {!short && (
        <Disclosure summary="Założenia i źródła">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {e.assumptions_pl.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <p className="mt-2 break-words text-xs text-muted-foreground">Źródło: {e.source}</p>
        </Disclosure>
      )}
    </div>
  )
}
