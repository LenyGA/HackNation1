import type { FeatureCollection, Geometry } from 'geojson'
import { type GeoJSONSource, Map as MlMap, NavigationControl } from 'maplibre-gl'
import { Crosshair, Loader2, MapPinOff, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiRequestError } from '@/api/client'
import type { Parcel } from '@/api/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { FullscreenButton } from './FullscreenButton'
import {
  baseStyle,
  collapseAttribution,
  geometryBounds,
  insidePoland,
  MAP_LOCALE,
  outsidePolandMask,
  PARCELS_MIN_ZOOM,
  POLAND_BOUNDS,
} from './mapStyle'
import { useMapFullscreen } from './useMapFullscreen'

interface Props {
  selected: Parcel | null
  // Farm mode (G11): more parcels of the same farm, drawn in blue; a tap then adds a parcel instead.
  extras?: Parcel[]
  adding?: boolean
  onPick: (parcel: Parcel) => void
  onError: (message: string) => void
  // Address search (M8.7): fly here; a new object flies again even to the same place.
  focus?: MapFocus | null
}

export interface MapFocus {
  lat: number
  lon: number
  zoom: number
}

const NO_EXTRAS: Parcel[] = []

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

function parcelCollection(parcels: Parcel | null | Parcel[]): FeatureCollection {
  const list = Array.isArray(parcels) ? parcels : parcels ? [parcels] : []
  if (list.length === 0) return EMPTY
  return {
    type: 'FeatureCollection',
    features: list.map((p) => ({ type: 'Feature', properties: {}, geometry: p.geometry as unknown as Geometry })),
  }
}

function geolocationError(err: GeolocationPositionError): string {
  if (!window.isSecureContext) {
    return 'Lokalizacja działa tylko na bezpiecznej stronie (https). Wpisz numer działki albo znajdź ją na mapie.'
  }
  if (err.code === err.PERMISSION_DENIED) {
    return 'Przeglądarka nie ma zgody na dostęp do lokalizacji. Zezwól na nią w ustawieniach albo znajdź działkę na mapie.'
  }
  return 'Nie udało się ustalić lokalizacji. Spróbuj ponownie na zewnątrz albo znajdź działkę na mapie.'
}

/** Map for choosing a parcel: tap a field to look it up in the cadastre (ULDK) and highlight its outline. */
export default function ParcelPickerMap({
  selected,
  extras = NO_EXTRAS,
  adding = false,
  onPick,
  onError,
  focus = null,
}: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const selectedRef = useRef<Parcel | null>(selected)
  const extrasRef = useRef<Parcel[]>(extras)
  const focusRef = useRef<MapFocus | null>(focus)
  // Latest callbacks, read by the map's click handler that is registered once.
  const handlers = useRef({ onPick, onError })
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [zoom, setZoom] = useState(5)
  // Shown on the map, without asking the server, when a click or the location is outside Poland (plan2 L1.4).
  const [outside, setOutside] = useState(false)
  const { full, toggle } = useMapFullscreen(mapRef)

  useEffect(() => {
    handlers.current = { onPick, onError }
  }, [onPick, onError])

  useEffect(() => {
    if (!container.current) return
    const map = new MlMap({
      container: container.current,
      // The outline layers are part of the initial style, so they never wait for the WMS tiles.
      style: baseStyle(
        {
          selected: { type: 'geojson', data: parcelCollection(selectedRef.current) },
          extras: { type: 'geojson', data: parcelCollection(extrasRef.current) },
          outside: { type: 'geojson', data: outsidePolandMask() },
        },
        [
          // Grey veil over everything outside Poland, under the parcel outline.
          { id: 'outside-fill', type: 'fill', source: 'outside', paint: { 'fill-color': '#334155', 'fill-opacity': 0.45 } },
          { id: 'outside-line', type: 'line', source: 'outside', paint: { 'line-color': '#dc2626', 'line-width': 1.5, 'line-opacity': 0.7 } },
          { id: 'extras-fill', type: 'fill', source: 'extras', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.25 } },
          { id: 'extras-line', type: 'line', source: 'extras', paint: { 'line-color': '#38bdf8', 'line-width': 2.5 } },
          { id: 'selected-fill', type: 'fill', source: 'selected', paint: { 'fill-color': '#facc15', 'fill-opacity': 0.25 } },
          { id: 'selected-line', type: 'line', source: 'selected', paint: { 'line-color': '#facc15', 'line-width': 3 } },
        ],
      ),
      bounds: POLAND_BOUNDS,
      maxBounds: [
        [12, 47.5],
        [26, 56.5],
      ],
      maxZoom: 19,
      // On phones one finger scrolls the page, two fingers move the map; on desktop Ctrl + wheel zooms.
      cooperativeGestures: true,
      attributionControl: { compact: true },
      locale: MAP_LOCALE,
    })
    mapRef.current = map
    collapseAttribution(map)
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    // A parcel chosen by number before the map was created is framed at once.
    const initial = selectedRef.current && geometryBounds([selectedRef.current.geometry])
    if (initial) map.fitBounds(initial, { padding: 60, maxZoom: 18, duration: 0 })
    else if (focusRef.current) map.jumpTo({ center: [focusRef.current.lon, focusRef.current.lat], zoom: focusRef.current.zoom })

    map.on('zoomend', () => setZoom(map.getZoom()))

    // Only the latest click may update the selection, whatever order the responses arrive in.
    let clickSeq = 0
    map.on('click', async (e) => {
      const { lat, lng } = e.lngLat
      // Checked at every zoom level, before anything is asked from the server.
      if (!insidePoland(lat, lng)) {
        setOutside(true)
        return
      }
      setOutside(false)
      if (map.getZoom() < PARCELS_MIN_ZOOM - 2) {
        // Zoomed out too far to hit one parcel: zoom in towards the click instead.
        map.easeTo({ center: e.lngLat, zoom: Math.min(map.getZoom() + 3, PARCELS_MIN_ZOOM) })
        return
      }
      const seq = ++clickSeq
      setBusy(true)
      try {
        const parcel = await api.parcelByPoint(lat, lng)
        if (seq === clickSeq) handlers.current.onPick(parcel)
      } catch (err) {
        if (seq === clickSeq) {
          handlers.current.onError(
            err instanceof ApiRequestError ? err.message : 'Nie udało się pobrać działki. Spróbuj ponownie.',
          )
        }
      } finally {
        if (seq === clickSeq) setBusy(false)
      }
    })

    return () => {
      clickSeq = -1
      mapRef.current = null
      map.remove()
    }
  }, [])

  useEffect(() => {
    if (selectedRef.current === selected) return
    selectedRef.current = selected
    const map = mapRef.current
    if (!map) return
    const apply = () => {
      ;(map.getSource('selected') as GeoJSONSource | undefined)?.setData(parcelCollection(selected))
    }
    if (map.getSource('selected')) apply()
    else map.once('style.load', apply)
    const b = selected && geometryBounds([selected.geometry])
    if (b) map.fitBounds(b, { padding: 60, maxZoom: 18, duration: 800 })
  }, [selected])

  useEffect(() => {
    if (focusRef.current === focus) return
    focusRef.current = focus
    if (focus) mapRef.current?.flyTo({ center: [focus.lon, focus.lat], zoom: focus.zoom, duration: 1200 })
  }, [focus])

  useEffect(() => {
    if (extrasRef.current === extras) return
    extrasRef.current = extras
    const map = mapRef.current
    if (!map) return
    const apply = () => {
      ;(map.getSource('extras') as GeoJSONSource | undefined)?.setData(parcelCollection(extras))
    }
    if (map.getSource('extras')) apply()
    else map.once('style.load', apply)
  }, [extras])

  function locate() {
    if (!('geolocation' in navigator)) {
      onError('Ta przeglądarka nie udostępnia lokalizacji. Wpisz numer działki albo znajdź ją na mapie.')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { latitude, longitude } = pos.coords
        if (!insidePoland(latitude, longitude)) {
          setOutside(true)
          return
        }
        setOutside(false)
        mapRef.current?.flyTo({ center: [longitude, latitude], zoom: 17 })
      },
      (err) => {
        setLocating(false)
        onError(geolocationError(err))
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  return (
    <div className="space-y-2">
      <div
        className={cn(
          'overflow-hidden border',
          full ? 'fixed inset-0 z-50 bg-background' : 'relative h-[60svh] max-h-[720px] min-h-[320px] rounded-lg',
        )}
      >
        <div ref={container} className="h-full w-full" aria-label="Mapa do wyboru działki" />
        <FullscreenButton full={full} onToggle={toggle} />
        {outside && (
          <div className="absolute inset-x-2.5 top-20 z-10 flex justify-center">
            <Alert variant="destructive" className="max-w-md pr-10 shadow-lg">
              <MapPinOff />
              <AlertTitle>To miejsce jest poza Polską</AlertTitle>
              <AlertDescription>Aplikacja działa tylko dla działek w Polsce. Kliknij na terenie Polski.</AlertDescription>
              <button
                type="button"
                className="absolute top-2 right-2 rounded p-1 text-muted-foreground hover:bg-muted"
                onClick={() => setOutside(false)}
                aria-label="Zamknij komunikat"
              >
                <X className="size-4" />
              </button>
            </Alert>
          </div>
        )}
        {busy && (
          <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
            <span className="flex items-center gap-2 rounded-full bg-background/90 px-3 py-1 text-sm shadow">
              <Loader2 className="size-4 animate-spin" /> Szukam działki…
            </span>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button type="button" variant="outline" size="lg" onClick={locate} disabled={locating}>
          {locating ? <Loader2 className="animate-spin" /> : <Crosshair />}
          Moja lokalizacja
        </Button>
        <p className="text-xs text-muted-foreground">
          {zoom < PARCELS_MIN_ZOOM
            ? 'Przybliż mapę, aby zobaczyć granice działek, i dotknij swojego pola.'
            : adding
              ? 'Dotknij kolejnego pola, aby dodać je do gospodarstwa.'
              : 'Dotknij swojego pola, aby je wybrać.'}
        </p>
      </div>
    </div>
  )
}
