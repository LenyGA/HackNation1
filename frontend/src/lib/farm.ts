// Farm mode (G11): client-side pre-check of extra parcels. The server stays authoritative (api/jobs.py).
import type { GeoJsonGeometry, Parcel } from '@/api/types'

export const MAX_FARM_DISTANCE_M = 2000

type Box = [number, number, number, number] // minLon, minLat, maxLon, maxLat

function collect(c: unknown, box: Box): void {
  if (!Array.isArray(c)) return
  if (typeof c[0] === 'number' && typeof c[1] === 'number') {
    box[0] = Math.min(box[0], c[0])
    box[1] = Math.min(box[1], c[1])
    box[2] = Math.max(box[2], c[0])
    box[3] = Math.max(box[3], c[1])
    return
  }
  for (const x of c) collect(x, box)
}

function bbox(g: GeoJsonGeometry): Box | null {
  const box: Box = [Infinity, Infinity, -Infinity, -Infinity]
  collect(g.coordinates, box)
  return Number.isFinite(box[0]) ? box : null
}

/**
 * Distance between the bounding boxes of two parcels in metres: never more than the true outline distance,
 * so a parcel rejected here is surely farther than the limit. Null when a geometry is empty.
 */
export function bboxDistanceM(a: Parcel, b: Parcel): number | null {
  const p = bbox(a.geometry)
  const q = bbox(b.geometry)
  if (!p || !q) return null
  const dLon = Math.max(0, q[0] - p[2], p[0] - q[2])
  const dLat = Math.max(0, q[1] - p[3], p[1] - q[3])
  const lat = (((p[1] + p[3]) / 2) * Math.PI) / 180
  const mPerDeg = 111_320
  return Math.hypot(dLon * mPerDeg * Math.cos(lat), dLat * mPerDeg)
}

/** True when the parcel is surely too far from the main one to join the farm. */
export function tooFar(main: Parcel, p: Parcel): boolean {
  const d = bboxDistanceM(main, p)
  return d !== null && d > MAX_FARM_DISTANCE_M
}
