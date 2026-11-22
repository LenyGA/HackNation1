# Scenariusz demo na finał (Z9)

Pitch 2–3 min + do 2 min pytań, demo na żywo dla 1–3 działek i dat wskazanych przez jury.

## Przed wejściem (ok. 15 min wcześniej)

1. Otworzyć https://129.121.162.156.sslip.io na laptopie i telefonie; sprawdzić `https://129.121.162.156.sslip.io/api/health`.
2. Rozgrzać cache: raz przepuścić przez aplikację działkę i datę pokazową (np. `302111_4.0001.468/1`, żyto, 15.07.2019).
   `scripts/warm_cache.py` rozgrzewa tylko 2 inne działki referencyjne, więc nie wystarczy.
3. Otworzyć w kartach zapasowe PDF-y z `docs/sample-reports/` (gdyby sieć na sali padła).
4. **Nie** uruchamiać `deploy/e2e-vps.sh` przed demo: zużywa dzienny limit Open-Meteo dla adresu serwera.

## Przebieg (ok. 2 min)

| Czas | Co pokazujemy | Co mówimy |
|---|---|---|
| 0:00 | Strona startowa | „Rolnik podaje numer działki, klika ją na mapie albo wpisuje adres.” |
| 0:15 | Numer działki od jury (albo `302111_4.0001.468/1`, żyto, 15.07.2019), uprawa, data | „Data to parametr: dowolny dzień z 10 lat, bez danych z przyszłości.” |
| 0:25 | Ekran postępu ze statusami źródeł | „9 publicznych źródeł, 8 z nich równolegle; gdy któreś nie odpowie, raport powie to wprost.” |
| 0:45 | Raport Podstawowy: Podsumowanie | Werdykt, zapas wody w glebie (X z Y mm) i próg stresu, próg IUNG-PIB, podatność 10 lat. |
| 1:05 | Przyczyny i retencja | Dowody liczbowe; metody POLECANE / NIEZALECANE z powodem; „ile wody da retencja”. |
| 1:25 | Wykres wody i nawadnianie | Przyciski „Dane z ostatnich” (7 dni → rok); termin, dawka, technologia, opłacalność. |
| 1:45 | Przełącznik Pełny, Źródła i Ograniczenia, PDF | „Każda liczba ma źródło i datę; bez LLM, ten sam wynik za każdym razem.” |

## Gdy coś pójdzie nie tak

- **ULDK ogranicza adres** („chwilowo nie odpowiada”, także przy kliknięciu na mapie): ograniczenie trwa kilka minut; w tym
  czasie pokazać gotowy raport ze stałego linku (`/raport/<ID>` z `docs/sample-reports/README.md`) albo PDF.
- **Brak sieci / serwer nie odpowiada:** pokazać PDF z `docs/sample-reports/` dla podobnej działki i daty.
- **Źródło `missing` (np. hydrologia, Overpass):** to zamierzone zachowanie; pokazać, że raport mówi o tym wprost
  i obniża pewność.

## Pytania, których możemy się spodziewać

- *Skąd progi suszy?* Z rozporządzenia Dz.U. 2019 poz. 739 (metodyka IUNG-PIB), sprawdzone z ekspertyzą IUNG-PIB 2019.
- *Czemu wynik różni się od mapy IUNG?* Liczymy ET0 metodą FAO-56 z modelu pogody, a nie wzorem IUNG ze stacji (opisane
  w ograniczeniach).
- *Ile to kosztuje?* Rolnik: 0 zł. Prototyp: 1 VPS. Produkcyjnie: licencja komercyjna Open-Meteo albo własna instancja.
- *Czy używacie AI?* Nie w aplikacji: raport powstaje z reguł i szablonów. Claude Code był narzędziem przy pisaniu kodu.
