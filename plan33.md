# Plan implementacji 33 — RolnikSzukaWody (zespół GeoSatel)

Plan nadrzędny na ostatnią noc. **Zastępuje `plan2.md`** (otwarte kroki R, L2, L3, L5, L6 są tu wciągnięte albo wycięte)
i realizuje kolejkę z macierzy zgodności w `claude33.md`. Zasady nadrzędne, workflow, Definition of Done i hooki: `claude33.md`.
ID wymagań (T1, Q1–Q7, G1–G13, Z*, R*) są te same co w macierzy — używaj ich w commitach.

## 1. Ustalenia (odpowiedzi zespołu, 22.11.2026, ok. 01:30)

| Temat | Decyzja |
|---|---|
| Termin zgłoszenia | **11:00**; zamrożenie kodu **09:00** |
| Wykonanie | 1 tor, kroki po kolei |
| Kolejka | **P0 → G1 → G7 → G9 → G10 → sady (L2) → G11**, pełne wersje, **twarda linia cięcia** o 09:00 |
| Raport | G7 = przełącznik Podstawowy / Pełny (strona, PDF, druk) + poprawa tylko tekstów wytkniętych w uwagach + zalecenia „teraz” / „na sezon” |
| README (R1–R12), opis, prezentacja, film, przykładowe raporty | **robi zespół**; plan zawiera tylko listę kontrolną (rozdz. 6) |
| LICENSE (Z8) | właściciel praw → „GeoSatel” |
| Wycięte z plan2 | R1, R2, R6, L3 (termin siewu, sposób uprawy), L5 (suwak lat, wyszukiwarka), L6 (woda gruntowa, spływ od sąsiadów), G5, G8, G12, G13 → rozdz. 7 |

## 2. Harmonogram i linia cięcia

Start ok. 01:45. Do zamrożenia jest 7 h 15 min, a pełna kolejka to ok. 15 h pracy. **Do 09:00 realnie mieszczą się moduły
M0–M4 (P0, G1, G7, G9). M5–M7 (G10, sady, G11) wchodzą tylko wtedy, gdy wcześniejsze moduły skończą się przed czasem.**

| Moduł | Zakres | Budżet | Koniec najpóźniej |
|---|---|---|---|
| M0 | Odblokowanie pusha (T1, T2), LICENSE (Z8) | 0:15 | 02:00 |
| M1 | P0: błędy raportu Q1–Q7, T3, hydrologia (G3 w zakresie Q4) | 2:30 | 04:30 |
| M2 | G1 progi KBW IUNG-PIB | 1:00 | 05:30 |
| M3 | G7 raport Podstawowy / Pełny + teksty + zalecenia teraz / na sezon | 1:45 | 07:15 |
| M4 | G9 synteza metod retencji | 1:30 | 08:45 |
| — | **09:00 zamrożenie kodu** → M8 | | |
| M5 | G10 technologia nawadniania i opłacalność | 3:00 | poniżej linii cięcia |
| M6 | Sady i krzewy owocowe (plan2 L2) | 2:00 | poniżej linii cięcia |
| M7 | G11 gospodarstwo / sąsiednie działki | 3:30 | poniżej linii cięcia |
| M8 | Ostatnie wdrożenie, E2E na VPS, macierz zgodności | 0:30 | 09:30 |
| M9 | Zgłoszenie (zespół) | 1:30 | 11:00 |

**Reguły twardej kolejki:**

1. Moduły idą w tej kolejności. Następny zaczyna się dopiero po bramce poprzedniego (rozdz. 3).
2. Gdy moduł przekracza swój „koniec najpóźniej”: kończymy bieżący krok, jeśli zostało mu ≤ 15 min; resztę kroków modułu
   przenosimy do rozdz. 7 i idziemy dalej. Wyjątek: M1 (P0) kończymy w całości, kosztem M4.
3. **O 08:30 nie zaczynamy żadnego nowego kroku**, który zmienia kontrakt API lub szablon PDF.
4. O 09:00 niedokończona zmiana jest cofana (`git stash` / `git checkout -- .`), a nie pushowana. `main` ma działać.
5. Krok z nowym źródłem lub liczbą z literatury ma limit 20 min na zdobycie źródła. Bez źródła nie wpisujemy liczby
   (zasada 1 i 6 z `claude33.md`) i krok spada do wariantu awaryjnego opisanego przy kroku.

## 3. Bramka po każdym kroku i module

- **Po kroku:** test dla zmiany (dla reguły: „odpala się” i „NIE”), `pytest` pojedynczego pliku, commit z ID wymagania, `git push origin main`
  (hook uruchamia pełne `pytest -q -x` i `tsc`).
- **Po module:** `ruff check . && mypy app`, `npm run lint && npx tsc --noEmit -p tsconfig.app.json`, raport na żywo dla 2 działek
  z `tests/e2e/parcels.yaml` (`heavy_soil` dla bieżącej daty i `slope` dla 2019-07-15) z czasem < 30 s, strona na szerokości
  komputera i telefonu + PDF, status w macierzy `claude33.md`, `deploy/deploy.sh root@129.121.162.156`.

## 4. Moduły i kroki (powyżej linii cięcia)

### M0. Odblokowanie (0:15)

- [ ] **M0.1 T1 — test z datą na sztywno.** `backend/tests/report/test_builder.py:142` oczekuje „Pobrano 21 listopada 2026”.
  Wstrzyknąć `fetched_at` z fixture (`tests/report/builders.py`) i wyliczać oczekiwany napis tym samym filtrem daty.
  **Gotowe, gdy:** `pytest tests/report/test_builder.py` przechodzi niezależnie od dnia uruchomienia; `git push` nie jest blokowany.
- [ ] **M0.2 T2 — `tsc`.** Sprawdzić, że hook i `claude33.md` używają `tsc --noEmit -p tsconfig.app.json`; poprawić `lint`/`build`
  w `frontend/package.json`, jeśli woła gołe `tsc --noEmit`.
- [ ] **M0.3 Z8 — LICENSE.** Właściciel praw „GeoSatel” zamiast osoby prywatnej.
- [ ] **M0.4** Commit `plan33.md`, w `claude33.md` wskazać `plan33.md` jako bieżącą kolejkę zamiast `plan2.md`.

### M1. P0 — błędy w raporcie (2:30)

Źródło: `Uwagi/uwagi krytyczne.docx`. Kolejność według ryzyka utraty punktów.

- [ ] **M1.1 Q1 — symulator 1–5 lat (0:40).** `analysis/simulate.py` (`_run`, `STRATEGIES`, `MULCH_EVAPORATION_CUT`),
  `analysis/water_plan.py` (`irrigated_balance`).
  - Najpierw test niezmiennika w `tests/analysis/test_outlook_modules.py`: dla każdego roku i każdej działki z fixture
    `stress(retention_rescue) ≤ stress(rescue) ≤ stress(none)` oraz `stress(retention) ≤ stress(none)`,
    a `woda(retention_rescue) ≤ woda(rescue)`.
  - Przyczyna do sprawdzenia: próg wyzwalania podlewania liczony od TAW powiększonego o SOC przesuwa moment podlania; ściółka
    nie wchodzi do bilansu, bo redukcja parowania jest przykładana do pojedynczego Kc w fazie pełnego pokrycia.
  - Naprawa: w strategii łączonej podlewanie wyzwala ten sam próg wyczerpania (mm poniżej RAW bazowej gleby) co w „rescue”;
    redukcja parowania ze ściółki działa na część glebową ETc (udział zależny od pokrycia pola przez uprawę), jawnie jako szacunek.
  - Gdy po naprawie „retention” nadal równa się „none” co do dnia, raport pokazuje także zaoszczędzone mm i m³, nie same dni.
  **Gotowe, gdy:** test niezmiennika przechodzi; tabela w raporcie dla `heavy_soil` nie ma wiersza gorszego po dołożeniu działania.
- [ ] **M1.2 Q2 + T3 — jedna dawka ratunkowa (0:20).** Jedna funkcja licząca „podlewanie ratunkowe w roku suchym” (w `water_plan.py`),
  używana przez `report/outlook.py`, `blocks/water_plan.j2`, `blocks/simulation.j2` i `recommendations/irrigation.py`. Jedno
  zaokrąglenie dawki (filtr w `report/texts.py`), także dla „2 × 21 mm” wobec „2 dawki po 20 mm”.
  **Gotowe, gdy:** test w `tests/report/test_outlook_blocks.py`: w wyrenderowanym raporcie każda wartość dawki ratunkowej jest identyczna.
- [ ] **M1.3 Q3 — fenologia i podpis satelity (0:25).** `analysis/assessment.py` (faza uprawy), `blocks/satellite.j2`, `sections/current.j2`,
  `analysis/texts_pl.py`. Osobne komunikaty: „przed siewem / wschody”, „dojrzewanie / żniwa”, „po zbiorze”. Podpis wykresu opisuje
  faktyczne punkty: datę ostatniej czystej sceny i jej położenie względem pasma z 10 lat.
  **Gotowe, gdy:** test: żyto 22.07 → tekst o dojrzewaniu / żniwach, bez „nie zakryło jeszcze pola”; kukurydza 15.04 → „przed wschodami”;
  podpis zawiera datę sceny z danych.
- [ ] **M1.4 Q4 + G3 — hydrologia odporna na awarię Overpass (0:30).** `sources/hydro.py`: trzeci mirror w `SERVERS`, rotacja kolejności,
  `TIMEOUT_S` 12 → 7 s, jedna ponowna próba w ramach `BUDGET_S`. `analysis/context.py` + `recommendations/retention.py`: gdy hydro ma
  status `missing`, zadrzewienia, wody i mokradła w buforze 500 m liczymy z już pobranego WorldCover (klasy 10, 80, 90;
  `sources/landcover.py` zwraca udziały w buforze). Status bloku `degraded`, a `missing/hydro.j2` mówi wprost: „brak danych tylko o rowach”.
  **Gotowe, gdy:** test z hydro `missing` i landcover `ok`: reguły zadrzewień i ochrony mokradeł działają, tekst wymienia tylko rowy;
  test `missing` + `missing` zostaje jak dziś; czas na zimno bez wzrostu.
  Pełny fallback MPHP / BDOT10k WFS → rozdz. 7.
- [ ] **M1.5 Q5 — kafelek trendu (0:15).** `report/outlook.py`, `frontend/src/components/report/SummaryTiles.tsx`. Werdykt „pogarsza się /
  bez zmian / poprawia się” i liczba pod nim pochodzą z tej samej miary (dni stresu wodnego, w drugiej kolejności dni upalne).
  Temperatura sezonu tylko w szczegółach. Dopisek „na dekadę” wyłącznie, gdy trend jest istotny w `analysis/trends.py`; inaczej
  porównanie „ostatnie 2 lata wobec 10 lat” bez ekstrapolacji (uwaga K5).
  **Gotowe, gdy:** test: werdykt „pogarsza się” nigdy nie stoi obok miary o przeciwnym znaku.
- [ ] **M1.6 Q6 — zagłębienie a glina i podtopienia (0:20).** `recommendations/retention.py` (`_depression_*`), `recommendations/texts_pl.py`.
  Gdy gleba ciężka **lub** ISOK / PIG-PIB wskazuje zagrożenie podtopieniami: wariant „kontrolowany staw lub zastawka z odpływem;
  niekontrolowane rozlewisko grozi wymakaniem ozimin”, z dowodami (kategoria gleby, źródło zagrożenia).
  **Gotowe, gdy:** testy wariantów: glina + podtopienia → tekst kontrolowany; piasek bez zagrożenia → dotychczasowy.
- [ ] **M1.7 Q7 — PDF (0:30, pierwszy kandydat do cięcia w M1: podkład mapy).**
  - `report/builder.py`: „pow. powiat” → jedna forma; w PDF lista dowodów bez ucinania („… i 1 inna wartość”).
  - `report/map_svg.py` + `blocks/profile.j2`: jedna definicja „główne zagłębienie w granicach działki” (ten sam filtr
    `DEPRESSION_MIN_INSIDE_SHARE` dla tekstu, przekroju i mapy), pozostałe plamy opisane w legendzie jako „poza działką”.
  - Podkład ortofoto: WMS GetMap Geoportalu po stronie serwera dla bbox działki, timeout 5 s, obraz osadzony w SVG; przy braku
    odpowiedzi mapa jak dziś + jawna uwaga. Nowe źródło do `docs/DATA_SOURCES.md` (URL, licencja, „na żywo”).
  **Gotowe, gdy:** PDF dla `heavy_soil` ma mapę z podkładem, zgodną liczbę zagłębień w 3 miejscach i komplet dowodów; `tests/report/test_pdf.py` przechodzi.
- [ ] **W1 — bramka modułu.** Punkt kontrolny **04:30**.

### M2. G1 — oficjalne progi KBW IUNG-PIB (1:00)

- [ ] **M2.1 Tabela progów (limit 20 min na źródło).** `crops/iung_thresholds.yaml`: wartości krytyczne KBW dla upraw z katalogu,
  kategorii gleby I–IV i okresów 60-dniowych, **przepisane z publikacji** (system monitoringu suszy rolniczej IUNG-PIB /
  Doroszewski i in. 2012) z pełnym cytatem, URL i datą dostępu w polu `source`. Nigdy z pamięci.
  **Wariant awaryjny (brak tabeli w 20 min):** robimy tylko M2.2, raport podaje kategorię gleby IUNG i mówi wprost, że werdykt
  opiera się na percentylu z 10 lat; G1 zostaje ⚠️.
- [ ] **M2.2 Mapowanie gleby na kategorię I–IV.** `analysis/soil.py`: funkcja czysta z uziarnienia SoilGrids (grupy granulometryczne
  wg metodyki IUNG), źródło w komentarzu; pewność „średnia” (SoilGrids 250 m).
  **Gotowe, gdy:** test na 4 glebach wzorcowych (piasek luźny, piasek gliniasty, glina lekka, glina ciężka / ił).
- [ ] **M2.3 Użycie w ocenie.** `crops/iung.py` (`iung_threshold`), `analysis/assessment.py`: KBW 60-dniowy porównany z progiem jako
  dodatkowy sygnał werdyktu; uprawa bez progu w tabeli → bez sygnału, jawnie. `sections/current.j2`, `limitations.j2`: usunąć
  „nie użyto oficjalnych progów” tam, gdzie próg jest.
  **Gotowe, gdy:** test „poniżej progu → susza rolnicza wg IUNG”, „powyżej → brak”, „brak progu → komunikat”; `docs/METHODOLOGY.md` uzupełnione.
- [ ] **W2 — bramka modułu** + świadome przepisanie `tests/e2e/baseline.json` (ocena może się zmienić). Punkt kontrolny **05:30**.

### M3. G7 — raport Podstawowy / Pełny (1:45)

- [ ] **M3.1 Wariant w kontrakcie (0:20).** `report/models.py`: każda sekcja i blok ma `tier: basic | full`. `api/routes.py`:
  `/reports/{id}.pdf?variant=basic|full` (domyślnie `basic`). `frontend/src/api/types.ts` zsynchronizowane.
- [ ] **M3.2 Podstawowy = 1–2 strony (0:40).** `ReportPage.tsx`, `SummaryTiles.tsx`, `report.html.j2`, `report.css`. Zawartość:
  nagłówek działki, kafelki KPI w kolorach (zapas wody z progiem stresu, bilans 60 dni, ryzyko podtopień, trend, najważniejszy ruch),
  po jednym zdaniu-werdykcie na sekcję, zalecenia, alerty i jawne braki danych, ograniczenia jako kafel, źródła w stopce.
  Pełny = Podstawowy + obecne szczegóły, bez powtarzania danych działki.
  **Gotowe, gdy:** PDF Podstawowy dla `heavy_soil` ma ≤ 2 strony i zawiera źródła, ograniczenia i braki (wymóg 3.3 pkt 5).
- [ ] **M3.3 Przełącznik (0:15).** Jeden przełącznik nad raportem; wybór zapisany w URL (`?variant=`), sterujący przyciskiem PDF i drukiem
  (`@media print`). Klasyczny spis treści w wariancie Pełnym (uwaga O: „spis treści klasycznie”).
  **Gotowe, gdy:** przełączenie zmienia stronę, PDF i wydruk; działa na telefonie.
- [ ] **M3.4 Teksty wytknięte w uwagach (0:20).** Tylko te miejsca (`sections/current.j2`, `causes.j2`, `vulnerability.j2`, `headline.j2`):
  - bez powtórzenia danych działki; zdanie zaczyna się „Na dzień DD.MM.YYYY…”;
  - liczba zawsze z oceną („mało / w normie / dużo”) i tendencją („zapas maleje, wystarczy na ok. X dni”);
  - opady: „94 mm (o 18 mm więcej niż zwykle)”;
  - satelita: „dobra / słabsza niż zwykle o X%” + data zdjęcia, zamiast „typowa”;
  - brak zagrożenia = jedno zdanie;
  - pojemność gleby (mm/m) oddzielona od małego zapasu przy płytkich korzeniach (sprzeczność sekcji 3 i 4).
  **Gotowe, gdy:** `tests/report/test_texts.py` zaktualizowany; w tekście głównym nie ma „typowa” ani zdania o nieużyciu progów IUNG.
- [ ] **M3.5 R5 — zalecenia „teraz” i „przed następnym sezonem” (0:10).** `recommendations/models.py`: `Recommendation.horizon: now | season`
  ustawiany przez regułę z daty analizy i fazy uprawy; dwie listy w raporcie. Zalecenie siewne w lipcu tylko jako międzyplon, nazwane wprost.
  **Gotowe, gdy:** test: 22.07 → żadna rada o siewie uprawy głównej na liście „teraz”.
- [ ] **W3 — bramka modułu.** Punkt kontrolny **07:15**.

### M4. G9 — synteza metod retencji (1:30)

- [ ] **M4.1 Progi prawne (limit 15 min).** Sprawdzić w ISAP aktualne brzmienie Prawa wodnego (staw ≤ 5000 m² i głębokość ≤ 3 m na
  zgłoszenie; zwykłe korzystanie z wód ≤ 5 m³/dobę). Artykuł, URL i data dostępu do `docs/METHODOLOGY.md` i stałych w kodzie.
  **Wariant awaryjny:** bez liczb — tekst „sprawdź w Wodach Polskich, czy wystarczy zgłoszenie”.
- [ ] **M4.2 Karta „% pokrycia potrzeb” (0:25).** `analysis/retention_balance.py` (nowy, czysty): objętość głównego zagłębienia
  (`analysis/terrain.py`) wobec potrzeb nawadniania w roku suchym — pełnego i ratunkowego (ta sama funkcja co w M1.2), w m³ i %.
  Brak zagłębienia lub NMT `missing` → karta mówi to wprost, bez zera udającego pomiar.
  **Gotowe, gdy:** test na liczbach z uwag (2320 m³ wobec 12 090 m³ → ok. 19%).
- [ ] **M4.3 Reguły 5 metod (0:35).** `recommendations/retention_methods.py` (nowy) + `texts_pl.py`. Każda metoda dostaje status
  `recommended | conditional | not_recommended`, jedno zdanie uzasadnienia z dowodami liczbowymi i wymóg formalny:
  1. oczko / staw w zagłębieniu — zagłębienie > 200 m³; gleba ciężka = naturalne uszczelnienie, lekka = „wymaga uszczelnienia”;
     flaga powierzchni lustra ponad próg z M4.1; spięcie z Q6 (podtopienia);
  2. zastawka / drenaż kontrolowany — rów lub ciek < 150 m **albo** spadek < 2% i zagrożenie podtopieniami;
  3. deszczówka z dachów — zabudowa w 100 m (WorldCover klasa 50); przy potrzebach liczonych w tysiącach m³ „niezalecane jako główne źródło”;
  4. studnia — luka między retencją a potrzebami; głębokość zwierciadła z PIG-PIB (z odległością stacji), ostrzeżenie o pozwoleniu;
  5. pasy zadrzewień — niski udział drzew w buforze 500 m + miejsce odpływu z działki.
  **Gotowe, gdy:** każda metoda ma test „polecane” i „niezalecane”; źródło `missing` → metoda ze statusem „brak danych”, nie „niezalecane”.
- [ ] **M4.4 Raport i UI (0:20).** `sections/retention.j2`, `frontend/src/components/report/RetentionMethods.tsx` (nowy), `types.ts`.
  Tabela z kolorowym statusem; w Podstawowym tylko metody polecane + karta pokrycia, w Pełnym cała tabela.
  **Gotowe, gdy:** tabela czytelna na 375 px i w PDF.
- [ ] **W4 — bramka modułu.** Punkt kontrolny **08:45**.

## 5. Moduły poniżej linii cięcia (tylko gdy M0–M4 skończą się przed czasem)

### M5. G10 — technologia nawadniania i opłacalność (3:00)

- [ ] **M5.1 Kształt działki.** `analysis/parcel_shape.py` (nowy, czysty): długość, szerokość i zwartość z `minimum_rotated_rectangle`
  geometrii ULDK w EPSG:2180. Test na pasie 950 × 80 m i kwadracie.
- [ ] **M5.2 Dobór technologii.** `recommendations/irrigation_tech.py` (nowy): deszczownia obrotowa / szpulowa / kroplowe i mikrozraszacze /
  bez stałej instalacji — reguły z areału, szerokości i rodzaju uprawy; progi ze źródłem w komentarzu (limit 20 min; bez źródła progi
  jako jawne założenie w raporcie). Sprawność metody wchodzi do dawki brutto zamiast stałych 75%.
- [ ] **M5.3 Opłacalność.** `analysis/economics.py` (nowy) + `crops/economics.yaml`: przychód z ha, koszt instalacji i koszt wody jako
  **widełki z nazwanym źródłem (GUS, CDR) i datą**, częstość lat z niedoborem w fazie krytycznej z `analysis/history.py`.
  Werdykt: „opłacalne / na granicy / nieopłacalne” + próg areału, od którego się opłaca. Bez kwot co do złotówki.
- [ ] **M5.4 UI.** `sections/irrigation.j2`, `frontend/src/components/report/IrrigationEconomics.tsx`: werdykt + edytowalne założenia
  (przeliczenie w przeglądarce); PDF pokazuje wartości domyślne z dopiskiem „założenia”.
  **Gotowe, gdy:** żyto 7,6 ha → „nieopłacalne” z uzasadnieniem; ziemniaki na tym samym polu → inny werdykt; testy obu.

### M6. Sady i krzewy owocowe (2:00) → `plan2.md` L2.1–L2.5 bez zmian

- [ ] **M6.1** `crops/catalog.py`, `catalog.yaml`: `kind: arable | grassland | fruit` + 4 uprawy (Kc FAO-56 tab. 12, daty okresów
  krytycznych zweryfikowane z publikacją przed commitem).
- [ ] **M6.2** `recommendations/common.py` `is_fruit`; wyłączenie 5 reguł polowych dla sadów; wariant `organic_matter` dla sadu.
- [ ] **M6.3** Reguła `orchard_mulch_sward` (testy „odpala się” i „NIE”).
- [ ] **M6.4** `irrigation.py`, `texts_pl.py`: teksty spoczynku i późnej fazy dla sadu; uwaga o nawadnianiu kroplowym.
- [ ] **M6.5** `assessment.py`, `builder.py`: drzewa w WorldCover nie wywołują ostrzeżenia dla sadu; działka `orchard` w `parcels.yaml` → `orchard_pome`.
  **Minimum, jeśli zaczynamy:** M6.1 + M6.2 razem (bez M6.2 sady dostają błędne rady o orce i międzyplonie).

### M7. G11 — gospodarstwo / sąsiednie działki (3:30)

- [x] **M7.1 Kontrakt.** `api/schemas.py`: `AnalysisRequest.extra_parcel_ids: list[str]` (maks. 5, walidacja formatu i odległości ≤ 2 km);
  domyślnie pusta lista, czyli przepływ jury bez zmian i < 30 s.
- [x] **M7.2 Backend.** `api/jobs.py`: dodatkowe geometrie z ULDK równolegle; pogoda, wody gruntowe i satelita tylko dla działki głównej.
  Suma areału wchodzi do potrzeb wody (m³), karty pokrycia (M4.2), progów prawnych i opłacalności (M5.3, jeśli jest).
- [x] **M7.3 UI.** `StartPage.tsx`, `ParcelPickerMap.tsx`: „+ Dodaj działkę” (ID lub klik), lista z usuwaniem; raport pokazuje
  „gospodarstwo: N działek, X ha” i mówi wprost, które wyniki dotyczą działki głównej, a które sumy.
- [ ] **M7.4** Wspólny NMT dla stykających się działek (zagłębienie na granicy) — tylko po M7.1–M7.3.
  **Gotowe, gdy:** 1 działka = wynik identyczny jak przed zmianą (test regresji); 3 działki < 30 s; PDF pokazuje sumę areału.

## 6. Zamrożenie i zgłoszenie

### M8. Po 09:00 (Claude, 0:30)

- [x] **M8.1** `git status` czysty, pełne `pytest`, `ruff`, `mypy`, `tsc`, `npm run build`.
- [x] **M8.2** `deploy/deploy.sh root@129.121.162.156`, potem `deploy/e2e-vps.sh`; publiczny adres sprawdzony dla działki i daty spoza cache.
- [x] **M8.3** Macierz zgodności w `claude33.md`: statusy i data; lista tego, co nie weszło, przekazana zespołowi do „znanych ograniczeń” w README.
- [ ] **M8.4** Po wdrożeniu żadnych zmian w kodzie poza poprawką błędu blokującego demo.
- [x] **M8.5 Nowy wygląd wg `../UI/`.** Przebudowa UI na wzór 3 makiet z folderu `UI/` (`*.webp`) + wstawienie logo zespołu
  (nagłówek strony, favicon, nagłówek PDF). **Plik logo trzeba dołączyć** — nie ma go jeszcze w repo ani w `UI/`.
- [x] **M8.6 Poprawka mapy: ciek oznaczony jako strefa powodziowa.** Linia wodna (ciek / rów) na mapie raportu wygląda
  lub jest opisana jak strefa zagrożenia powodziowego ISOK — rozdzielić warstwy, kolory i legendę
  (`frontend/src/components/map/ReportMapView.tsx`, mapa w PDF).
- [x] **M8.7 Wyszukiwanie działki po adresie** (zgodnie z wymaganiami z treści zadania): adres → współrzędne → działka z ULDK
  (`StartPage.tsx`, `ParcelPickerMap.tsx`, endpoint w backendzie). Nie mylić z G12 (gmina / obręb, rozdz. 7).
- [x] **M8.8 „Najważniejsze wnioski” → „Podsumowanie”** w obu wersjach raportu (Podstawowy i Pełny), na stronie i w PDF:
  `BasicReport.tsx:52`, `report_basic.html.j2:44`, podpowiedź w `ReportPage.tsx:131`, odpowiedniki w raporcie pełnym.
- [x] **M8.9 Suwak ładniejszy i płynniejszy** (`frontend/src/components/report/Simulator.tsx`): wygląd zgodny z nowym UI,
  płynne przesuwanie bez szarpania (przeliczenie z opóźnieniem / po puszczeniu, bez przerysowania całego raportu).

- [x] **M8.10 Zaznaczanie kilku działek naraz** (zrobione w M7) (klik na mapie i ID) — zakres i kroki jak w **M7.1–M7.3** (G11); robić tamte kroki,
  nie duplikować. Przeniesione tu jako obowiązkowe po 09:00, jeśli M7 nie weszło przed zamrożeniem.

- [x] **M8.11 Zmiany zespołu (22.11, 07:00):** nazwa „RolnikSzukaWody” usunięta (nagłówek: samo logo, w tekstach „GeoSatel”,
  także w zapisanych raportach); symulator 1–5 lat ukryty na stronie i w PDF (kod zostaje, `pdf.SHOW_SIMULATION`);
  wykres sytuacji wodnej z przełącznikiem „Dane z ostatnich: 24 h / 7 dni / miesiąc / 6 miesięcy / rok / własny”
  (strona + PDF i druk, `report/chart_range.py` ↔ `chartRange.ts`).

  **Uwaga:** M8.5–M8.10 kłócą się z M8.4 (po wdrożeniu bez zmian w kodzie) — robić przed M8.1–M8.2, a po nich wdrożyć ponownie.

### M9. Lista kontrolna zespołu (do 11:00)

- [x] **README (wymóg formalny 4.2)** (22.11: README §1–12; zespół wpisuje koszt VPS i wynik T4): R1 uruchomienie (lokalnie, Docker, testy) · R2 funkcje · R3 architektura · R4 źródła i zakresy ·
  R5 dane na żywo / pobrane wcześniej z datami · R6 biblioteki, usługi i **narzędzia AI (Claude Code)** · R7 licencje danych i komponentów ·
  R8 znane ograniczenia · R9 weryfikacja wyników · R10 koszty (0 zł dla rolnika, koszt VPS) · R11 skalowalność · R12 bezpieczeństwo.
  Materiał źródłowy: `claude33.md`, `docs/DATA_SOURCES.md`, `docs/METHODOLOGY.md`, `backend/requirements.txt`, `frontend/package.json`.
- [x] **Z6** (22.11: 24 PDF + spis) przykładowe raporty PDF w `docs/sample-reports/` (działki z `parcels.yaml`, data bieżąca i 2019-07-15, oba warianty) — po M8.2.
- [ ] **Z2** (szkic: `docs/submission/opis.md`) opis: problem, funkcje, użycie danych, korzyści · **Z4** prezentacja PDF ≤ 10 slajdów (22.11: `docs/submission/GeoSatel-prezentacja.pdf`, 9 slajdów) · **Z5** film ≤ 3 min (22.11: `docs/submission/GeoSatel-film.mp4`, 2:00).
- [ ] **Z3** dostęp jury do prywatnego repo wg instrukcji Platformy · **Z7** link `https://129.121.162.156.sslip.io` w zgłoszeniu.
- [ ] **T4** szybki test w Chrome, Firefox, Edge, Operze i Safari (strona, PDF, druk) — ręcznie, w trakcie M5–M8.
- [ ] **Z9** (szkic: `docs/submission/demo.md`) scenariusz demo na finał: 1–3 działki, rozgrzany cache, zapasowe PDF-y z Z6.
- [ ] Zgłoszenie wysłane **najpóźniej 10:45**.

## 7. Wycięte — wpisać do „Znanych ograniczeń” w README i raporcie

| Co | Skąd | Dlaczego |
|---|---|---|
| Fallback hydrologii MPHP / BDOT10k WFS | G3 | zostaje mirror Overpass + WorldCover (M1.4) |
| Werdykt z 3 sygnałów, test Manna–Kendalla, przypisy numerowane | plan2 R1, R2, R6 | częściowo pokryte przez M1.5 i M3.4 |
| Termin siewu, sposób uprawy | plan2 L3 | zmiana kontraktu API bez wpływu na wymogi |
| Suwak lat, wyszukiwarka upraw, zakres dzień / tydzień / miesiąc | plan2 L5 | wygoda, nie wymóg |
| Płytka woda gruntowa, spływ od sąsiadów, kopalnie, śnieg | plan2 L4, L6 | nowe dane, ryzyko czasu |
| Trend wód gruntowych > 3 lat, IMGW hydro | G5 | — |
| 4 per mille w agrotechnice | G8 | reguła niskiego SOC zostaje |
| Wyszukiwanie po gminie i obrębie | G12 | opcjonalne |
| Kontrola krzyżowa z IUNG / EDO | G13 | częściowo zastępuje G1 |
| Wspólny NMT dla stykających się działek gospodarstwa; gleba, teren i satelita dla działek dodatkowych | G11, M7.4 | m³ i opłacalność liczone dla sumy areału, reszta z działki głównej (raport mówi to wprost) |
| Działki skrajne (bardzo małe, duże, wieloczęściowe) | T5 | ostrzeżenie o użytkowaniu jest; rozmiary nietestowane |

## 8. Ryzyka

| Ryzyko | Zabezpieczenie |
|---|---|
| Brak publikowanej tabeli progów IUNG w 20 min | wariant awaryjny M2.1; nie wpisujemy liczb z pamięci |
| Naprawa Q1 zmienia wyniki symulatora i baseline E2E | test niezmiennika przed zmianą; baseline przepisany świadomie w W1 |
| WMS ortofoto wolny lub niedostępny | timeout 5 s, mapa bez podkładu + jawna uwaga; krok jest pierwszy do cięcia w M1 |
| G7 psuje PDF tuż przed terminem | reguła 3 z rozdz. 2 (od 08:30 bez zmian szablonu PDF); wariant Pełny = obecny raport |
| Nowe źródło wydłuża analizę ponad 30 s | pomiar na zimno w bramce modułu; źródło z własnym timeoutem i statusem `missing` |
| Push zablokowany przez hook | naprawiamy przyczynę (M0.1), nie obchodzimy hooka |
