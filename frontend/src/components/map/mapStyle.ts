import 'maplibre-gl/dist/maplibre-gl.css'
import { type LngLatBoundsLike, type Map as MlMap, type MapOptions, setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import type { GeoJsonGeometry } from '@/api/types'

// Base map: OpenStreetMap at small scales, Geoportal orthophoto when zoomed in, and parcel boundaries with
// numbers from the national cadastre integration (KIEG) at field scale. All free, public services.

const ORTO_WMS =
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution?SERVICE=WMS&REQUEST=GetMap' +
  '&VERSION=1.3.0&LAYERS=Raster&STYLES=&FORMAT=image/jpeg&CRS=EPSG:3857&BBOX={bbox-epsg-3857}&WIDTH=512&HEIGHT=512'

// KIEG draws parcels only at large scales (≈ 1.2 m per pixel or finer), so 512 px images are requested for
// 256 px tiles: boundaries appear from zoom 16 and stay sharp on high-density phone screens.
const KIEG_WMS =
  'https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow?SERVICE=WMS&REQUEST=GetMap' +
  '&VERSION=1.3.0&LAYERS=dzialki,numery_dzialek&STYLES=&FORMAT=image/png&TRANSPARENT=TRUE&CRS=EPSG:3857' +
  '&BBOX={bbox-epsg-3857}&WIDTH=512&HEIGHT=512'

// MapLibre 6 builds its worker URL at runtime, which Vite cannot see: without this the worker is never
// emitted and no GeoJSON layer (parcel outline, water features) is drawn.
setWorkerUrl(workerUrl)

type StyleSpecification = Exclude<MapOptions['style'], string | undefined>

export const ORTO_MIN_ZOOM = 13
export const PARCELS_MIN_ZOOM = 16

// Whole Poland; the same range is accepted by GET /api/parcels (backend/app/api/routes.py).
export const POLAND_BOUNDS: LngLatBoundsLike = [
  [14.0, 48.9],
  [24.2, 55.0],
]

export function insidePoland(lat: number, lon: number): boolean {
  return lat >= 48.9 && lat <= 55.0 && lon >= 14.0 && lon <= 24.2
}

// Polish texts for MapLibre's built-in controls (keys of maplibre's defaultLocale).
export const MAP_LOCALE: Record<string, string> = {
  'AttributionControl.ToggleAttribution': 'Pokaż lub ukryj źródła mapy',
  'AttributionControl.MapFeedback': 'Zgłoś błąd mapy',
  'FullscreenControl.Enter': 'Pełny ekran',
  'FullscreenControl.Exit': 'Zamknij pełny ekran',
  'GeolocateControl.FindMyLocation': 'Moja lokalizacja',
  'GeolocateControl.LocationNotAvailable': 'Lokalizacja niedostępna',
  'LogoControl.Title': 'Logo MapLibre',
  'Map.Title': 'Mapa',
  'Marker.Title': 'Znacznik',
  'NavigationControl.ResetBearing': 'Obróć mapę na północ',
  'NavigationControl.ZoomIn': 'Przybliż',
  'NavigationControl.ZoomOut': 'Oddal',
  'Popup.Close': 'Zamknij',
  'ScaleControl.Feet': 'ft',
  'ScaleControl.Meters': 'm',
  'ScaleControl.Kilometers': 'km',
  'GlobeControl.Enable': 'Włącz globus',
  'GlobeControl.Disable': 'Wyłącz globus',
  'TerrainControl.Enable': 'Włącz teren',
  'TerrainControl.Disable': 'Wyłącz teren',
  'CooperativeGesturesHandler.WindowsHelpText': 'Użyj Ctrl + kółko myszy, aby przybliżyć mapę',
  'CooperativeGesturesHandler.MacHelpText': 'Użyj ⌘ + kółko myszy, aby przybliżyć mapę',
  'CooperativeGesturesHandler.MobileHelpText': 'Przesuń mapę dwoma palcami',
}

type Sources = StyleSpecification['sources']
type Layers = StyleSpecification['layers']

/** Base layers plus the caller's own GeoJSON sources and layers. Overlays are part of the initial style so they
 *  are drawn as soon as the style is parsed, without waiting for every (possibly slow) WMS tile. */
export function baseStyle(extraSources: Sources = {}, extraLayers: Layers = []): StyleSpecification {
  return {
    version: 8,
    sources: {
      ...extraSources,
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>',
      },
      orto: {
        type: 'raster',
        tiles: [ORTO_WMS],
        tileSize: 256,
        minzoom: ORTO_MIN_ZOOM,
        maxzoom: 20,
        attribution: 'Ortofotomapa © <a href="https://www.geoportal.gov.pl" target="_blank" rel="noreferrer">GUGiK</a>',
      },
      kieg: {
        type: 'raster',
        tiles: [KIEG_WMS],
        tileSize: 256,
        minzoom: PARCELS_MIN_ZOOM,
        maxzoom: 20,
        attribution: 'Granice działek © GUGiK',
      },
    },
    layers: [
      { id: 'osm', type: 'raster', source: 'osm' },
      { id: 'orto', type: 'raster', source: 'orto', minzoom: ORTO_MIN_ZOOM },
      { id: 'kieg', type: 'raster', source: 'kieg', minzoom: PARCELS_MIN_ZOOM },
      ...extraLayers,
    ],
  }
}

/** MapLibre opens the compact attribution at start; on a small map it covers the field, so start it collapsed
 *  (same class change as MapLibre's own toggle button; the "i" button still opens it). */
export function collapseAttribution(map: MlMap): void {
  const el = map.getContainer().querySelector('.maplibregl-ctrl-attrib')
  if (!el) return
  // MapLibre adds the "shown" class once, after the first attribution update; collapse it the moment it appears.
  const collapse = () => {
    if (!el.classList.contains('maplibregl-compact-show')) return false
    el.setAttribute('open', '')
    el.classList.remove('maplibregl-compact-show')
    return true
  }
  if (collapse()) return
  const observer = new MutationObserver(() => {
    if (collapse()) observer.disconnect()
  })
  observer.observe(el, { attributes: true, attributeFilter: ['class'] })
  map.once('remove', () => observer.disconnect())
}

type Position = [number, number]

function collectPositions(coords: unknown, out: Position[]): void {
  if (!Array.isArray(coords)) return
  if (coords.length >= 2 && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
    out.push([coords[0], coords[1]])
    return
  }
  for (const c of coords) collectPositions(c, out)
}

export function geometryBounds(geometries: GeoJsonGeometry[]): [Position, Position] | null {
  const pts: Position[] = []
  for (const g of geometries) collectPositions(g.coordinates, pts)
  if (pts.length === 0) return null
  let [minX, minY] = pts[0]
  let [maxX, maxY] = pts[0]
  for (const [x, y] of pts) {
    minX = Math.min(minX, x)
    minY = Math.min(minY, y)
    maxX = Math.max(maxX, x)
    maxY = Math.max(maxY, y)
  }
  return [
    [minX, minY],
    [maxX, maxY],
  ]
}

export function representativePoint(g: GeoJsonGeometry): Position | null {
  const b = geometryBounds([g])
  if (!b) return null
  if (g.type === 'Point') return b[0]
  if (g.type === 'LineString' && Array.isArray(g.coordinates) && g.coordinates.length > 0) {
    // Middle vertex of the line, so the marker sits on it.
    const mid = g.coordinates[Math.floor(g.coordinates.length / 2)] as unknown
    if (Array.isArray(mid) && typeof mid[0] === 'number' && typeof mid[1] === 'number') return [mid[0], mid[1]]
  }
  return [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2]
}
