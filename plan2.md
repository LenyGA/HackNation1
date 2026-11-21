# Plan implementacji 2 — RolnikSzukaWody (runda zmian z `lista2.md` i uwag z `Uwagi/`)

Zespół **GeoSatel**, HackNation 2026. Ten plan zamienia `lista2.md` w jedną kolejkę kroków do wykonania po kolei.
Zasady nadrzędne, stack i konwencje: `CLAUDE.md`. Uzasadnienia merytoryczne i tabele wartości: `lista2.md` (ten plan ich nie powtarza,
tylko wskazuje krok, np. „→ lista2 L2.1”). Dokumentacja zgłoszeniowa (M10) zostaje w `plan.md`.

## 1. Ustalenia do tego planu (odpowiedzi zespołu, 21.11.2026 wieczorem)

| Temat | Decyzja |
|---|---|
| Czas do zamrożenia funkcji | 12 h lub więcej → **cały zakres L1–L6 jest obowiązkowy**, cięcie tylko awaryjnie (rozdz. 6) |
| Tryb pracy | **jedna kolejka**: jedna sesja, krok po kroku, każdy krok = commit + `git push origin main` |
| Zaległe kroki z `plan.md` | do tego planu wchodzą tylko **wdrożenie (M8.1)** i **testy (M9)**; M7.5 i M10 zostają w `plan.md` |
| Niecommitowane zmiany w katalogu upraw | **cofamy** (`git checkout`), L2.1 robi katalog od nowa |
| Granica Polski (L1.4) | obrys **PRG GUGiK**, własna funkcja punkt-w-wielokącie, alert **i maska** terenu poza Polską |
| Suwak lat (L5.1) | obejmuje **wykres sezonu, wykres satelity i mapę ciepła stresu** |
| Wdrożenie | **po każdym module L** `deploy/deploy.sh` + sprawdzenie publicznego adresu |
| Działki referencyjne | wybieramy sami: 5 działek rolnych z różnych regionów + 1 sad |
| Mapa w raporcie (L1.3) | tylko przycisk „Pełny ekran”, wysokość bez zmian (wartość domyślna z `lista2.md`) |
| L7.1 (sposób uprawy w bilansie) | poza planem, zostaje „na później” |
| Uwagi `krotkie uwagi.docx` (K1–K7) i `Uwagi ogólne.docx` (O1–O31), 21.11.2026 ok. 23:00 | nowy moduł **R — przebudowa raportu** zaraz po L1; tabela uwag i rozwiązań w rozdz. 7 |
| Raport (O2) | **Podstawowy + Pełny**: przełącznik na stronie i przy PDF/druku; podstawowy 1–2 strony, ale ze źródłami, ograniczeniami i brakami danych (wymóg regulaminu) |
| Ocena „brak niedoboru” przy suchym polu (K1) | **werdykt z 3 sygnałów** (zapas w glebie, bilans 60 dni na tle 10 lat, bilans sezonu) + tendencja „wystarczy na ok. X dni”; wyniki bazowe E2E przepisujemy |
| Sposób nawadniania (K2) | **pole w formularzu** (deszczownia / kroplowe / mikrozraszacze), robione w L2.4 i L3.3 |
| Cięcie zakresu na rzecz R | **L4 w całości i L6.2 wypadają** (do „Ograniczeń analizy” i do `lista2` L7 „na później”) |

## 2. Kolejność i czas

Czas liczony od startu prac nad tym planem (T). Szacunki zakładają pracę z Claude Code.

| Nr | Moduł | Czas | Koniec | Zmiana kontraktu API |
|---|---|---|---|---|
| K0 | Start: porządek, wdrożenie bazowe, działki referencyjne | 0,75 h | T+0,75 | — |
| L1 | Widoczne w demo: osie, daty, mapa, granica Polski | 2,25 h | T+3 | — |
| L2 | Sady i krzewy owocowe | 1,75 h | T+4,75 | `CropOut.kind` |
| R | Przebudowa raportu: werdykt, Podstawowy/Pełny, krótkie teksty, trendy | 5,5 h | T+8,5 | `Report` (werdykt, `horizon` zaleceń, źródła numerowane), parametr wersji PDF |
| L2 | Sady i krzewy owocowe (+ sposób nawadniania, K2) | 2 h | T+10,5 | `CropOut.kind`, `AnalysisRequest.irrigation_method` |
| L3 | Termin siewu i sposób uprawy | 1,75 h | T+12,25 | `AnalysisRequest`, `Report` (dane wejściowe) |
| ~~L4~~ | ~~Śnieg i pogoda wyjaśniająca~~ — **wycięte** (decyzja z 21.11, ok. 23:00) | — | — | — |
| L5 | Suwak lat i wyszukiwarka upraw | 3 h | T+15,25 | serie per rok, `CropOut.aliases_pl` |
| L6 | Woda gruntowa i spływ od sąsiadów (bez L6.2) | 2 h | T+17,25 | nowe pola w `Report` |
| K7 | Stabilizacja i dokumentacja tej rundy | 1 h | T+18,25 | — |

Kolejność wykonania: **K0 → L1 → R → L2 → L3 → L5 → L6 → K7**.

**Punkty kontrolne:**
- **T+3 h:** L1 wdrożone, publiczny adres pokazuje osie Y, daty `DD.MM.YYYY`, dużą mapę i alert poza Polską. Jeśli nie — kończymy L1, zanim ruszymy dalej (L1 nie tniemy).
- **T+8,5 h:** R wdrożone: przełącznik Podstawowy/Pełny działa na stronie i w PDF, werdykt z 3 sygnałów, wyniki bazowe przepisane.
  **R nie tniemy** poza punktami oznaczonymi w R jako „opcjonalne”.
- **T+12,25 h:** L2 i L3 wdrożone; formularz wysyła się bez dotykania nowych pól.
- **T+15,25 h:** L5 skończone. Jeśli nie — tniemy wg rozdz. 6 i z L6 robimy tylko L6.1.
- **Zamrożenie funkcji:** najpóźniej 2 h przed terminem zgłoszenia, niezależnie od tego, gdzie jesteśmy. Dalej tylko K7, poprawki błędów i `plan.md` M10.

**Zależności:** L2.1 przed L2.2–L2.5, L3.1 i L5.2 (pole `kind`, 13 upraw). L3.1–L3.2 przed L3.3. L4.1 (spike zmiennych) przed L4.2.
L5.1a przed L5.1b–c. K0.3 przed każdą bramką W. R1 przed R3 (kafle i zdania korzystają z nowego werdyktu); R5 przed R3 (kafel
„Najważniejszy ruch” bierze zalecenie „teraz”). Poza tym moduły są niezależne.

## 3. Bramka po każdym kroku i po każdym module

**Po każdym kroku (przed commitem):**
1. Backend: `pytest` (bez E2E), `ruff check .`, `mypy app` — z `backend/`.
2. Frontend (jeśli dotknięty): `npm run lint`, `npx tsc --noEmit`, `npm run build`; UI obejrzane na szerokości 1280 px i 375 px.
3. Commit w stylu Conventional Commits + `git push origin main`. Odhaczyć krok w tym pliku.
4. Zmiana kontraktu API (`backend/app/api/`, `backend/app/report/models.py`, `frontend/src/api/types.ts`): backend i front w **jednym** commicie, opis zmiany w treści commita.

**Bramka W po każdym module (W1…W6):**
1. `pytest -m e2e` na działkach referencyjnych (K0.3) — raport w < 30 s, komplet sekcji, jawne braki danych.
   Gdy lokalny adres ma blokadę (ULDK, dzienny limit Open-Meteo), po wdrożeniu: `deploy/e2e-vps.sh root@129.121.162.156 -k 2019`
   (6 przypadków historycznych; każdy przypadek zużywa limit Open-Meteo adresu produkcyjnego, więc nie tuż przed demo).
2. `deploy/deploy.sh root@129.121.162.156` (wdraża tylko zacommitowany `main`).
3. Na publicznym adresie: jedna działka dla daty bieżącej i dla **15.07.2019**, obejrzeć raport i pobrać PDF. Z telefonu choć raz na moduł.
4. Porównać poziom niedoboru z wynikami bazowymi z K0.3. Zmienić może się tylko to, co moduł miał zmienić (L1, L3.2, L4.2, L5 — nic).

## 4. Moduły i kroki

### K0. Start (0,75 h)

- [x] **K0.1 Cofnięcie zmian w katalogu.** `git checkout -- backend/app/crops/catalog.py backend/app/crops/catalog.yaml`.
  **Gotowe, gdy:** `git status` pokazuje czyste drzewo (poza nowymi plikami planu), `pytest` zielony.
- [x] **K0.2 Wdrożenie bazowe (M8.1).** Sprawdzić, czy `https://129.121.162.156.sslip.io` odpowiada. Jeśli nie: `deploy/setup-vps.sh`
  (Docker na VPS), potem `deploy/deploy.sh root@129.121.162.156`. Zapisać w `README.md` publiczny adres.
  **Gotowe, gdy:** raport dla dowolnej działki powstaje pod publicznym adresem z innej sieci; M8.1 odhaczone w `plan.md`.
- [x] **K0.3 Działki referencyjne i E2E (M9.1–M9.2).** `backend/tests/e2e/parcels.yaml`: 6 działek znalezionych przez ULDK (`GetParcelByXY`
  w punktach na gruntach rolnych, sprawdzone na ortofotomapie):
  1. gleba lekka — Wielkopolska lub Kujawy, 2. gleba ciężka — Żuławy lub Lubelszczyzna (lessy), 3. stok — Pogórze Karpackie,
  4. dolina rzeki z rowami — dolina Noteci lub Biebrzy, 5. okolice odkrywki Bełchatów (dla L6.2), 6. sad — rejon Grójca (dla L2;
  do czasu L2.1 liczony jako `spring_barley`, L2 zmienia go na `orchard_pome` i przepisuje wynik bazowy).
  Każda z uprawą i dwiema datami (bieżąca, 15.07.2019). `backend/tests/e2e/test_reports.py` (`-m e2e`): czas < 30 s, komplet sekcji,
  żadna wartość bez źródła, braki jawne. Wyniki bazowe (poziom niedoboru, lista identyfikatorów rekomendacji) zapisać do
  `backend/tests/e2e/baseline.json` jako punkt odniesienia dla bramki W.
  **Gotowe, gdy:** `pytest -m e2e` przechodzi na obecnym `main`; plik z wynikami bazowymi w repo.
  **Wykonane 21.11.2026:** 12/12 na VPS, 13–18 s na przypadek. Pokrycie terenu sprawdzone mapą ESA WorldCover, a nie ortofotomapą.
  W wyniku bazowym `hydro` = `missing` wszędzie (Overpass przeciążony tego wieczoru), więc gdy Overpass znów odpowiada, rekomendacje
  nie są porównywane (ostrzeżenie `BaselineNote`). Wtedy przepisać bazę: `deploy/e2e-vps.sh root@129.121.162.156 --update -k 2019`.

### L1. Widoczne w demo (2,25 h) → lista2 L1

- [ ] **L1.1 Osie Y na wszystkich wykresach.** Jedna funkcja podziałki (istniejące `niceMax` w `chartUtils.ts`; odpowiednik w
  `charts_svg.py`), 3–5 okrągłych wartości, polski przecinek, jednostka przy osi. Pliki: `SeasonChartView.tsx`, `Charts.tsx`
  (satelita, trendy, przekrój terenu, plan wody), `backend/app/report/charts_svg.py`.
  **Gotowe, gdy:** każdy wykres na stronie i w PDF ma opisaną oś Y z jednostką; czytelne przy 375 px; test `charts_svg` sprawdza obecność etykiet osi.
- [ ] **L1.2 „na dzień DD.MM.YYYY” zamiast „teraz”.** Filtr Jinja `date_dmy` (backend) i `formatDateDmy` w `frontend/src/lib/format.ts`.
  Miejsca wg lista2 L1.2: `labels_pl.py`, `outlook.py`, `Charts.tsx`, `report.html.j2`, `charts_svg.py`, `blocks/satellite.j2`, `sections/current.j2`.
  **Gotowe, gdy:** `grep -rni "teraz" frontend/src backend/app/report` nie znajduje nagłówków ani legend; test szablonu dla 15.07.2019.
- [ ] **L1.3 Większa mapa wyboru działki + pełny ekran.** `ParcelPickerMap.tsx`: wysokość `60svh` (min. 320 px, maks. 720 px).
  Pełny ekran jako własny tryb `fixed inset-0` (działa w Safari na iOS, gdzie Fullscreen API nie obejmuje zwykłych elementów),
  z `map.resize()` po przełączeniu i wyjściem klawiszem Esc. Ten sam przycisk w `ReportMapView.tsx` (wysokość bez zmian).
  **Gotowe, gdy:** na telefonie mapa zajmuje większość ekranu, a strona się przewija; klik działki działa w obu trybach.
- [ ] **L1.4 Granica Polski, alert i maska.**
  - Skrypt jednorazowy `backend/scripts/build_poland_outline.py`: obrys państwa z PRG GUGiK (usługa lub paczka — adres i datę pobrania
    ustalić przy wdrożeniu; zapas: Natural Earth 1:10m), **bufor ok. 200 m na zewnątrz**, potem uproszczenie do 50–100 KB i zapis do
    `frontend/src/components/map/poland.json`. Bufor gwarantuje, że uproszczenie nie odrzuci żadnej polskiej działki; ostatecznie
    i tak rozstrzyga ULDK.
  - `mapStyle.ts`: `insidePoland()` jako punkt-w-wielokącie (ray casting, bez nowej zależności), z szybkim odrzuceniem po prostokącie.
  - Alert na mapie (komponent `Alert` shadcn): „Aplikacja działa tylko dla działek w Polsce. Kliknij na terenie Polski.” — także przy
    kliknięciu na oddalonej mapie i przy „Moja lokalizacja” poza Polską. Bez zapytania do serwera.
  - Maska: warstwa `fill` (cały świat z otworem w kształcie Polski), półprzezroczysta, pod warstwą działek.
  - Test: `vitest` jako zależność deweloperska (MIT, dopisać do tabeli licencji), 6 punktów przygranicznych: Słubice / Frankfurt nad Odrą,
    Cieszyn / Český Těšín, Braniewo / Kaliningrad.
  - `docs/DATA_SOURCES.md`: źródło obrysu, licencja, data pobrania („pobrane wcześniej”).
  **Gotowe, gdy:** Słubice wybierają działkę, Frankfurt i Kaliningrad pokazują alert; test przechodzi; paczka frontu rośnie o < 100 KB.
- [ ] **W1** — bramka modułu (rozdz. 3). **Punkt kontrolny T+3 h.**

### R. Przebudowa raportu (5,5 h) → uwagi K1–K7, O1–O31 (rozdz. 7)

Zasada (O26): raport to **seria zdań-esencji, pod każdym kafel ze szczegółami do rozwinięcia**. Liczba zawsze idzie z oceną (dobrze / źle /
w normie), bez powtarzania danych działki i bez opisów źródeł w treści. Metodyka bez zmian poza R1 i R2 — zmienia się forma.

- [ ] **R1 Werdykt z trzech sygnałów (K1, O13).** `analysis/assessment.py`: poziom bieżący = max z (a) zapasu w strefie korzeni (jak dziś),
  (b) bilansu 60 dni na tle 10 lat (percentyl), (c) bilansu sezonu (opad − potrzeby uprawy od początku wegetacji, percentyl na tle 10 lat).
  Gdy (a) mówi „brak”, a (b) lub (c) są w najsuchszych 20% lat → stan **„zapas się kurczy”** (osobna flaga `watch`, nie nowy poziom —
  kolory i reguły nawadniania bez zmian). Progi percentylowe z cytatem (IUNG-PIB / SPI: McKee et al. 1993 — klasy suchości), nie z pamięci.
  Tendencja: średni dobowy ubytek z ostatnich 7 dni (i prognozy, gdy data = dziś) → „przy obecnej pogodzie zapas wystarczy na ok. X dni”.
  Kolor paska zapasu zgodny z werdyktem. Czyste funkcje + testy: 3 scenariusze (sucho w glebie / sucho tylko w bilansie / mokro).
  **Gotowe, gdy:** działka 96 Jeżów (`102104_5.0008.96`, buraki, 21.07.2026) nie dostaje już „Brak niedoboru” bez zastrzeżeń; `baseline.json`
  przepisany w tym samym commicie z opisem, co i dlaczego się zmieniło.
- [ ] **R2 Trendy uczciwe i czytelne (K5, K6, K7, O22, O23).** `analysis/trends.py`: nachylenie Sena + test Manna–Kendalla; „X na dekadę”
  tylko przy p < 0,1, inaczej samo porównanie „ostatnie 2 lata vs 10 lat”. Sześć małych wykresów → **jeden wykres** z przełącznikiem metryki
  (bilans / dni stresu / temperatura / upały / parowanie), oś Y od sensownego zakresu, linia zera dla bilansu (słupki w dół), linia trendu
  tylko gdy istotny. W PDF tylko bilans. Tekst trendów: jedno zdanie wniosku + trzy liczby.
  **Gotowe, gdy:** test: szereg losowy bez trendu → brak „na dekadę”; szereg z trendem → jest; wykres czytelny przy 375 px.
- [ ] **R3 Szkielet: Podstawowy / Pełny (O1–O9, O26).** Przełącznik „Podstawowy / Pełny” nad raportem; ten sam parametr dla PDF i druku
  (`/reports/{id}.pdf?variant=basic|full`, domyślnie `basic`). **Podstawowy** (1–2 strony A4): nagłówek z datą „Na dzień DD.MM.YYYY”,
  5–7 zdań-esencji (stan wody · ostatnie 30 dni · wpływ na uprawę · alerty · co teraz · prognoza/zalecany termin), siatka kafli bez dziur
  (2–3 kolumny desktop, 1 telefon; zielony/żółty/czerwony), zalecenia „teraz”, stopka: źródła (numerowane), 3 najważniejsze ograniczenia,
  braki danych — **wymóg regulaminu, nie usuwamy**. **Pełny**: te same kafle na początku, potem sekcje z jednym zdaniem + grafiką,
  szczegóły zwinięte (w PDF rozwinięte). Spis treści klasyczny, pionowy (O9). Kafel powodzi: 1 zdanie, gdy brak zagrożenia (O7).
  Kafel „Najważniejszy ruch”: konkretna czynność z terminem, nie numer zalecenia (O6).
  **Gotowe, gdy:** PDF podstawowy ≤ 2 strony dla 6 działek referencyjnych; oba warianty mają źródła, ograniczenia i braki; test E2E sprawdza
  obie wersje; obejrzane na 1280 i 375 px.
- [ ] **R4 Teksty na krótko (O10, O12, O14–O18, O24, O27, O29, O30, K4).** Przepisanie szablonów `sections/*.j2`, `blocks/*.j2` wg wzorów
  z rozdz. 7: „30 dni: 94 mm (+18 mm więcej niż zwykle)”; satelita „zieleń o X% wyższa/niższa niż zwykle, zdjęcie z DD.MM (N dni przed
  datą analizy)”; przyczyny jednym zdaniem (niestwierdzone w zwiniętym bloku); bez „oczko siatki 8 m” w przekroju; nawadnianie: TAK/NIE,
  kiedy, ile mm i m³, sposób — plan miesięczny zwinięty, bez powtórzonego „Nie nawadniaj”; symulator: jedno zdanie + wykres; kafel
  „Woda na rok suchy” z jednym zdaniem „skąd ta liczba” (netto vs brutto). „Pewność: wysoka” bez dopisków — wyjaśnienia do szczegółów.
  **Gotowe, gdy:** testy szablonów dla 15.07.2019 i daty bieżącej; żadne zdanie w treści głównej nie przekracza ~25 słów (test).
- [ ] **R5 Zalecenia „teraz” i „przed następnym sezonem” (O11, O28).** `Recommendation.horizon: now | next_season`, ustawiany przez regułę
  z daty analizy i fazy uprawy (np. `crop_timing_variety`, `winter_cover_crop` w lipcu → `next_season`). UI i PDF: dwie grupy.
  **Gotowe, gdy:** test: buraki 21.07 → rada o terminie siewu tylko w „przed następnym sezonem”, a „Najważniejszy ruch” jest z grupy „teraz”.
- [ ] **R6 Źródła numerowane (O4, O19, O31).** Przy liczbach odnośniki [1], [2]; jedna lista źródeł na końcu (nazwa, licencja, data pobrania);
  „Liczby, na których opiera się ocena” zostają (podobają się), ale bez powtarzania pełnego opisu źródła w każdej pozycji. Ograniczenia
  jako kafel „Na co uważać” (3 najważniejsze), reszta rozwijana. Każda liczba nadal ma źródło i datę (zasada 5).
  **Gotowe, gdy:** test: każdy odnośnik wskazuje istniejącą pozycję listy; E2E „każda liczba ma źródło” przechodzi.
- [ ] **W-R** — bramka modułu (rozdz. 3) + wyniki bazowe przepisane świadomie (R1 zmienia ocenę). **Punkt kontrolny T+8,5 h.**

### L2. Sady i krzewy owocowe (2 h) → lista2 L2, uwaga K2

- [ ] **L2.1 Katalog: `kind` i 4 nowe uprawy.** `catalog.py`: `kind: arable | grassland | fruit` (domyślnie `arable`). `catalog.yaml`:
  cztery uprawy z wartościami z tabeli w lista2 L2.1, każda liczba z komentarzem źródła (FAO-56 Tab. 11, 12, 22). Daty okresów
  krytycznych **zweryfikować z publikacją Instytutu Ogrodnictwa – PIB** i wpisać pełny cytat; czego nie da się potwierdzić, oznaczyć
  w komentarzu jako przyjęte założenie i dopisać do ograniczeń raportu. `CropOut` i `types.ts` dostają `kind`. `tests/crops/test_catalog.py`.
  **Gotowe, gdy:** `load_crops()` zwraca 13 upraw; Kc w styczniu = 0 dla sadów; ograniczenie o podkładkach karłowych w raporcie.
- [ ] **L2.2 Reguły agrotechniczne nie dla sadów.** `recommendations/common.py`: `is_fruit(ctx)`. Wyłączyć dla `fruit`:
  `reduced_tillage_mulch`, `contour_tillage`, `crop_timing_variety`, `winter_cover_crop`, `crop_residues`. `organic_matter`: wariant
  tekstu dla sadu w `texts_pl.py`. Commit **razem z L2.1** (sam katalog bez reguł dałby sadom rady o orce).
  **Gotowe, gdy:** test: dla każdej uprawy `fruit` w suchym scenariuszu żadna z 5 reguł się nie pojawia; `test_edge_cases.py` obejmuje sady.
- [ ] **L2.3 Reguła `orchard_mulch_sward`.** Warunek: `fruit` i (gleba lekka lub niedobór w maju–sierpniu w ≥ 30% lat). Dowody liczbowe
  w uzasadnieniu. Testy „odpala się” i „nie” w `test_rules.py`; wpis w `docs/METHODOLOGY.md` rozdz. 8.
  **Gotowe, gdy:** oba testy przechodzą; reguła nie pojawia się dla upraw polowych.
- [ ] **L2.4 Nawadnianie dla sadów.** `irrigation.py` / `texts_pl.py`: teksty `no_crop` i `late_stage` dla `fruit`, uwaga o nawadnianiu
  kroplowym (udział zwilżonej powierzchni, FAO-56), parametr `grassland` zastąpiony przez `kind`.
  **Sposób nawadniania (K2):** `AnalysisRequest.irrigation_method: sprinkler | drip | micro_sprinkler` (domyślnie `sprinkler`, dla `fruit`
  domyślnie `drip`); sprawność ze źródłem (FAO Irrigation and Drainage Paper 24 / FAO-56 — wartości wpisać z cytatem, nie z pamięci)
  zamiast stałych 75%; dawka brutto i m³ liczone z wybranej sprawności. Parametr wchodzi do klucza zapisanej analizy (jak w L3.1).
  **Gotowe, gdy:** `test_irrigation_qa.py` przechodzi dla 13 upraw; w tekstach dla sadów nie ma słów „pole” ani „siew”; test: ta sama
  działka, kroplowe → mniejsza dawka brutto niż deszczownia, netto bez zmian.
- [ ] **L2.5 Użytkowanie terenu a sad.** Dla `fruit` do „zgodnego użytkowania” liczą się pola + łąki + drzewa (`assessment.py`,
  `builder.py`, `sections/current.j2`, `limitations.j2`). `sources/landcover.py` bez zmian.
  **Gotowe, gdy:** test: 80% drzew + sad → brak ostrzeżenia; 80% drzew + pszenica → ostrzeżenie zostaje.
- [ ] **W2** — bramka modułu; dodatkowo działka nr 6 (sad) z uprawą `orchard_pome`.

### L3. Termin siewu i sposób uprawy (1,75 h) → lista2 L3

- [ ] **L3.1 Termin siewu.** `AnalysisRequest.sowing_shift: early | typical | late` (domyślnie `typical`). `Crop.with_sowing_shift(±14 dni)`
  przesuwa siew i okresy krytyczne; w ozimych siew jesienny. Walidacja (422) odrzuca wartość inną niż `typical` dla `grassland` i `fruit`.
  **Sprawdzić klucz cache i identyfikator zapisanej analizy** (`api/jobs.py`, `report/storage.py`): nowe parametry muszą do niego wchodzić,
  inaczej raport dla „późno” wróci z pamięci jako „typowo”.
  **Gotowe, gdy:** test: kukurydza `late` ma Kc = 0 jeszcze 10.05; test walidacji; raport mówi, że to przesunięcie średniej krajowej.
- [ ] **L3.2 Sposób uprawy.** `AnalysisRequest.tillage: plough | reduced | no_till | unknown` (domyślnie `unknown`), tylko dla `arable`.
  Zmienia wyłącznie teksty reguł `reduced_tillage_mulch` i `contour_tillage` (warianty w `texts_pl.py`). Bilans wodny bez zmian.
  **Gotowe, gdy:** test wariantu tekstu dla każdej opcji; test, że poziom niedoboru jest identyczny dla wszystkich czterech opcji.
- [ ] **L3.3 Formularz i raport.** `StartPage.tsx`: dwa pola pod wyborem uprawy, widoczne tylko dla `kind == arable`, z wartością domyślną;
  trzecie pole „Sposób nawadniania” (L2.4) dla wszystkich upraw, zwinięte w „Więcej opcji”.
  `ReportPage.tsx` i szablon PDF: termin siewu i sposób uprawy w danych wejściowych. `types.ts` w tym samym commicie co L3.1–L3.2.
  **Gotowe, gdy:** przepływ działka → uprawa → data → „Sprawdź działkę” działa bez dotykania nowych pól; brak poziomego przewijania przy 375 px.
- [ ] **W3** — bramka modułu. **Punkt kontrolny T+6,5 h.**

### ~~L4. Śnieg i pogoda wyjaśniająca~~ → lista2 L4 — **WYCIĘTE** (21.11, ok. 23:00, na rzecz modułu R; zostaje w lista2 jako „na później”)

Kroki poniżej zostają jako zapis, **nie wykonujemy ich** w tej rundzie. Śnieg i roztopy dopisać do „Ograniczeń analizy” (K7.2).

- [ ] **L4.0 Sprawdzenie zmiennych (maks. 30 min).** Dla jednego punktu i 10 lat sprawdzić w archiwum **i** w prognozie Open-Meteo:
  dobowe `snowfall_sum`, `shortwave_radiation_sum`, `sunshine_duration`, średnie dobowe wilgotności, punktu rosy, zachmurzenia i wiatru
  (nazwy z aktualnej dokumentacji, nie z pamięci) oraz godzinowe `snow_depth` i temperaturę gleby 0–7 cm. Zmierzyć czas i rozmiar odpowiedzi.
  **Decyzja:** jeśli dane godzinowe za 10 lat wydłużają pobieranie o więcej niż 2 s, pokrywę śnieżną liczymy sami z opadu i temperatury
  (model stopniodni, czysta funkcja, współczynnik topnienia ze źródłem), a zamarzniętą glebę szacujemy z temperatury powietrza — jawnie jako szacunek.
  Wynik wpisać do `docs/DATA_SOURCES.md`.
- [ ] **L4.1 Śnieg i roztopy.** `open_meteo.py`: nowe zmienne w `DAILY_VARS`, podbita wersja klucza cache. `analysis/snow.py` (czyste
  funkcje): zapas wody w śniegu na dzień analizy, suma śniegu tej zimy względem 10 lat, dni roztopów na zamarzniętej glebie → przyczyna
  „słabe zasilanie zimowe” w `causes.py`. Opadu nie liczymy drugi raz. Fallback NASA POWER → status `degraded` dla tej części.
  Wszystko ograniczone do `<= analysis_date`.
  **Gotowe, gdy:** raport dla 15.03 mówi, ile było śniegu względem 10 lat i czy roztopy wypadły na zamarzniętą glebę; test na syntetycznej
  zimie; wpisy w `docs/DATA_SOURCES.md` i `docs/METHODOLOGY.md`.
- [ ] **L4.2 Dlaczego parowanie było wysokie.** `analysis/evaporation_drivers.py`: parowanie z ostatnich 30 dni względem tych samych dni
  w 10 latach; jeśli odchylenie przekracza próg, wskazać czynnik o największym odchyleniu (suche powietrze / dużo słońca / silny wiatr).
  Zdanie w raporcie z szablonu; wilgotność i punkt rosy w „Szczegółach dla zainteresowanych”. Nie wchodzi do oceny.
  **Gotowe, gdy:** test progu (zdanie jest / nie ma); test, że poziom niedoboru jest identyczny z tymi danymi i bez nich.
- [ ] **W4** — bramka modułu; sprawdzić czas pobierania pogody na zimno (cel: bez wzrostu o więcej niż 2 s).

### L5. Suwak lat i wyszukiwarka (3 h) → lista2 L5

- [ ] **L5.1a Suwak — wykres sezonu.** `report/models.py`: `SeasonChart` dostaje serie narastające per rok (`years: [{year, values}]`);
  mediana, minimum i maksimum liczone we froncie dla N ostatnich lat (`chartUtils.ts`, czysta funkcja z testem `vitest`). Suwak 3–10
  (shadcn `Slider`, obsługa klawiaturą i palcem), domyślnie 10. Przy N = 3–4 ostrzeżenie „za mało lat, porównanie orientacyjne”.
  Stały napis: „Ocena i zalecenia zawsze opierają się na 10 latach”. PDF zawsze 10 lat (pola zagregowane zostają dla PDF).
  **Gotowe, gdy:** suwak zmienia pasmo bez zapytania do serwera; test backendu na kształt danych; rozmiar JSON raportu rośnie < 50% (zmierzyć).
- [ ] **L5.1b Suwak — mapa ciepła stresu.** `StressHeatmap` ma już wiersze per rok — front pokazuje N ostatnich. Tabela „jak często
  brakowało wody w miesiącu” (`MonthRisk`) zostaje z 10 lat, bo wchodzi do oceny.
  **Gotowe, gdy:** ten sam suwak steruje mapą ciepła; liczby w tabeli ryzyka się nie zmieniają.
- [ ] **L5.1c Suwak — wykres satelity.** `SatelliteSeries`: punkty z poprzednich lat z rokiem (jeśli dziś przychodzi tylko gotowe pasmo —
  dodać pole per rok); pasmo liczone we froncie dla N lat. Lata bez bezchmurnej sceny pokazane jako brak, nie jako zero.
  **Gotowe, gdy:** suwak zmienia pasmo satelity; przy braku scen w wybranych latach wykres mówi to wprost.
- [ ] **L5.1d Zakres krótki: dzień / tydzień / miesiąc (O20).** W sekcji „Jak było” obok suwaka lat przełącznik „ostatni dzień / 7 dni /
  30 dni / sezon / lata”: opad, potrzeby uprawy i zmiana zapasu w glebie dla wybranego okna — z bilansu dobowego, który już liczymy
  (bez nowych zapytań). Ocena i zalecenia nadal z 10 lat (stały napis jak w L5.1a). Opcjonalne (rozdz. 6, punkt 7).
  **Gotowe, gdy:** przełącznik zmienia liczby bez zapytania do serwera; test czystej funkcji agregującej okna.
- [ ] **L5.2 Wyszukiwarka upraw.** Combobox shadcn (`Command` + `Popover`) zamiast listy w `StartPage.tsx`. Podpowiedzi od 3 liter,
  filtrowanie w przeglądarce, bez polskich znaków, dopasowanie w środku nazwy. `aliases_pl` w `catalog.yaml`, `CropOut` i `types.ts`.
  Poniżej 3 liter: „Wpisz co najmniej 3 litery”. Test `vitest` funkcji dopasowania dla wszystkich 13 upraw.
  **Gotowe, gdy:** każdą uprawę da się znaleźć po 3 literach nazwy lub synonimu („zyto”, „jabl”, „porzeczka”); strzałki i Enter działają.
- [ ] **W5** — bramka modułu. **Punkt kontrolny T+12 h.**

### L6. Woda gruntowa, kopalnie, spływ od sąsiadów (2,5 h) → lista2 L6

- [ ] **L6.1 Zasilanie korzeni przez płytką wodę gruntową.** Dane: `sources/groundwater.py` (`depth_now_m`, `distance_km`). Reguła w
  `causes.py`: zwierciadło płytko pod strefą korzeni → „woda gruntowa może łagodzić niedobór” + obniżona pewność bilansu. Próg zależny
  od gleby, **wpisany z cytatem** (FAO-56 rozdz. 8 lub FAO Irrigation and Drainage Paper 24), nie z pamięci. Wniosek tylko, gdy stacja
  jest dostatecznie blisko (użyć istniejącego progu odległości z `groundwater.py`); odległość zawsze w raporcie.
  **Gotowe, gdy:** testy: płytkie i głębokie zwierciadło, stacja za daleko → brak wniosku, brak stacji → brak wniosku.
- [ ] ~~**L6.2 Kopalnie odkrywkowe**~~ — **WYCIĘTE** (21.11, na rzecz R): tylko wpis do „Ograniczeń analizy” w K7.2. Zapis pierwotny: Sprawdzić usługę PIG-PIB MIDAS (obszary górnicze, WMS/WFS, licencja, filtr na
  odkrywki). Działa → `sources/mining.py` (odległość do najbliższego obszaru górniczego odkrywki, `SourceResult`), zdanie o możliwej
  przyczynie niskich wód gruntowych z niską pewnością. Nie działa w 30 min → wpis do „Ograniczeń analizy” i koniec kroku.
  **Gotowe, gdy:** działka nr 5 (Bełchatów) dostaje wzmiankę, działka na Podlasiu nie; źródło w `docs/DATA_SOURCES.md` — albo wpis w ograniczeniach.
- [ ] **L6.3 Spływ z działek sąsiednich.** `analysis/terrain.py`: powierzchnia spoza działki spływająca na działkę (z akumulacji D8 na
  komórkach wlotowych) i punkty, którędy woda wpływa. **Uwaga:** model terenu obejmuje tylko bufor 150 m wokół działki, więc raport pisze
  „z co najmniej X ha”, a gdy zlewnia sięga krawędzi wycinka — mówi to wprost. Rowy u sąsiada z `hydro.py`. Strzałka napływu na mapie
  raportu (`MapFeatureKind: inflow`) i w `map_svg.py`. Rekomendacje retencyjne: pas zieleni lub zastawka w miejscu napływu.
  **Gotowe, gdy:** test na syntetycznym stoku: działka u podnóża dostaje „X ha”, działka na szczycie nie; strzałka na mapie i w PDF.
- [ ] **W6** — bramka modułu. Po nim zamrożenie funkcji (rozdz. 2).

### K7. Stabilizacja i dokumentacja tej rundy (1 h)

- [ ] **K7.1 Wydajność i odporność (M9.4–M9.5).** Czas każdego źródła na zimno i z cache na 6 działkach; suma < 25 s. Test z wyłączonym
  po kolei każdym źródłem (w tym nowymi z L6): raport z jawnym brakiem, nie błąd.
- [ ] **K7.2 Dokumentacja wg lista2 rozdz. 5.** `CLAUDE.md` (lista 13 upraw, nowe pola formularza), `docs/METHODOLOGY.md` (reguła dla sadów,
  wyłączenia, warianty sposobu uprawy, sposób nawadniania, werdykt z 3 sygnałów, trendy Manna–Kendalla, woda gruntowa; śnieg
  i kopalnie jako ograniczenia), `docs/DATA_SOURCES.md` (komplet), `README.md` (nowe funkcje, ograniczenia).
- [ ] **K7.3 Ostatnie wdrożenie** i przejście całej ścieżki na telefonie. Dalej `plan.md` M10 (README, przykładowe PDF-y, zgłoszenie).

## 5. Ryzyka tej rundy

| Ryzyko | Jak ograniczamy |
|---|---|
| Werdykt z 3 sygnałów zmienia oceny na wszystkich działkach | R1 przepisuje `baseline.json` w tym samym commicie, z opisem zmian; testy 3 scenariuszy |
| Raport podstawowy gubi elementy wymagane regulaminem | R3: test E2E sprawdza źródła, ograniczenia i braki danych w obu wariantach |
| Parametry formularza nie wchodzą do klucza cache | jawny punkt kontrolny w L3.1 + test dwóch analiz różniących się tylko terminem siewu |
| Serie per rok rozdymają JSON raportu | pomiar w L5.1a; wartości zaokrąglone do 1 mm, daty jako jedna wspólna oś |
| Uproszczony obrys odrzuca polskie działki przy granicy | bufor 200 m na zewnątrz; ULDK rozstrzyga ostatecznie |
| Wartości dla sadów bez potwierdzonego źródła | L2.1: bez cytatu wartość jest oznaczona jako założenie i trafia do ograniczeń raportu |
| Zmiana psuje ocenę na działkach referencyjnych | wyniki bazowe z K0.3 porównywane w każdej bramce W |

## 6. Co tniemy, gdy punkt kontrolny nie jest osiągnięty (w tej kolejności)

L4 i L6.2 są już wycięte (decyzja z 21.11). Dalej, w tej kolejności:

1. R2: przełącznik metryk na wykresie trendów (zostaje jeden wykres bilansu).
2. R6: odnośniki numerowane (zostaje dzisiejszy opis źródła przy liczbie, lista źródeł w stopce).
3. L5.1c suwak na wykresie satelity, potem L5.1b mapa ciepła (zostaje wykres sezonu).
4. Synonimy w wyszukiwarce (L5.2 — zostaje wyszukiwanie po nazwie).
5. Maska terenu poza Polską (L1.4 — zostaje alert).
6. L6.3 strzałka napływu na mapie (zostaje zdanie w raporcie).
7. O20: zakres dzień / tydzień / miesiąc w sekcji „Jak było” (zostaje suwak lat z L5).

**Nie tniemy:** L1.1–L1.4, R1, R3, R4, R5, L2.1–L2.2, bramek W, testów „odpala się / nie odpala się” dla nowych reguł.

## 7. Uwagi z 21.11.2026 (ok. 23:00) i gdzie je załatwiamy

Źródła: `Uwagi/krotkie uwagi.docx` (K), `Uwagi/Uwagi ogólne.docx` (O). Zrzuty dotyczą raportu działki 96 w Jeżowie (buraki, 21.07.2026)
i działki z żytem. Wymogi formalne sprawdzone ponownie (`docs/REQUIREMENTS.md`): każdy wariant raportu musi mieć stan niedoboru
i przyczyny, rekomendacje z uzasadnieniem, datę i źródła, ograniczenia oraz jawne braki danych.

| Uwaga | Czego dotyczy | Rozwiązanie | Krok |
|---|---|---|---|
| K1 | „Brak niedoboru”, choć na polu sucho (sezon: 214 mm deszczu przy potrzebie 351 mm, bilans 60 dni −101 mm) | werdykt z 3 sygnałów + stan „zapas się kurczy” + tendencja | R1 |
| K2 | Sprawność 75% to deszczownia; sady i krzewy nawadnia się kroplowo | pole „sposób nawadniania” ze sprawnościami z FAO | L2.4, L3.3 |
| K4 | Kafel „Woda na rok suchy” — nie wiadomo, skąd liczba | jedno zdanie „skąd”, netto vs brutto | R4 |
| K5 | „Przybywa 8 dni upalnych na dekadę” z 10 lat danych | trend tylko istotny (Mann–Kendall, Sen) | R2 |
| K6 | Wykres bilansu sezonu wygląda dziwnie | linia zera, słupki w dół, oś Y | L1.1, R2 |
| K7 | „+91 mm na dekadę” niewidoczne na wykresie parowania | oś od sensownego zakresu, linia trendu tylko gdy istotny | R2 |
| O1 | Wybory na stronie mają zmieniać raport do druku | ten sam parametr wariantu dla widoku, PDF i druku | R3 |
| O2, O8 | **KRYTYCZNE:** raport podstawowy / pełny i wybór przy eksporcie | przełącznik Podstawowy / Pełny | R3 |
| O3, O26 | **KRYTYCZNE:** maksimum w grafice; zdania-esencje, pod nimi kafle | szkielet raportu | R3 |
| O4 | Pełny bez powtórzeń, krótszy | usunięte powtórzenia, źródła numerowane | R3, R6 |
| O5 | Podsumowanie: pusta przestrzeń, brak kolorów i parametrów | siatka kafli bez dziur, zielony/żółty/czerwony, alerty, termin siewu (pełny) | R3 |
| O6 | „Zalecenie nr 1 — w sumie 3” to ucieczka | kafel „Najważniejszy ruch” = czynność z terminem | R3, R5 |
| O7 | Powódź: esej, choć brak zagrożenia | jedno zdanie, szczegóły zwinięte | R3, R4 |
| O9 | Spis treści kafelkowy nieczytelny | klasyczny pionowy spis | R3 |
| O10, O12 | Lanie wody, powtórzone dane działki, liczba bez oceny | „Na dzień …”, liczba + ocena, krótkie zdania | R4 |
| O11, O28 | W lipcu rada o terminie siewu; podzielić na rady teraz i na później | `horizon: now / next_season` | R5 |
| O13 | „Brak wody za ok. 7 mm” — dodać tendencję | „wystarczy na ok. X dni” | R1 |
| O14 | Opad 30/90 dni za długo | „30 dni: 94 mm (+18 mm więcej niż zwykle)” | R4 |
| O15 | Satelita „typowa” — dobrze czy źle, z kiedy zdjęcie | ocena + data zdjęcia i opóźnienie | R4 |
| O16 | Zdanie o pewności i progach IUNG nie jest konkretem | „Pewność: wysoka”, reszta w szczegółach | R4 |
| O17 | Wykres deszcz vs potrzeby — podoba się; jak w PDF | zostaje; w PDF SVG, w podstawowym mniejszy | R3 |
| O18 | Wykres satelity nic rolnikowi nie mówi | zdanie „zieleń o X% wyższa/niższa niż zwykle” | R4 |
| O19 | „Szczegóły” i „Liczby” — podobają się; przypisy numerowane i jedna bibliografia | odnośniki [n] + lista źródeł | R6 |
| O20 | Zakres 10 lat / rok / miesiąc / tydzień / dzień | przełącznik okna w „Jak było” | L5.1d |
| O21 | Mapa ciepła stresu — podoba się | główna grafika sekcji „Jak było” | R3 |
| O22, O23 | Tekst trendów za długi; 6 wykresów mało czytelne | jedno zdanie + jeden wykres z przełącznikiem | R2 |
| O24 | „Dlaczego brakuje wody” — jednym zdaniem | jedno zdanie, niestwierdzone zwinięte | R4 |
| O25 | Mapa retencji — najmocniejszy punkt | bez zmian (+ strzałka napływu w L6.3) | — |
| O27 | Przekrój: „dokładność / oczko 8 m” pokazuje wadę | usunąć z treści, zostaje w ograniczeniach | R4 |
| O29 | Nawadnianie maksymalnie krótko | TAK/NIE, kiedy, ile, sposób; plan zwinięty; bez duplikatu | R4 |
| O30 | Symulator — jednym zdaniem | zdanie + wykres, suwak w pełnym | R4 |
| O31 | Źródła się powtarzają → stopka; ograniczenia jako kafel | stopka + kafel „Na co uważać” | R6 |

