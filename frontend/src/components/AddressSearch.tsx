import { Building2, Loader2, MapPin, Search, Signpost } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { api, ApiRequestError } from '@/api/client'
import type { Place } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const ICON = { address: MapPin, street: Signpost, city: Building2 } as const

/** Address search (plan33 M8.7): GUGiK address points → a place on the map. The parent decides what to do
 *  with it (an address with a number picks the parcel there, a village or street only moves the map). */
export function AddressSearch({
  onChoose,
  stamp,
  className,
}: {
  /** `stamp` is the value `stamp()` returned when the search started, so the parent can drop a choice that
   *  arrives after the user picked a parcel another way (map tap, number). */
  onChoose: (place: Place, stamp?: number) => void
  stamp?: () => number
  className?: string
}) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState<Place[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const listId = useId()
  // Only the latest search may show results or choose a place (answers can arrive out of order).
  const seq = useRef(0)

  async function search() {
    if (busy) return
    const text = q.trim()
    if (text.length < 2) {
      setError('Wpisz miejscowość, a najlepiej miejscowość i numer domu.')
      return
    }
    const mine = ++seq.current
    const started = stamp?.()
    setBusy(true)
    setError(null)
    try {
      const found = await api.places(text)
      if (mine !== seq.current) return
      if (found.length === 1) {
        setResults(null)
        onChoose(found[0], started)
      } else {
        setResults(found)
        if (found.length === 0) setError('Nie znaleziono takiego adresu. Spróbuj: „Ksawerów 12” albo „Bydgoszcz, Gdańska 10”.')
      }
    } catch (err) {
      if (mine !== seq.current) return
      setResults(null)
      setError(err instanceof ApiRequestError ? err.message : 'Nie udało się wyszukać adresu. Spróbuj ponownie.')
    } finally {
      if (mine === seq.current) setBusy(false)
    }
  }

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex gap-2">
        <Input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setError(null)
            setResults(null)
            // Typing again cancels a search in flight: its answer no longer matches the text.
            seq.current += 1
            setBusy(false)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              void search()
            }
          }}
          placeholder="np. Ksawerów 12 albo Bydgoszcz, Gdańska 10"
          aria-label="Adres lub miejscowość"
          aria-controls={results?.length ? listId : undefined}
          autoComplete="off"
          enterKeyHint="search"
          className="h-11 text-base"
        />
        <Button
          type="button"
          variant="secondary"
          className="h-11"
          onClick={() => void search()}
          disabled={busy}
          aria-label="Szukaj adresu"
        >
          {busy ? <Loader2 className="animate-spin" /> : <Search />}
          <span className="hidden sm:inline">Szukaj</span>
        </Button>
      </div>
      {results && results.length > 1 && (
        <ul id={listId} className="divide-y overflow-hidden rounded-md border bg-card" aria-label="Znalezione miejsca">
          {results.map((p, i) => {
            const Icon = ICON[p.kind]
            return (
              <li key={`${p.label_pl}-${p.detail_pl}-${i}`}>
                <button
                  type="button"
                  className="flex min-h-11 w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                  onClick={() => {
                    setResults(null)
                    onChoose(p, stamp?.())
                  }}
                >
                  <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                  <span>
                    <span className="font-medium">{p.label_pl}</span>
                    {p.detail_pl && <span className="block text-xs text-muted-foreground">{p.detail_pl}</span>}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
