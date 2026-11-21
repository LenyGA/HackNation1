# Wymagania zadania KOWR — skrót i checklista

Źródło: `docs/task/zadanie.pdf` (rozdz. 3–7), `docs/task/regulamin.pdf`. W razie rozbieżności rozstrzyga oryginał.

## Kryteria oceny (wagi)

| Kryterium | Waga | Co to znaczy dla nas |
|---|---|---|
| Wartość praktyczna dla rolnika | 25% | Konkretne, wykonalne działania na tej działce, a nie ogólniki |
| Wykorzystanie danych i wiarygodność rekomendacji | 25% | Łączenie źródeł, zgodność z nauką (FAO-56, IUNG, NWRM), uzasadnienie danymi, jawna niepewność |
| Innowacyjność i potencjał rozwojowy | 20% | Wartość dodana vs istniejące narzędzia, skalowanie, integracje |
| Prostota obsługi | 15% | Bez wiedzy GIS, czytelne na telefonie w polu |
| Działający prototyp i jakość techniczna | 15% | Dowolna działka i data, < 30 s, stabilność, bezpieczeństwo, dokumentacja, licencje |

Próg nagrody: ≥ 50% punktów i spełnienie wymagań formalnych.

## Jak jury testuje

- **Etap 1:** jurorzy uruchamiają prototyp dla tych samych działek z całej Polski (numer działki), dla daty bieżącej **lub historycznej
  z ostatnich 10 lat**, i porównują wynik z danymi referencyjnymi.
- **Etap 2 (finał, 3–5 zespołów):** pitch 2–3 min + do 2 min pytań, demo na żywo dla 1–3 działek i dat wskazanych przez jury.

## Obowiązkowy zakres prototypu (3.3)

- [ ] Uruchamia się w przeglądarce (Chrome, Firefox, Edge, Safari, Opera na Windows) bez instalowania czegokolwiek
- [ ] Wybór działki: numer ewidencyjny **lub** klik na mapie
- [ ] Wybór aktualnej uprawy
- [ ] Wybór daty analizy (dziś lub dowolna data z ostatnich 10 lat)
- [ ] Pobranie danych źródłowych i **obliczenie** oceny bieżącej oraz historycznej podatności (10 lat)
- [ ] Raport: stan niedoboru wody i jego przyczyny · rekomendacje retencyjne, agrotechniczne i nawodnieniowe (opcjonalnie) uzasadnione danymi ·
      data i źródła danych · ograniczenia (aktualność, dokładność, niepewność, czynniki nieuwzględnione) · jawne braki danych
- [ ] Zapis raportu w systemie **i/lub** PDF **i/lub** druk
- [ ] Wszystkie kategorie danych: meteo · satelita · gleba · hydrologia · przestrzenne (lokalizacja, użytkowanie, ukształtowanie terenu)
- [ ] (atut) działa na urządzeniach mobilnych

## Zgłoszenie (4.1)

- [ ] Nazwa zespołu i tytuł rozwiązania
- [ ] Zwięzły opis: problem · główne funkcje · sposób wykorzystania danych · korzyści dla użytkownika
- [ ] Link do **prywatnego** repozytorium + dostęp dla jury wg instrukcji z Platformy konkursowej
- [ ] README (patrz niżej)
- [ ] Prezentacja PDF, maks. **10 slajdów**
- [ ] Działający prototyp: link do działającej wersji lub instrukcja uruchomienia w README (**obowiązkowe**)
- [ ] Film do **3 minut** pokazujący działanie
- [ ] Przykładowe raporty wygenerowane przez prototyp (PDF w `docs/sample-reports/`)

## README musi zawierać (4.2)

- [ ] 1. Instrukcję uruchomienia
- [ ] 2. Opis podstawowych funkcjonalności
- [ ] 3. Skrócony opis architektury
- [ ] 4. Opis źródeł i zakresów danych
- [ ] 5. Które dane pobierane są na żywo, a które wcześniej (z datami pobrania). Wynik liczy aplikacja.
- [ ] 6. Wykaz bibliotek, komponentów, modeli, usług zewnętrznych i narzędzi AI (w tym AI użytego przy tworzeniu kodu)
- [ ] 7. Licencje i warunki korzystania z danych oraz komponentów
- [ ] 8. Znane ograniczenia techniczne
- [ ] 9. Sposób weryfikacji wyników i rekomendacji
- [ ] Skalowalność (5.5): limity i dostępność źródeł (cache, zapis wyników, ograniczanie zapytań), aktualizacja danych, wydajność
      przy większym ruchu, szacunkowe koszty infrastruktury
- [ ] Usługi płatne (5.4): wskazanie i koszty, jeśli jakiekolwiek wystąpią (cel: brak)
- [ ] Bezpieczeństwo (5.6): podstawowe zabezpieczenia, brak zbierania danych osobowych

## Ograniczenia formalne

- Dane muszą być **bezpłatne i legalnie dostępne**, z udokumentowanym pochodzeniem i licencją.
- Rolnik nie może potrzebować: płatnej licencji, specjalistycznego sprzętu, znajomości GIS, programowania, przetwarzania danych
  przestrzennych ani instalacji oprogramowania.
- Rozwiązanie powstaje w trakcie wydarzenia. Komponenty open source są dozwolone, o ile ich licencje pozwalają KOWR przejąć
  autorskie prawa majątkowe (§ 2 ust. 10, § 5 regulaminu).
- Repozytorium pozostaje niepubliczne co najmniej do końca wydarzenia.
