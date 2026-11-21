import { Loader2 } from 'lucide-react'
import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const APP_TITLE = 'RolnikSzukaWody'

// Pages load on demand: the map library is large, and a phone in the field should see the first screen fast.
const StartPage = lazy(() => import('@/pages/StartPage').then((m) => ({ default: m.StartPage })))
const AnalysisPage = lazy(() => import('@/pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })))
const ReportPage = lazy(() => import('@/pages/ReportPage').then((m) => ({ default: m.ReportPage })))

/** A new page starts at the top (the router keeps the scroll position otherwise). */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    if (!window.location.hash) window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function PageLoading() {
  return (
    <p className="flex items-center gap-2 text-muted-foreground">
      <Loader2 className="size-4 animate-spin" /> Wczytuję…
    </p>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="flex min-h-dvh flex-col">
        <header className="border-b bg-card">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Link to="/" className="text-lg font-semibold text-primary">
              {APP_TITLE}
            </Link>
          </div>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-3 py-5 sm:px-4 sm:py-6">
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<StartPage />} />
              <Route path="/analiza/:id" element={<AnalysisPage />} />
              <Route path="/raport/:id" element={<ReportPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </main>
        <footer className="border-t text-xs text-muted-foreground">
          <div className="mx-auto max-w-3xl px-4 py-3">
            {APP_TITLE} · zespół GeoSatel · HackNation 2026 · dane: GUGiK, Copernicus, Open-Meteo, ISRIC, OpenStreetMap
          </div>
        </footer>
      </div>
    </BrowserRouter>
  )
}
