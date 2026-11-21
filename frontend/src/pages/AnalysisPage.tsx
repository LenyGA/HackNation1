import { AlertTriangle, CheckCircle2, CircleSlash, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiRequestError } from '@/api/client'
import type { AnalysisStatus, SourceProgressState } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const POLL_MS = 1000
// Transient network errors are retried; after this many in a row the farmer is told what happened.
const MAX_POLL_FAILURES = 10

const STATE_TEXT: Record<SourceProgressState, string> = {
  pending: 'pobieram…',
  ok: 'gotowe',
  degraded: 'gotowe, z ograniczeniami',
  missing: 'brak danych',
}

function StateIcon({ state }: { state: SourceProgressState }) {
  switch (state) {
    case 'pending':
      return <Loader2 className="size-5 shrink-0 animate-spin text-muted-foreground" aria-hidden />
    case 'ok':
      return <CheckCircle2 className="size-5 shrink-0 text-primary" aria-hidden />
    case 'degraded':
      return <AlertTriangle className="size-5 shrink-0 text-amber-600" aria-hidden />
    case 'missing':
      return <CircleSlash className="size-5 shrink-0 text-destructive" aria-hidden />
  }
}

export function AnalysisPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<AnalysisStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The job lives on the server for an hour: after a lost connection polling can simply be restarted.
  const [lostConnection, setLostConnection] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    let failures = 0

    async function poll() {
      try {
        const s = await api.analysis(id)
        if (!alive) return
        failures = 0
        setStatus(s)
        if (s.status === 'done' && s.report_id) {
          navigate(`/raport/${encodeURIComponent(s.report_id)}`, { replace: true })
          return
        }
        if (s.status === 'failed') return
      } catch (err) {
        if (!alive) return
        failures += 1
        if (err instanceof ApiRequestError && err.status === 404) {
          setError(err.message)
          return
        }
        if (failures >= MAX_POLL_FAILURES) {
          setLostConnection(true)
          return
        }
      }
      timer = window.setTimeout(poll, POLL_MS)
    }

    void poll()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [id, navigate, attempt])

  if (lostConnection && !error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Straciliśmy połączenie z serwerem</CardTitle>
          <CardDescription>Analiza nadal może się liczyć. Sprawdź internet i spróbuj ponownie.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            size="lg"
            className="w-full sm:w-auto"
            onClick={() => {
              setLostConnection(false)
              setAttempt((a) => a + 1)
            }}
          >
            Spróbuj ponownie
          </Button>
        </CardContent>
      </Card>
    )
  }

  const failed = status?.status === 'failed'
  const message = error ?? (failed ? (status?.error_pl ?? 'Analiza nie powiodła się.') : null)
  const done = status?.sources.filter((s) => s.status !== 'pending').length ?? 0
  const total = status?.sources.length ?? 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">{message ? 'Nie udało się przygotować raportu' : 'Liczę sytuację wodną działki'}</CardTitle>
        <CardDescription>
          {message
            ? message
            : 'Pobieram dane pogodowe, zdjęcia satelitarne, mapy gleb i terenu. Zwykle trwa to do pół minuty.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {total > 0 && !message && (
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={done}
            aria-label="Postęp pobierania danych"
          >
            <div className="h-full bg-primary transition-all" style={{ width: `${(100 * done) / total}%` }} />
          </div>
        )}
        {status ? (
          <ul className="divide-y rounded-md border" aria-live="polite">
            {status.sources.map((s) => (
              <li key={s.name} className="flex items-center justify-between gap-3 px-3 py-2.5">
                <span className="flex items-center gap-2.5">
                  <StateIcon state={s.status} />
                  <span>{s.label_pl}</span>
                </span>
                <span className="text-right text-sm text-muted-foreground">{STATE_TEXT[s.status]}</span>
              </li>
            ))}
          </ul>
        ) : (
          !message && (
            <p className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Uruchamiam analizę…
            </p>
          )
        )}
        {status && !message && status.sources.some((s) => s.status === 'missing') && (
          <p className="text-sm text-muted-foreground">
            Gdy jakieś źródło nie odpowie, raport i tak powstanie — powie wprost, czego zabrakło.
          </p>
        )}
        {message && (
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link to="/">Wróć i spróbuj ponownie</Link>
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
