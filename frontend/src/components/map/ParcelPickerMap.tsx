import type { FeatureCollection, Geometry } from 'geojson'
import { type GeoJSONSource, Map as MlMap, NavigationControl } from 'maplibre-gl'
import { Crosshair, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiRequestError } from '@/api/client'
import type { Parcel } from '@/api/types'
import { Button } from '@/components/ui/button'
import { baseStyle, collapseAttribution, geometryBounds, insidePoland, MAP_LOCALE, PARCELS_MIN_ZOOM, POLAND_BOUNDS } from './mapStyle'

interface Props {
  selected: Parcel | null
  onPick: (parcel: Parcel) => void
  onError: (message: string) => void
}

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }
const OUTSIDE_PL = 'Wskazane miejsce leży poza Polską. Wybierz działkę na terenie Polski.'

function parcelCollection(parcel: Parcel | null): FeatureCollection {
  if (!parcel) return EMPTY
  return {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: {}, geometry: parcel.geometry as unknown as Geometry }],
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
export default function ParcelPickerMap({ selected, onPick, onError }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const selectedRef = useRef<Parcel | null>(selected)
  // Latest callbacks, read by the map's click handler that is registered once.
  const handlers = useRef({ onPick, onError })
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [zoom, setZoom] = useState(5)

  useEffect(() => {
    handlers.current = { onPick, onError }
  }, [onPick, onError])

  useEffect(() => {
    if (!container.current) return
    const map = new MlMap({
      container: container.current,
      // The outline layers are part of the initial style, so they never wait for the WMS tiles.
      style: baseStyle({ selected: { type: 'geojson', data: parcelCollection(selectedRef.current) } }, [
        { id: 'selected-fill', type: 'fill', source: 'selected', paint: { 'fill-color': '#facc15', 'fill-opacity': 0.25 } },
        { id: 'selected-line', type: 'line', source: 'selected', paint: { 'line-color': '#facc15', 'line-width': 3 } },
      ]),
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

    map.on('zoomend', () => setZoom(map.getZoom()))

    // Only the latest click may update the selection, whatever order the responses arrive in.
    let clickSeq = 0
    map.on('click', async (e) => {
      if (map.getZoom() < PARCELS_MIN_ZOOM - 2) {
        // Zoomed out too far to hit one parcel: zoom in towards the click instead.
        map.easeTo({ center: e.lngLat, zoom: Math.min(map.getZoom() + 3, PARCELS_MIN_ZOOM) })
        return
      }
      const { lat, lng } = e.lngLat
      if (!insidePoland(lat, lng)) {
        handlers.current.onError(OUTSIDE_PL)
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
          onError(OUTSIDE_PL)
          return
        }
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
      <div className="relative h-[320px] overflow-hidden rounded-lg border sm:h-[420px]">
        <div ref={container} className="h-full w-full" aria-label="Mapa do wyboru działki" />
        {busy && (
          <div className="pointer-events-none absolute inset-x-0 top-2 flex justify-center">
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
            : 'Dotknij swojego pola, aby je wybrać.'}
        </p>
      </div>
    </div>
  )
}
