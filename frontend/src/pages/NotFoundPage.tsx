import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <p>
      Nie ma takiej strony.{' '}
      <Link className="text-primary underline" to="/">
        Wróć na start
      </Link>
    </p>
  )
}
