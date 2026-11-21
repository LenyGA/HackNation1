import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AnalysisPage } from '@/pages/AnalysisPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ReportPage } from '@/pages/ReportPage'
import { StartPage } from '@/pages/StartPage'

export const APP_TITLE = 'RolnikSzukaWody'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-dvh flex flex-col">
        <header className="border-b bg-card">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Link to="/" className="text-lg font-semibold text-primary">
              {APP_TITLE}
            </Link>
          </div>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
          <Routes>
            <Route path="/" element={<StartPage />} />
            <Route path="/analiza/:id" element={<AnalysisPage />} />
            <Route path="/raport/:id" element={<ReportPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
        <footer className="border-t text-xs text-muted-foreground">
          <div className="mx-auto max-w-3xl px-4 py-3">
            {APP_TITLE} · zespół GeoSatel · HackNation 2026
          </div>
        </footer>
      </div>
    </BrowserRouter>
  )
}
