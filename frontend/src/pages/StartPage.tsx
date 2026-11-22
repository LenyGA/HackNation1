import {
  Carrot,
  ClipboardList,
  Droplets,
  Flower2,
  Leaf,
  Loader2,
  MapPin,
  MousePointerClick,
  Plus,
  Satellite,
  Search,
  Sprout,
  Wheat,
  X,
} from 'lucide-react'
import { type FormEvent, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiRequestError } from '@/api/client'
import { tooFar } from '@/lib/farm'
import { type Crop, type CropKind, MAX_EXTRA_PARCELS, type Parcel, type Place } from '@/api/types'
import { AddressSearch } from '@/components/AddressSearch'
import type { MapFocus } from '@/components/map/ParcelPickerMap'
import { Button } from '@/components/ui/button'
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
import { cn } from '@/lib/utils'

// The map library is large; the form renders first and the map follows.
const ParcelPickerMap = lazy(() => import('@/components/map/ParcelPickerMap'))

// The most common crops as one-tap chips (mock-up); every crop, orchards included, is in the list below them.
const POPULAR_CROPS = ['grassland', 'winter_wheat', 'maize', 'winter_rapeseed', 'potato']
const CROP_ICON: Record<string, typeof Sprout> = {
  grassland: Leaf,
  winter_wheat: Wheat,
  maize: Sprout,
  winter_rapeseed: Flower2,
  potato: Carrot,
}

// Crop list grouped by kind; the backend catalogue decides which crop belongs where.
const CROP_GROUPS: { label: string; kinds: CropKind[] }[] = [
  { label: 'Uprawy polowe i łąki', kinds: ['arable', 'grassland'] },
  { label: 'Sady i krzewy owocowe', kinds: ['fruit'] },
]

function MapPlaceholder() {
  return (
    <div className="flex h-[60svh] max-h-[720px] min-h-[320px] items-center justify-center rounded-lg border bg-muted text-sm text-muted-foreground">
      <Loader2 className="mr-2 size-4 animate-spin" /> Wczytuję mapę…
    </div>
  )
}

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiRequestError ? err.message : fallback
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

  // Address search (M8.7): fly the map there; an address with a house number also picks the parcel at it.
  const [focus, setFocus] = useState<MapFocus | null>(null)
  const [addressNote, setAddressNote] = useState<string | null>(null)
  async function onAddress(place: Place) {
    setFocus({ lat: place.lat, lon: place.lon, zoom: place.kind === 'address' ? 17 : place.kind === 'street' ? 16 : 14 })
    setParcelError(null)
    if (place.kind !== 'address') {
      setAddressNote(`Mapa pokazuje: ${place.label_pl}. Przybliż ją i dotknij swojego pola, aby je wybrać.`)
      return
    }
    const seq = ++pickSeq.current
    setLookingUp(true)
    setAddressNote(null)
    try {
      const found = await api.parcelByPoint(place.lat, place.lon)
      if (seq !== pickSeq.current) return
      setParcel(found)
      setParcelInput(found.id)
      keepExtrasFor(found)
      setAddressNote(
        `Wybrano działkę pod adresem ${place.label_pl} (zwykle ta z domem). Jeśli pole leży gdzie indziej, dotknij go na mapie.`,
      )
    } catch (err) {
      if (seq !== pickSeq.current) return
      setAddressNote(`Mapa pokazuje adres ${place.label_pl}. Dotknij swojego pola, aby je wybrać.`)
      setParcelError(errorText(err, 'Nie udało się znaleźć działki pod tym adresem. Dotknij swojego pola na mapie.'))
    } finally {
      if (seq === pickSeq.current) setLookingUp(false)
    }
  }

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
  const popular = POPULAR_CROPS.map((id) => crops.find((c) => c.id === id)).filter((c): c is Crop => c !== undefined)
  const otherChosen = cropId !== '' && !popular.some((c) => c.id === cropId)
  const chooseCrop = (id: string) => {
    setCropId(id)
    setCropError(null)
  }

  return (
    <form id="start" onSubmit={onSubmit} noValidate className="scroll-mt-16">
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 bg-[url('/hero-fields.svg')] bg-cover bg-center"
          aria-hidden
        />
        <div
          className="absolute inset-0 bg-gradient-to-b from-navy/90 via-navy/70 to-navy/30 lg:bg-gradient-to-r lg:from-navy/95 lg:via-navy/70 lg:to-navy/10"
          aria-hidden
        />
        <div className="relative mx-auto grid max-w-6xl gap-5 px-3 py-6 sm:px-5 sm:py-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:items-start lg:gap-8 lg:py-12">
          <div className="space-y-5">
            <div className="space-y-2 text-white">
              <h1 className="text-3xl leading-tight font-extrabold tracking-tight text-balance drop-shadow-sm sm:text-5xl">
                Sprawdź wodę na swojej działce
              </h1>
              <p className="max-w-xl text-base text-white/90 sm:text-lg">
                Bezpłatny raport z danych satelitarnych, pogodowych, glebowych i terenu w około 30 sekund. Bez logowania.
              </p>
            </div>

            <div className="space-y-4 rounded-2xl bg-card p-4 text-card-foreground shadow-xl sm:p-5">
              <div className="space-y-1.5">
                <Label htmlFor="parcel-id" className="text-sm font-semibold">
                  Numer działki ewidencyjnej
                </Label>
                <div className="relative">
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
                    placeholder={`np. ${PARCEL_ID_EXAMPLE}`}
                    autoComplete="off"
                    spellCheck={false}
                    inputMode="text"
                    aria-invalid={parcelError ? true : undefined}
                    aria-describedby="parcel-help parcel-error"
                    className="h-12 rounded-lg pr-12 text-base"
                  />
                  <button
                    type="button"
                    onClick={() => void lookUp()}
                    disabled={lookingUp}
                    className="absolute top-1/2 right-1 flex size-10 -translate-y-1/2 items-center justify-center rounded-md text-navy hover:bg-muted disabled:opacity-50"
                    aria-label="Znajdź działkę"
                  >
                    {lookingUp ? <Loader2 className="size-5 animate-spin" /> : <Search className="size-5" />}
                  </button>
                </div>
                <p id="parcel-help" className="text-xs text-muted-foreground">
                  Numer znajdziesz w wypisie z rejestru gruntów albo we wniosku o dopłaty. Nie znasz go? Wyszukaj adres
                  lub dotknij pola na mapie.
                </p>
                {parcelError && (
                  <p id="parcel-error" role="alert" className="text-sm text-destructive">
                    {parcelError}
                  </p>
                )}
              </div>
              {parcelMatchesInput && parcel && <ParcelSummary parcel={parcel} />}

              <fieldset className="space-y-2">
                <legend className="mb-2 text-sm font-semibold">Co teraz rośnie na działce?</legend>
                <div role="radiogroup" aria-label="Popularne uprawy" className="flex flex-wrap gap-2">
                  {popular.map((c) => {
                    const Icon = CROP_ICON[c.id] ?? Sprout
                    const on = c.id === cropId
                    return (
                      <button
                        key={c.id}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        onClick={() => chooseCrop(c.id)}
                        className={cn(
                          'flex min-h-11 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors',
                          on
                            ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                            : 'border-border bg-background hover:border-primary/50 hover:bg-secondary',
                        )}
                      >
                        <Icon className="size-4" aria-hidden />
                        {c.name_pl}
                      </button>
                    )
                  })}
                </div>
                <Select value={otherChosen ? cropId : ''} onValueChange={chooseCrop}>
                  <SelectTrigger
                    id="crop"
                    className={cn('h-11 w-full text-base', otherChosen && 'border-primary ring-1 ring-primary')}
                    aria-label="Inna uprawa"
                    aria-invalid={cropError ? true : undefined}
                    disabled={crops.length === 0}
                  >
                    <SelectValue
                      placeholder={cropsError ? 'Lista upraw niedostępna' : crops.length === 0 ? 'Wczytuję uprawy…' : 'Inna uprawa, sad lub krzewy owocowe…'}
                    />
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
              </fieldset>

              <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] sm:items-end">
                <div className="space-y-1.5">
                  <Label htmlFor="date" className="text-sm font-semibold">
                    Data analizy
                  </Label>
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
                    aria-describedby="date-help"
                    className="h-12 w-full rounded-lg text-base"
                  />
                </div>
                <Button type="submit" size="lg" className="h-12 w-full rounded-lg text-base font-semibold" disabled={submitting || lookingUp}>
                  {submitting ? <Loader2 className="animate-spin" /> : <Droplets />}
                  Analizuj działkę
                </Button>
              </div>
              <p id="date-help" className="-mt-2 text-xs text-muted-foreground">
                Domyślnie dziś. Możesz wybrać dowolny dzień od {formatDatePl(minDate)}.
              </p>
              {dateError && (
                <p role="alert" className="text-sm text-destructive">
                  {dateError}
                </p>
              )}
              {submitError && (
                <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {submitError}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-3 rounded-2xl bg-card p-3 text-card-foreground shadow-xl sm:p-4">
            <div className="space-y-1.5">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <MapPin className="size-4 text-primary" aria-hidden /> Nie znasz numeru? Znajdź działkę po adresie
              </p>
              <AddressSearch onChoose={(p) => void onAddress(p)} />
              {addressNote && <p className="text-sm text-muted-foreground">{addressNote}</p>}
            </div>
            <p className="text-sm font-semibold">…albo dotknij swojego pola na mapie</p>
            <Suspense fallback={<MapPlaceholder />}>
              <ParcelPickerMap
                selected={parcelMatchesInput ? parcel : null}
                extras={extras}
                adding={addingActive}
                onPick={onMapPick}
                onError={onMapError}
                focus={focus}
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
          </div>
        </div>
      </section>

      <HowItWorks />
    </form>
  )
}

const HOW_STEPS: { icon: typeof MapPin; title: string; text: string }[] = [
  {
    icon: MapPin,
    title: '1. Wskaż działkę i uprawę',
    text: 'Numer z ewidencji, adres albo dotknięcie pola na mapie. Do tego uprawa i dzień — dziś albo dowolny z ostatnich 10 lat.',
  },
  {
    icon: Satellite,
    title: '2. Liczymy z danych publicznych',
    text: 'Pogoda i bilans wodny (FAO-56), zdjęcia Sentinel-2, gleba, ukształtowanie terenu, cieki i mapy powodziowe — na żywo, dla tej działki.',
  },
  {
    icon: ClipboardList,
    title: '3. Dostajesz konkretne działania',
    text: 'Najpierw zatrzymanie wody, potem zabiegi na polu i nawadnianie z terminem i dawką. Każda liczba ma źródło i datę. Raport w PDF.',
  },
]

function HowItWorks() {
  return (
    <section id="jak-to-dziala" className="mx-auto max-w-6xl scroll-mt-16 px-3 py-8 sm:px-5 sm:py-10">
      <h2 className="mb-4 text-2xl font-bold tracking-tight text-navy">Jak to działa</h2>
      <ol className="grid gap-3 md:grid-cols-3">
        {HOW_STEPS.map(({ icon: Icon, title, text }) => (
          <li key={title} className="rounded-2xl border bg-card p-4 shadow-sm">
            <span className="mb-2 flex size-10 items-center justify-center rounded-full bg-secondary text-primary">
              <Icon className="size-5" aria-hidden />
            </span>
            <p className="font-semibold text-navy">{title}</p>
            <p className="mt-1 text-sm text-muted-foreground">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
