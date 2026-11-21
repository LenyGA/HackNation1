# Plan implementacji — „Zatrzymaj wodę, chroń plony” (KOWR, HackNation 2026)

Plan dla 1–2 osób pracujących z Claude Code, na ok. 20–24 h do zgłoszenia.
Zasady nadrzędne, stack i konwencje: `CLAUDE.md`. Wymagania i checklista zgłoszenia: `docs/REQUIREMENTS.md`.
Ten plik mówi tylko **co robimy, w jakiej kolejności i po czym poznać, że krok jest gotowy**.

## 1. Ustalenia (odpowiedzi zespołu z 21.11)

| Temat | Decyzja |
|---|---|
| Zespół | 1–2 osoby, kroki wykonuje głównie Claude Code |
| Czas | ok. 20–24 h do zgłoszenia |
| Dodatki ponad minimum | mapa miejsc retencji na działce · nawadnianie: termin i dawka |
| Poza zakresem | szacunek efektu działań w mm · osobny wykres „kalendarz ryzyka” (zostaje prosta tabela miesięcy, bo wynika z obowiązkowej oceny 10-letniej) |
| Uprawy | 9 z `CLAUDE.md`: pszenica ozima, żyto, jęczmień jary, rzepak ozimy, kukurydza, ziemniaki, buraki cukrowe, użytki zielone, warzywa polowe |
| Hosting | osobny VPS (2 GB RAM) z jednym kontenerem Docker; domena z LH.pl, subdomena rekordem `A` na VPS. Hosting współdzielony LH.pl nie uruchomi backendu |
| Raport | zapis w systemie (link z ID) + PDF z serwera (WeasyPrint) + druk z przeglądarki |
| Materiały zgłoszeniowe | tylko checklista (rozdz. 7), treść przygotowuje zespół |
| Nazwa zespołu i tytuł | zespół: **GeoSatel**; tytuł aplikacji: **RolnikSzukaWody** (`core/config.py`: `APP_TITLE = "RolnikSzukaWody"`) |

## 2. Decyzje projektowe, które rozstrzygam w planie

1. **Analiza asynchroniczna z odpytywaniem.** `POST /api/analyses` zwraca od razu `id`, a front co 1 s pyta `GET /api/analyses/{id}`
   i pokazuje stan każdego źródła. Unikamy timeoutów proxy, a rolnik widzi, co się dzieje.
2. **Teksty raportu powstają raz, w backendzie** (szablony Jinja → zdania w JSON). React tylko je układa, a szablon PDF używa tych
   samych zdań. Nie ma dwóch wersji treści.
3. **Tryb poza sezonem wegetacyjnym.** Jury może podać datę 21 listopada. Dla dat poza okresem 21.03–30.09 raport ocenia:
   ostatni zakończony sezon, bieżące odbudowywanie zapasu wody w glebie (bilans od 1.10) oraz stan ozimin, i mówi to wprost.
4. **10 lat to za mało na klasyczne SPI.** Liczymy percentyl empiryczny w 10-letnim rozkładzie tych samych okresów i tak to nazywamy.
5. **Progi IUNG wpisujemy z publikacji, nie z pamięci.** Tabela wartości krytycznych KBW (uprawa × kategoria gleby × okres) trafia
   do `crops/iung_thresholds.yaml` z podanym źródłem. Gdy dla uprawy lub okresu nie ma progu, ocena opiera się na percentylu
   i bilansie FAO-56, a raport to zaznacza.
6. **Satelita jest potwierdzeniem, nie podstawą oceny.** Porównujemy działkę z jej własną historią w tym samym oknie roku.
   Uprawy w poprzednich latach nie znamy (płodozmian), więc ta część zawsze ma obniżoną pewność i raport to mówi.
7. **Każde źródło ma zapas albo jawny brak.** NMT Geoportal → Copernicus DEM 30 m (`degraded`). Overpass → drugi serwer lustrzany.
   SoilGrids → `missing` (bez podstawiania „typowej gleby”).
8. **Jeden obraz Docker.** FastAPI serwuje też zbudowany frontend. Przed nim Caddy z automatycznym HTTPS.

## 3. Harmonogram

Czas liczony od startu prac (T). Przy dwóch osobach: **A** = dane i analiza, **B** = frontend, raport, wdrożenie, dokumentacja.
Przy jednej osobie kolejność jak w tabeli, a kroki B wykonuje się w trakcie oczekiwania na Claude Code w krokach A.

| Faza | Czas | Cel | Moduły |
|---|---|---|---|
| 0. Fundament | T+0 – T+1,5 h | szkielet repo, kontrakty, sprawdzenie ryzykownych źródeł | M0, M1 |
| 1. Cienka ścieżka | T+1,5 – T+5 h | działka → pogoda → bilans → prosty raport w przeglądarce, **wdrożone na VPS** | M2.1–2.2, M3.1–3.2, M6.1, M7.1–7.2, M8.1 |
| 2. Komplet danych | T+5 – T+10 h | satelita, gleba, teren, hydrologia, użytkowanie; pełna ocena i przyczyny | M2.3–2.7, M3.3–3.6 |
| 3. Rekomendacje i raport | T+10 – T+15 h | reguły, mapa retencji, nawadnianie, PDF | M4, M5, M6.2–6.3, M7.3–7.4 |
| 4. Stabilizacja | T+15 – T+18 h | 5 działek × 2 daty, < 30 s, telefon, zabezpieczenia | M9, M8.2 |
| 5. Zgłoszenie | T+18 – T+21 h | README, przykładowe raporty, checklista | M10 |
| Zapas | ok. 2–3 h | awarie źródeł, poprawki po testach | — |

**Punkty kontrolne (jeśli nie osiągnięte, tniemy wg rozdz. 6):**
- T+5 h: publiczny adres zwraca raport z samej pogody dla dowolnej działki i daty.
- T+10 h: wszystkie pięć kategorii danych ma działające źródło lub jawny status `missing`.
- T+15 h: raport ma wszystkie sekcje, a PDF się pobiera.
- T+18 h: zamrożenie funkcji. Dalej tylko poprawki błędów i dokumentacja.

---

## 4. Moduły i kroki

Każdy krok to jedno zadanie dla Claude Code. Format: **co** · pliki · **gotowe, gdy**.

### M0. Szkielet i kontrakty (A+B, 1 h)

- [ ] **M0.1 Szkielet backendu.** `backend/` wg architektury z `CLAUDE.md`: `app/main.py`, puste pakiety, `requirements.txt`,
  `requirements-dev.txt`, `pyproject.toml` (ruff, mypy, pytest z markerem `e2e`), `.env.example`, `.gitignore`.
  **Gotowe, gdy:** `uvicorn app.main:app` startuje, `GET /api/health` zwraca `{"status":"ok"}`, `ruff check . && mypy app && pytest` przechodzą.
- [ ] **M0.2 Szkielet frontendu.** Vite + React + TS + Tailwind + shadcn/ui, proxy `/api` → `:8000`, trasy `/`, `/analiza/:id`, `/raport/:id`.
  Usunąć `frontend/sample.txt`.
  **Gotowe, gdy:** `npm run build && npm run lint && npx tsc --noEmit` przechodzą.
- [ ] **M0.3 Modele wspólne.** `core/models.py`: `SourceResult[T]` (`status: ok|degraded|missing`, `source`, `license`, `fetched_at`,
  `period`, `uncertainty`, `message_pl`, `data`), `Uncertainty` (`high|medium|low` + powód), `Parcel`, `AnalysisRequest`,
  `Indicator` (wartość + jednostka + źródło + okres + pewność).
  **Gotowe, gdy:** modele mają testy serializacji, a `SourceResult` ze statusem `missing` nie może nieść `data`.
- [ ] **M0.4 Kontrakt API.** Endpointy poniżej opisane w `api/schemas.py` i odwzorowane ręcznie w `frontend/src/api/types.ts`.
  Backend zwraca na razie dane przykładowe **tylko w testach**, nigdy w działającej aplikacji.

  | Endpoint | Opis |
  |---|---|
  | `GET /api/crops` | lista upraw (id, nazwa po polsku) |
  | `GET /api/parcels?id=…` lub `?lat=…&lon=…` | geometria GeoJSON (EPSG:4326), identyfikator, gmina, powierzchnia |
  | `POST /api/analyses` | `{parcel_id, crop_id, analysis_date}` → `{id}` |
  | `GET /api/analyses/{id}` | `{status, sources: [{name, status}], report_id?}` |
  | `GET /api/reports/{id}` | pełny raport JSON |
  | `GET /api/reports/{id}.pdf` | PDF |

  **Gotowe, gdy:** `tsc` przechodzi, a OpenAPI na `/docs` pokazuje wszystkie endpointy.
- [ ] **M0.5 Klient HTTP i cache.** `core/http.py` (wspólny `httpx.AsyncClient`, timeout na źródło, 1 ponowienie, nagłówek `User-Agent`
  z nazwą aplikacji bez danych osobowych), `core/cache.py` (cache na dysku: klucz = źródło + skrót parametrów; dane historyczne
  bezterminowo, dane bieżące 1 h).
  **Gotowe, gdy:** test pokazuje, że drugie wywołanie nie robi zapytania sieciowego.

### M1. Sprawdzenie ryzykownych źródeł (A, 30 min, równolegle z M0)

Krótkie skrypty w `backend/scripts/spikes/`, wynik dopisany do `docs/DATA_SOURCES.md`. Cel: wiedzieć przed fazą 2, co działa.

- [ ] **M1.1 NMT Geoportal WCS:** pobrać `GetCapabilities`, ustalić identyfikator pokrycia i format, pobrać wycinek 500 × 500 m.
  Zmierzyć czas. Jeśli > 8 s lub niestabilne, podstawowym źródłem zostaje Copernicus DEM 30 m.
- [ ] **M1.2 Earth Search:** dla jednej działki pobrać NDVI z 10 scen (po jednej na rok) odczytem okienkowym w wątkach. Zmierzyć czas.
  Potwierdzić nazwy zasobów (`red`, `nir`, `swir16`, `scl`) i od którego roku są sceny L2A nad Polską.
- [ ] **M1.3 SoilGrids REST:** zmierzyć czas odpowiedzi i sprawdzić dostępność w 5 punktach Polski.
- [ ] **M1.4 IUNG:** sprawdzić, czy mapa kategorii gleb ma usługę WMS z `GetFeatureInfo` i jaka jest licencja. Znaleźć opublikowaną
  tabelę wartości krytycznych KBW. Jeśli WMS nie ma, kategorię gleby wyznaczamy z uziarnienia SoilGrids (i tak to opisujemy).
- [ ] **M1.5 Overpass:** zapytanie o rowy, cieki, zbiorniki, mokradła i zadrzewienia w promieniu 1 km. Zmierzyć czas na dwóch serwerach.

**Gotowe, gdy:** w `docs/DATA_SOURCES.md` jest tabela: źródło · URL · licencja · zakres czasowy i przestrzenny · na żywo czy wcześniej ·
zmierzony czas · decyzja (podstawowe / zapasowe / odrzucone).

### M2. Źródła danych — `backend/app/sources/` (A)

Wspólne wymagania: funkcja `async fetch(parcel, analysis_date) -> SourceResult[...]`, własny timeout, żadnych danych po `analysis_date`,
cache, test na zapisanej odpowiedzi w `tests/fixtures/`, wpis w `docs/DATA_SOURCES.md`.

- [x] **M2.1 `uldk.py` (faza 1).** `GetParcelById` i `GetParcelByXY` z `srid=4326`, parsowanie WKT, powierzchnia liczona w EPSG:2180.
  Walidacja formatu identyfikatora, kodowanie znaku `/`. Czytelny błąd po polsku, gdy działki nie ma.
  **Gotowe, gdy:** działa dla `141201_1.0001.6509`, dla numeru z `/` i dla kliknięcia; nieistniejący numer daje komunikat, nie wyjątek.
- [x] **M2.2 `open_meteo.py` (faza 1).** Jedno zapytanie do archiwum o 10 lat danych dobowych do `analysis_date`: opad, ET0 (FAO),
  temperatura min/maks/średnia. Gdy `analysis_date` jest w ostatnich 7 dniach, brakujące dni dociągamy z endpointu prognozy
  (`past_days`) i oznaczamy jako wstępne. Prognozę na 7 dni naprzód pobieramy **tylko** dla daty bieżącej (potrzebna w M5).
  **Gotowe, gdy:** dla daty historycznej ostatni dzień w danych = `analysis_date`, a test sprawdza brak późniejszych rekordów.
- [x] **M2.3 `sentinel2.py` (faza 2).** Wyszukiwanie STAC `sentinel-2-l2a` po geometrii działki. Wybór scen: do 3 najlepszych z 45 dni
  przed `analysis_date` (stan bieżący) oraz po 1 najlepszej z okna ±20 dni wokół tego samego dnia roku w każdym z poprzednich lat.
  Odczyt okienkowy B04, B08, B11, SCL w puli wątków, maska chmur z SCL, średnia NDVI i NDMI z pikseli wewnątrz działki.
  Zwraca też liczbę czystych pikseli i liczbę lat z danymi.
  **Gotowe, gdy:** całość < 15 s na zimno, < 1 s z cache; działka < 10 pikseli lub brak czystych scen daje `degraded`/`missing` z opisem.
- [x] **M2.4 `soilgrids.py` (faza 2).** Piasek, pył, ił, węgiel organiczny, gęstość objętościowa dla warstw do 100 cm w centroidzie działki.
  Twardy timeout 8 s. Pewność najwyżej „średnia” (siatka 250 m). Jeśli M1.4 potwierdzi WMS IUNG, dodać `iung.py` z kategorią gleby.
  **Gotowe, gdy:** zwraca wartości w jednostkach z nazw pól (`sand_pct`, `soc_g_per_kg`), a timeout daje `missing`.
- [x] **M2.5 `dem.py` (faza 2).** Wycinek NMT dla działki z buforem 150 m, rozdzielczość robocza 5 m (limit rozmiaru siatki).
  Zapas: Copernicus DEM 30 m z publicznego katalogu, status `degraded`.
  **Gotowe, gdy:** zwraca siatkę wysokości z transformacją i układem współrzędnych; test na zapisanym wycinku.
- [x] **M2.6 `hydro.py` (faza 2).** Overpass w promieniu 1 km: rowy i dreny, cieki, zbiorniki i oczka, mokradła, lasy i zadrzewienia.
  Wynik: geometrie GeoJSON + odległość do najbliższego elementu każdego typu + długość rowów przy granicy działki (≤ 30 m).
  **Gotowe, gdy:** pusty wynik odróżnia „nie ma w danych” od „źródło nie odpowiedziało”; w raporcie jest dopisek o niepełności OSM.
- [x] **M2.7 `landcover.py` (faza 2).** ESA WorldCover 10 m (odczyt okienkowy): udział pól uprawnych, łąk, drzew i zabudowy na działce.
  Ostrzeżenie, gdy działka nie wygląda na rolną. To stan z jednego roku, więc trafia do ograniczeń raportu.
  **Gotowe, gdy:** zwraca udziały procentowe; kafel wybierany poprawnie dla całej Polski.

### M3. Analiza — `backend/app/analysis/` (A)

Czyste funkcje bez I/O, każda z testami jednostkowymi na danych z fixture.

- [ ] **M3.1 `crops/catalog.yaml` + `crops/catalog.py` (faza 1).** Dla 9 upraw: Kc (ini/mid/end) i długości faz wg FAO-56 dostosowane
  do terminów w Polsce, głębokość korzeni, współczynnik `p`, okresy krytyczne dla wody, czy ozima. Każda wartość ze źródłem w komentarzu.
  **Gotowe, gdy:** `kc(crop, date)` zwraca wartość dla każdego dnia roku; test: kukurydza w marcu ma Kc = 0 (pole puste).
- [ ] **M3.2 `water_balance.py` (faza 1).** Dobowy bilans wody w strefie korzeniowej wg FAO-56: `ETc = Kc·ET0`, wyczerpanie `Dr`,
  `TAW`, `RAW`, współczynnik stresu `Ks`. Do tego KBW = P − ET0 w oknach 60-dniowych. Gdy brak danych o glebie, bilans glebowy
  ma status `missing`, a ocena opiera się na samym KBW z obniżoną pewnością.
  **Gotowe, gdy:** testy na ręcznie policzonym przykładzie (10 dni) zgadzają się co do 0,1 mm.
- [ ] **M3.3 `soil.py` (faza 2).** Z uziarnienia i węgla organicznego: polowa pojemność wodna i punkt więdnięcia funkcją pedotransferową
  (Saxton i Rawls 2006), `TAW` w mm dla głębokości korzeni uprawy, kategoria gleby I–IV wg progów uziarnienia IUNG.
  **Gotowe, gdy:** piasek luźny daje kategorię I i niskie TAW, glina ciężka kategorię IV; test obu.
- [ ] **M3.4 `history.py` (faza 2).** Dla każdego z 10 lat: liczba dni stresu wodnego w sezonie i w podziale na miesiące, KBW w tych
  samych oknach, percentyl bieżącego opadu z 30 i 90 dni. Wynik: **częstość lat z niedoborem w każdym miesiącu** (tabela w raporcie)
  oraz miesiące najwyższego ryzyka dla wybranej uprawy.
  **Gotowe, gdy:** test na syntetycznych 10 latach z 3 suchymi czerwcami zwraca 30% dla czerwca.
- [ ] **M3.5 `terrain.py` (faza 2).** Z siatki wysokości: spadek średni i maksymalny na działce, ekspozycja, akumulacja spływu (D8),
  zagłębienia bezodpływowe, punkty, w których spływ opuszcza działkę. Wynik zawiera geometrie GeoJSON kandydatów na miejsca retencji.
  **Gotowe, gdy:** test na sztucznej pochyłej płaszczyźnie z niecką znajduje nieckę i punkt wylotu po właściwej stronie.
- [ ] **M3.6 `assessment.py` + `causes.py` (faza 2).** Składa wyniki w ocenę:
  - **stan bieżący** (brak / lekki / umiarkowany / silny niedobór) z: KBW względem progu IUNG, `Dr/TAW`, percentyla opadu;
    satelita podnosi lub obniża pewność, nigdy sam nie zmienia poziomu,
  - **podatność strukturalna** (niska / średnia / wysoka) z: TAW i kategorii gleby, częstości lat z niedoborem, spadków,
    braku elementów retencji w otoczeniu,
  - **przyczyny** — cztery flagi z `CLAUDE.md`, każda z dowodem liczbowym i źródłem,
  - **pewność wyniku** wyliczana z liczby i statusów źródeł.

  Kompletna ocena jest warunkiem uruchomienia M4. Gdy brakuje pogody (źródło krytyczne), raport kończy się na komunikacie o braku danych.
  **Gotowe, gdy:** testy pokrywają: wszystkie źródła `ok`, brak gleby, brak satelity, brak pogody, datę poza sezonem.

### M4. Rekomendacje — `backend/app/recommendations/` (A, faza 3)

- [ ] **M4.1 Silnik reguł.** `Rule`: `id`, `category` (`retention|agrotech|irrigation`), `condition(ctx) -> bool`,
  `evidence(ctx) -> list[Indicator]`, `template`, `priority`. Wynik posortowany: retencja → agrotechnika → nawadnianie.
  Każda rekomendacja niesie listę dowodów (liczba, źródło, data), które uruchomiły regułę.
- [ ] **M4.2 Reguły retencyjne (ok. 6).** Przykłady warunków: rów przy granicy działki + deficyt w sezonie → zastawka lub piętrzenie;
  zagłębienie na działce z dużą akumulacją spływu → oczko lub okresowe zatrzymanie wody; spadek powyżej progu + wylot spływu →
  pas buforowy lub miedza w poprzek stoku w konkretnym miejscu; brak zadrzewień w otoczeniu + gleba lekka → zadrzewienie śródpolne;
  mokradło lub oczko w pobliżu → ochrona, nie odwadnianie.
- [ ] **M4.3 Reguły agrotechniczne (ok. 7).** Niska zawartość węgla organicznego → obornik, słoma, międzyplony; gleba lekka + częste
  niedobory wiosną → uprawa uproszczona i mulcz; spadek → uprawa w poprzek stoku; okres krytyczny uprawy pokrywa się z miesiącami
  najwyższego ryzyka → odmiany wcześniejsze lub zmiana terminu siewu; pole bez okrywy zimą (uprawa jara) → międzyplon ozimy.
- [ ] **M4.4 Testy reguł.** Dla każdej reguły test „odpala się” i „nie odpala się”. Test całości: przy braku kompletnej oceny lista jest pusta.

**Gotowe, gdy:** dla dwóch różnych działek testowych listy rekomendacji się różnią, a każda pozycja ma co najmniej jeden dowód liczbowy.

### M5. Nawadnianie — termin i dawka (A, faza 3, 2 h)

- [ ] **M5.1 `recommendations/irrigation.py`.** Zasadność: `Dr > RAW` w fazie, w której uprawa reaguje na wodę, i dopiero po
  rekomendacjach retencyjnych. Dawka: uzupełnienie do polowej pojemności, ograniczone jednorazowo zależnie od gleby (lekka mniej,
  częściej). Termin: dla daty bieżącej projekcja `Dr` na 7 dni z prognozą opadu i ET0 („nawadniaj w ciągu N dni” albo „poczekaj,
  prognozowany opad pokryje niedobór”). Dla dat historycznych bez prognozy: stan na dzień analizy i wyraźna informacja o braku prognozy.
- [ ] **M5.2 Zastrzeżenia w szablonie.** Informacja o dostępności wody i pozwoleniach wodnoprawnych jako czynnik nieuwzględniony w analizie.

**Gotowe, gdy:** testy: mokra gleba → „nie nawadniaj”; sucha + brak opadu w prognozie → dawka w mm i termin; poza sezonem → sekcja
mówi, że nawadnianie nie dotyczy.

### M6. Raport — `backend/app/report/` (B)

- [ ] **M6.1 Składanie raportu i zapis (faza 1).** `report/builder.py` buduje `Report` (JSON) z sekcjami w obowiązkowej kolejności:
  1) podsumowanie w 3 zdaniach, 2) sytuacja wodna teraz, 3) podatność w ostatnich 10 latach, 4) przyczyny, 5) zatrzymywanie wody,
  6) zabiegi na polu, 7) nawadnianie, 8) źródła danych z datami, 9) ograniczenia analizy i braki danych.
  Zapis do SQLite pod losowym, nieodgadnialnym ID. `GET /api/reports/{id}`.
- [ ] **M6.2 Szablony tekstów (faza 3).** `report/templates/*.j2`: zdania po polsku prostym językiem, wypełniane wyliczonymi wartościami.
  Bez słów „NDVI”, „KBW”, „percentyl” w treści głównej (tylko w części „Szczegóły dla zainteresowanych”). Zaokrąglenia wg `CLAUDE.md`.
  Osobne szablony komunikatów braku danych dla każdego źródła.
- [ ] **M6.3 PDF (faza 3).** `report/pdf.py`: szablon HTML do druku + WeasyPrint, ze statyczną mapką działki (obrys + miejsca retencji
  narysowane jako SVG, bez zewnętrznych kafli). `GET /api/reports/{id}.pdf`. Ten sam arkusz stylów obsługuje druk z przeglądarki.

**Gotowe, gdy:** raport ma wszystkie 9 sekcji także wtedy, gdy 2 źródła mają status `missing`; PDF mieści się na 2–4 stronach A4
i otwiera się poprawnie.

### M7. Frontend — `frontend/src/` (B)

- [ ] **M7.1 Strona startowa (faza 1).** Trzy kroki na jednym ekranie: (1) działka — pole na numer **albo** klik na mapie,
  (2) uprawa — lista z `GET /api/crops`, (3) data — domyślnie dziś, zakres do 10 lat wstecz. Jeden duży przycisk „Sprawdź działkę”.
  Walidacja z komunikatami po polsku. Przykład formatu numeru pod polem.
- [ ] **M7.2 Mapa (faza 1).** MapLibre: ortofotomapa Geoportalu + granice i numery działek (WMS KIEG) + przycisk „Moja lokalizacja”.
  Klik → `GET /api/parcels?lat&lon` → podświetlenie obrysu i wpisanie numeru do pola. Atrybucje źródeł na mapie.
- [ ] **M7.3 Ekran postępu i raport (faza 3).** Postęp: lista źródeł ze stanem (pobieram / gotowe / brak danych). Raport: u góry
  kolorowy wskaźnik stanu z jednym zdaniem, potem sekcje z M6.1 jako karty; każda rekomendacja ma rozwijane „Dlaczego?” z dowodami.
  Wykres opadu i zapotrzebowania na wodę (bieżący sezon na tle 10 lat) oraz tabela miesięcy ryzyka. Przyciski: „Pobierz PDF”,
  „Drukuj”, „Kopiuj link do raportu”.
- [ ] **M7.4 Mapa miejsc retencji (faza 3).** Na mapie raportu: obrys działki, miejsca gromadzenia się wody, kierunek i wylot spływu,
  pobliskie rowy, cieki, oczka i zadrzewienia. Każdy znacznik powiązany z numerem rekomendacji z sekcji 5. Legenda prostym językiem.
- [ ] **M7.5 Telefon i przeglądarki (faza 4).** Układ jednokolumnowy przy 360 px, duże pola dotykowe, mapa nie blokuje przewijania.
  Sprawdzenie w Chrome, Firefox, Edge, Safari i Operze.

**Gotowe, gdy:** osoba spoza zespołu przechodzi od wejścia na stronę do raportu bez pytań, na komputerze i na telefonie.

### M8. Wdrożenie (B)

- [ ] **M8.1 Pierwsze wdrożenie (faza 1, przed T+5 h).** `Dockerfile` wieloetapowy (budowa frontu → obraz Pythona z bibliotekami
  WeasyPrint), `docker-compose.yml` (aplikacja + Caddy + wolumen na cache i SQLite), `Caddyfile`. VPS 2 GB RAM z Ubuntu i Dockerem.
  W panelu LH.pl rekord `A` dla subdomeny → adres VPS.
  **Wymaga od zespołu:** założenia VPS, dostępu SSH i dodania rekordu DNS.
  **Gotowe, gdy:** `https://<subdomena>/api/health` odpowiada z zewnątrz, a `docker compose up` działa lokalnie wg README.
- [ ] **M8.2 Zabezpieczenia (faza 4).** Limit zapytań na `POST /api/analyses` (na adres, bez zapisywania adresu w raporcie), limit
  równoległych analiz, CORS tylko dla własnej domeny, nagłówki bezpieczeństwa w Caddy, walidacja wszystkich wejść, przypięte wersje
  zależności, brak sekretów w repo, logi bez danych osobowych.
- [ ] **M8.3 Rozgrzanie cache.** Skrypt uruchamiający analizę dla działek referencyjnych po wdrożeniu (kafle WorldCover, połączenia).
  Nie zapisuje gotowych wyników dla działek jury — wynik zawsze liczy aplikacja.

### M9. Testy i weryfikacja (A, faza 4)

- [ ] **M9.1 Działki referencyjne.** `backend/tests/e2e/parcels.yaml`: 5 działek z różnych regionów (gleba lekka w Wielkopolsce lub
  na Kujawach, gleba ciężka na Żuławach lub Lubelszczyźnie, teren ze spadkami na Podkarpaciu lub w Małopolsce, mała wąska działka,
  łąka w dolinie rzeki), każda z dwiema datami: bieżącą i z suszy w czerwcu–lipcu jednego z ostatnich lat.
- [ ] **M9.2 Testy E2E.** `pytest -m e2e`: raport powstaje w < 30 s, ma 9 sekcji, braki danych są jawne, żaden rekord nie jest
  późniejszy niż `analysis_date`.
- [ ] **M9.3 Porównanie z referencją.** Dla dat historycznych zestawić ocenę aplikacji z raportami Systemu Monitoringu Suszy
  Rolniczej IUNG dla tej samej gminy i okresu. Rozbieżności i ich wyjaśnienie zapisać w `docs/METHODOLOGY.md` (rozdział o weryfikacji).
- [ ] **M9.4 Wydajność.** Pomiar czasu każdego źródła na zimno i z cache. Jeśli suma przekracza 25 s: mniej scen satelitarnych,
  krótsze timeouty, niższa rozdzielczość terenu.
- [ ] **M9.5 Odporność.** Test z wyłączonym każdym źródłem po kolei: analiza kończy się raportem z jawnym brakiem, nie błędem.

### M10. Dokumentacja i zgłoszenie (B, faza 5)

- [ ] **M10.1 README** z 9 punktami z rozdz. 4.2 zadania oraz skalowalnością, kosztami i bezpieczeństwem (lista w `docs/REQUIREMENTS.md`).
  W wykazie narzędzi AI: Claude Code użyty do tworzenia kodu; w aplikacji brak modeli AI.
- [ ] **M10.2 `docs/METHODOLOGY.md`:** wzory, progi, reguły, bibliografia z załącznika naukowego, sposób weryfikacji.
- [ ] **M10.3 `docs/DATA_SOURCES.md`:** komplet po M1 i M2, z licencjami i podziałem „na żywo / wcześniej z datą”.
- [ ] **M10.4 Przykładowe raporty:** 3–4 PDF-y w `docs/sample-reports/` (różne regiony, data bieżąca i historyczna).
- [ ] **M10.5 Tabela licencji zależności** (Python i npm) w README; sprawdzić brak licencji blokujących przekazanie praw.

---

## 5. Zależności między modułami

```
M0 ──► M2.1, M2.2 ──► M3.1, M3.2 ──► M6.1 ──► M7.1, M7.2 ──► M8.1      (cienka ścieżka, faza 1)
M1 ──► M2.3 … M2.7 ──► M3.3 … M3.6 ──► M4 ──► M5                        (ścieżka A)
                          M3.5 ──► M7.4        M4, M5 ──► M6.2 ──► M6.3, M7.3   (ścieżka B)
wszystko ──► M9 ──► M10
```

Ścieżkę B można prowadzić niezależnie od A dzięki kontraktowi z M0.4 i raportom zapisanym z fazy 1.

## 6. Co tniemy, gdy brakuje czasu (w tej kolejności)

1. Wykres w raporcie (M7.3) → zostaje tabela.
2. Dane o użytkowaniu z WorldCover (M2.7) → użytkowanie tylko z OSM, pewność niższa.
3. Projekcja nawadniania z prognozą (M5.1) → tylko stan na dzień analizy i dawka.
4. PDF z serwera (M6.3) → druk z przeglądarki do PDF (nadal spełnia wymaganie zapisu raportu).
5. Akumulacja spływu D8 (M3.5) → tylko spadek i najniższe miejsce na działce.

**Nie tniemy nigdy:** pięciu kategorii danych, parametru daty, jawnych braków danych, sekcji źródeł i ograniczeń, wdrożenia publicznego, README.

## 7. Checklista zgłoszenia (treść przygotowuje zespół)

- [ ] Nazwa zespołu i tytuł rozwiązania (podmienić `APP_TITLE`)
- [ ] Opis: problem · główne funkcje · sposób wykorzystania danych · korzyści dla rolnika
- [ ] Link do prywatnego repozytorium + dostęp dla jury wg instrukcji z Platformy konkursowej
- [ ] README kompletne (M10.1)
- [ ] Prezentacja PDF, maks. 10 slajdów
- [ ] Publiczny link do prototypu sprawdzony z innej sieci i z telefonu
- [ ] Film do 3 minut (nagrać po zamrożeniu funkcji, T+18 h)
- [ ] Przykładowe raporty PDF w `docs/sample-reports/`
- [ ] Repozytorium nadal prywatne

## 8. Ryzyka

| Ryzyko | Skutek | Zabezpieczenie |
|---|---|---|
| Sentinel-2 nie mieści się w 30 s | przekroczony limit czasu | maks. 13 scen, odczyt okienkowy w wątkach, cache profilu historycznego, twardy limit 15 s i wynik częściowy |
| Brak scen L2A dla dat z lat 2016–2017 | brak satelity dla starych dat | status `missing` z wyjaśnieniem; ocena z pogody i gleby |
| SoilGrids niedostępne w czasie oceny jury | brak bilansu glebowego | timeout 8 s, cache trwały, ocena z KBW z niższą pewnością |
| Brak opublikowanej tabeli progów IUNG | słabsza zgodność z referencją jury | ocena percentylowa + FAO-56, opisane w metodyce; zapytać mentora (dr inż. T. Bolewski) |
| Overpass przeciążony | brak hydrologii | drugi serwer, cache, status `missing` |
| WeasyPrint w Dockerze | brak PDF | sprawdzić już w M8.1; zapas: druk z przeglądarki |
| Data poza sezonem (np. dziś, 21.11) | pusty lub mylący raport | tryb poza sezonem (decyzja 3 w rozdz. 2), test w M3.6 |
| Limity darmowego Open-Meteo | odmowa przy wielu analizach | jedno zapytanie na analizę, cache po współrzędnych zaokrąglonych do siatki modelu |

## 9. Pytania do mentorów (warto zadać na Discordzie w pierwszych godzinach)

1. Czym są „dane referencyjne” jury: kategorią zagrożenia suszą wg IUNG, wartością KBW, czy czymś innym?
2. Czy jest publiczna usługa (WMS/WFS) z mapą kategorii podatności gleb na suszę IUNG i na jakiej licencji?
3. Czy darmowy plan Open-Meteo (licencja niekomercyjna) jest akceptowalny w prototypie konkursowym?
