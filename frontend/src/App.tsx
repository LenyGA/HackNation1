import { Loader2 } from 'lucide-react'
import { lazy, type ReactNode, Suspense, useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const APP_TITLE = 'RolnikSzukaWody'
export const TEAM = 'GeoSatel'

// Pages load on demand: the map library is large, and a phone in the field should see the first screen fast.
const StartPage = lazy(() => import('@/pages/StartPage').then((m) => ({ default: m.StartPage })))
const AnalysisPage = lazy(() => import('@/pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })))
const ReportPage = lazy(() => import('@/pages/ReportPage').then((m) => ({ default: m.ReportPage })))

const DATA_SOURCES = ['GUGiK', 'Copernicus Sentinel-2', 'Open-Meteo', 'SoilGrids', 'Wody Polskie', 'PIG-PIB', 'OpenStreetMap']

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
    <p className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-8 text-muted-foreground">
      <Loader2 className="size-4 animate-spin" /> Wczytuję…
    </p>
  )
}

/** Inner pages (progress, report) keep a narrow reading column; the start page lays out its own width. */
function Narrow({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-3xl px-3 py-5 sm:px-4 sm:py-6">{children}</div>
}

function Header() {
  const { pathname } = useLocation()
  const onStart = pathname === '/'
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/85 print:hidden">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-3 py-2 sm:px-5">
        <Link to="/" className="flex min-w-0 items-center gap-3" aria-label={`${APP_TITLE} — strona główna`}>
          <img src="/logo.png" alt={TEAM} width={132} height={44} className="h-8 w-auto sm:h-10" />
          <span className="hidden h-7 w-px bg-border sm:block" aria-hidden />
          <span className="truncate text-base font-bold tracking-tight text-navy sm:text-lg">{APP_TITLE}</span>
        </Link>
        <nav className="ml-auto flex items-center gap-1 sm:gap-2" aria-label="Menu">
          {onStart && (
            <a href="#jak-to-dziala" className="hidden rounded-md px-3 py-2 text-sm font-medium text-navy hover:bg-muted md:block">
              Jak to działa
            </a>
          )}
          <Button asChild variant={onStart ? 'navy' : 'default'} className="h-10 px-4">
            {onStart ? (
              <a href="#start">
                Sprawdź<span className="hidden sm:inline"> działkę</span>
              </a>
            ) : (
              <Link to="/">
                Nowa<span className="hidden sm:inline"> analiza</span>
              </Link>
            )}
          </Button>
        </nav>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="mt-6 border-t border-border/70 bg-card/60 print:hidden">
      <div className="mx-auto max-w-6xl space-y-2 px-4 py-5 text-center">
        <p className="text-sm font-medium text-navy/80">
          Dane publiczne: {DATA_SOURCES.join(' · ')}
        </p>
        <p className="text-xs text-muted-foreground">
          {APP_TITLE} · zespół {TEAM} © 2026 · HackNation 2026 · bez logowania, bez opłat, bez danych osobowych
        </p>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="bg-contours flex min-h-dvh flex-col">
        <Header />
        <main className="w-full flex-1">
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<StartPage />} />
              <Route
                path="/analiza/:id"
                element={
                  <Narrow>
                    <AnalysisPage />
                  </Narrow>
                }
              />
              <Route
                path="/raport/:id"
                element={
                  <Narrow>
                    <ReportPage />
                  </Narrow>
                }
              />
              <Route
                path="*"
                element={
                  <Narrow>
                    <NotFoundPage />
                  </Narrow>
                }
              />
            </Routes>
          </Suspense>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  )
}
