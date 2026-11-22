import { Loader2, MapPin, MousePointerClick, Plus, Search, X } from 'lucide-react'
import { type FormEvent, lazy, type ReactNode, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiRequestError } from '@/api/client'
import { tooFar } from '@/lib/farm'
import { type Crop, type CropKind, MAX_EXTRA_PARCELS, type Parcel } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  analysisDateError,
  formatAreaHa,
  formatDatePl,
  minAnalysisDateIso,
  parcelsPl,
  PARCEL_ID_EXAMPLE,
  parcelIdError,
  todayIso,
} from '@/lib/format'

// The map library is large; the form renders first and the map follows.
const ParcelPickerMap = lazy(() => import('@/components/map/ParcelPickerMap'))

// Crop list grouped by kind; the backend catalogue decides which crop belongs where.
const CROP_GROUPS: { label: string; kinds: CropKind[] }[] = [
  { label: 'Uprawy polowe i łąki', kinds: ['arable', 'grassland'] },
  { label: 'Sady i krzewy owocowe', kinds: ['fruit'] },
]

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

// Why a parcel cannot be added to the farm, or null when it can (the server checks it again).
function extraError(p: Parcel, main: Parcel | null, list: Parcel[]): string | null {
  if (!main) return 'Najpierw wybierz działkę główną.'
  if (p.id === main.id) return 'To jest działka główna — wybierz inną.'
  if (list.some((x) => x.id === p.id)) return 'Ta działka jest już na liście.'
  if (list.length >= MAX_EXTRA_PARCELS) return `Można dodać najwyżej ${MAX_EXTRA_PARCELS} działek.`
  if (tooFar(main, p)) return 'Ta działka leży dalej niż 2 km od działki głównej — przeanalizuj ją osobno.'
  return null
}

function FarmParcels({
  main,
  extras,
  adding,
  onAdd,
  onRemove,
  onToggleAdding,
  notice,
}: {
  notice: string | null
  main: Parcel | null
  extras: Parcel[]
  adding: boolean
  onAdd: (id: string) => Promise<string | null>
  onRemove: (id: string) => void
  onToggleAdding: () => void
}) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const full = extras.length >= MAX_EXTRA_PARCELS
  const total = (main?.area_ha ?? 0) + extras.reduce((s, p) => s + p.area_ha, 0)

  async function add() {
    setBusy(true)
    const err = await onAdd(input.trim())
    setBusy(false)
    setError(err)
    if (!err) setInput('')
  }

  return (
    <div className="space-y-2 rounded-md border border-dashed px-3 py-3">
      <p className="text-sm font-medium">Inne działki tego gospodarstwa (opcjonalnie)</p>
      <p className="text-xs text-muted-foreground">
        Dodaj do {MAX_EXTRA_PARCELS} sąsiednich działek (do 2 km od głównej) z tą samą uprawą. Ilości wody i opłacalność
        nawadniania policzymy dla wszystkich razem; pogodę, glebę i teren sprawdzamy na działce głównej.
      </p>
      {extras.length > 0 && (
        <ul className="space-y-1.5">
          {extras.map((p) => (
            <li key={p.id} className="flex items-center gap-2 rounded-md border border-sky-400/50 bg-sky-50 px-2 py-1.5 text-sm dark:bg-sky-950/30">
              <span className="size-3 shrink-0 rounded-sm bg-sky-400" aria-hidden />
              <span className="min-w-0 flex-1 truncate">
                Działka nr {p.number ?? p.id} · {formatAreaHa(p.area_ha)}
                <span className="block truncate text-xs text-muted-foreground">{p.id}</span>
              </span>
              <Button type="button" variant="ghost" size="icon" onClick={() => onRemove(p.id)} aria-label={`Usuń działkę ${p.id}`}>
                <X />
              </Button>
            </li>
          ))}
          <li className="text-sm font-medium">
            Razem: {extras.length + 1} {parcelsPl(extras.length + 1)}, {formatAreaHa(total)}
          </li>
        </ul>
      )}
      {!full && (
        <div className="flex flex-wrap gap-2">
          <Input
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              setError(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void add()
              }
            }}
            placeholder="Numer kolejnej działki"
            aria-label="Numer kolejnej działki"
            autoComplete="off"
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            className="h-11 min-w-0 flex-1 basis-48 text-base"
            disabled={!main}
          />
          <Button type="button" variant="secondary" className="h-11" onClick={() => void add()} disabled={busy || !main}>
            {busy ? <Loader2 className="animate-spin" /> : <Plus />} Dodaj działkę
          </Button>
          <Button
            type="button"
            variant={adding ? 'default' : 'outline'}
            className="h-11"
            onClick={onToggleAdding}
            disabled={!main}
            aria-pressed={adding}
          >
            <MousePointerClick /> {adding ? 'Dodawanie z mapy: włączone' : 'Dodaj z mapy'}
          </Button>
        </div>
      )}
      {!main && <p className="text-xs text-muted-foreground">Najpierw wybierz działkę główną.</p>}
      {(error ?? notice) && (
        <p role="alert" className="text-sm text-destructive">
          {error ?? notice}
        </p>
      )}
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

  // Farm mode (G11): extra parcels; while `adding`, a map tap adds a parcel instead of replacing the main one.
  const [extras, setExtras] = useState<Parcel[]>([])
  const [adding, setAdding] = useState(false)
  const [farmNotice, setFarmNotice] = useState<string | null>(null)

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
      keepExtrasFor(found)
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

  async function addExtra(id: string): Promise<string | null> {
    const formatError = parcelIdError(id)
    if (formatError) return formatError
    const main = parcelMatchesInput ? parcel : null
    try {
      const found = await api.parcelById(id)
      const err = extraError(found, main, extras)
      if (err) return err
      // Re-checked on the latest list: map picks may have landed during the lookup.
      setExtras((list) => (extraError(found, main, list) ? list : [...list, found]))
      setFarmNotice(null)
      return null
    } catch (err) {
      return errorText(err, 'Nie udało się sprawdzić działki. Spróbuj ponownie.')
    }
  }

  const removeExtra = useCallback((id: string) => setExtras((list) => list.filter((p) => p.id !== id)), [])

  // A new main parcel: drop itself and the parcels surely too far from it from the farm list.
  const keepExtrasFor = useCallback(
    (main: Parcel) => {
      const others = extras.filter((p) => p.id !== main.id)
      const kept = others.filter((p) => !tooFar(main, p))
      const far = others.length - kept.length
      setExtras(kept)
      setFarmNotice(
        far === 0
          ? null
          : far === 1
            ? 'Usunięto z listy działkę, która leży dalej niż 2 km od nowej działki głównej.'
            : `Usunięto z listy ${far} ${parcelsPl(far)}, które leżą dalej niż 2 km od nowej działki głównej.`,
      )
    },
    [extras],
  )

  const addingActive = adding && parcelMatchesInput && extras.length < MAX_EXTRA_PARCELS
  const onMapPick = useCallback(
    (picked: Parcel) => {
      if (addingActive) {
        const err = extraError(picked, parcel, extras)
        setFarmNotice(err)
        if (!err) setExtras((list) => (extraError(picked, parcel, list) ? list : [...list, picked]))
        return
      }
      pickSeq.current += 1
      setLookingUp(false)
      setParcel(picked)
      setParcelInput(picked.id)
      setParcelError(null)
      keepExtrasFor(picked)
    },
    [addingActive, extras, keepExtrasFor, parcel],
  )
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
      const { id } = await api.createAnalysis({
        parcel_id: found.id,
        crop_id: cropId,
        analysis_date: date,
        extra_parcel_ids: extras.filter((p) => p.id !== found.id).map((p) => p.id),
      })
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
            <ParcelPickerMap
              selected={parcelMatchesInput ? parcel : null}
              extras={extras}
              adding={addingActive}
              onPick={onMapPick}
              onError={onMapError}
            />
          </Suspense>
          <FarmParcels
            main={parcelMatchesInput ? parcel : null}
            extras={extras}
            adding={addingActive}
            onAdd={addExtra}
            onRemove={removeExtra}
            onToggleAdding={() => setAdding((a) => !a)}
            notice={farmNotice}
          />
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
                {CROP_GROUPS.map((g) => {
                  const items = crops.filter((c) => g.kinds.includes(c.kind))
                  if (items.length === 0) return null
                  return (
                    <SelectGroup key={g.label}>
                      <SelectLabel>{g.label}</SelectLabel>
                      {items.map((c) => (
                        <SelectItem key={c.id} value={c.id} className="py-2.5 text-base">
                          {c.name_pl}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  )
                })}
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
