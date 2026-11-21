import { describe, expect, it } from 'vitest'
import { insidePoland, outsidePolandMask, pointInRing, POLAND_POLYGONS } from './poland'

// plan2 L1.4: pairs of towns on both sides of the border (coordinates of the town centres).
const BORDER_PAIRS: { pl: [string, number, number]; abroad: [string, number, number] }[] = [
  { pl: ['Słubice', 52.3497, 14.56], abroad: ['Frankfurt nad Odrą', 52.342, 14.544] },
  { pl: ['Cieszyn', 49.75, 18.633], abroad: ['Český Těšín', 49.744, 18.614] },
  { pl: ['Braniewo', 54.38, 19.82], abroad: ['Kaliningrad', 54.71, 20.51] },
]

describe('insidePoland', () => {
  it.each(BORDER_PAIRS.map((p) => p.pl))('%s is in Poland', (_name, lat, lon) => {
    expect(insidePoland(lat, lon)).toBe(true)
  })

  it.each(BORDER_PAIRS.map((p) => p.abroad))('%s is not in Poland', (_name, lat, lon) => {
    expect(insidePoland(lat, lon)).toBe(false)
  })

  it.each([
    ['Warszawa', 52.2297, 21.0122],
    ['Hel', 54.6077, 18.8008],
    ['Wolin (wyspa)', 53.85, 14.6],
    ['Sejny', 54.11, 23.35],
    ['Ustrzyki Górne', 49.105, 22.65],
  ])('%s is in Poland', (_name, lat, lon) => {
    expect(insidePoland(lat, lon)).toBe(true)
  })

  it.each([
    ['Bałtyk', 54.9, 18.0],
    ['Wilno', 54.687, 25.28],
    ['Lwów', 49.84, 24.03],
    ['Berlin', 52.52, 13.405],
    ['Bratysława', 48.15, 17.11],
    ['Grodno', 53.68, 23.83],
  ])('%s is not in Poland', (_name, lat, lon) => {
    expect(insidePoland(lat, lon)).toBe(false)
  })
})

describe('outline', () => {
  it('is small and covers Poland', () => {
    const vertices = POLAND_POLYGONS.flat().reduce((n, ring) => n + ring.length, 0)
    expect(vertices).toBeGreaterThan(500)
    expect(vertices).toBeLessThan(10_000)
  })

  it('ray casting on a unit square', () => {
    const sq = [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
      [0, 0],
    ]
    expect(pointInRing(0.5, 0.5, sq)).toBe(true)
    expect(pointInRing(1.5, 0.5, sq)).toBe(false)
  })

  it('mask is the world with Poland as holes', () => {
    const mask = outsidePolandMask()
    const holes = POLAND_POLYGONS.reduce((n, p) => n + p.length - 1, 0)
    expect(mask.geometry.coordinates[0].length).toBe(1 + POLAND_POLYGONS.length)
    expect(mask.geometry.coordinates.length).toBe(1 + holes)
  })
})
