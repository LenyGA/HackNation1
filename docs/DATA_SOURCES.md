# Źródła danych

Wyniki sprawdzenia źródeł (plan, krok M1) z **21.11.2026**, wykonane z sieci na miejscu wydarzenia (wspólny adres IP).
Skrypty: `backend/scripts/spikes/`. Działka testowa: `141201_1.0001.6509` (ok. 52,17° N, 21,59° E).

Wszystkie dane są pobierane **na żywo** w chwili analizy (z cache na dysku: dane historyczne bez wygasania, bieżące 1 h).
Aplikacja nie zawiera żadnych wcześniej przygotowanych wyników.

## Podsumowanie decyzji

| Kategoria | Źródło | URL | Licencja | Zakres | Zmierzony czas | Decyzja |
|---|---|---|---|---|---|---|
| Działka | GUGiK ULDK | `https://uldk.gugik.gov.pl/` | dane publiczne GUGiK, bezpłatne | cała Polska, stan bieżący | 0,2–0,5 s | **podstawowe** |
| Meteo | Open-Meteo Historical (ERA5) | `https://archive-api.open-meteo.com/v1/archive` | CC BY 4.0, darmowe API tylko niekomercyjnie, limit 10 000 wywołań/dzień | 1940 – ok. 5 dni wstecz, siatka ~11 km | — (429: limit dzienny wyczerpany przez wspólny IP) | **podstawowe** + zapas |
| Meteo (dni bieżące) | Open-Meteo Forecast (`past_days`) | `https://api.open-meteo.com/v1/forecast` | jw. | do 92 dni wstecz + 16 dni prognozy | 0,2 s | **podstawowe** dla ostatnich dni i prognozy |
| Meteo (zapas) | NASA POWER (społeczność AG) | `https://power.larc.nasa.gov/api/temporal/daily/point` | dane NASA, bezpłatne, wymagane podanie źródła | 1981 – ok. kilka dni wstecz, siatka 0,5° × 0,625° | 3,0 s (10 lat) | **zapasowe** (`degraded`): ET0 liczymy sami wg FAO-56 z T, RH, wiatru i promieniowania |
| Satelita | Sentinel-2 L2A, Microsoft Planetary Computer | `https://planetarycomputer.microsoft.com/api/stac/v1` | dane Copernicus (bezpłatne, z podaniem źródła); token SAS anonimowy, bez konta | od 2016 (nad Polską), 10–20 m | wyszukiwanie 10 lat 2,9 s · odczyt 10 scen 2,6 s | **podstawowe** |
| Satelita | Sentinel-2 L2A, Earth Search (AWS us-west-2) | `https://earth-search.aws.element84.com/v1` | jw. | jw. | ok. 30 s na scenę | **odrzucone** (za wolne z Polski) |
| Gleba | SoilGrids 2.0, WCS (ISRIC) | `https://maps.isric.org/mapserv?map=/map/<prop>.map` | CC BY 4.0 | globalnie, 250 m, 6 warstw do 200 cm | 0,07–1,1 s na właściwość | **podstawowe** |
| Gleba | SoilGrids REST | `https://rest.isric.org/soilgrids/v2.0/properties/query` | CC BY 4.0 | jw. | 3–4 s, w 9 z 10 punktów zwraca `null` | **odrzucone** |
| Teren | Copernicus DEM GLO-30 (Planetary Computer) | kolekcja `cop-dem-glo-30` | licencja Copernicus DEM (bezpłatna, z podaniem źródła) | globalnie, 30 m | 7 s pierwszy odczyt | **podstawowe** (`degraded`: 30 m i model pokrycia terenu, nie gruntu) |
| Teren | NMT GUGiK, WCS | `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF` | dane publiczne GUGiK, bezpłatne | Polska, 1 m | GetCapabilities 1,7 s; GetCoverage 500 × 500 m > 30 s (timeout) | **do ponownego sprawdzenia z VPS**; na razie odrzucone (próg 8 s) |
| Użytkowanie | ESA WorldCover 2021 v200 (Planetary Computer) | kolekcja `esa-worldcover` | CC BY 4.0 | globalnie, 10 m, stan z 2021 r. | 1,4 s | **podstawowe** |
| Hydrologia | OpenStreetMap, Overpass API | `https://overpass-api.de/api/interpreter` + serwery lustrzane | ODbL 1.0 | globalnie, kompletność zmienna | brak połączenia z sieci wydarzenia (3 serwery, timeout) | **do sprawdzenia z VPS**; przy braku odpowiedzi status `missing` |
| Meteo (stacje) | IMGW-PIB dane publiczne | `https://danepubliczne.imgw.pl/` | dane publiczne IMGW-PIB, wymagana informacja o źródle | stacje synoptyczne | 0,2 s (API działa) | rezerwa, nieużywane w v1 |
| Gleba, KBW | IUNG-PIB | `https://susza.iung.pulawy.pl/` | — | — | — | **niesprawdzone** (krok M1.4 otwarty) |

## Uwagi, które muszą trafić do implementacji

1. **Open-Meteo i wspólny IP.** Darmowy limit liczy się na adres IP. Na wydarzeniu sieć jest wspólna, więc limit był wyczerpany już
   przy pierwszym zapytaniu. VPS ma własny IP, ale i tak: (a) agresywny cache, (b) automatyczne przejście na NASA POWER ze statusem
   `degraded` i informacją w raporcie.
2. **Sentinel-2: przesunięcie wartości od 25.01.2022.** Od wersji przetwarzania 04.00 do wartości odbicia dodano offset −1000
   (`BOA_ADD_OFFSET`). Bez korekty NDVI z lat 2022+ wychodzi ok. 0,2 niżej niż z lat wcześniejszych, co fałszywie wygląda na suszę.
   W teście: 2016–2021 ok. 0,55, 2022–2025 ok. 0,33 przed korektą. Korekta: `reflectance = (DN + offset) / 10000` z metadanych sceny.
3. **Sentinel-2: chmury.** Scena z 27.06.2017 przy `eo:cloud_cover` = 21% dała NDVI 0,02. Maska SCL jest obowiązkowa, a wybór sceny
   powinien brać pod uwagę zachmurzenie **nad działką**, nie całej sceny.
4. **SoilGrids WCS:** wartość `0` oznacza brak danych (obszary zabudowane, wody). Jednostki: piasek i ił w g/kg (÷10 → %),
   SOC w dg/kg (÷10 → g/kg). Siatka 250 m, więc pewność najwyżej „średnia”.
5. **Copernicus DEM** to model pokrycia terenu (DSM): zadrzewienia i zabudowa zawyżają wysokość. Spadki na polu otwartym są wiarygodne,
   przy zadrzewieniach nie. Zapisujemy w ograniczeniach raportu.
6. **WorldCover** to stan z jednego roku (2021), więc trafia do ograniczeń raportu.

## Testowe wyniki (do porównań)

- SoilGrids 0–5 cm (piasek / ił / SOC w jednostkach WCS): 52,55° N 17,60° E (Wielkopolska) 716–737 / 73–75 / 507–633 ·
  50,90° N 22,10° E (Lubelszczyzna) 272–293 / 177–193 / 441–467 · 54,10° N 19,00° E (Żuławy) 165–182 / 303–325 / 515–679.
- WorldCover dla działki testowej: klasy 10 (drzewa) i 50 (zabudowa) w buforze 200 m, co wymaga sprawdzenia na samej geometrii działki.

## Implementacja (krok M2, 21.11.2026)

Każde źródło to moduł w `backend/app/sources/` z funkcją `fetch(parcel, analysis_date) -> SourceResult[...]`
(wyjątek: `uldk.py`, który zwraca samą działkę). Wszystkie pobierane są **na żywo** w chwili analizy, z cache na dysku.

| Moduł | Źródło | Zakres pobierany dla działki | Timeout | Cache | Status przy problemach |
|---|---|---|---|---|---|
| `uldk.py` | GUGiK ULDK | geometria (EPSG:4326), TERYT, gmina, obręb; powierzchnia liczona w EPSG:2180 | 8 s | 1 dzień (po numerze) | błąd po polsku (404 / 503 w API) |
| `open_meteo.py` | Open-Meteo archiwum → zapas NASA POWER; ostatnie dni i prognoza: Open-Meteo Forecast | dane dobowe od 1.10 roku `rok − 11` do `analysis_date`; prognoza 7 dni tylko gdy `analysis_date` = dziś | 12 s / zapytanie | bez wygasania; 1 h dla dat z ostatnich 10 dni | NASA POWER → `degraded` (ET0 z FAO-56); dni z prognozy oznaczone `provisional_from`; brak obu → `missing` |
| `sentinel2.py` | Sentinel-2 L2A, Planetary Computer | do 3 scen z 45 dni przed `analysis_date` + 1 scena z okna ±20 dni w każdym z 10 lat; tylko okno działki | 15 s łącznie | profil historyczny bez wygasania | brak czystej sceny bieżącej → `missing`; < 10 pikseli lub < 5 lat → `degraded` |
| `soilgrids.py` | SoilGrids 2.0 WCS | piasek, pył, ił, SOC, gęstość; 5 warstw do 100 cm; komórka centroidu | 8 s łącznie | bez wygasania | brak w centroidzie → najbliższa komórka (≤ 300 m) i `degraded`; wszystko puste → `missing` |
| `dem.py` | NMT 1 m GUGiK (lidar) przez usługę wysokości punktów `GetHByPointList` (domyślnie); zapasowo Copernicus DEM GLO-30 (Planetary Computer) | siatka wysokości działka + 150 m w EPSG:2180, co 5 m (rzadziej dla dużych działek, maks. 8000 punktów), paczki po 1000 punktów równolegle | 7 s NMT, potem COP; 18 s łącznie | bez wygasania | NMT → `ok`; COP zawsze `degraded` (30 m, DSM); brak → `missing` |
| `hydro.py` | OSM Overpass (3 serwery równolegle w rotowanej kolejności: overpass-api.de, overpass.kumi.systems, overpass.private.coffee; pierwsza odpowiedź; 1 ponowna runda) | rowy, cieki, zbiorniki, mokradła, lasy w 1 km od krawędzi działki; odległości i długość rowów ≤ 30 m od granicy | 7 s na zapytanie, 15 s łącznie | 1 dzień | „brak w OSM” = `ok` z komunikatem; brak odpowiedzi = `missing`, wtedy zadrzewienia, wody i mokradła z pierścienia WorldCover (niżej), brak dotyczy tylko rowów i cieków |
| `landcover.py` | ESA WorldCover 2021 v200 (Planetary Computer) | udziały klas pokrycia na działce (piksele 10 m) oraz w pierścieniu 500 m wokół działki: udziały i odległość do najbliższego piksela drzew (10), wód (80), mokradeł (90) i zabudowy (50) — ten sam odczyt okna, zapas za OSM | 10 s | bez wygasania | < 50% pola i łąki → `degraded` z ostrzeżeniem |
| `orthophoto.py` | Ortofotomapa GUGiK, WMS Geoportal `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution` (GetMap 1.1.1, EPSG:2180, warstwa `Raster`) | podkład mapy działki w PDF: jeden obraz JPEG ≤ 900 px dla ramki mapy, osadzony w SVG jako data URI; na żywo przy pierwszym PDF raportu; licencja: dane PZGiK udostępniane bezpłatnie (Prawo geodezyjne i kartograficzne, art. 40a ust. 2) | 5 s | 30 dni | brak odpowiedzi → mapa bez podkładu i jawna uwaga w legendzie |

**ULDK pod obciążeniem (obserwacja 21.11.2026):** usługa czasem zwraca pustą odpowiedź, a gdy ogranicza klienta, odpowiada `302` na
`integracja01.gugik.gov.pl/resp/uldk.php` — adres bez parametrów zapytania, który wysyła gigabajty śmieci. `uldk.py` nie podąża za
przekierowaniami i ponawia pustą/nieczytelną odpowiedź lub przekierowanie do 4 razy (łącznie ok. 3 s przerw); potem zwraca polski komunikat
„chwilowo nie odpowiada”. Ograniczenie trwa kilka–kilkanaście minut po serii kilkudziesięciu zapytań z jednego adresu.

Uwagi:
- Open-Meteo archiwum odpowiada 429 z sieci wydarzenia (wspólny IP), więc lokalnie działa zapas NASA POWER. Z VPS działa (sprawdzone
  21.11.2026). Darmowy limit jest dzienny na adres IP, a zapytanie o 11 lat danych dobowych liczy się jak wiele zwykłych zapytań: po kilkunastu
  analizach na zimno z jednego adresu archiwum odpowiada `429` „Daily API request limit exceeded” do końca doby (obserwacja 21.11.2026).
  Cache na dysku (bez wygasania dla dat historycznych) sprawia, że ponowna analiza tej samej okolicy nie zużywa limitu.
- Overpass nie odpowiadał z sieci wydarzenia (oba serwery) — moduł zwraca wtedy jawne `missing`. 21.11.2026 wieczorem także z VPS:
  `overpass-api.de` zgłaszał „currently at capacity” (proste zapytanie ok. 26 s, powyżej naszego timeoutu 12 s), `overpass.kumi.systems`
  nie odpowiadał. To przeciążenie publicznych serwerów, nie błąd zapytania.
- NMT GUGiK: WCS GetCoverage nie odpowiedział ani razu (21.11.2026, wszystkie zapytania > 30–60 s), dlatego używamy usługi wysokości punktów `https://services.gugik.gov.pl/nmt/` (`GetHByPointList`, POST, lista `N E` w EPSG:2180). Usługa zwraca wysokości dla maks. 1000 punktów na zapytanie; brak danych to punkt bez wysokości albo `0.0`. 5700 punktów (działka 0,27 ha + 150 m) ≈ 2,8 s.
- WorldCover i OSM pokazują stan obecny / z 2021 r., a nie z dnia analizy. Wynika to z dostępności danych i jest opisane w wyniku źródła.
- Zmierzony czas wszystkich źródeł równolegle dla działki `302108_5.0014.88/8`: 12 s na zimno (ograniczone timeoutem Overpass),
  < 1 s z cache.


## Nowe źródła (21.11.2026, wieczór)

| Moduł | Źródło | Co pobieramy | Czas / limit | Cache | Brak danych |
|---|---|---|---|---|---|
| `flood.py` | Wody Polskie (KZGW), mapy zagrożenia powodziowego ISOK, II cykl, WMS `https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS`, warstwa `NZ.Fluvial` | GetFeatureInfo (`text/plain`) w 1–5 punktach działki → scenariusze 10, 100, 500 lat (`loo_ql_returnperiod`) | 0,2–8 s na punkt, równolegle; 11 s łącznie | 30 dni | żaden punkt nie odpowiedział → `missing` („nie sprawdzono”, nigdy „brak zagrożenia”) |
| `flood.py` | Wody Polskie, mapa powodzi historycznych (WORP), WMS `..._WORP_WMS`, warstwa `NZ.ObservedEvent` | GetFeatureInfo w centroidzie | 5 s (21.11.2026 serwer nie odpowiadał w 20 s) | j.w. | `historical = None` → raport mówi „nie sprawdzono” |
| `flood.py` | PIG-PIB, obszary zagrożone podtopieniami, ArcGIS REST `cbdgmapa.pgi.gov.pl/.../hydrogeologia/podtopienia/MapServer/0` | zapytanie punktowe | 0,2 s | j.w. | `None` |
| `groundwater.py` | PIG-PIB / PSH, automatyczny monitoring wód podziemnych, ArcGIS REST `cbdgmapa.pgi.gov.pl/.../hydrogeologia/mwp_auto/MapServer` (warstwa 0: stacje, tabela 2: pomiary, dane bez walidacji) | stacje w promieniu 50 km; średnia głębokość zwierciadła (m p.p.t.) z 60 dni przed datą analizy i z tych samych 60 dni 1–3 lata wcześniej (`outStatistics`, po stronie serwera) | ~0,1 s na zapytanie; 9 s łącznie | bez wygasania dla dat historycznych | brak stacji z danymi → `missing`; stacja bez historii → `degraded` (poziom bez trendu) |

Licencje: dane publiczne Wód Polskich (INSPIRE) i PIG-PIB — bezpłatne, z podaniem źródła. Wszystkie pobierane na żywo.

Ograniczenia: mapy zagrożenia powodziowego opisują stan z II cyklu planistycznego (mapy 2020–2022) i nie zależą od daty analizy. Automatyczne stacje PSH w wielu miejscach mierzą dopiero od 2026 r., więc dla dat historycznych trendu często nie ma — raport mówi to wprost.

Sprawdzone i odrzucone: BDOT10k / MPHP jako WFS z cieków po bbox — publicznej usługi nie znaleziono (BDOT10k tylko jako paczki GML na powiat, 50–100 MB); zostaje OSM Overpass. IMGW `api/data/hydro` daje tylko stan bieżący (bez historii), więc nie nadaje się dla dat z przeszłości.

## Dane pobrane wcześniej (dołączone do aplikacji)

| Plik | Źródło | Licencja | Zakres | Pobrane | Jak odtworzyć |
|---|---|---|---|---|---|
| `frontend/src/components/map/poland.json` (51 KB) | PRG GUGiK (Państwowy Rejestr Granic), WFS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries`: warstwa `A00_Granice_panstwa` minus `W02_Morze_terytorialne_RP` i `W03_Morskie_wody_wewnetrzne` (ląd) | dane otwarte PZGiK (art. 40a Prawa geodezyjnego i kartograficznego), bezpłatne, z podaniem źródła | obrys lądowej części Polski, bufor 200 m na zewnątrz, uproszczenie 150 m, WGS84, 4 miejsca po przecinku | **21.11.2026** (wcześniej, nie na żywo) | `python backend/scripts/build_poland_outline.py` |

Do czego służy: mapa wyboru działki sprawdza w przeglądarce (punkt w wielokącie, bez zapytania do serwera), czy kliknięcie lub
„Moja lokalizacja” leży w Polsce, i wyszarza teren poza Polską. Bufor gwarantuje, że uproszczenie nie odrzuci żadnej polskiej działki
(sprawdzone: poza obrysem zostaje 0,27 km² pasów węższych niż 50 m — falochrony w Świnoujściu i Gdańsku). Kliknięcie do ok. 200 m
za granicą trafia do ULDK, które rozstrzyga ostatecznie.
