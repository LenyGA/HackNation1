import { useParams } from 'react-router-dom'

export function ReportPage() {
  const { id } = useParams()
  return <p className="text-muted-foreground">Raport {id} — w budowie.</p>
}
