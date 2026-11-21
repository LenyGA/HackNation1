import type { Map as MlMap } from 'maplibre-gl'
import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'

// "Full screen" as an own mode (the map box becomes `fixed inset-0`) instead of the Fullscreen API, which Safari on
// iOS does not offer for ordinary elements (plan2 L1.3). Esc closes it; the page does not scroll underneath.
export function useMapFullscreen(mapRef: RefObject<MlMap | null>) {
  const [full, setFull] = useState(false)
  const toggle = useCallback(() => setFull((v) => !v), [])
  const cooperative = useRef(false)
  // Read when a map is (re)created while full screen is on, so the new map starts without cooperative gestures.
  const fullRef = useRef(false)

  useEffect(() => {
    fullRef.current = full
    const map = mapRef.current
    if (!map) return
    // One finger moves the map in full screen (nothing to scroll there); back in the page the map's own setting returns.
    if (full) {
      cooperative.current = map.cooperativeGestures.isEnabled()
      map.cooperativeGestures.disable()
    } else if (cooperative.current) {
      map.cooperativeGestures.enable()
    }
    // The container changes size with the class: let MapLibre redraw at the new size after layout.
    const frame = requestAnimationFrame(() => map.resize())
    return () => cancelAnimationFrame(frame)
  }, [full, mapRef])

  useEffect(() => {
    if (!full) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFull(false)
    }
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = overflow
      window.removeEventListener('keydown', onKey)
    }
  }, [full])

  return { full, toggle, fullRef }
}
