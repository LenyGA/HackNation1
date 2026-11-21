import { useParams } from 'react-router-dom'

export function AnalysisPage() {
  const { id } = useParams()
  return <p className="text-muted-foreground">Analiza {id} — ekran postępu w budowie.</p>
}
