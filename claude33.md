# CLAUDE.md — RolnikSzukaWody (zespół GeoSatel)

HackNation 2026, Bydgoszcz, 21–22.11.2026. Zadanie KOWR: **„Zatrzymaj wodę, chroń plony”**.
Aplikacja webowa dla rolnika. Rolnik podaje numer działki ewidencyjnej (albo klika ją na mapie), wybiera uprawę i datę analizy.
Narzędzie pobiera dane publiczne, **liczy** ocenę sytuacji wodnej (stan na dzień analizy + 10 lat wstecz) i wydaje raport
z przyczynami niedoboru oraz rekomendacjami retencyjnymi, agrotechnicznymi i nawodnieniowymi.

Cel nadrzędny: spełnić **każde** wymaganie z `docs/task/zadanie.pdf` i `docs/task/regulamin.pdf` oraz zdobyć maksimum punktów
w 5 kryteriach oceny. Przy wątpliwościach rozstrzyga oryginał PDF, nie ten plik.

- Macierz zgodności i luki: rozdział **„Macierz zgodności”** niżej (aktualizuj ją przy każdej zmianie).
- Bieżąca kolejka zadań: `plan2.md` (kroki) i `lista2.md` (uzasadnienia). Zgłoszenie i README: `plan.md`, moduł M10.
- Metodyka i bibliografia: `docs/METHODOLOGY.md`. Źródła, licencje i daty pobrania: `docs/DATA_SOURCES.md`.
- Załącznik naukowy KOWR: `docs/task/podstawy-naukowe.pdf`.

## Kryteria oceny (regulamin § 3 ust. 4) i jak jury testuje

| Kryterium | Waga | Na co jury patrzy |
|---|---|---|
| Wartość praktyczna | 25% | Konkretne decyzje dla tej działki: retencja, nawadnianie, ograniczanie strat wilgoci |
| Dane i wiarygodność | 25% | Łączenie źródeł, zgodność z nauką (FAO-56, IUNG-PIB, NWRM, 4 per mille), uzasadnienie danymi, jawna niepewność |
| Innowacyjność i rozwój | 20% | Wartość dodana wobec istniejących narzędzi, integracje, skalowanie |
| Prostota obsługi | 15% | Bez wiedzy GIS; czytelne w kilka sekund, także na telefonie |
| Prototyp i jakość | 15% | Dowolna działka i data, < 30 s, stabilność, bezpieczeństwo, dokumentacja, licencje |

Etap 1: jurorzy wpisują **numery działek z całej Polski** i **datę (dziś lub do 10 lat wstecz)**, a wynik porównują z danymi
referencyjnymi. Finał: demo na żywo dla 1–3 działek i dat jury (pitch 2–3 min + 2 min pytań). Próg nagrody to ≥ 50% punktów
i spełnienie wymagań formalnych.

## Zasady nadrzędne (złamanie = utrata punktów lub dyskwalifikacja)

1. **Wynik jest liczony z pobranych danych, nigdy wpisany na sztywno.** Każda rekomendacja wynika z reguły sprawdzającej
   wartości policzone dla tej działki i daty. Gotowe rekomendacje nie spełniają wymagań (3.3 pkt 4).
2. **Obowiązkowa kolejka:** ocena sytuacji wodnej → przyczyny → retencja → agrotechnika → (opcjonalnie) nawadnianie.
   Bez kompletnej oceny nie ma rekomendacji (`assessment.complete`). Retencja zawsze przed nawadnianiem („retain water where it falls”).
3. **Data analizy jest parametrem, a nie „dziś”.** Wszystkie dane czasowe obcinamy do `<= analysis_date`, a okno historii to
   10 lat wstecz od tej daty. Dane, które istnieją tylko w stanie bieżącym (gleba, NMT, OSM, ISOK, geometria), raport oznacza jako
   „stan obecny”.
4. **Bieżąca susza ≠ podatność wieloletnia.** Raport pokazuje je osobno.
5. **Satelity nie interpretujemy samodzielnie** i zawsze robimy to w kontekście uprawy i fazy rozwoju (niski NDVI w marcu przy
   kukurydzy to norma). Porównujemy z krzywą wieloletnią tej działki.
6. **Brak danych mówimy wprost, bez pozornej precyzji.** Status źródła: `ok | degraded | missing`. Nigdy nie podstawiamy wartości
   udającej pomiar. Awaria jednego źródła obniża pewność, ale nie wywraca analizy. Zaokrąglamy sensownie i **jednolicie**
   (ta sama wartość ma w całym raporcie tę samą liczbę).
7. **Każda liczba ma źródło, datę i poziom pewności** (`source`, `fetched_at`, `period`, `uncertainty`).
8. **Bez LLM i bez płatnych usług.** Tekst powstaje z szablonów Jinja wypełnianych wyliczonymi wartościami (powtarzalność wyników
   wobec danych referencyjnych jury). Rolnik niczego nie kupuje, nie instaluje i nie zakłada konta. AI używamy tylko jako narzędzia
   deweloperskiego (Claude Code), co musi być opisane w README (4.2 pkt 6, 5.1).
9. **Do 30 s na działkę** (obecnie 14–18 s, `tests/e2e/baseline.json`). Źródła pobieramy równolegle, każde z własnym timeoutem.
   Cache na dysku, rastry czytamy tylko oknem bbox. Każde nowe źródło musi zmieścić się w tym budżecie.
10. **Cała Polska.** Nie zakładamy województwa, zasięgu ani układu współrzędnych.
11. **Bez danych osobowych** (5.6, regulamin § 6): nie ma kont, IP nie trafia do logów, klienta identyfikujemy solonym skrótem.
12. **Licencje:** dane bezpłatne i legalne, komponenty na licencjach pozwalających KOWR przejąć prawa (§ 2 ust. 10, § 5), bez GPL/AGPL.
    Każdą nową zależność i każde nowe źródło od razu dopisujemy do tabel w README i `docs/DATA_SOURCES.md`.
13. **Repo jest prywatne do końca wydarzenia** (§ 2 ust. 6, § 5 ust. 7). Nie zmieniamy widoczności i nie publikujemy kodu gdzie indziej.

## Zasady raportu i UI („mistrzowska metodyka, przyjazny wynik”)

Analiza ma być profesorska, ale rolnik ma rzucić okiem i wiedzieć, co robić („do porannej kawy”).

- **Dwa warianty raportu:** **Podstawowy** (1–2 strony) i **Pełny**. Przełącznik jest na stronie oraz przy PDF i druku, a wybór
  w UI kształtuje wydruk. Podstawowy też zawiera źródła, ograniczenia i jawne braki danych (wymóg 3.3 pkt 5).
- **Najpierw werdykt.** Każda sekcja zaczyna się jednym zdaniem: werdykt, liczba i kierunek. Przykład: „Wody w glebie wystarczy
  na ok. 6 dni; zapas maleje”. Uzasadnienie trafia do rozwijanych „Szczegółów”, nigdy do zdania głównego.
- **Wizualizacja przed tekstem:** kafelki KPI z kolorem (zielony/żółty/czerwony), paski zapasu wody z progiem stresu i małe
  wykresy w sekcjach. Tekst jest tylko syntetycznym uzasadnieniem.
- **Krótko i bez powtórzeń.** Danych działki nie powtarzamy (są w nagłówku). Gdy nie ma zagrożenia, piszemy jedno zdanie.
  Treść raportu Pełnego nie duplikuje Podstawowego.
- **Słowa oceniające zamiast ogólników:** zamiast „typowa” piszemy „dobra / słabsza niż zwykle o X%”. Podajemy datę zdjęcia satelitarnego.
- **Zalecenia dzielimy na „teraz”** (dni–tygodnie, dopasowane do daty analizy i fazy uprawy) **i „na sezon/lata”**. Nie dajemy
  zaleceń siewnych w lipcu, chyba że dotyczą międzyplonu, i wtedy mówimy to wprost.
- **Prognozy i plany ostrożnościowo:** obok mediany pokazujemy rok suchy (P80/P90), nie samą średnią.
- **Trendy tylko tam, gdzie dane je uzasadniają.** Nie ekstrapolujemy „na dekadę” z 1–2 lat.
- **Źródła danych w stopce** z numerami przypisów i jedną bibliografią. Ograniczenia mają osobny kafelek.
- Język prosty, po polsku. Żargon (NDVI, KBW, TAW) pojawia się tylko w „Szczegółach dla zainteresowanych”.

## Macierz zgodności (stan z audytu 22.11.2026; ✅ zrobione · ⚠️ częściowo · ❌ brak)

Po każdej zmianie aktualizuj status i datę. ID są stałe, więc w commitach i planie odwołuj się do nich (np. `fix(hydro): G3`).

### Prototyp (zadanie 3.2–3.3, 5.2, 6)
| ID | Wymaganie | Status | Gdzie / luka |
|---|---|---|---|
| P1 | Przeglądarka bez instalacji (Chrome, Firefox, Edge, Safari, Opera); mobile jako atut | ✅ | VPS + Caddy; Tailwind `sm:` |
| P2 | Działka po ID **i** kliknięciem na mapie | ✅ | `api/routes.py`, `components/map/ParcelPickerMap.tsx` |
| P3 | Wybór uprawy | ✅ | `crops/catalog.yaml` (9 upraw) |
| P4 | Data analizy (dziś…−10 lat) bez przecieku przyszłych danych | ✅ | `core/models.py`, `open_meteo.py`, `sentinel2.py`; WorldCover 2020 dla dat < 2021 ujawniony |
| P5 | Ocena bieżąca + podatność 10-letnia, liczona z danych | ✅ | `analysis/assessment.py`, `analysis/history.py` |
| P6 | Raport: stan i przyczyny, retencja, agrotechnika, nawadnianie, data i źródła, ograniczenia, jawne braki | ✅ | `report/templates/{sections,missing}/`, `limitations.j2` |
| P7 | Zapis w systemie / PDF / druk | ✅ | SQLite `report/storage.py`, `/reports/{id}.pdf` |
| P8 | Wszystkie 5 kategorii danych **działa w praktyce** | ⚠️ | Hydrologia (OSM Overpass) była `missing` w 12/12 przebiegach E2E → G3 |
| P9 | Kolejność etapów, brak rekomendacji bez oceny | ✅ | `report/models.py` `SECTION_ORDER`, `recommendations/engine.py` |
| P10 | Satelita zależny od uprawy i fazy | ✅ | `analysis/assessment.py` (typowe daty faz, nie realna fenologia) |
| P11 | < 30 s na działkę | ✅ | 14–18 s w `tests/e2e/baseline.json` |

### Wymagane rozszerzenia (decyzja zespołu 22.11)
| ID | Wymaganie | Status | Luka |
|---|---|---|---|
| G1 | Oficjalne progi KBW IUNG-PIB (Doroszewski i in. 2012) + mapowanie gleby na kategorie I–IV | ❌ | `crops/iung_thresholds.yaml` jest pusty, a raport pisze „nie użyto progów” |
| G2 | NMT 1 m GUGiK + profil spadku i miejsca pod zastawki/bufory | ✅ | `sources/dem.py` (Copernicus 30 m jako zapas), `analysis/profile.py` |
| G3 | Hydrologia z fallbackiem (MPHP / BDOT10k WFS) obok OSM | ⚠️ | Są tylko 2 mirrory Overpass (`sources/hydro.py`) |
| G4 | Strefy zagrożenia powodziowego ISOK | ✅ | `sources/flood.py` |
| G5 | Wody gruntowe (PIG-PIB, najbliższa stacja, trend) | ⚠️ | `sources/groundwater.py`, ale trend obejmuje tylko 3 lata; brak IMGW hydro na żywo |
| G6 | Wariant ostrożnościowy P80/P90 w planie wody i symulatorze | ✅ | `analysis/simulate.py`, `analysis/water_plan.py` (sprawdzić, czy P80 widać w raporcie Podstawowym) |
| G7 | Raport Podstawowy / Pełny | ❌ | Są tylko rozwijane „Szczegóły” per sekcja (`ReportPage.tsx`) |
| G8 | SOC i 4 per mille (Minasny 2017) w agrotechnice i symulatorze | ⚠️ | Jest reguła niskiego SOC (`recommendations/agrotech.py`), brakuje ujęcia 4 per mille |

### Zgłoszenie (4.1) i README (4.2, 5.3–5.6)
| ID | Wymaganie | Status | Luka |
|---|---|---|---|
| Z1 | Nazwa zespołu i tytuł | ✅ | README |
| Z2 | Zwięzły opis: problem, funkcje, użycie danych, korzyści | ❌ | — |
| Z3 | Link do prywatnego repo + dostęp jury wg Platformy | ⚠️ | Repo prywatne; dostęp jury do zrobienia ręcznie |
| Z4 | Prezentacja PDF ≤ 10 slajdów | ❌ | `docs/submission/prezentacja.pdf` |
| Z5 | Film ≤ 3 min | ❌ | Link w README |
| Z6 | Wygenerowane raporty | ❌ | `docs/sample-reports/` (PDF dla działek z `parcels.yaml`, data bieżąca i historyczna) |
| Z7 | Działający link lub instrukcja uruchomienia (obowiązkowe) | ✅ | https://129.121.162.156.sslip.io + Docker |
| R1 | README: uruchomienie (lokalnie, Docker, testy) | ⚠️ | Jest tylko Docker i VPS |
| R2–R4 | README: funkcje, architektura, źródła i zakresy danych | ❌ | Treść jest w CLAUDE.md i docs/, ale nie w README |
| R5 | README: dane na żywo vs pobrane wcześniej (z datami) | ⚠️ | Tylko w `DATA_SOURCES.md` |
| R6 | README: biblioteki, komponenty, modele, usługi, **narzędzia AI** (w tym Claude Code) | ❌ | — |
| R7 | README: licencje danych i komponentów | ⚠️ | Tabela ma 2 wiersze |
| R8 | README: znane ograniczenia | ❌ | Są tylko w szablonie raportu |
| R9 | README: weryfikacja wyników (testy, E2E, porównanie z IUNG/EDO) | ❌ | — |
| R10 | Koszty, brak usług płatnych, alternatywy (5.4) | ⚠️ | Brak kwoty VPS i jasnego „0 zł dla rolnika” |
| R11 | Skalowalność (5.5): limity źródeł, cache, aktualizacja danych, ruch, koszty | ❌ | W kodzie jest (cache, semafor, rate limit), w README brak opisu |
| R12 | Bezpieczeństwo (5.6) | ✅ | `api/ratelimit.py`, `deploy/Caddyfile`, walidacja wejścia; trzeba to opisać w README |

### Jakość techniczna
| ID | Problem | Status |
|---|---|---|
| T1 | `test_builder.py::test_sources_section_lists_every_source_with_date` ma na sztywno „21 listopada 2026” (5 przypadków pada) | ❌ **blokuje push przez hook** |
| T2 | `npx tsc --noEmit` w `frontend/` nic nie sprawdza (`files: []`); używaj `-p tsconfig.app.json` lub `npm run build` | ⚠️ |
| T3 | Rozjazd zaokrągleń dawki (plan wody 5/10 mm vs dawka 1 mm) | ⚠️ |

**Priorytet (od największego wpływu na punkty):** T1 → G3 → G1 → G7 → Z6 → R1–R12 → G8 → G5 → Z2/Z4/Z5 (materiały zgłoszeniowe
na końcu, ale z zapasem czasu przed zamknięciem Platformy).

## Stack

| Warstwa | Technologia |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, httpx (async), rasterio, pystac-client, shapely, pyproj, numpy |
| Raport | Jinja2 + WeasyPrint (PDF), ten sam HTML do druku; wykresy i mapy jako SVG (`report/charts_svg.py`, `map_svg.py`) |
| Storage | SQLite (raporty z ID), cache na dysku `backend/.cache/` |
| Frontend | React 19, Vite, TypeScript 6.0 (nie 7), Tailwind 4 + shadcn/ui, MapLibre GL, React Router, vitest |
| Deploy | Docker + Caddy (HTTPS, CSP, HSTS), VPS Ubuntu, `deploy/*.sh` |

## Komendy

```bash
# Backend (backend/)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest                                  # unit, bez sieci (~45 s); pojedynczo: pytest tests/analysis/test_x.py -k nazwa
pytest -m e2e                           # działki referencyjne, sieć, wolne — tylko przed deployem
ruff check . && ruff format . && mypy app

# Frontend (frontend/)
npm install && npm run dev              # http://localhost:5173, proxy /api -> :8000
npx tsc --noEmit -p tsconfig.app.json   # (gołe `tsc --noEmit` nic nie sprawdza)
npm run lint && npm test && npm run build

# Docker / VPS
docker compose up -d --build            # http://localhost
deploy/deploy.sh root@129.121.162.156   # z czystego main; buduje, czeka na /api/health, rozgrzewa cache
deploy/e2e-vps.sh                       # E2E na serwerze
```

## Architektura

```
backend/app/
  main.py, api/{routes,jobs,schemas,ratelimit}.py   # /parcels, /analyses, /reports/{id}[.pdf]; jobs.py = asyncio.gather źródeł
  core/{config,models,cache,http}.py                # SourceResult, Uncertainty, limity, cache
  sources/      # tylko pobieranie i normalizacja, ZERO logiki domenowej; każde zwraca SourceResult(status, source, license, fetched_at, data)
    uldk.py           geometria i TERYT (GUGiK ULDK)
    open_meteo.py     opad, temperatura, ET0 (ERA5 + forecast dla „dziś”; NASA POWER jako zapas)
    planetary.py, sentinel2.py   Sentinel-2 L2A z Microsoft Planetary Computer (STAC + COG, windowed read)
    soilgrids.py      uziarnienie, SOC, retencja
    dem.py            NMT 1 m GUGiK (GetHByPointList), zapas Copernicus GLO-30
    hydro.py          cieki, rowy, zbiorniki (OSM Overpass, 2 mirrory) — brak fallbacku PL (G3)
    flood.py          strefy ISOK · groundwater.py  PIG-PIB PSH · landcover.py  ESA WorldCover
  analysis/     # CZYSTE funkcje: assessment, causes, water_balance, et0, soil, history, terrain, profile, trends,
                #   water_plan, simulate, series, context
  crops/        # catalog.yaml (Kc FAO-56, fazy, okresy krytyczne), iung.py + iung_thresholds.yaml (G1)
  recommendations/  # engine → retention → agrotech → irrigation; teksty w texts_pl.py
  report/       # builder, outlook, pdf, storage; templates/{report.html.j2, report.css, headline.j2, limitations.j2,
                #   sections/, blocks/, missing/}
frontend/src/
  pages/{StartPage,AnalysisPage,ReportPage}.tsx · components/{map,report}/ · api/{client,types}.ts
backend/tests/  # unit (analysis/, recommendations/, report/) · e2e/{parcels.yaml, baseline.json, runner.py}
```

**Przepływ:** ID lub (x, y) → ULDK → równoległe `sources/` → `analysis/` → `recommendations/` → `report/` → SQLite → JSON + PDF.
`analysis/` i `recommendations/` nie robią I/O i testuje się je na fixture'ach (`tests/fixtures/`).

## Metodyka (szczegóły: `docs/METHODOLOGY.md`)

- **Bilans:** KBW = P − ET0 (Penman–Monteith), ETc = Kc · ET0 (FAO-56, Kc wg fazy), bilans strefy korzeniowej (TAW, RAW).
  **Pojemność wodna gleby (mm/m) ≠ zapas wynikający z płytkich korzeni uprawy.** Nie mieszamy tych dwóch rzeczy w przyczynach.
- **Susza rolnicza:** KBW 60-dniowy porównywany z progami IUNG-PIB dla uprawy i kategorii gleby I–IV (G1) oraz z rozkładem
  10 lat na tej działce (percentyle). Miesiąc z niedoborem liczymy jako ≥ 1/3 dni sezonu ze stresem (`history.py`
  `STRESS_SHARE`), nie od jednego dnia.
- **Werdykt bieżący z 3 sygnałów:** zapas w glebie, bilans 60 dni na tle 10 lat, bilans sezonu + „wystarczy na ok. X dni”.
- **Satelita:** NDVI, NDMI, chmury maskowane SCL; porównanie z krzywą tej działki z tego samego terminu.
- **Przyczyny** (flaga + dowód liczbowy): deficyt opadów/upał · słaba retencja gleby (lekka, mało SOC) · odpływ (spadki, brak
  elementów retencji) · wrażliwość uprawy w fazie krytycznej.
- **Działania:** retencja krajobrazowa (NWRM: zastawki, oczka, bufory, zadrzewienia) → glebowa (międzyplony, resztki, uprawa
  uproszczona, SOC / 4 per mille) → nawadnianie (termin, dawka, sposób: deszczownia / kroplowe / mikrozraszacze, pozwolenie wodnoprawne).
- **Symulator 1–5 lat:** samo nawadnianie **nie buduje** wieloletniego zapasu wody w glebie (zimą profil i tak się uzupełnia,
  a nadmiar odpływa). Trwały efekt daje tylko wzrost SOC, czyli wyższe AWC.
- **Niepewność** każdego wskaźnika (wysoka/średnia/niska) zależy od kompletności danych, rozdzielczości (SoilGrids 250 m)
  i liczby bezchmurnych scen.

## Pułapki danych

- ID działki: `WWPPGG_R.OOOO.NR` (np. `141201_1.0001.6509`). Numery z `/` trzeba URL-encodować. Kliknięcie obsługuje
  `GetParcelByXY`. ULDK domyślnie zwraca EPSG:2180, a `srid=4326` daje WGS84.
- Układy: front 4326/3857, dane PL 2180, Sentinel-2 UTM 32633/32634. Przed odczytem rastra zawsze reprojektuj przez `pyproj`.
- Open-Meteo: ERA5 ma opóźnienie ~5 dni, więc dla „dziś” doklejamy forecast. Licencja CC BY 4.0, bezpłatnie tylko niekomercyjnie
  (opisz w README i w kosztach skalowania).
- Sentinel-2: maks. 1 najlepsza scena na okres; profil historyczny jest cache'owany. Mała działka (kilka pikseli) daje niską pewność.
- Overpass, SoilGrids i ISOK bywają wolne: twardy timeout, status `missing`, nigdy wyjątek na całą analizę.
- Każde nowe źródło od razu dopisz do `docs/DATA_SOURCES.md` (URL, licencja, zakres czasu i przestrzeni, na żywo czy wcześniej + data).

## Konwencje kodu

- Kod, nazwy, komentarze i commity **po angielsku**. Teksty UI i raportu **po polsku**, w szablonach/słownikach (`texts_pl.py`,
  `labels_pl.py`, `*.j2`), nigdy w logice.
- Python: pełne type hints, Pydantic na granicach, jednostki w nazwach pól (`precip_mm`, `et0_mm`, `slope_pct`).
- Frontend: komponenty funkcyjne, typy API w `frontend/src/api/types.ts`, bez `any`.
- Walidacja wejścia: format ID, zakres dat, uprawa z listy, granice Polski. Sekrety tylko w `.env` (dziś żadne nie są potrzebne).
- Testy nie mogą zależeć od dzisiejszej daty: wstrzykuj `now`/`fetched_at` (patrz T1).

## Workflow dla każdej zmiany

1. **Wskaż ID wymagania** z macierzy (np. G3, R8) albo krok z `plan2.md`. Jeśli zmiana nie służy żadnemu wymaganiu ani kryterium
   oceny, zapytaj, zanim ją zrobisz.
2. **Test najpierw:** dla reguły rekomendacji test „kiedy się odpala” i „kiedy NIE”; dla źródła fixture + test statusu `missing`.
3. **Implementuj** w granicach modułów (sources bez logiki, analysis bez I/O).
4. **Sprawdź na żywo** 1–2 działki z `tests/e2e/parcels.yaml` (data bieżąca i historyczna), z czasem < 30 s. Zmiany UI sprawdzaj
   w przeglądarce na szerokości komputera i telefonu, w obu wariantach raportu oraz w PDF.
5. **Zaktualizuj macierz zgodności** w tym pliku (status + data) oraz README / `DATA_SOURCES.md`, jeśli zmiana tego wymaga.
6. **Commit + push na `main`** (Conventional Commits z ID, np. `feat(hydro): add MPHP WFS fallback (G3)`).
7. **Deploy** po zamknięciu modułu: `deploy/deploy.sh root@129.121.162.156`, potem sprawdź publiczny adres.

## Definition of Done

Zadanie jest gotowe dopiero, gdy:
- [ ] `pytest` przechodzi, `ruff check .` i `mypy app` są czyste, `npx tsc --noEmit -p tsconfig.app.json` i `npm run lint` przechodzą
- [ ] nowa reguła lub źródło ma testy (w tym ścieżkę `missing`/`degraded`)
- [ ] raport dla działki referencyjnej powstaje w < 30 s, ma wszystkie sekcje, a braki danych są jawne
- [ ] żadna liczba nie jest wpisana na sztywno do tekstu, wszystkie pochodzą z danych
- [ ] nowe źródło lub zależność jest w `DATA_SOURCES.md` i w tabeli licencji README (bez GPL/AGPL, bez płatnych API)
- [ ] macierz zgodności jest zaktualizowana
- [ ] zmiana UI jest sprawdzona na desktopie i telefonie, w wariancie Podstawowym, Pełnym i w PDF

## Hooki (`.claude/settings.json`, skrypty w `.claude/hooks/`)

- Po edycji `backend/**/*.py`: `ruff format` + `ruff check --fix`. Błędy wracają do Claude (exit 2) i trzeba je naprawić.
- Po edycji `frontend/src/**/*.ts(x)`: `tsc --noEmit -p tsconfig.app.json`.
- Przed `git push`: `pytest -q -x` i `tsc`. Gdy coś pada, push jest zablokowany. Nie obchodź tego (`--no-verify`, inna powłoka),
  tylko napraw przyczynę.
- Podgląd i wyłączanie: `/hooks`.

## Git i praca zespołowa

- Pracujemy **prosto na `main`**, bez gałęzi i PR. Każdy gotowy krok to commit + `git push origin main`. `main` zawsze musi działać,
  bo z niego idzie demo.
- Nie commitujemy `.venv/`, `node_modules/`, cache, baz SQLite ani `.env`.
- Zmiany kontraktu API (`api/schemas.py` ↔ `frontend/src/api/types.ts`) ogłaszaj zespołowi.
- Przy kompaktowaniu kontekstu zachowaj: ID wymagań w toku, wyniki ostatnich testów i niezacommitowane zmiany.
