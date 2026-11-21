import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function StartPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sprawdź swoją działkę</CardTitle>
        <CardDescription>
          Podaj numer działki lub wskaż ją na mapie, wybierz uprawę i datę. Policzymy, jak wygląda sytuacja wodna
          na polu i co możesz zrobić, żeby zatrzymać wodę.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">Formularz w budowie.</CardContent>
    </Card>
  )
}
