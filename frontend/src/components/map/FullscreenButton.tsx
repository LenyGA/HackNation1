import { Maximize2, Minimize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

/** Toggle shown in the top-left corner of a map. */
export function FullscreenButton({ full, onToggle }: { full: boolean; onToggle: () => void }) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="absolute top-2.5 left-2.5 z-10 bg-background/95 shadow"
      onClick={onToggle}
      aria-pressed={full}
    >
      {full ? <Minimize2 /> : <Maximize2 />}
      {full ? 'Zamknij pełny ekran' : 'Pełny ekran'}
    </Button>
  )
}
