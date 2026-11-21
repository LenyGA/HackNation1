# CLAUDE.md

**RolnikSzukaWody** — zespół **GeoSatel**.

Projekt na HackNation 2026 (Bydgoszcz, 21–22.11.2026). Zadanie KOWR: **„Zatrzymaj wodę, chroń plony”**.
Aplikacja webowa dla rolnika: podajesz numer działki ewidencyjnej (lub klikasz ją na mapie) i wybierasz uprawę. Narzędzie pobiera
dane publiczne i liczy ocenę sytuacji wodnej (stan bieżący + 10 lat historii). Na tej podstawie generuje raport z rekomendacjami
retencyjnymi, agrotechnicznymi i nawodnieniowymi.

- Pełne wymagania, kryteria oceny i checklista zgłoszenia: @docs/REQUIREMENTS.md
- Źródła oryginalne (czytaj przy wątpliwościach): `docs/task/zadanie.pdf`, `docs/task/regulamin.pdf`, `docs/task/podstawy-naukowe.pdf`

## Zasady nadrzędne (łamanie = przegrana)

1. **Wynik jest LICZONY z pobranych danych, nigdy wpisany na sztywno.** Wyświetlenie gotowych rekomendacji nie spełnia wymagań.
   Każda rekomendacja musi wynikać z reguły, która sprawdza konkretne wartości wyliczone dla tej działki.
2. **Kolejność analizy jest obowiązkowa:** ocena sytuacji wodnej → przyczyny → retencja → agrotechnika → (opcjonalnie) nawadnianie.
   Bez kompletnej oceny (krok 1) nie generujemy rekomendacji.
3. **Data analizy to parametr, a nie „dziś”.** Jury podaje dowolną datę z ostatnich 10 lat. Wszystkie pobrane dane muszą być ograniczone
   do `<= analysis_date`, bo inaczej dane z przyszłości przeciekają do analizy. Okno historyczne to 10 lat wstecz od `analysis_date`.
4. **Brak danych mówimy wprost, bez pozornej precyzji.** Gdy źródło nie odpowie albo nie ma pokrycia (np. chmury na Sentinel-2),
   wynik ma status `missing` lub `degraded`, a raport mówi to rolnikowi wprost. Nigdy nie podstawiamy wartości domyślnej udającej pomiar.
   Zaokrąglamy sensownie (np. NDVI do 0,01, opad do 1 mm).
5. **Każda liczba w raporcie ma źródło i datę.** Model wyniku niesie `source`, `fetched_at`, `period` i `uncertainty`.
   Raport kończy się sekcjami „Źródła danych” i „Ograniczenia analizy”.
6. **Bez LLM i bez płatnych usług.** Tekst dla rolnika generujemy z szablonów (`backend/app/report/templates/`), wypełnianych wyliczonymi
   wartościami. Rolnik niczego nie kupuje, nie instaluje i nie zakłada konta. Nie dodawaj zależności od płatnych API.
7. **Do 30 s na działkę.** Zapytania do źródeł idą równolegle (async) i każde ma własny timeout. Cache na dysku. Rastry czytamy wyłącznie
   oknem bbox działki (COG + windowed read), nigdy całych scen.
8. **Ma działać dla każdej działki w Polsce.** Nie zakładaj konkretnego województwa, zasięgu danych ani układu współrzędnych.
9. **Prosty język.** UI i raport po polsku, bez żargonu GIS i teledetekcji. „NDVI” może się pojawić tylko w rozwijanym „Szczegóły
   dla zainteresowanych”, a w treści głównej piszemy np. „kondycja roślin”.
10. **Bez danych osobowych.** Żadnych kont ani logowania. Nie logujemy IP do raportów.

## Stack

| Warstwa | Technologia |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, httpx (async), rasterio, pystac-client, shapely, pyproj, numpy |
| Raport PDF | Jinja2 + WeasyPrint (ten sam szablon HTML służy do druku w przeglądarce) |
| Storage | SQLite (zapisane raporty z ID), cache odpowiedzi API na dysku (`backend/.cache/`, w .gitignore) |
| Frontend | React 19 + Vite + TypeScript 6.0 (nie 7 — typescript-eslint go jeszcze nie wspiera), Tailwind CSS 4 + shadcn/ui, MapLibre GL, React Router |
| Zależności | `pip` + `venv` (`backend/requirements.txt`), `npm` (`frontend/package-lock.json`) |
| Jakość | ruff, mypy, pytest · ESLint, `tsc --noEmit` |

## Komendy

```bash
# Backend (z katalogu backend/)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest                         # testy jednostkowe (szybkie, bez sieci)
pytest -m e2e                  # E2E na działkach referencyjnych (wymaga sieci, wolne)
ruff check . && ruff format . && mypy app

# Frontend (z katalogu frontend/)
npm install
npm run dev                    # http://localhost:5173, proxy /api -> :8000
npm run build && npm run lint && npx tsc --noEmit
```

Uruchamiaj pojedyncze testy (`pytest tests/analysis/test_water_balance.py -k nazwa`), a nie cały zestaw E2E po każdej zmianie.

## Architektura

```
backend/app/
  main.py               # FastAPI, CORS, routery
  api/                  # endpointy: /parcels, /analyses, /reports/{id}, /reports/{id}.pdf
  sources/              # jeden moduł = jedno zewnętrzne źródło; zwraca SourceResult[T]
    uldk.py             #   geometria i TERYT działki (GUGiK ULDK)
    open_meteo.py       #   opad, temperatura, ET0 (archiwum ERA5 + prognoza)
    sentinel2.py        #   NDVI/NDMI z Earth Search STAC (sentinel-2-l2a, COG)
    soilgrids.py        #   uziarnienie, SOC, retencja wodna gleby
    iung.py             #   podatność gleb na suszę, Monitoring Suszy Rolniczej (KBW)
    dem.py              #   NMT Geoportal WCS → spadki, ekspozycja, akumulacja spływu
    hydro.py            #   cieki, rowy, zbiorniki, mokradła (MPHP / BDOT10k / OSM Overpass)
  analysis/             # CZYSTE funkcje (bez I/O): bilans wodny, anomalie, ryzyko, przyczyny
  recommendations/      # silnik reguł: (wyniki analizy + uprawa) -> lista Recommendation z uzasadnieniem
  crops/                # katalog upraw: Kc (FAO-56), fazy fenologiczne, okresy krytyczne
  report/               # składanie raportu, szablony Jinja (tekst + HTML/PDF)
  core/                 # config, cache, http client, modele wspólne (SourceResult, Uncertainty)
backend/tests/          # unit (analysis/, recommendations/) + e2e/ (działki referencyjne)
frontend/src/
  pages/                # Start (wybór działki) → Analiza (postęp) → Raport
  components/map/       # MapLibre, warstwa ortofoto Geoportalu, wybór działki kliknięciem
  api/                  # typowany klient backendu
docs/                   # REQUIREMENTS.md, METHODOLOGY.md, DATA_SOURCES.md, task/ (PDF-y)
```

**Przepływ:** identyfikator działki lub klik (x, y) → ULDK (geometria) → równoległe pobranie wszystkich `sources/` →
`analysis/` (ocena) → `recommendations/` (reguły) → `report/` (szablony) → zapis do SQLite → JSON dla UI + PDF.

**Granice modułów:**
- `sources/` nie zawiera logiki domenowej, tylko pobieranie, parsowanie i normalizację jednostek.
- `analysis/` i `recommendations/` nie robią I/O, więc testuje się je na danych z fixture.
- Każde źródło zwraca `SourceResult` z `status: ok | degraded | missing`, `source`, `license`, `fetched_at`, `data`.
  Analiza musi obsłużyć każdy status. Awaria jednego źródła nie wywraca całej analizy, tylko obniża pewność wyniku.

## Metodyka (szczegóły i bibliografia w `docs/METHODOLOGY.md`)

- **Bilans wodny:** klimatyczny bilans wodny KBW = P − ET0 (ET0 FAO Penman–Monteith z Open-Meteo), z ET uprawy ETc = Kc · ET0
  (Kc z FAO-56 dla fazy rozwoju). Progi suszy rolniczej liczymy wg metodyki IUNG-PIB (KBW vs kategoria gleby).
- **Kontekst wieloletni:** bieżące wartości porównujemy z rozkładem z tych samych okresów w 10 poprzednich latach
  (percentyl/anomalia, SPI tam, gdzie to sensowne). Rozróżniamy **bieżącą suszę** od **strukturalnej podatności** działki.
- **Satelita:** NDVI = (B08−B04)/(B08+B04), NDMI = (B08−B11)/(B08+B11). Chmury maskujemy pasmem SCL. Interpretacja **zależy od uprawy
  i fazy**: niski NDVI w marcu przy kukurydzy to norma, a nie susza. Porównujemy z krzywą wieloletnią tej działki, nie z progiem globalnym.
  Wskaźników satelitarnych nigdy nie interpretujemy samodzielnie.
- **Przyczyny** (każda ma flagę i dowód liczbowy): deficyt opadów i wysoka temperatura · niska retencja gleby (lekka, mało SOC) ·
  nadmierny odpływ (spadki, brak elementów retencji w otoczeniu) · wrażliwość uprawy w fazie krytycznej.
- **Priorytet działań:** najpierw retencja („retain water where it falls”, NWRM), potem agrotechnika (międzyplony, mulcz, resztki
  pożniwne, uprawa uproszczona, SOC), a nawadnianie na końcu, z terminem i dawką.
- **Niepewność:** każdy wskaźnik ma poziom pewności (wysoka/średnia/niska) zależny od kompletności danych, rozdzielczości
  (np. SoilGrids 250 m vs działka) i liczby bezchmurnych scen.

## Pułapki dotyczące danych

- **Format ID działki:** `WWPPGG_R.OOOO.NR` (np. `141201_1.0001.6509`). Numery z `/` (np. `123/4`) są poprawne, więc trzeba je
  URL-encodować. Dla kliknięcia używaj `GetParcelByXY`. ULDK domyślnie zwraca EPSG:2180, a parametr `srid=4326` daje WGS84.
- **Układy współrzędnych:** front działa w EPSG:4326/3857, polskie dane w EPSG:2180, a Sentinel-2 w UTM (32633/32634, w zależności
  od strefy). Zawsze reprojektuj geometrię przez `pyproj` przed odczytem rastra.
- **Open-Meteo:** archiwum ERA5 ma opóźnienie ~5 dni, więc dla `analysis_date` ≈ dziś dociągamy dane z endpointu forecast.
  Darmowe API jest na licencji niekomercyjnej (CC BY 4.0), co trzeba zapisać w README.
- **Sentinel-2:** pełne 10 lat scen nie zmieści się w 30 s. Wybieramy maks. 1 najlepszą scenę na okres (np. dekadę lub miesiąc
  sezonu wegetacyjnego) z filtrem `eo:cloud_cover`. Historyczny profil działki cache'ujemy, bo nie zmienia się wstecz.
  Działka mniejsza niż kilka pikseli 10 m daje niską pewność wyniku.
- **SoilGrids REST** bywa wolne lub niedostępne, dlatego potrzebny jest twardy timeout i status `missing`, a nie wywrócenie analizy.
- Każde nowe źródło **dopisz od razu** do `docs/DATA_SOURCES.md`: URL, licencja, zakres czasowy i przestrzenny, czy pobierane na żywo
  czy wcześniej (z datą pobrania). Tego wymaga README dla jury.

## Konwencje kodu

- Kod, nazwy, komentarze i commity **po angielsku**. Teksty UI i raportu **po polsku**, trzymane w szablonach/słownikach, nie w logice.
- Python: pełne type hints, modele Pydantic na granicach (API, `SourceResult`), jednostki w nazwach pól (`precip_mm`, `et0_mm`, `slope_pct`).
- Frontend: komponenty funkcyjne, typy API współdzielone w `frontend/src/api/types.ts`. Bez `any`.
- Sekrety tylko w `.env` (w `.gitignore`), a w repo trzymamy `.env.example`. Obecnie żaden klucz nie jest wymagany i tak ma zostać.
- Walidacja wejścia: format ID działki, zakres dat (≤ dziś, ≥ dziś − 10 lat), uprawa z listy. Rate limiting na endpoint analizy.

## Testy

- **Unit (obowiązkowe dla `analysis/` i `recommendations/`):** fixture z zapisanymi odpowiedziami źródeł (`tests/fixtures/`),
  bez sieci. Każda nowa reguła rekomendacji dostaje test „kiedy się odpala” i „kiedy NIE”.
- **E2E (`pytest -m e2e`):** 5 działek referencyjnych z różnych regionów Polski (gleby lekkie/ciężkie, płasko/spadki) dla dwóch dat
  (bieżąca i historyczna). Sprawdzamy, czy raport powstaje w < 30 s, ma wszystkie sekcje, a braki danych są jawne.
  Lista działek: `backend/tests/e2e/parcels.yaml`.
- Przed zgłoszeniem zmiany jako „gotowej” uruchom testy unit, ruff, mypy i `tsc`. Jeśli dotykasz UI, sprawdź je w przeglądarce
  na szerokości desktopowej i mobilnej.

## Praca zespołowa

- `main` ma zawsze działać, bo z niego robimy demo. Pracujemy prosto na `main` (patrz sekcja Git), więc przed pushem uruchom testy i lintery.
- Małe commity w stylu Conventional Commits (`feat(sources): add SoilGrids client`).
- **Repo jest prywatne do końca wydarzenia** (wymóg regulaminu). Nie zmieniaj widoczności i nie publikuj kodu gdzie indziej.
- Zmiany w kontrakcie API (`api/`, `frontend/src/api/types.ts`) ogłaszaj zespołowi, bo dotykają frontu i backendu jednocześnie.
- Nowa zależność: sprawdź licencję (musi pozwalać KOWR na przejęcie praw, więc bez GPL w kodzie dystrybuowanym, jeśli da się
  tego uniknąć) i dopisz ją do tabeli w README.

## Otwarte decyzje (TODO)

- [ ] Hosting wersji dla jury (publiczny link) oraz `docker-compose.yml` jako zapasowa instrukcja uruchomienia.
- [x] Nazwa zespołu i tytuł rozwiązania: zespół **GeoSatel**, tytuł **RolnikSzukaWody**.
- [ ] Dokładna lista upraw. Planowane: pszenica ozima, żyto, jęczmień jary, rzepak ozimy, kukurydza, ziemniaki,
      buraki cukrowe, użytki zielone, warzywa polowe.

## Git

- Commitujemy i pushujemy **prosto na `main`** (bez gałęzi funkcyjnych i PR). Każdy gotowy krok planu = commit + `git push`.
- Nie commitujemy zależności (`.venv/`, `node_modules/`), cache, baz SQLite ani `.env` — pilnuje tego `.gitignore`.
