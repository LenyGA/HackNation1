import { Loader2, MapPin, Search } from 'lucide-react'
import { type FormEvent, lazy, type ReactNode, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiRequestError } from '@/api/client'
import type { Crop, Parcel } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  analysisDateError,
  formatAreaHa,
  formatDatePl,
  minAnalysisDateIso,
  PARCEL_ID_EXAMPLE,
  parcelIdError,
  todayIso,
} from '@/lib/format'

// The map library is large; the form renders first and the map follows.
const ParcelPickerMap = lazy(() => import('@/components/map/ParcelPickerMap'))

function MapPlaceholder() {
  return (
    <div className="flex h-[320px] items-center justify-center rounded-lg border bg-muted text-sm text-muted-foreground sm:h-[420px]">
      <Loader2 className="mr-2 size-4 animate-spin" /> Wczytuję mapę…
    </div>
  )
}

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiRequestError ? err.message : fallback
}

function StepTitle({ n, children }: { n: number; children: ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 text-base font-semibold">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm text-primary-foreground">
        {n}
      </span>
      {children}
    </h2>
  )
}

function ParcelSummary({ parcel }: { parcel: Parcel }) {
  const place = [
    parcel.commune && (/^gmina/i.test(parcel.commune) ? parcel.commune : `gmina ${parcel.commune}`),
    parcel.precinct && (/^obręb/i.test(parcel.precinct) ? parcel.precinct : `obręb ${parcel.precinct}`),
  ]
    .filter(Boolean)
    .join(', ')
  return (
    <div className="flex items-start gap-2 rounded-md border border-primary/30 bg-secondary px-3 py-2 text-sm">
      <MapPin className="mt-0.5 size-4 shrink-0 text-primary" />
      <div>
        <p className="font-medium">
          Działka nr {parcel.number ?? parcel.id} · {formatAreaHa(parcel.area_ha)}
        </p>
        <p className="text-muted-foreground">{place || parcel.id}</p>
      </div>
    </div>
  )
}

export function StartPage() {
  const navigate = useNavigate()
  const [crops, setCrops] = useState<Crop[]>([])
  const [cropsError, setCropsError] = useState<string | null>(null)

  const [parcelInput, setParcelInput] = useState('')
  const [parcel, setParcel] = useState<Parcel | null>(null)
  const [parcelError, setParcelError] = useState<string | null>(null)
  const [lookingUp, setLookingUp] = useState(false)
  // Bumped by every lookup and map pick: only the latest one may set the parcel.
  const pickSeq = useRef(0)

  const [cropId, setCropId] = useState('')
  const [cropError, setCropError] = useState<string | null>(null)

  const [date, setDate] = useState(todayIso)
  const [dateError, setDateError] = useState<string | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .crops()
      .then((list) => alive && setCrops(list))
      .catch((err: unknown) => alive && setCropsError(errorText(err, 'Nie udało się pobrać listy upraw.')))
    return () => {
      alive = false
    }
  }, [])

  // The parcel shown on the map always matches the number in the field.
  const parcelMatchesInput = parcel !== null && parcel.id === parcelInput.trim()

  async function lookUp(): Promise<Parcel | null> {
    const id = parcelInput.trim()
    const formatError = parcelIdError(id)
    if (formatError) {
      setParcelError(formatError)
      return null
    }
    if (parcel && parcel.id === id) return parcel
    const seq = ++pickSeq.current
    setLookingUp(true)
    setParcelError(null)
    try {
      const found = await api.parcelById(id)
      if (seq !== pickSeq.current) return null
      setParcel(found)
      setParcelInput(found.id)
      return found
    } catch (err) {
      if (seq !== pickSeq.current) return null
      setParcel(null)
      setParcelError(errorText(err, 'Nie udało się sprawdzić działki. Spróbuj ponownie.'))
      return null
    } finally {
      if (seq === pickSeq.current) setLookingUp(false)
    }
  }

  const onMapPick = useCallback((picked: Parcel) => {
    pickSeq.current += 1
    setLookingUp(false)
    setParcel(picked)
    setParcelInput(picked.id)
    setParcelError(null)
  }, [])
  const onMapError = useCallback((message: string) => setParcelError(message), [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    const cErr = cropId ? null : 'Wybierz uprawę z listy.'
    const dErr = analysisDateError(date)
    setCropError(cErr)
    setDateError(dErr)
    const found = await lookUp()
    if (!found || cErr || dErr) return
    setSubmitting(true)
    try {
      const { id } = await api.createAnalysis({ parcel_id: found.id, crop_id: cropId, analysis_date: date })
      navigate(`/analiza/${encodeURIComponent(id)}`)
    } catch (err) {
      setSubmitError(errorText(err, 'Nie udało się uruchomić analizy. Spróbuj ponownie.'))
      setSubmitting(false)
    }
  }

  const minDate = minAnalysisDateIso()
  const maxDate = todayIso()

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Sprawdź swoją działkę</CardTitle>
          <CardDescription>
            Podaj numer działki lub wskaż ją na mapie, wybierz uprawę i datę. Policzymy, jak wygląda sytuacja wodna na
            polu i co możesz zrobić, żeby zatrzymać wodę. Bez logowania, za darmo.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <StepTitle n={1}>Działka</StepTitle>
          <div className="space-y-1.5">
            <Label htmlFor="parcel-id">Numer działki ewidencyjnej</Label>
            <div className="flex gap-2">
              <Input
                id="parcel-id"
                value={parcelInput}
                onChange={(e) => {
                  setParcelInput(e.target.value)
                  setParcelError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void lookUp()
                  }
                }}
                placeholder={PARCEL_ID_EXAMPLE}
                autoComplete="off"
                spellCheck={false}
                inputMode="text"
                aria-invalid={parcelError ? true : undefined}
                aria-describedby="parcel-help parcel-error"
                className="h-11 text-base"
              />
              <Button type="button" variant="secondary" className="h-11" onClick={() => void lookUp()} disabled={lookingUp}>
                {lookingUp ? <Loader2 className="animate-spin" /> : <Search />}
                <span className="hidden sm:inline">Znajdź</span>
              </Button>
            </div>
            <p id="parcel-help" className="text-xs text-muted-foreground">
              Przykład: <code>{PARCEL_ID_EXAMPLE}</code>. Pełny numer znajdziesz w wypisie z rejestru gruntów, we wniosku
              o dopłaty albo na mapie poniżej.
            </p>
            {parcelError && (
              <p id="parcel-error" role="alert" className="text-sm text-destructive">
                {parcelError}
              </p>
            )}
          </div>
          {parcelMatchesInput && parcel && <ParcelSummary parcel={parcel} />}
          <p className="text-sm font-medium">…albo wskaż działkę na mapie</p>
          <Suspense fallback={<MapPlaceholder />}>
            <ParcelPickerMap selected={parcelMatchesInput ? parcel : null} onPick={onMapPick} onError={onMapError} />
          </Suspense>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <StepTitle n={2}>Uprawa</StepTitle>
          <div className="space-y-1.5">
            <Label htmlFor="crop">Co teraz rośnie na działce?</Label>
            <Select
              value={cropId}
              onValueChange={(v) => {
                setCropId(v)
                setCropError(null)
              }}
            >
              <SelectTrigger
                id="crop"
                className="h-11 w-full text-base"
                aria-invalid={cropError ? true : undefined}
                disabled={crops.length === 0}
              >
                <SelectValue placeholder={cropsError ? 'Lista upraw niedostępna' : 'Wybierz uprawę'} />
              </SelectTrigger>
              <SelectContent>
                {crops.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="py-2.5 text-base">
                    {c.name_pl}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {(cropError || cropsError) && (
              <p role="alert" className="text-sm text-destructive">
                {cropError ?? cropsError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <StepTitle n={3}>Data analizy</StepTitle>
          <div className="space-y-1.5">
            <Label htmlFor="date">Na jaki dzień sprawdzić sytuację?</Label>
            <Input
              id="date"
              type="date"
              value={date}
              min={minDate}
              max={maxDate}
              onChange={(e) => {
                setDate(e.target.value)
                setDateError(null)
              }}
              aria-invalid={dateError ? true : undefined}
              className="h-11 w-full text-base sm:w-60"
            />
            <p className="text-xs text-muted-foreground">
              Domyślnie dziś. Możesz wybrać dowolny dzień od {formatDatePl(minDate)}.
            </p>
            {dateError && (
              <p role="alert" className="text-sm text-destructive">
                {dateError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {submitError && (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {submitError}
        </p>
      )}
      <Button type="submit" size="lg" className="h-14 w-full text-lg" disabled={submitting || lookingUp}>
        {submitting && <Loader2 className="animate-spin" />}
        Sprawdź działkę
      </Button>
    </form>
  )
}
