import type { Feature, MultiPolygon } from 'geojson'
import outline from './poland.json'

// Outline of Poland (land, PRG GUGiK, buffered 200 m outwards and simplified — backend/scripts/build_poland_outline.py):
// a main polygon with holes (enclosed water: lagoons, river mouths) and a few islands
// and a point-in-polygon test without any dependency (plan2 L1.4). Pure module: no MapLibre import, so it is tested
// with vitest in Node.

type Ring = number[][]
type PolygonCoords = Ring[]

interface OutlineFeature {
  geometry: { type: 'Polygon'; coordinates: PolygonCoords } | { type: 'MultiPolygon'; coordinates: PolygonCoords[] }
}

const geometry = (outline as unknown as OutlineFeature).geometry
export const POLAND_POLYGONS: PolygonCoords[] = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates

function ringBounds(ring: Ring): [number, number, number, number] {
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const [x, y] of ring) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  return [minX, minY, maxX, maxY]
}

const BOXES = POLAND_POLYGONS.map((p) => ringBounds(p[0]))

/** Ray casting (even–odd rule) for one ring; x = longitude, y = latitude. */
export function pointInRing(x: number, y: number, ring: Ring): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export function insidePoland(lat: number, lon: number): boolean {
  return POLAND_POLYGONS.some((poly, k) => {
    const [minX, minY, maxX, maxY] = BOXES[k]
    // Quick rejection by the bounding box before the full test.
    if (lon < minX || lon > maxX || lat < minY || lat > maxY) return false
    return pointInRing(lon, lat, poly[0]) && !poly.slice(1).some((hole) => pointInRing(lon, lat, hole))
  })
}

/** The world with Poland cut out, plus the water enclosed by the outline (its holes, e.g. the Szczecin Lagoon):
 *  a grey mask over exactly the area where `insidePoland` is false. */
export function outsidePolandMask(): Feature<MultiPolygon> {
  const world: Ring = [
    [-180, -85],
    [180, -85],
    [180, 85],
    [-180, 85],
    [-180, -85],
  ]
  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'MultiPolygon',
      coordinates: [[world, ...POLAND_POLYGONS.map((p) => p[0])], ...POLAND_POLYGONS.flatMap((p) => p.slice(1).map((hole) => [hole]))],
    },
  }
}
