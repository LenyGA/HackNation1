# GeoSatel

HackNation 2026 (Bydgoszcz, 21–22.11.2026) · zadanie KOWR **„Zatrzymaj wodę, chroń plony”**.

Aplikacja webowa dla rolnika. Wystarczy podać numer działki ewidencyjnej, kliknąć działkę na mapie albo wpisać adres, a potem
wybrać uprawę i datę analizy (dziś lub dowolny dzień z ostatnich 10 lat). Aplikacja pobiera dane publiczne o pogodzie, zdjęcia
satelitarne oraz dane o glebie, terenie i wodach. Z nich **liczy** sytuację wodną działki na dzień analizy i jej podatność na suszę
w ostatnich 10 latach, a na końcu tworzy raport z przyczynami niedoboru wody i działaniami: najpierw zatrzymanie wody (retencja),
potem uprawa i nawadnianie.

**Działająca wersja:** https://129.121.162.156.sslip.io · bez konta, instalacji i opłat, działa też na telefonie.

| | |
|---|---|
| Przykładowe raporty PDF | [`docs/sample-reports/`](docs/sample-reports/) |
| Metodyka, wzory, progi, odwołania do literatury | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) |
| Źródła danych, licencje, daty pobrania | [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) |
| Wymagania zadania i checklista | [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) |
| Licencja kodu | [`LICENSE`](LICENSE) (MIT, © GeoSatel) |

---

## 1. Uruchomienie

Żaden klucz API, konto ani płatna usługa nie są potrzebne.

### Docker (zalecane)

Wymagany jest tylko Docker z Compose v2.

```bash
docker compose up -d --build        # http://localhost  (Caddy na porcie 80 → aplikacja)
docker compose logs -f app          # logi (bez adresów IP)
docker compose down                 # zatrzymanie; raporty i cache zostają w wolumenie app-data
```

Z własną domeną (automatyczny certyfikat HTTPS z Let's Encrypt): `SITE_ADDRESS=moja.domena.pl docker compose up -d --build`.

### Lokalnie, do rozwoju

Wymagane: Python 3.12 i Node.js 22.

```bash
# Backend (katalog backend/)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000              # API: http://localhost:8000/api, dokumentacja: /docs

# Frontend (katalog frontend/, drugi terminal)
npm install
npm run dev                                            # http://localhost:5173, proxy /api → :8000
```

WeasyPrint (PDF) potrzebuje bibliotek Pango. Na macOS: `brew install pango`, na Debianie/Ubuntu: `apt install libpango-1.0-0
libpangoft2-1.0-0 libharfbuzz-subset0`. Bez nich działa wszystko poza pobieraniem PDF, a druk z przeglądarki działa nadal.

Ustawienia (opcjonalne, zmienne `RSW_*`, wartości domyślne w `backend/app/core/config.py`): katalog cache, ścieżka bazy SQLite,
limity zapytań, liczba równoległych analiz, timeout źródeł.

### Testy i kontrola jakości

```bash
# backend/
pytest                         # testy jednostkowe, bez sieci (ok. 1280 testów, ok. 5 min)
pytest -m e2e tests/e2e/test_reports.py   # 6 działek referencyjnych × 2 daty, na żywo (sieć, kilka minut)
ruff check . && mypy app       # lint i typy

# frontend/
npm run lint && npm test && npm run build      # ESLint, vitest, tsc -b + vite build
```

### Wdrożenie na VPS

1. Jednorazowo na serwerze (Ubuntu, root): `scp deploy/setup-vps.sh root@<IP>:/root/ && ssh root@<IP> bash /root/setup-vps.sh`
   (Docker, 2 GB swap, zapora: tylko porty 22, 80 i 443).
2. Z własnego komputera, z czystego `main`: `deploy/deploy.sh root@<IP> [domena]`. Bez domeny aplikacja dostaje adres
   `https://<IP>.sslip.io`. Skrypt buduje obraz na serwerze, czeka na `/api/health` i rozgrzewa cache (`scripts/warm_cache.py`).
3. Testy E2E z adresu serwera: `deploy/e2e-vps.sh root@<IP>`.

## 2. Funkcje

**Wybór działki** na trzy sposoby: numer ewidencyjny (np. `141201_1.0001.6509`, także z `/`), kliknięcie na mapie (ortofotomapa
Geoportalu, przycisk „Moja lokalizacja”) albo adres (miejscowość, ulica, numer). Można dodać do 5 sąsiednich działek gospodarstwa
(≤ 2 km); wtedy ilości wody w m³ i opłacalność nawadniania są liczone dla sumy powierzchni.

**Uprawa** z listy 13 pozycji: pszenica ozima, żyto, jęczmień jary, rzepak ozimy, kukurydza, ziemniaki, buraki cukrowe,
użytki zielone, warzywa polowe, sad (jabłonie i grusze; wiśnie i czereśnie; śliwy) oraz krzewy owocowe.

**Data analizy:** dziś albo dowolny dzień z ostatnich 10 lat. Wszystkie dane zależne od czasu są ucinane do tej daty, więc dane
z przyszłości nie przeciekają do analizy.

**Raport** w kolejności wymaganej przez zadanie. Każda sekcja zaczyna się jednozdaniowym werdyktem, a szczegóły są rozwijane:

1. **Podsumowanie:** kafelki z kolorem: zapas wody w glebie, najważniejsze działanie, zmiana klimatu na działce, woda
   potrzebna w roku suchym, zagrożenie powodzią.
2. **Stan bieżący:** zapas wody w glebie (X z Y mm) i próg, poniżej którego uprawa cierpi, bilans opadu i parowania z 60 dni na tle 10 lat, wykres deszczu i potrzeb wodnych uprawy na tle
   tych samych dni w 10 poprzednich latach z wyborem zakresu („Dane z ostatnich: 24 h / 7 dni / miesiąc / 6 miesięcy / rok /
   własny”; wybrany zakres trafia też do PDF i wydruku),
   porównanie z oficjalnym progiem suszy rolniczej IUNG-PIB dla uprawy i kategorii gleby, kondycja roślin z satelity
   (w kontekście uprawy i fazy rozwoju) oraz poziom wód gruntowych z najbliższej stacji PIG-PIB.
3. **Podatność 10-letnia:** w ilu latach i miesiącach było za sucho, trendy klimatu na działce, strefy zagrożenia powodziowego
   i podtopień.
4. **Przyczyny,** każda z dowodem liczbowym: brak opadów i upał, słaba retencja gleby (lekka, mało próchnicy), szybki odpływ
   (spadki, brak rowów, oczek i zadrzewień), wrażliwa faza uprawy.
5. **Retencja (najpierw):** 5 metod (oczko lub staw w zagłębieniu, zastawka lub drenaż kontrolowany, deszczówka z dachów, studnia,
   pasy zadrzewień) ze statusem POLECANE / WARUNKOWO / NIEZALECANE / BRAK DANYCH, uzasadnieniem z danych działki
   i formalnościami z Prawa wodnego. Do tego karta „ile wody da retencja”: objętość zagłębień w porównaniu z potrzebami
   nawadniania w roku suchym. Profil spadku terenu i mapa z zagłębieniami, ciekami i rowami.
6. **Agrotechnika:** międzyplony, mulcz i resztki pożniwne, uprawa uproszczona, próchnica, uprawa w poprzek stoku; dla sadów
   osobne reguły (ściółkowanie, murawa w międzyrzędziach).
7. **Nawadnianie (na końcu):** termin i dawka, plan wody na sezon (mediana i rok suchy, 80. percentyl), dobór technologii
   (deszczownia szpulowa, pivot, kroplowe) na podstawie kształtu działki oraz opłacalność z widełkami i jawnymi założeniami.
8. **Zalecenia** podzielone na „teraz” (dopasowane do daty i fazy uprawy) i „przed następnym sezonem”.
9. **Źródła danych** z datą pobrania, **ograniczenia analizy** i jawne braki danych (np. „zdjęcie satelitarne niedostępne:
   chmury”).

**Dwa warianty raportu:** Podstawowy (1–2 strony A4) i Pełny (wszystkie wykresy, mapa, tabele). Przełącznik działa na stronie,
w PDF i przy druku. Każdy raport jest zapisany w systemie pod stałym linkiem.

## 3. Architektura

```
przeglądarka (React + MapLibre)
      │  POST /api/analyses  →  GET /api/analyses/{id} (postęp źródeł)  →  GET /api/reports/{id}[.pdf]
      ▼
Caddy (HTTPS, CSP, HSTS, limit rozmiaru zapytania)
      ▼
FastAPI (Python 3.12)
  sources/          1 moduł = 1 źródło zewnętrzne, równolegle (asyncio), każde z własnym timeoutem
                    → SourceResult(status: ok | degraded | missing, source, license, fetched_at, data)
  analysis/         czyste funkcje bez I/O: bilans wodny FAO-56, gleba, historia 10 lat, teren, trendy, symulator
  recommendations/  silnik reguł: (wyniki analizy + uprawa) → zalecenia z uzasadnieniem liczbowym
  report/           model raportu → szablony Jinja2 → JSON dla UI, HTML do druku, PDF (WeasyPrint)
  SQLite            zapisane raporty · cache odpowiedzi źródeł na dysku
```

Przepływ: numer działki, punkt lub adres → ULDK (geometria) → równoległe pobranie 8 kolejnych źródeł → ocena sytuacji wodnej → przyczyny
→ retencja → agrotechnika → nawadnianie → raport. Bez kompletnej oceny (krok 1) reguły nie wydają zaleceń. Awaria jednego źródła
obniża pewność wyniku i jest opisana w raporcie, ale nie przerywa analizy.

Kod: `backend/app/{api,core,sources,analysis,recommendations,crops,report}`, `frontend/src/{pages,components,api}`,
testy w `backend/tests/` (fixture'y z zapisanymi odpowiedziami źródeł w `tests/fixtures/`), wdrożenie w `deploy/`.

## 4. Źródła i zakresy danych

| Kategoria | Źródło | Co bierzemy | Zakres przestrzenny i czasowy |
|---|---|---|---|
| Działka | GUGiK ULDK | geometria, TERYT, gmina, obręb | cała Polska, stan bieżący |
| Adres | GUGiK, Usługa Uniwersalnego Geokodowania (punkty adresowe PRG) | adres → punkt → działka | cała Polska, stan bieżący |
| Meteo | Open-Meteo: archiwum ERA5 + prognoza (dni bieżące); zapas: NASA POWER | opad, temperatura, ET0 (FAO Penman–Monteith) | siatka ok. 10 km (NASA POWER 0,5° × 0,625°, ok. 50 km); 11 lat do dnia analizy + 7 dni prognozy dla „dziś” |
| Satelita | Sentinel-2 L2A (Copernicus) przez Microsoft Planetary Computer | NDVI i NDMI z maską chmur SCL, tylko okno działki | 10–20 m; do 3 scen z 45 dni przed datą + 1 scena na rok z 10 lat |
| Gleba | ISRIC SoilGrids 2.0 (WCS) | piasek, pył, ił, węgiel organiczny, gęstość do 100 cm → retencja wody, kategoria gleby I–IV | 250 m, stan bieżący |
| Teren | NMT 1 m GUGiK (lidar, usługa wysokości punktów); zapas: Copernicus DEM GLO-30 | spadki, ekspozycja, zagłębienia, profil, kierunek spływu | działka + 150 m, siatka 5 m (NMT) lub 30 m |
| Użytkowanie terenu | ESA WorldCover 2020 (v100) i 2021 (v200), 10 m | pole, łąka, sad, drzewa, wody, mokradła na działce i w pierścieniu 500 m | najnowsza edycja nie późniejsza niż data analizy (dla dat sprzed 2021 r. edycja 2020, z informacją w raporcie) |
| Hydrologia | OpenStreetMap (Overpass, 3 serwery); zapas: WorldCover | rowy, cieki, zbiorniki, mokradła, lasy w 1 km | stan bieżący |
| Powodzie, podtopienia | Wody Polskie ISOK (mapy zagrożenia powodziowego, powodzie historyczne), PIG-PIB (podtopienia) | scenariusze 10, 100 i 500 lat w punktach działki | II cykl planistyczny (2020–2022) |
| Wody podziemne | PIG-PIB / PSH, automatyczny monitoring | głębokość zwierciadła na najbliższej stacji ≤ 50 km, 60 dni przed datą i te same dni 1–3 lata wcześniej | wiele stacji mierzy dopiero od 2026 r. |
| Progi suszy | Rozporządzenie MRiRW, Dz.U. 2019 poz. 739 (wartości KBW IUNG-PIB) | krytyczny bilans wodny dla uprawy, kategorii gleby i okresu | 21.III–30.IX, 12 upraw |
| Ekonomia nawadniania | GUS (plony 2024, ceny skupu 12.2024), FAO Paper 33/66 (Ky) | widełki przychodu z nawadniania | średnie krajowe |
| Podkład mapy | Ortofotomapa GUGiK (WMS), OpenStreetMap | mapa w aplikacji i w PDF | stan bieżący |

Szczegóły (adresy usług, timeouty, cache, zmierzone czasy, zachowanie przy braku danych): [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## 5. Dane na żywo i dane pobrane wcześniej

**Wynik zawsze liczy aplikacja w chwili analizy.** Nie ma żadnych wcześniej przygotowanych wyników dla konkretnych działek.

- **Na żywo** (w chwili analizy, z cache na dysku): wszystkie źródła z tabeli w rozdz. 4 poza wierszami „Progi suszy”
  i „Ekonomia nawadniania” (pobrane wcześniej, niżej). Ortofotomapę do PDF pobieramy przy pierwszym wydruku raportu. Cache: dane historyczne (pogoda sprzed 10+ dni, profil satelitarny, gleba, teren) bez wygasania,
  bo nie zmieniają się wstecz; dane bieżące 1 h; działka i hydrologia OSM 1 dzień; adresy 7 dni; strefy powodziowe
  i ortofotomapa 30 dni. Data pobrania każdego źródła jest
  w sekcji „Źródła danych” raportu.
- **Pobrane wcześniej i dołączone do aplikacji:**

| Plik | Źródło | Pobrane |
|---|---|---|
| `backend/app/crops/iung_thresholds.yaml` | progi KBW z Dz.U. 2019 poz. 739, zweryfikowane z tab. 3 ekspertyzy IUNG-PIB 2019 | 22.11.2026 |
| `backend/app/crops/economics.yaml` | GUS: plony 2024 i ceny 12.2024; FAO Paper 33/66 (Ky); koszty instalacji = założenia zespołu | 22.11.2026 |
| `frontend/src/components/map/poland.json` | obrys Polski z PRG GUGiK (sprawdzenie, czy klik leży w Polsce) | 21.11.2026 |
| `backend/app/crops/catalog.yaml` | współczynniki Kc i długości faz z FAO-56 (tab. 11–12), okresy krytyczne upraw | 21–22.11.2026 |

## 6. Biblioteki, komponenty, usługi i narzędzia AI

**Backend (Python):** FastAPI, Uvicorn, Pydantic + pydantic-settings, httpx (async), rasterio (GDAL, odczyt COG oknem), pystac-client,
Shapely, pyproj, NumPy, Jinja2, WeasyPrint (z pyphen), PyYAML, python-dateutil. Deweloperskie: pytest, pytest-asyncio, respx, ruff, mypy.

**Frontend:** React 19, React Router, MapLibre GL, Tailwind CSS 4, shadcn/ui (Radix UI, class-variance-authority, clsx,
tailwind-merge, tw-animate-css, cn), ikony lucide-react, Vite, TypeScript 6. Deweloperskie: ESLint + typescript-eslint, vitest.

**Infrastruktura:** Docker, Caddy 2 (HTTPS z Let's Encrypt), VPS Ubuntu, adres `sslip.io`.

**Usługi zewnętrzne:** wyłącznie bezpłatne usługi danych z rozdz. 4. Bez kluczy API i kont.

**Modele:** aplikacja **nie używa modeli AI ani LLM** w działaniu. Tekst raportu powstaje z szablonów Jinja2 wypełnianych
wyliczonymi wartościami, więc ten sam zestaw danych zawsze daje ten sam raport. Modele fizyczne i empiryczne: FAO-56
(Penman–Monteith, Kc, bilans strefy korzeniowej), progi KBW IUNG-PIB, FAO-33 (Ky), Theil–Sen (trendy), priority-flood (zagłębienia).

**Narzędzia AI przy tworzeniu kodu:** zespół korzystał z **Claude Code** (Anthropic, model Claude Opus) jako asystenta
programistycznego: pisanie i refaktoryzacja kodu, testy, przegląd kodu, dokumentacja. Każdą zmianę sprawdzały testy
automatyczne i zespół. Metodykę, progi i źródła sprawdzaliśmy z publikacjami (bibliografia w `docs/METHODOLOGY.md`).

## 7. Licencje

**Kod aplikacji:** MIT, © 2026 GeoSatel ([`LICENSE`](LICENSE)). Zależności mają licencje permisywne (MIT, BSD, Apache-2.0,
ISC) albo licencje słabego copyleftu, które nie wymagają otwarcia naszego kodu: MPL-2.0 (certifi; lightningcss tylko przy
budowaniu frontu), LGPL-2.1 (biblioteka GEOS w kole Shapely, Pango w obrazie Docker, obie linkowane dynamicznie). pyphen
(dzielenie wyrazów w WeasyPrint) ma licencję do wyboru GPL/LGPL/MPL-1.1 i używamy go na MPL-1.1. Żaden komponent nie wymaga
GPL ani AGPL, więc autorskie prawa majątkowe do kodu zespołu można przenieść na KOWR (regulamin § 5).

| Komponent | Licencja |
|---|---|
| FastAPI 0.165, Pydantic 2.14, pydantic-settings, pyproj, PyYAML, ruff, mypy, pytest | MIT |
| Uvicorn, httpx, rasterio, Shapely, python-dateutil, Jinja2, WeasyPrint, respx | BSD-3-Clause |
| NumPy | BSD-3-Clause (z częściami 0BSD, MIT, Zlib) |
| pystac-client, pytest-asyncio | Apache-2.0 |
| React 19, React Router 7, Tailwind CSS 4, Radix UI, clsx, tailwind-merge, tw-animate-css, cn, Vite, ESLint, vitest | MIT |
| MapLibre GL 6 | BSD-3-Clause |
| TypeScript, class-variance-authority | Apache-2.0 |
| lucide-react | ISC |
| Caddy 2 (obraz Docker) | Apache-2.0 |
| GDAL (w kole rasterio) | MIT |
| certifi (przez httpx) | MPL-2.0 |
| pyphen (przez WeasyPrint) | GPL-2.0+ / LGPL-2.1+ / MPL-1.1 do wyboru (używamy MPL-1.1); słownik pl_PL: LPPL |
| GEOS (w kole Shapely), Pango (biblioteka systemowa w obrazie) | LGPL-2.1, linkowane dynamicznie |
| Czcionki DejaVu i Liberation (PDF) | Bitstream Vera / SIL OFL 1.1 |
| lightningcss (tylko przy budowaniu, przez Tailwind) | MPL-2.0 |

**Dane:**

| Źródło | Licencja i warunki |
|---|---|
| GUGiK: ULDK, UUG, NMT, ortofotomapa, PRG | dane publiczne PZGiK, bezpłatne (Prawo geodezyjne i kartograficzne, art. 40a ust. 2) |
| Open-Meteo | CC BY 4.0. Darmowe API **tylko do użytku niekomercyjnego**, limit 10 000 wywołań/dzień; wdrożenie produkcyjne KOWR wymaga planu komercyjnego lub własnej instancji (open source, AGPL; uruchamiana jako osobna usługa, nie jest częścią naszego kodu) |
| NASA POWER | dane NASA, bezpłatne, z podaniem źródła |
| Sentinel-2, Copernicus DEM | dane Copernicus, bezpłatne, z podaniem źródła |
| Microsoft Planetary Computer | bezpłatny dostęp anonimowy (token SAS bez konta); dane na licencjach jak wyżej |
| ISRIC SoilGrids 2.0 | CC BY 4.0 |
| ESA WorldCover 2021 | CC BY 4.0 |
| OpenStreetMap | ODbL 1.0 (© współtwórcy OpenStreetMap); kafle mapy wg polityki OSMF |
| Wody Polskie (ISOK), PIG-PIB (PSH, podtopienia) | dane publiczne, bezpłatne, z podaniem źródła |
| Dz.U. 2019 poz. 739 | akt prawny, nie podlega prawu autorskiemu (art. 4 pkt 1 ustawy o prawie autorskim) |
| GUS | informacja publiczna, ponowne wykorzystanie z podaniem źródła |

## 8. Znane ograniczenia

**Dane:**
- Pogoda pochodzi z modelu w siatce ok. 10 km (NASA POWER 0,5° × 0,625°, ok. 50 km), a nie z deszczomierza na polu. Lokalna burza może nie być
  widoczna. Dane z ostatnich dni są wstępne (prognoza).
- Bilans liczymy z ET0 FAO-56, a nie wzorem IUNG-PIB na parowanie, więc może różnić się od mapy susza.iung.pulawy.pl. Progi
  z 2019 r. stosujemy też dla dat wcześniejszych. Dla użytków zielonych oficjalnych progów nie ma.
- Gleba pochodzi z mapy światowej 250 m (SoilGrids), a nie z polskiej mapy glebowo-rolniczej. Kategoria gleby I–IV jest
  przybliżona.
- Hydrologia z OSM bywa niepełna, zwłaszcza dla małych rowów i oczek. Publiczne serwery Overpass bywają przeciążone: wtedy
  zadrzewienia, wody i mokradła bierzemy z WorldCover, ale rowów i cieków nie ma. Fallbacku z MPHP / BDOT10k nie ma, bo nie
  znaleźliśmy publicznego WFS.
- Rowy, oczka, zadrzewienia, użytkowanie terenu (WorldCover 2020 lub 2021), gleba, teren i strefy powodziowe opisują stan obecny, a nie dzień analizy.
- Wody gruntowe: trend tylko do 3 lat wstecz, a wiele stacji mierzy dopiero od 2026 r. Danych IMGW hydro nie ma, bo nie mają
  historii.
- Nie wiemy, co rosło na działce w poprzednich latach, więc porównanie satelity z historią jest pomocnicze. Satelity nie
  interpretujemy samodzielnie, tylko w kontekście uprawy i fazy.
- Fazy rozwoju i okresy krytyczne to typowe terminy dla Polski (dla sadów: przyjęte przez zespół), a nie obserwacja z pola.
- Koszty instalacji nawadniania to jawne założenia zespołu (brak otwartego cennika), pokazane jako widełki.

**Model:**
- Bilans wody w glebie nie uwzględnia podsiąku wody gruntowej, wcześniejszego nawadniania ani spływu z sąsiednich pól.
- Gospodarstwo (kilka działek): glebę, teren i satelitę analizujemy tylko dla działki głównej. Wspólnego modelu terenu dla
  stykających się działek nie liczymy.
- Nie sprawdzamy dostępu do wody do nawadniania. Wymogi Prawa wodnego podajemy orientacyjnie; wiążąco decydują Wody Polskie.
- Poza zakresem: termin siewu i sposób uprawy jako dane wejściowe, kopalnie odkrywkowe i śnieg w bilansie, wyszukiwanie po
  gminie i obrębie, automatyczne porównanie z IUNG SMSR / EDO.

**Techniczne:**
- Darmowe API Open-Meteo ma dzienny limit na adres IP. Cache ogranicza zużycie, a po wyczerpaniu limitu działa zapas NASA POWER
  (raport pokazuje wtedy „źródło zapasowe”).
- ULDK przy serii zapytań z jednego adresu potrafi ograniczać klienta na kilka minut; aplikacja ponawia zapytanie i pokazuje
  polski komunikat.
- Bardzo małe działki (kilka pikseli 10 m) dają niską pewność wyników z satelity i terenu. Działki skrajnie duże i wieloczęściowe
  nie były systematycznie testowane. Działka, która nie wygląda na pole, łąkę ani sad, dostaje ostrzeżenie.
- Aplikację rozwijaliśmy i sprawdzaliśmy głównie w Chrome (komputer i telefon). Pełnego testu we wszystkich przeglądarkach
  z zadania (Firefox, Edge, Opera na Windows, Safari), łącznie z PDF i drukiem, nie zdążyliśmy przeprowadzić systematycznie.
  **[ZESPÓŁ: zaktualizować po teście T4]**

## 9. Weryfikacja wyników i rekomendacji

- **Testy jednostkowe (ok. 1280, bez sieci):** wzory (bilans FAO-56, retencja gleby, percentyle, trendy, zagłębienia,
  symulator) na danych z fixture'ów, w tym przypadki brzegowe i statusy `missing` / `degraded` każdego źródła. Każda reguła
  zalecenia ma test „odpala się” i „nie odpala się”. Symulator ma test niezmiennika: dołożenie działania nigdy nie zwiększa
  liczby dni stresu.
- **Testy E2E (`pytest -m e2e tests/e2e/test_reports.py`):** 6 działek referencyjnych z różnych regionów (`backend/tests/e2e/parcels.yaml`: gleba lekka
  w Wielkopolsce, ciężka na Żuławach, stok na Pogórzu, dolina Noteci, okolica kopalni Bełchatów, sad w Grójcu) × 2 daty
  (bieżąca i 15.07.2019). Sprawdzamy, że raport powstaje w < 30 s, ma wszystkie sekcje, braki danych są jawne, a poziom suszy,
  zalecenia i statusy źródeł zgadzają się z zapisanym wzorcem (`baseline.json`). Ostatni przebieg na serwerze: 12/12, 8–18 s.
- **Zgodność z nauką:** progi suszy przepisane z Dz.U. 2019 poz. 739 i porównane wartość po wartości z tab. 3 ekspertyzy IUNG-PIB
  2019; Kc i fazy z FAO-56; metody retencji wg katalogu NWRM (Natural Water Retention Measures, Komisja Europejska) i załącznika naukowego
  KOWR. Każdy próg jest nazwaną stałą w kodzie opisaną w `docs/METHODOLOGY.md`.
- **Wiarygodność:** każda liczba w raporcie ma źródło, datę pobrania i poziom pewności (wysoka / średnia / niska), zależny od
  kompletności danych, rozdzielczości i liczby bezchmurnych scen.
- **Jak sprawdzić samodzielnie:** dla tej samej daty porównać werdykt suszy z mapą IUNG-PIB (https://susza.iung.pulawy.pl/,
  okresy sześciodekadowe) i z European Drought Observatory (CDI). Pamiętaj, że nasz bilans liczymy z ET0 FAO-56, a nie wzorem IUNG
  (rozdz. 8). Pełny raport pokazuje w „Szczegółach” wszystkie wartości pośrednie (KBW, TAW, NDVI, percentyle).

## 10. Koszty i usługi płatne

- **Dla rolnika:** **0 zł.** Bez konta, instalacji, płatnych licencji, znajomości GIS i specjalistycznego sprzętu — wystarczy przeglądarka internetowa.
- **Usługi płatne w prototypie:** **brak.** Wszystkie źródła danych są bezpłatne i nie wymagają kluczy API.
- **Infrastruktura demonstracyjna prototypu:** 1 VPS (1 vCPU, 2 GB RAM, 48 GB NVMe, Docker + Caddy) do oceny przez Jury — orientacyjnie **40–60 zł netto/mies.** Darmowa alternatywa (**0 zł**): uruchomienie lokalne w Dockerze (`docker compose up -d --build`).
- **Ograniczenie prototypu:** pojedynczy VPS (SPOF) oraz darmowe warstwy API (niekomercyjny plan Open-Meteo z limitem 10 000 wywołań/dobę, publiczny Overpass, limitowany ULDK, anonimowe tokeny Planetary Computer) nie spełniają wymogów KRI (Dz.U. 2024 poz. 773) ani SLA dla wdrożenia krajowego.
- **Docelowy dostęp do danych w produkcji (dla operatora — KOWR):**
  - **Rejestry publiczne (0 zł licencji):** GUGiK EGiB/NMT/BDOT10k (art. 40a ust. 2 PGiK — bez danych osobowych), PGW Wody Polskie (MPHP/ISOK), PIG-PIB (PSH), GUS, Dz.U. 2019 poz. 739 oraz cyfrowa Mapa Glebowo-Rolnicza IUNG-PIB i dane IMGW-PIB (w ramach porozumień międzyinstytucjonalnych).
  - **Usługi wymagające opłat SLA lub własnego hostingu:** meteorologia — plan komercyjny Open-Meteo (szac. 1–3 tys. zł/mies.) albo własny import IMGW-PIB/ERA5 (0 zł licencji; uwaga: ewentualny własny serwer Open-Meteo na AGPL-3.0 wyłącznie jako odrębny mikroserwis, nielinkowany z kodem GeoSatel; bezpłatny fallback NASA POWER już działa); satelita Sentinel-2 — gwarantowane przetwarzanie wsadowe CDSE / Sentinel Hub (1,5–4,5 tys. zł/mies.); podkład mapowy — własny serwer kafli lub komercyjny CDN zamiast darmowych serwerów OSMF (1–2,5 tys. zł/mies.; warstwa OSM ODbL 1.0 w osobnym schemacie *Collective Database*, bez mieszania z BDOT10k/MPHP).

## 11. Skalowalność

### Mechanizmy już wdrożone w prototypie
- **Cache dyskowy (TTL):** dane historyczne niezmienne wstecz (pogoda > 10 dni, historia satelitarna, gleba, NMT) nie wygasają; bieżąca pogoda 1 h; ULDK i OSM 24 h; adresy 7 dni; ISOK i ortofotomapa 30 dni. Powtórna analiza tej samej działki lub komórki siatki pogodowej (10 km) trwa < 1 s/źródło i nie zużywa limitów API. Po wdrożeniu `scripts/warm_cache.py` rozgrzewa cache dla 2 działek referencyjnych.
- **Zapis wyników:** każdy raport trafia do SQLite pod stałym ID — ponowne otwarcie, PDF i druk nie wykonują zapytań zewnętrznych.
- **Ograniczanie zapytań i izolacja błędów:** maks. 4 analizy jednocześnie, kolejka do 50 zadań (dalej HTTP 429), limity na klienta (10 analiz/min, 30/10 min, 120 zapytań o działkę/min), indywidualne timeouty, automatyczne fallbacki (NASA POWER, Copernicus DEM, WorldCover) i odczyt rastrów wyłącznie oknem działki (COG).
- **Zmierzona wydajność prototypu:** **8–18 s** na zimno na 1 vCPU (E2E) — czas zdominowany przez oczekiwanie na zewnętrzne HTTP, a nie obliczenia.

### Model obciążenia i architektura ogólnopolska
Ruch w polskim rolnictwie (~1,25 mln gospodarstw) jest silnie sezonowy (~75% zapytań w IV–VIII) i impulsowy (4–5× skok w dniach alertów suszowych IUNG-PIB; 45–50% ruchu wieczorem 18:00–22:00):
- **Etap 1 — Pilotaż (Rok 1, SLA 99,5%):** 30–50 tys. rolników/rok, ~250 tys. analiz/rok (~1 225/dobę w sezonie; szczyt alertowy 550–750/godz.).
- **Etap 2 — Skala kraju (SLA 99,9%):** 250–400 tys. rolników/rok, ~2,5 mln analiz/rok (~12 250/dobę typowo; **50–60 tys./dobę** w alertach IUNG, tj. 5,5–7,7 tys./godz., $\lambda \approx 1{,}5\text{–}2{,}1\text{/s}$, impulsy *burst* do ~4,2/s).
- **Skalowanie poziome i hurtownia danych:** zamiast odpytywać limitowane API per działka, cykliczne potoki ETL zasilają lokalną hurtownię (PostgreSQL + PostGIS HA, Redis Cluster na kolejkę i limity, Object Storage S3/MinIO z automatycznym TTL): krajowe paczki EGiB, BDOT10k/MPHP/ISOK, NMT w COG, dekadowe mozaiki Sentinel-2 oraz całą siatkę pogodową Polski (**zaledwie ~3 500–4 000 oczek 10 km** pobieranych nocą — spadek liczby zapytań API o 3 rzędy wielkości). Z prawa Little’a ($W \approx 2\text{–}4\text{ s}$) klaster Etapu 2 wymaga **32–48 vCPU / 64–96 GB RAM** w szczycie IV–VIII (autoskalowanie zimą do 8–12 vCPU), **5–8 TB** magazynu (z 12-mies. retencją PDF i HA) oraz **1,5–6 TB/mies.** transferu w sezonie.
- **Szybkość odpowiedzi przy dużym ruchu:** lokalna hurtownia skraca czas analizy przy 50–60 tys. analiz/dobę do **2–5 s (p95)** — znacznie poniżej progu 30 s z kryteriów oceny.
- **Aktualizacja danych:** w prototypie źródła na żywo odświeżają się automatycznie, a pliki YAML (progi IUNG, ceny GUS) ręcznie. W produkcji: pogoda 1×/dobę o 04:00 (prognoza co 6 h), mozaiki Sentinel-2 co 5 dni, PSH 1×/dobę, EGiB miesięcznie, BDOT10k/MPHP/ISOK kwartalnie/rocznie, tabele IUNG/GUS rocznie w panelu administracyjnym.

### Szacunkowe koszty rozwoju i utrzymania (operator — ceny netto)
*Inżynierskie szacunki rynkowe (chmura EOG: widełki dolne = IaaS / RChO, górne = zarządzana chmura HA przez ZUCH); wiążący budżet wymaga wyceny ofertowej (RFI/PZP).*

| Pozycja (netto / mies.) | Etap 1: Pilotaż (250 tys. analiz/rok) | Etap 2: Skala kraju (2,5 mln analiz/rok) |
| :--- | :---: | :---: |
| Klaster obliczeniowy (autoskalowanie IV–VIII) + LB + WAF/CDN + transfer | 2 000 – 4 000 zł | 8 000 – 16 000 zł |
| Bazy HA (PostGIS, Redis) + Object Storage S3 (1,5–8 TB) + backupy | 1 500 – 3 000 zł | 6 000 – 12 000 zł |
| Bezpieczeństwo, monitoring i zgodność (KRI / KSC / NIS2 / SIEM) | 1 000 – 2 000 zł | 3 000 – 6 000 zł |
| Profesjonalny dostęp do danych i serwer kafli mapowych (SLA) | 1 000 – 3 000 zł | 3 500 – 10 000 zł |
| **Podsuma: infrastruktura i dane (miesięcznie / rocznie)** | **5,5–12 tys. zł / 66–144 tys. zł** | **20,5–44 tys. zł / 246–528 tys. zł** |
| Utrzymanie techniczne, DevOps, SLA, aktualizacje (0,5–1 / 1,5–2,5 FTE) | 15 000 – 30 000 zł | 40 000 – 70 000 zł |
| **Razem całkowity OPEX / TCO (miesięcznie / rocznie)** | **20,5–42 tys. zł / 246–504 tys. zł** | **60,5–114 tys. zł / 726 tys.–1,37 mln zł** |

- **Koszt jednostkowy (Etap 2):** **0,10–0,21 zł** samej infrastruktury i danych za raport (**0,29–0,55 zł** z zespołem SLA), czyli **2,42–4,56 zł rocznie na aktywne gospodarstwo**.
- **Jednorazowy CAPEX „produktyzacji” (3–6 mies.):** szacunkowo **250–500 tys. zł netto** (migracja na PostGIS/Redis/S3, potoki ETL, audyt WCAG 2.1 AA, testy obciążeniowe na 50–60 tys. analiz/dobę, testy penetracyjne i zgodność z KRI/NIS2; niższy przy zaangażowaniu własnego zespołu IT KOWR).
- **Opcjonalne dane premium (poza zakresem bazowym):** komercyjne zobrazowania wysokiej rozdzielczości (np. PlanetScope 3 m dla działek < 1 ha) stanowią odrębną pozycję licencyjną (rząd kilkuset tys. zł/rok) i nie są wymagane w wersji bazowej.





## 12. Bezpieczeństwo i dane osobowe

- **Brak danych osobowych:** nie ma kont ani logowania. Adresy IP nie trafiają do logów (Caddy usuwa je z logów błędów, logu
  dostępu nie ma) ani do raportów. Limit zapytań liczony jest po skrócie adresu z losową solą, który nie jest nigdzie zapisywany.
  Wyszukiwany adres nie trafia do raportu ani do logów (sam tekst zapytania, bez IP, zostaje w cache na dysku do 7 dni).
- **Walidacja wejścia:** format numeru działki, data (≤ dziś, ≥ dziś − 10 lat), uprawa z listy, punkt w prostokącie obejmującym
  Polskę (dokładny obrys sprawdza przeglądarka, a ostatecznie ULDK),
  maks. 5 dodatkowych działek ≤ 2 km, limit rozmiaru zapytania (64 KB).
- **Serwer:** HTTPS z HSTS, nagłówki bezpieczeństwa i Content-Security-Policy w Caddy, aplikacja jako użytkownik bez uprawnień root,
  port API niewystawiony na zewnątrz, zapora ufw (tylko 22, 80 i 443 TCP/UDP), limit pamięci kontenera aplikacji.
- **Brak sekretów:** żaden klucz nie jest potrzebny, a w repozytorium nie ma haseł ani tokenów.

---

Zespół **GeoSatel**. Repozytorium pozostaje prywatne do końca wydarzenia (regulamin § 2 ust. 6).
