# Lista zmian 2 — RolnikSzukaWody

Druga runda zmian po pierwszej wersji prototypu (`plan.md` M0–M10). Zasady nadrzędne, stack i konwencje: `CLAUDE.md`.
Ten plik mówi **co zmieniamy, w jakiej kolejności i po czym poznać, że krok jest gotowy**.

## 1. Ustalenia (odpowiedzi zespołu z 21.11.2026)

| Temat | Decyzja |
|---|---|
| Kolejność | najpierw to, co jury zobaczy w demo (L1), na końcu nowe źródła danych (L6) |
| Format daty w nagłówkach | `DD.MM.YYYY` = data analizy, zamiast słowa „teraz” — **wszędzie** w raporcie (strona i PDF) |
| Mapa wyboru działki | wyższa (ok. 60% ekranu) + przycisk „Pełny ekran”; poza Polską wyraźny komunikat |
| Nowe uprawy | sad – jabłonie, grusze · sad – wiśnie, czereśnie · sad – śliwy · krzewy owocowe (porzeczki, agrest, maliny, aronia) |
| Termin siewu | wybór „wcześnie / typowo / późno” (przesunięcie średniej daty krajowej o ok. 14 dni); nie dotyczy sadów, krzewów i łąk |
| Sposób uprawy | orka / uprawa uproszczona / siew bezpośredni / nie wiem; zmienia **tylko rekomendacje**, nie bilans wodny; nie dotyczy sadów, krzewów i łąk |
| Wyszukiwarka upraw | podpowiedzi od 3 liter |
| Suwak lat | 3–10 lat, zmienia **tylko wykresy**; ocena i rekomendacje zawsze z 10 lat (wymóg zadania); przy 3–4 latach ostrzeżenie |
| Pogoda „wyjaśniająca” | wilgotność, punkt rosy, nasłonecznienie, zachmurzenie, wiatr — tylko jako wyjaśnienie przyczyn wysokiego parowania; są już w ET0 (Penman–Monteith), więc **nie** wchodzą drugi raz do oceny |
| Poza zakresem | mgły (znikomy wpływ na bilans, brak wiarygodnych danych dla dowolnej działki) · wpływ miasta (wyspa ciepła nie sięga pól, siatka meteo 9–25 km) |

### Stan wyjściowy

- [ ] **Do cofnięcia przed startem L2:** w `backend/app/crops/catalog.py` i `catalog.yaml` leżą niecommitowane, częściowe zmiany
  (pole `kind`, 4 uprawy owocowe). Zespół zdecydował o cofnięciu (`git checkout -- backend/app/crops/catalog.py backend/app/crops/catalog.yaml`);
  L2.1 robi to od nowa razem z regułami i testami. **Nie pushować tego stanu** — sady dostałyby rady o międzyplonie i orce.

## 2. Zasady dla tej rundy

1. **Każda nowa wartość liczbowa ma źródło w komentarzu** (FAO-56 tabela/wiersz, IUNG, Instytut Ogrodnictwa), jak w `catalog.yaml`.
2. **Zmiany kontraktu API** (`backend/app/api/`, `frontend/src/api/types.ts`) ogłaszamy zespołowi przed pushem: dotyczą L3.1, L3.2, L5.1.
3. **Nowe źródło danych** od razu do `docs/DATA_SOURCES.md` (URL, licencja, zakres, na żywo / wcześniej + data pobrania).
4. **Nowa reguła rekomendacji** = test „kiedy się odpala” + „kiedy NIE” (`backend/tests/recommendations/test_rules.py`).
5. Przed pushem na `main`: `pytest`, `ruff check .`, `mypy app`, `npm run lint`, `npx tsc --noEmit`; UI sprawdzone na desktopie i telefonie.

## 3. Kroki

### L1. Widoczne w demo (UI, B)

- [ ] **L1.1 Osie Y na wszystkich wykresach.** Podziałka z wartościami i jednostką (mm, %, m n.p.m., wskaźnik zieleni) na: wykresie sezonu
  (`SeasonChartView.tsx`), satelity, trendów, przekroju terenu, planu wody (`Charts.tsx`) oraz w PDF (`backend/app/report/charts_svg.py`).
  Wartości z polskim przecinkiem, 3–5 podziałek „okrągłych” (istniejące `niceMax`).
  **Gotowe, gdy:** każdy wykres na stronie i w PDF ma opisaną oś Y z jednostką; czytelne na szerokości 375 px.
- [ ] **L1.2 Nagłówki „na dzień DD.MM.YYYY” zamiast „teraz”.** Data analizy, nie dzisiejsza. Miejsca:
  `labels_pl.py:97` („Sytuacja wodna teraz” → „Sytuacja wodna na dzień 15.07.2019”), `labels_pl.py:24` („Kondycja roślin teraz”),
  `outlook.py` („Najważniejszy ruch teraz” ×3), `Charts.tsx` (podpis i legenda wykresu satelity, „(teraz)” przy słupku),
  `report.html.j2:46`, `charts_svg.py:191` (etykieta osi „teraz” → rok/data), `blocks/satellite.j2`, `sections/current.j2:100`.
  Jedna funkcja formatująca w backendzie (filtr Jinja `date_dmy`) i jedna we froncie (`formatDateDmy`), bez sklejania napisów w logice.
  **Gotowe, gdy:** `grep -rni "teraz" frontend/src backend/app/report` nie znajduje nagłówków ani legend; raport dla 15.07.2019
  wszędzie pokazuje „15.07.2019”; test szablonu na dacie historycznej.
- [ ] **L1.3 Większa mapa wyboru działki.** `ParcelPickerMap.tsx:157`: wysokość `h-[60svh]` (min. 320 px, maks. ok. 720 px) zamiast
  320/420 px, plus przycisk „Pełny ekran” (`FullscreenControl` z MapLibre lub własny tryb `fixed inset-0`, który działa też w Safari na iOS).
  Ten sam zabieg na mapie w raporcie (`ReportMapView.tsx:193`) — do decyzji przy wdrożeniu, domyślnie tylko przycisk.
  **Gotowe, gdy:** na telefonie mapa zajmuje większość ekranu, ale strona się przewija; pełny ekran włącza się i wyłącza; klik działki działa w obu trybach.
- [ ] **L1.4 Granica Polski zamiast prostokąta + wyraźny komunikat.** Teraz `insidePoland()` (`mapStyle.ts:35`) sprawdza prostokąt
  48,9–55,0° N × 14,0–24,2° E, więc przepuszcza Niemcy przy Odrze, Czechy, Słowację, Litwę i obwód królewiecki, a błąd wyświetla się małym
  tekstem pod polem. Zmiana:
  - uproszczony obrys granicy państwa (GeoJSON kilkadziesiąt KB, np. PRG GUGiK — licencja otwarta; zapas: Natural Earth, domena publiczna)
    dołączony do frontu, sprawdzanie punkt-w-wielokącie (bez nowej zależności albo `@turf/boolean-point-in-polygon`, MIT);
  - komunikat jako wyraźny alert na mapie (np. `Alert` / toast shadcn): „Aplikacja działa tylko dla działek w Polsce. Kliknij na terenie Polski.”;
  - ten sam komunikat przy kliknięciu poza Polską na oddalonej mapie (teraz mapa tylko się przybliża, `ParcelPickerMap.tsx:84`);
  - opcjonalnie wyszarzenie terenu poza Polską (warstwa maski), żeby było widać granicę.
  Źródło obrysu do `docs/DATA_SOURCES.md`.
  **Gotowe, gdy:** klik w Słubicach (PL) wybiera działkę, klik we Frankfurcie nad Odrą (DE) i w Kaliningradzie pokazuje alert bez
  zapytania do serwera; test jednostkowy funkcji na 6 punktach przygranicznych.

### L2. Sady i krzewy owocowe (A)

- [ ] **L2.1 Katalog: rodzaj uprawy i 4 nowe uprawy.** `catalog.py`: pole `kind: arable | grassland | fruit` (domyślnie `arable`),
  `grassland` dostaje `kind: grassland`. `catalog.yaml`, wartości FAO-56 (Tab. 11, 12, 22) z komentarzem źródła:

  | id | nazwa | Kc ini/mid/end | korzenie | p | start sezonu | okresy krytyczne |
  |---|---|---|---|---|---|---|
  | `orchard_pome` | Sad – jabłonie, grusze | 0,50 / 1,20 / 0,95 | 1,0 m | 0,5 | 10.04 | 10.05–30.06 kwitnienie, zawiązywanie, opad czerwcowy · 01.07–31.08 wzrost owoców, pąki na przyszły rok |
  | `orchard_cherry` | Sad – wiśnie, czereśnie | 0,50 / 1,20 / 0,95 | 1,0 m | 0,5 | 01.04 | 01.05–10.07 owoce do zbioru · 11.07–31.08 pąki na przyszły rok |
  | `orchard_plum` | Sad – śliwy | 0,50 / 1,15 / 0,90 | 1,0 m | 0,5 | 05.04 | 10.05–31.08 zawiązywanie i wzrost owoców |
  | `berry_bushes` | Krzewy owocowe – porzeczki, agrest, maliny, aronia | 0,30 / 1,05 / 0,50 | 0,6 m | 0,5 | 01.04 | 01.05–31.07 kwitnienie, zawiązywanie, dojrzewanie |

  Kc dla sadów w wariancie FAO-56 „z murawą w międzyrzędziach, z przymrozkami” (typowy sad w Polsce). Sezon kończy się opadaniem liści.
  Okresy krytyczne: zalecenia nawadniania Instytutu Ogrodnictwa – PIB — **przed commitem zweryfikować daty z publikacją** i wpisać pełny cytat.
  W ograniczeniach raportu: „sady na podkładkach karłowych (M.9) mają płytsze korzenie niż przyjęte 1 m”.
  **Gotowe, gdy:** `load_crops()` zwraca 13 upraw; `tests/crops/test_catalog.py` zaktualizowany; Kc w styczniu = 0 (spoczynek).
- [ ] **L2.2 Reguły agrotechniczne nie dla sadów.** `recommendations/common.py`: `is_fruit(ctx)`. Wyłączyć dla `fruit`:
  `reduced_tillage_mulch`, `contour_tillage`, `crop_timing_variety`, `winter_cover_crop` (teraz odpaliłaby się, bo sad „nie jest ozimy”),
  `crop_residues`. `organic_matter`: trzeci wariant tekstu dla sadu (kompost, ściółka w rzędach, zwarta murawa) w `texts_pl.py` `OM_ACTIONS_PL`.
  **Gotowe, gdy:** test: dla każdej uprawy `fruit` w suchym scenariuszu żadna z 5 reguł się nie pojawia; `TILLAGE_RULES` w
  `test_edge_cases.py` sprawdzane także dla sadów.
- [ ] **L2.3 Nowa reguła `orchard_mulch_sward`** — „Ściółkuj rzędy i ogranicz konkurencję trawy o wodę”. Warunek: `fruit` i
  (gleba lekka **lub** niedobór w maju–sierpniu w ≥ 30% lat). Tekst: ściółka 5–10 cm w pasie rzędów (kora, zrębki, słoma), częste i niskie
  koszenie murawy w międzyrzędziach w czasie suszy, bez spulchniania gleby w rzędach w suszy. Dowody: `light_soil` + częstości miesięcy.
  **Gotowe, gdy:** testy „odpala się” (lekka gleba, suche lata) i „nie” (gleba ciężka i mokre lata; uprawa polowa); wpis w `docs/METHODOLOGY.md` rozdz. 8.
- [ ] **L2.4 Nawadnianie dla sadów i krzewów.** `irrigation.py` / `texts_pl.py`:
  - `no_crop` dla `fruit`: „drzewa/krzewy są w spoczynku albo już zrzuciły liście” zamiast „na polu nie ma uprawy”;
  - `late_stage` dla `fruit`: osobny tekst w `LATE_PL`;
  - dodatkowa uwaga w `irrigation_caveats` dla `fruit`: w sadach stosuje się nawadnianie kroplowe, które zwilża tylko pas rzędu, więc
    rzeczywista ilość wody jest mniejsza niż dawka na całą powierzchnię (FAO-56, udział zwilżonej powierzchni `fw`).
  Param `grassland` zastąpić `kind` (zgodność wsteczna szablonów).
  **Gotowe, gdy:** `test_irrigation_qa.py` (przegląd całego katalogu) przechodzi dla 13 upraw; teksty bez „pole”/„siew” dla sadów.
- [ ] **L2.5 Mapa użytkowania terenu a sad.** ESA WorldCover często klasyfikuje sad jako „drzewa”, więc teraz raport ostrzega,
  że działka „nie wygląda na pole ani łąkę”. Dla `fruit` liczyć pola + łąki + drzewa (`assessment.py:621`, `builder.py:321`,
  tekst w `sections/current.j2:85` i `limitations.j2:17`: „pole, łąkę ani sad”). `sources/landcover.py` zostaje bez wiedzy o uprawie.
  **Gotowe, gdy:** test: działka 80% drzew + sad → brak ostrzeżenia; 80% drzew + pszenica → ostrzeżenie zostaje.

### L3. Termin siewu i sposób uprawy (A+B, zmiana kontraktu API)

- [ ] **L3.1 Termin siewu „wcześnie / typowo / późno”.** `AnalysisRequest`: `sowing_shift: early | typical | late` (domyślnie `typical`).
  `Crop.with_sowing_shift(±14 dni)` przesuwa `sowing` i okresy krytyczne. Pole widoczne tylko dla `kind == arable`
  („Kiedy siałeś lub sadziłeś? Wcześniej niż zwykle / jak zwykle / później niż zwykle”). Raport mówi wprost, że to przesunięcie
  średniej krajowej, nie dokładna data. W ozimych: przesunięcie siewu jesiennego.
  **Gotowe, gdy:** test: kukurydza `late` ma Kc = 0 jeszcze 10.05; walidacja odrzuca `sowing_shift` dla łąki/sadu; `types.ts` zaktualizowany.
- [ ] **L3.2 Sposób uprawy.** `AnalysisRequest`: `tillage: plough | reduced | no_till | unknown` (domyślnie `unknown`); pole tylko dla `arable`.
  Wpływ wyłącznie na rekomendacje:
  - `reduced` / `no_till` → `reduced_tillage_mulch` nie mówi „ogranicz orkę”, tylko „zostawiaj więcej resztek na powierzchni”;
  - `no_till` → `contour_tillage` mówi o siewie w poprzek stoku (bez „orki”);
  - `plough` → bez zmian; `unknown` → obecne teksty.
  Bilans wodny bez zmian (patrz L7.1).
  **Gotowe, gdy:** testy wariantów tekstu dla każdej opcji; raport w sekcji danych wejściowych pokazuje wybrany sposób uprawy.
- [ ] **L3.3 Formularz startowy.** `StartPage.tsx`: dwa nowe pola pod wyborem uprawy, ukrywane dla łąk, sadów i krzewów, z wartością domyślną
  (formularz nadal da się wysłać bez ich dotykania). Do raportu (`ReportPage.tsx:305`) dopisać termin siewu i sposób uprawy, jeśli podane.
  **Gotowe, gdy:** przepływ działka → uprawa → data → „Sprawdź działkę” działa bez nowych pól; na telefonie formularz mieści się bez poziomego przewijania.

### L4. Śnieg i pogoda wyjaśniająca (A)

- [ ] **L4.1 Śnieg i roztopy.** `open_meteo.py`: dobowe `snowfall_sum`; pokrywa śnieżna `snow_depth` (w archiwum godzinowa → maksimum dobowe)
  i temperatura gleby 0–7 cm — **najpierw sprawdzić dostępność w archiwum ERA5 i forecast** (jak M1 w `plan.md`). Opad już zawiera wodę ze śniegu,
  więc nie dodajemy go drugi raz; zmienia się **termin** zasilania gleby. W analizie (czyste funkcje): zapas wody w śniegu w danym dniu,
  dni roztopów na zamarzniętej glebie → część wody spływa zamiast wsiąkać (przyczyna „słabe zasilanie zimowe”). Fallback NASA POWER nie ma
  pokrywy śnieżnej → status `degraded` dla tej części, jawnie w raporcie.
  **Gotowe, gdy:** raport dla daty 15.03 mówi, ile było śniegu tej zimy względem 10 lat i czy roztopy wypadły na zamarzniętą glebę;
  test na syntetycznej zimie; wpis w `docs/DATA_SOURCES.md` i `docs/METHODOLOGY.md`.
- [ ] **L4.2 Pogoda wyjaśniająca wysokie parowanie.** Dobowe: nasłonecznienie (`shortwave_radiation_sum`, `sunshine_duration`),
  wilgotność względna i punkt rosy (średnie dobowe), zachmurzenie, wiatr — do sprawdzenia nazwy zmiennych w archiwum. Tylko w raporcie:
  „parowanie w ostatnich 30 dniach było o X% wyższe niż zwykle, bo powietrze było suche / dużo słońca / silny wiatr” — z porównaniem
  do 10 lat. **Nie zmienia poziomu niedoboru** (te dane już są w ET0). Wilgotność i punkt rosy w „Szczegółach dla zainteresowanych”.
  **Gotowe, gdy:** zdanie wyjaśniające powstaje z reguły (próg odchylenia od 10 lat), a nie na sztywno; test, że ocena niedoboru jest identyczna
  z tymi danymi i bez nich.

### L5. Suwak lat i wyszukiwarka (B, + A dla danych)

- [ ] **L5.1 Suwak „porównaj z ostatnimi N latami” (3–10).** Teraz `SeasonChart` przysyła gotową medianę/min/max z 10 lat
  (`backend/app/report/models.py:335`), więc front nie przeliczy innego okresu. Zmiana: backend przysyła serie per rok (narastająco, jak teraz),
  front liczy medianę i zakres dla N ostatnich lat. Ten sam suwak dla wykresu satelity i mapy ciepła stresu, jeśli dane per rok są dostępne.
  Przy N = 3–4 widoczne ostrzeżenie „za mało lat, porównanie orientacyjne”. Ocena, tekst raportu i rekomendacje **nie zmieniają się**
  (zawsze 10 lat) — napis przy suwaku to mówi. PDF: zawsze 10 lat.
  **Gotowe, gdy:** przesunięcie suwaka zmienia pasmo na wykresie bez zapytania do serwera; rozmiar JSON raportu rośnie < 50%; test
  backendu na kształt danych; suwak obsługiwany palcem na telefonie i klawiaturą.
- [ ] **L5.2 Wyszukiwarka upraw.** Combobox shadcn/ui (`Command` + `Popover`) zamiast listy rozwijanej w `StartPage.tsx:226`.
  Podpowiedzi od 3 liter, filtrowanie w przeglądarce (lista z `GET /api/crops`), bez polskich znaków („zyto” → „Żyto”), dopasowanie też
  w środku nazwy („jabl” → „Sad – jabłonie, grusze”). Synonimy w katalogu (`aliases_pl`: „trawa”, „łąka” → użytki zielone; „porzeczka” →
  krzewy owocowe) — pole opcjonalne w `catalog.yaml` i w `CropOut`. Poniżej 3 liter podpowiedź „Wpisz co najmniej 3 litery”.
  **Gotowe, gdy:** wszystkie 13 upraw da się znaleźć po 3 literach nazwy lub synonimu; obsługa klawiaturą (strzałki, Enter) i czytnikiem ekranu;
  walidacja „uprawa z listy” bez zmian.

### L6. Woda gruntowa, kopalnie, działki sąsiednie (A, nowe dane — ryzykowne)

- [ ] **L6.1 Zasilanie korzeni przez płytką wodę gruntową.** Dane już są (`sources/groundwater.py`, najbliższa stacja PSH PIG-PIB).
  Gdy zwierciadło jest płytko pod korzeniami (np. < 1–2 m pod strefą korzeni, próg z FAO-56 rozdz. 8 / literatury — wpisać ze źródłem),
  przyczyna „woda gruntowa łagodzi niedobór” i obniżona pewność bilansu (model jej nie liczy). Odległość stacji od działki jawnie w raporcie.
  Sama odległość od rzeki **nie** jest czynnikiem (pozorna precyzja).
  **Gotowe, gdy:** test reguły na stacji z płytkim i głębokim zwierciadłem; brak stacji w promieniu → brak wniosku, bez wartości domyślnej.
- [ ] **L6.2 Kopalnie odkrywkowe i duże ujęcia wody (lej depresji).** Sprawdzić darmowe źródło (PIG-PIB MIDAS: obszary górnicze,
  WMS/WFS; mapy lejów depresji tylko dla części kopalń) i licencję. Wynik: „działka leży X km od obszaru górniczego odkrywki”, jako
  możliwa przyczyna niskich wód gruntowych, z niską pewnością. Jeśli źródło nie zadziała w 30 min sprawdzania — przenieść do „Ograniczeń analizy”.
  **Gotowe, gdy:** działka w pobliżu Bełchatowa dostaje wzmiankę, działka na Podlasiu nie; źródło w `docs/DATA_SOURCES.md`.
- [ ] **L6.3 Spływ z działek sąsiednich pokazany wprost.** Model terenu już liczy obszar, z którego spływa woda (D8 w `analysis/terrain.py`,
  `contributing_area_m2`). Dodać: ile ha spoza działki spływa na nią („woda po deszczu spływa na działkę z ok. X ha sąsiednich pól”) oraz rowy
  odprowadzające wodę z działki u sąsiada (OSM, `hydro.py`). W rekomendacjach retencyjnych: pas zieleni/zastawka na granicy, którędy woda wpływa.
  **Gotowe, gdy:** test na syntetycznym stoku: działka u podnóża dostaje „X ha”, działka na szczycie nie; strzałka napływu na mapie raportu.

### L7. Na później (po zgłoszeniu lub gdy zostanie czas)

- [ ] **L7.1 Sposób uprawy w bilansie wodnym.** Mniejsze parowanie z gleby przy resztkach na powierzchni wg FAO-56 rozdz. 11
  (ok. 5% mniej na każde 10% przykrycia). Wymaga założenia o przykryciu resztkami (nie mierzymy go), więc w raporcie jako jawny szacunek.

## 4. Co tniemy, gdy brakuje czasu (w tej kolejności)

1. L6.2 kopalnie (najbardziej niepewne źródło) → do „Ograniczeń analizy”.
2. L4.2 pogoda wyjaśniająca.
3. Suwak dla wykresów innych niż sezon (L5.1 — zostaje tylko wykres sezonu).
4. Synonimy w wyszukiwarce (L5.2 — zostaje samo wyszukiwanie po nazwie).
5. Maska terenu poza Polską (L1.4 — zostaje alert).

Nie tniemy: L1.1–L1.4 (demo), L2.1–L2.2 (bez nich sady dostają błędne rady), L1.2 (jury testuje daty historyczne).

## 5. Dokumentacja do zaktualizowania

- [ ] `CLAUDE.md` — lista upraw w „Otwarte decyzje”, nowe pola formularza.
- [ ] `docs/METHODOLOGY.md` — rozdz. 8 (nowa reguła, wyłączenia dla sadów, warianty sposobu uprawy), śnieg, woda gruntowa.
- [ ] `docs/DATA_SOURCES.md` — obrys granicy Polski, nowe zmienne Open-Meteo, ewentualnie MIDAS.
- [ ] `README.md` — nowe funkcje, znane ograniczenia (sady na karłowych podkładkach, termin siewu jako przesunięcie, suwak tylko na wykresach).
