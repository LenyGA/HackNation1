import type { FeatureCollection, Geometry } from 'geojson'
import { type AddLayerObject, Map as MlMap, Marker, NavigationControl, Popup } from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'
import type { FloodInfo, MapFeatureKind, ReportMap } from '@/api/types'
import { cn } from '@/lib/utils'
import { FullscreenButton } from './FullscreenButton'
import { baseStyle, collapseAttribution, geometryBounds, MAP_LOCALE, representativePoint } from './mapStyle'
import { useMapFullscreen } from './useMapFullscreen'

// Colours per feature kind, shared by the map layers and the legend.
const KIND_COLORS: Record<MapFeatureKind, string> = {
  depression: '#06b6d4',
  depression_minor: '#a5f3fc',
  flow_path: '#0ea5e9',
  outlet: '#dc2626',
  ditch: '#2563eb',
  watercourse: '#1d4ed8',
  water_body: '#3b82f6',
  wetland: '#14b8a6',
  trees: '#16a34a',
}

const KIND_ORDER: MapFeatureKind[] = [
  'outlet',
  'flow_path',
  'depression',
  'depression_minor',
  'ditch',
  'watercourse',
  'water_body',
  'wetland',
  'trees',
]

const FEATURE_LAYERS = ['f-point', 'f-flow', 'f-line', 'f-fill']

// MapLibre expression: colour by the `kind` property of each feature.
type ColorValue = NonNullable<Extract<AddLayerObject, { type: 'fill' }>['paint']>['fill-color']
const colorExpr = ['match', ['get', 'kind'], ...Object.entries(KIND_COLORS).flat(), '#64748b'] as unknown as ColorValue

function featureCollection(map: ReportMap): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: map.features.map((f) => ({
      type: 'Feature',
      properties: { kind: f.kind, label: f.label_pl, recs: f.recommendation_numbers.join(', ') },
      geometry: f.geometry as unknown as Geometry,
    })),
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

function popupHtml(label: string, recs: string): string {
  const rec = recs ? `<br><span style="color:#4b5563">Zalecenie nr ${escapeHtml(recs)}</span>` : ''
  return `<strong>${escapeHtml(label)}</strong>${rec}`
}

/** Report map: parcel outline, where water gathers and leaves the field, nearby water and trees,
 *  with numbered markers that match the recommendation numbers in section 5. */
/** WMS GetMap tile template in Web Mercator (MapLibre fills in the tile bbox). */
function wmsTiles(url: string, layers: string[]): string {
  const sep = url.includes('?') ? '&' : '?'
  return (
    `${url}${sep}SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=${encodeURIComponent(layers.join(','))}` +
    '&STYLES=&FORMAT=image/png&TRANSPARENT=true&CRS=EPSG:3857&WIDTH=256&HEIGHT=256&BBOX={bbox-epsg-3857}'
  )
}

export function ReportMapView({ map: data, flood = null }: { map: ReportMap; flood?: FloodInfo | null }) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const floodUrl = flood?.wms_url && flood.wms_layers.length > 0 ? wmsTiles(flood.wms_url, flood.wms_layers) : null
  // The legend entry appears only once a flood tile has really loaded (CSP or a slow service may block them),
  // so an empty map never reads as "no flood zone".
  const [loadedFloodUrl, setLoadedFloodUrl] = useState<string | null>(null)
  const { full, toggle, fullRef } = useMapFullscreen(mapRef)

  useEffect(() => {
    if (!container.current) return
    const bounds = geometryBounds([data.parcel])
    const map = new MlMap({
      container: container.current,
      // Overlays are part of the initial style, so they are drawn without waiting for the WMS tiles.
      style: baseStyle(
        {
          ...(floodUrl ? { flood: { type: 'raster' as const, tiles: [floodUrl], tileSize: 256, attribution: 'Mapy zagrożenia powodziowego © Wody Polskie (ISOK)' } } : {}),
          features: { type: 'geojson', data: featureCollection(data) },
          parcel: {
            type: 'geojson',
            data: { type: 'Feature', properties: {}, geometry: data.parcel as unknown as Geometry },
          },
        },
        [
          ...(floodUrl ? [{ id: 'flood', type: 'raster' as const, source: 'flood', paint: { 'raster-opacity': 0.5 } }] : []),
          {
            id: 'f-fill',
            type: 'fill',
            source: 'features',
            filter: ['in', ['geometry-type'], ['literal', ['Polygon', 'MultiPolygon']]],
            paint: { 'fill-color': colorExpr, 'fill-opacity': 0.35 },
          },
          {
            id: 'f-line',
            type: 'line',
            source: 'features',
            filter: [
              'all',
              ['in', ['geometry-type'], ['literal', ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']]],
              ['!=', ['get', 'kind'], 'flow_path'],
            ],
            paint: {
              'line-color': colorExpr,
              'line-width': ['match', ['get', 'kind'], 'watercourse', 3, 'ditch', 3, 1.5],
            },
          },
          {
            id: 'f-flow',
            type: 'line',
            source: 'features',
            filter: ['==', ['get', 'kind'], 'flow_path'],
            paint: { 'line-color': KIND_COLORS.flow_path, 'line-width': 4, 'line-dasharray': [2, 1] },
          },
          {
            id: 'f-point',
            type: 'circle',
            source: 'features',
            filter: ['in', ['geometry-type'], ['literal', ['Point', 'MultiPoint']]],
            paint: {
              'circle-color': colorExpr,
              'circle-radius': 7,
              'circle-stroke-color': '#ffffff',
              'circle-stroke-width': 2,
            },
          },
          { id: 'parcel-line', type: 'line', source: 'parcel', paint: { 'line-color': '#facc15', 'line-width': 3 } },
        ],
      ),
      bounds: bounds ?? undefined,
      fitBoundsOptions: { padding: 40, maxZoom: 18 },
      maxZoom: 19,
      cooperativeGestures: !fullRef.current,
      attributionControl: { compact: true },
      locale: MAP_LOCALE,
    })
    mapRef.current = map
    collapseAttribution(map)
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')

    // One handler for all feature layers, so a click on a polygon edge opens one popup, not two.
    let popup: Popup | null = null
    map.on('sourcedata', (e) => {
      if (floodUrl && e.sourceId === 'flood' && e.tile) setLoadedFloodUrl(floodUrl)
    })
    map.on('click', (e) => {
      const layers = FEATURE_LAYERS.filter((id) => map.getLayer(id))
      const f = layers.length ? map.queryRenderedFeatures(e.point, { layers })[0] : undefined
      popup?.remove()
      popup = null
      if (!f) return
      popup = new Popup({ closeButton: true, maxWidth: '240px' })
        .setLngLat(e.lngLat)
        .setHTML(popupHtml(String(f.properties.label ?? ''), String(f.properties.recs ?? '')))
        .addTo(map)
    })
    for (const layer of FEATURE_LAYERS) {
      map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
    }

    // Numbered badges for the places a recommendation points to (HTML markers need no style).
    const markers: Marker[] = []
    for (const f of data.features) {
      if (f.recommendation_numbers.length === 0) continue
      const at = representativePoint(f.geometry)
      if (!at) continue
      const el = document.createElement('div')
      el.className =
        'flex h-7 min-w-7 items-center justify-center rounded-full border-2 border-white bg-primary px-1.5 text-sm font-bold text-primary-foreground shadow'
      el.textContent = f.recommendation_numbers.join(',')
      el.setAttribute('aria-label', `Miejsce do zalecenia nr ${f.recommendation_numbers.join(', ')}`)
      markers.push(new Marker({ element: el, offset: [0, -18] }).setLngLat(at).addTo(map))
    }

    return () => {
      markers.forEach((m) => m.remove())
      mapRef.current = null
      map.remove()
    }
  }, [data, floodUrl, fullRef])

  const kinds = KIND_ORDER.filter((k) => data.legend_pl[k])
  const hasNumbered = data.features.some((f) => f.recommendation_numbers.length > 0)

  return (
    <div className="space-y-3">
      <div className={cn('overflow-hidden border', full ? 'fixed inset-0 z-50 bg-background' : 'relative h-[300px] rounded-lg sm:h-[400px]')}>
        <div ref={container} className="h-full w-full" aria-label="Mapa działki z miejscami zatrzymywania wody" />
        <FullscreenButton full={full} onToggle={toggle} />
      </div>
      <ul className="grid grid-cols-1 gap-1.5 text-sm sm:grid-cols-2">
        <li className="flex items-center gap-2">
          <span className="inline-block h-3 w-5 rounded-sm border-2 border-yellow-400" aria-hidden /> Twoja działka
        </li>
        {hasNumbered && (
          <li className="flex items-center gap-2">
            <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground" aria-hidden>
              1
            </span>
            Numer zalecenia z listy poniżej
          </li>
        )}
        {floodUrl && loadedFloodUrl === floodUrl && (
          <li className="flex items-center gap-2">
            <span className="inline-block h-3 w-5 rounded-sm" style={{ background: '#60a5fa', opacity: 0.6 }} aria-hidden />
            Strefa zagrożenia powodziowego
          </li>
        )}
        {kinds.map((k) => (
          <li key={k} className="flex items-center gap-2">
            <LegendSwatch kind={k} />
            {data.legend_pl[k]}
          </li>
        ))}
      </ul>
    </div>
  )
}

function LegendSwatch({ kind }: { kind: MapFeatureKind }) {
  const color = KIND_COLORS[kind]
  if (kind === 'outlet') return <span className="inline-block size-3.5 rounded-full border-2 border-white shadow" style={{ background: color }} aria-hidden />
  if (kind === 'flow_path' || kind === 'ditch' || kind === 'watercourse') {
    return (
      <span
        className="inline-block w-5"
        style={{ borderTop: `3px ${kind === 'flow_path' ? 'dashed' : 'solid'} ${color}` }}
        aria-hidden
      />
    )
  }
  return <span className="inline-block h-3 w-5 rounded-sm" style={{ background: color, opacity: 0.7 }} aria-hidden />
}
