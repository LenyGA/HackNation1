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
