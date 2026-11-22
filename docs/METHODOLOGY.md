# Metodyka analizy — RolnikSzukaWody

Dokument opisuje, jak aplikacja liczy ocenę sytuacji wodnej (moduł M3, `backend/app/analysis/`). Każdy próg jest stałą
w kodzie z nazwą podaną niżej, więc zmiana progu = zmiana w jednym miejscu i w tym dokumencie.
Rozdział o weryfikacji wyników (M9.3) oraz bibliografię pełną (M10.2) uzupełnimy później.

## 1. Dane wejściowe i zasada daty analizy

Wszystkie serie są obcinane do `analysis_date` (`Weather.from_daily(..., until=analysis_date)`), a sceny satelitarne
późniejsze niż ta data są pomijane. Seria pogodowa zaczyna się 1 października roku `Y − 11`, więc obejmuje
10 pełnych poprzednich lat i rozbieg bilansu glebowego (pierwsza jesień i zima).

## 2. Katalog upraw (`crops/catalog.yaml`)

Dla 9 upraw: współczynniki Kc (ini/mid/end, FAO-56 tab. 12), długości faz (FAO-56 tab. 11, przesunięte do typowych
terminów w Polsce), głębokość korzeni Zr i współczynnik `p` (FAO-56 tab. 22), okresy krytyczne dla wody.
Krzywa Kc jest odcinkowo liniowa (FAO-56 rys. 25). Poza sezonem Kc = 0 (pole bez uprawy).
Dla ozimin Kc_ini = 0,4 (przypis FAO-56 tab. 12, gleba zamarznięta).

## 3. Bilans wodny (`water_balance.py`)

- **KBW** = Σ(P − ET0) w oknie 60 dni (`KBW_WINDOW_DAYS`); ET0 FAO Penman–Monteith z Open-Meteo.
- **Bilans strefy korzeniowej** FAO-56 r. 8, krok dobowy:
  `Dr_i = clamp(Dr_{i−1} − P_i + Ks·Kc·ET0_i, 0, TAW)`, `RAW = p·TAW`,
  `Ks = 1` gdy `Dr ≤ RAW`, inaczej `Ks = (TAW − Dr)/((1 − p)·TAW)` (równ. 83–85).
  Nie modelujemy spływu powierzchniowego, podsiąku kapilarnego ani nawadniania (brak danych z pola) — to ograniczenie raportu.
- Poza sezonem uprawy pole traci wodę jak gleba bez roślin: `BARE_SOIL_KC = 0,3` (FAO-56 rys. 29, dolna granica
  dla rzadkiego zwilżania przy niskim ET0), ale tylko z warstwy powierzchniowej — parowanie ustaje, gdy
  wyczerpanie osiągnie `BARE_SOIL_TEW_MM = 20 mm` (FAO-56 tab. 19, TEW).
- Dzień bez danych P lub ET0 nie zmienia `Dr` i jest liczony jako luka. Okno z lukami > 10 % (`MAX_GAP_SHARE`) nie ma wartości.
- Bez danych o glebie bilans glebowy ma status brak, a ocena opiera się na KBW z obniżoną pewnością.

## 4. Gleba (`soil.py`)

- Polowa pojemność wodna (−33 kPa) i punkt trwałego więdnięcia (−1500 kPa): Saxton i Rawls (2006), równ. 1–2;
  materia organiczna = 1,724 · węgiel organiczny (SoilGrids).
- `TAW = 1000 · (θFC − θWP) · Zr` [mm], całkowane po warstwach SoilGrids do głębokości korzeni. Poniżej 100 cm
  przyjmujemy właściwości najgłębszej warstwy. Gdy dane pokrywają < 60 % głębokości korzeni, TAW nie jest podawane.
- Kategoria gleby I–IV: klasa uziarnienia USDA warstwy 0–30 cm przypisana do kategorii podatności na suszę IUNG-PIB
  (ekspertyza IUNG-PIB 2019, tab. 4 za Ślusarczyk 1979: I — piaski luźne i słabo gliniaste; II — piaski gliniaste;
  III — gliny lekkie i pyły; IV — gliny średnie i ciężkie, iły). Odpowiedniki USDA: I sand; II loamy sand;
  III sandy loam, loam, silt loam, silt; IV clay loamy i clay. To przybliżenie polskiej klasyfikacji gatunków gleb
  (SoilGrids nie rozróżnia frakcji < 0,02 mm), raport mówi o tym wprost.

## 5. Historia 10 lat (`history.py`)

- Lata `Y − 10 … Y − 1`, miesiące marzec–październik, w których uprawa jest na polu (≥ 7 dni).
- **Miesiąc z niedoborem**: stres wodny (Ks < 1) w ≥ 1/3 dni sezonu w miesiącu (`STRESS_SHARE`). Wymaga danych
  o glebie. Bez nich częstości nie podajemy: latem bilans P − Kc·ET0 jest ujemny także w zwykłych latach, więc stały
  próg oznaczyłby prawie każdy miesiąc, a próg względny dawałby ~30 % z definicji. Raport mówi o tym wprost.
- Częstość = liczba lat z niedoborem / liczba lat z danymi. **Miesiące ryzyka**: częstość ≥ 30 % (`RISK_FREQUENCY`).
- **Percentyl empiryczny** (10 lat to za mało na SPI): odsetek poprzednich lat z wartością niższą, remisy liczone
  w połowie; wymaga ≥ 5 lat (`MIN_YEARS_FOR_PERCENTILE`). Liczony dla opadu z 30 i 90 dni oraz KBW z 60 dni.

## 6. Teren (`terrain.py`)

- Spadek z różnic centralnych na siatce EPSG:2180, średni i maksymalny w obrębie działki; ekspozycja = kierunek
  średniego gradientu w dół stoku (poniżej 1 % — teren płaski).
- Zagłębienia: wypełnianie metodą priority-flood (Barnes i in. 2014); komórki z głębokością ≥ 0,2 m
  (`DEPRESSION_MIN_DEPTH_M`), co najmniej 2 komórki, stykające się z działką. Podajemy głębokość i objętość.
- Spływ: D8 na powierzchni wypełnionej z ε, akumulacja = powierzchnia zlewni komórki. Ścieżki koncentracji spływu:
  komórki działki ze zlewnią ≥ 0,5 ha (`FLOW_PATH_MIN_AREA_M2`).
- Wyloty: komórki działki oddające wodę poza działkę, maks. 3, co najmniej 50 m od siebie.
- Copernicus DEM 30 m (zapas) nie pokaże drobnych zagłębień — pewność średnia.

## 7. Ocena (`assessment.py`, `causes.py`)

**Okres wegetacji** 21.03–30.09 (decyzja 3 planu). Poza nim raport ocenia odbudowę zapasu wody (KBW od 1.10),
ostatni zakończony sezon (liczba dni stresu 1.03–30.09 na tle tych samych okien w poprzednich latach; tylko z danymi
o glebie) oraz — dla ozimin — stan strefy korzeniowej.

**Stan bieżący** (brak / lekki / umiarkowany / silny niedobór):

| Sygnał | Brak | Lekki | Umiarkowany | Silny |
|---|---|---|---|---|
| Ks na dzień analizy (sygnał główny, gdy jest gleba i uprawa na polu) | 1 | ≥ 0,75 | ≥ 0,5 | < 0,5 |
| Percentyl KBW 60 dni / opadu 30 dni / KBW od 1.10 | > 30 | ≤ 30 | ≤ 20 | < 10 |

Sygnał pomocniczy może podnieść poziom o najwyżej jeden stopień i nigdy go nie obniża. Gdy żadnego sygnału nie da
się porównać z historią (za mało lat z danymi), poziomu nie podajemy i ocena jest niekompletna. **Oficjalny próg suszy rolniczej IUNG-PIB (G1).** Wartości krytyczne KBW pochodzą z załącznika do
rozporządzenia MRiRW z 11.04.2019 w sprawie wartości klimatycznego bilansu wodnego dla poszczególnych gatunków roślin
uprawnych i gleb (Dz.U. 2019 poz. 739, akt obowiązujący wg API Sejmu, sprawdzone 22.11.2026), na którym opiera się
System Monitoringu Suszy Rolniczej IUNG-PIB. Tabela `crops/iung_thresholds.yaml` jest wygenerowana skryptem z oficjalnego
tekstu (`https://api.sejm.gov.pl/eli/acts/DU/2019/739/text.html`) i porównana wartość po wartości z tab. 3 ekspertyzy
IUNG-PIB (umowa 155/19, Puławy 2019) — 56 wierszy zgodnych. Przekroczenie wartości oznacza spadek plonu o ≥ 20 % w skali
gminy wobec średnich warunków (ekspertyza, s. 5).
- Okresy: 14 okresów sześciodekadowych od 21.III–20.V do 1.VIII–30.IX. Bierzemy ostatni okres oceniany dla uprawy,
  który skończył się nie później niż data analizy i nie dawniej niż 11 dni (`MAX_PERIOD_AGE_DAYS`, IUNG publikuje KBW
  po każdej dekadzie). KBW = suma (opad − ET0) dokładnie w tym okresie, zaokrąglona do 1 mm przed porównaniem
  (tekst i werdykt zawsze zgodne). `KBW ≤ próg` → susza rolnicza wg IUNG i poziom co najmniej „umiarkowany”;
  powyżej progu poziom się nie zmienia (wtedy `iung` nie trafia do `basis`). Próg stosujemy tylko w okresie wegetacji
  i gdy uprawa jest na polu (`in_vegetation` i `crop_on_field`): okresy z rozporządzenia sięgają dalej niż nasz
  kalendarz upraw, a po zbiorze werdykt dotyczyłby uprawy, której już nie ma (`IungMissing.CROP_NOT_ON_FIELD`).
- Uprawy: pszenica ozima i żyto → „zboża ozime”, jęczmień jary → „zboża jare”, kukurydza → „kukurydza na ziarno”,
  rzepak ozimy → „rzepak i rzepik”, ziemniaki, burak cukrowy, warzywa polowe → „warzywa gruntowe”. Użytki zielone nie
  mają progu w rozporządzeniu, a burak cukrowy nie ma wartości dla kategorii I — raport mówi to wprost (`IungMissing`).
- Różnice wobec SMSR (w „Ograniczeniach analizy”): IUNG liczy ETP wzorem Doroszewskiego z danych stacji i interpoluje
  na gminy; my używamy ET0 FAO-56 z modelu pogody dla punktu działki. Progi z 2019 r. stosujemy także do dat sprzed
  1.05.2019 (wcześniej obowiązywały tabele z 2016 i 2017 r.) — wtedy raport dodaje ograniczenie `iung_backdated`.
  Obserwacja z E2E (22.11.2026): na działkach referencyjnych, także latem 2018 i 2019, nasz KBW okresu był 50–100 mm
  powyżej progu, więc próg nie zmienił żadnego poziomu. Możliwe przyczyny: ET0 FAO-56 niższe od ETP wg wzoru
  Doroszewskiego oraz kategoria gleby z SoilGrids cięższa od mapy glebowo-rolniczej. Próg jest więc sygnałem
  ostrożnym (rzadko alarmuje), a główną rolę pełnią bilans w strefie korzeni i percentyle z 10 lat. Kategorię gleby wyznaczamy z SoilGrids, a nie z mapy
  glebowo-rolniczej 1:25 000.

**Satelita** porównuje kondycję roślin (mediana bieżących scen) z historią tej działki w tym samym oknie roku
(percentyl ≤ 25 = słaba kondycja). Tylko gdy uprawa jest na polu i ma rozwiniętą okrywę (Kc ≥ średnia Kc_ini i Kc_mid).
Zgodność nie zmienia poziomu; niezgodność obniża pewność o jeden stopień.

**Podatność strukturalna** — punkty; poziom z udziału punktów w maksimum możliwym dla ocenionych składników
(≥ 0,6 wysoka, ≥ 0,25 średnia, mniej niska — przy komplecie 8 pkt to ≥ 5 i ≥ 2). Gdy da się ocenić składniki warte
mniej niż 4 pkt, poziomu ogólnego nie podajemy:

| Składnik | Punkty |
|---|---|
| Gleba: kategoria I → 2, II → 1; TAW < 60 mm → 2, < 100 mm → 1 (większa z dwóch) | 0–2 |
| Lata z ≥ 1 miesiącem niedoboru: ≥ 50 % → 2, ≥ 30 % → 1 | 0–2 |
| Miesiące ryzyka pokrywają się z okresem krytycznym uprawy | 0–1 |
| Średni spadek ≥ 10 % → 2, ≥ 5 % → 1 | 0–2 |
| Brak oczek, mokradeł i zadrzewień w promieniu 500 m (OSM) | 0–1 |

Składnik bez danych nie wchodzi do sumy ani do maksimum i obniża pewność. Próg TAW jest w mm dla głębokości
korzeni danej uprawy, więc uprawy płytko korzeniące się (warzywa, ziemniaki) są z natury bardziej podatne.

**Przyczyny** (flaga tak / nie / brak danych, zawsze z dowodami liczbowymi):

1. *Deficyt opadów i wysoka temperatura*: percentyl opadu 90 dni lub KBW 60 dni ≤ 30, albo średnia Tmax z 30 dni
   ≥ 1,5 °C powyżej średniej z tych samych okien w poprzednich latach przy KBW poniżej mediany.
2. *Niska retencja gleby*: kategoria I–II, TAW < 100 mm/m lub węgiel organiczny w warstwie ornej < 10 g/kg.
3. *Nadmierny odpływ*: średni spadek ≥ 5 %, albo spadek ≥ 2 % i brak elementów retencji w promieniu 500 m lub
   wylot spływu ze zlewnią ≥ 1 ha.
4. *Wrażliwość uprawy*: data analizy w okresie krytycznym przy niedoborze albo miesiące ryzyka pokrywają się
   z okresem krytycznym.

**Pewność wyniku**: start „wysoka”, −1 za dane pogodowe zapasowe (−2 przy dużych brakach), −1 za brak gleby,
−1 za brak porównania z historią, −1 za niezgodny sygnał satelitarny. Pewność ogólna = gorsza z oceny bieżącej
i podatności.

**Warunek kompletności**: dane pogodowe obejmują 90 dni przed datą analizy, a opad z 30 dni i KBW z 60 dni dają się
policzyć. Inaczej ocena kończy się komunikatem o braku danych i rekomendacje nie powstają.

## 8. Rekomendacje (`recommendations/`)

Silnik reguł uruchamia się **tylko po kompletnej ocenie** (rozdz. 7). Każda reguła sprawdza wartości policzone dla
tej działki i dołącza je jako dowody (wartość, jednostka, źródło, okres, pewność). Reguła bez choć jednej liczby
w dowodach jest pomijana. Kolejność na liście: retencja → agrotechnika → nawadnianie (M5), a w kategorii wg priorytetu.
Teksty po polsku są w `recommendations/texts_pl.py` i wypełniane wyliczonymi wartościami.

„Potrzeba wody” (warunek wielu reguł) = bieżący niedobór co najmniej lekki **albo** co najmniej połowa z 10 lat
z miesiącem niedoboru (przy progu 30 % warunek byłby spełniony niemal wszędzie). Jako dowód bieżącego niedoboru
dołączamy tylko wskaźniki, które ustaliły poziom (`CurrentState.basis`).
„Gleba lekka” = kategoria I–II albo TAW < 100 mm/m.

| Reguła | Kategoria | Warunek | Miejsce na mapie |
|---|---|---|---|
| `ditch_check_dam` — zastawka na rowie | retencja | rów ≥ 20 m w pasie 30 m od granicy (OSM) + potrzeba wody | rowy przy granicy |
| `depression_retention` — rozlewisko / oczko | retencja | zagłębienie ≥ 0,2 m, ≥ 50 % na działce, zlewnia ≥ 1000 m² + potrzeba wody | zagłębienia |
| `outlet_buffer_strip` — pas zieleni przy wylocie spływu | retencja | przyczyna „nadmierny odpływ” + wyznaczony wylot | wyloty spływu |
| `grassed_flow_path` — zadarnienie linii spływu | retencja | średni spadek ≥ 2 %, linia spływu ze zlewnią ≥ 0,5 ha + potrzeba wody | linie spływu |
| `midfield_trees` — zadrzewienie śródpolne | retencja | brak zadrzewień w 500 m (OSM) + gleba lekka + potrzeba wody | — |
| `protect_wetlands` — ochrona mokradeł i oczek | retencja | mokradło lub zbiornik w 300 m (OSM) | te obiekty |
| `organic_matter` — obornik, słoma, międzyplony | agrotechnika | węgiel organiczny w warstwie ornej < 10 g/kg | — |
| `reduced_tillage_mulch` — uprawa uproszczona, mulcz | agrotechnika | gleba lekka + niedobór w kwietniu lub maju w ≥ 30 % lat | — |
| `contour_tillage` — uprawa w poprzek stoku | agrotechnika | średni spadek ≥ 3 % (nie dla użytków zielonych) | — |
| `crop_timing_variety` — odmiana / termin siewu | agrotechnika | miesiące ryzyka pokrywają się z okresem krytycznym uprawy | — |
| `winter_cover_crop` — międzyplon ozimy | agrotechnika | uprawa jara + (potrzeba wody lub gleba lekka) | — |
| `crop_residues` — resztki pożniwne, płytka uprawa | agrotechnika | niedobór w czerwcu–sierpniu w ≥ 30 % lat | — |
| `grassland_cutting` — wyższe koszenie | agrotechnika | użytek zielony + (niedobór teraz lub w maju–sierpniu w ≥ 30 % lat) | — |

Teksty zależą od uprawy: resztki pożniwne ze słomą tylko dla zbóż, rzepaku i kukurydzy (dla okopowych i warzyw
— szybki międzyplon); dla użytków zielonych próchnica bez orki i międzyplonów; dla ozimin odmiana zamiast
wcześniejszego siewu, dla ziemniaków „sadzenie”. Węgiel organiczny porównujemy z progiem po zaokrągleniu do 0,1 g/kg,
tak jak go pokazujemy. Na łące „brakuje teraz wody” piszemy tylko w okresie wegetacji.

Elementy z OSM mogą być niepełne (pewność niska), a teren z modelu 30 m nie pokaże drobnych zagłębień — reguły,
które z nich korzystają, dziedziczą tę pewność w dowodach. Piętrzenie wody na rowach wymaga uzgodnienia ze spółką
wodną lub Wodami Polskimi, co mówi tekst rekomendacji.

## 9. Nawadnianie — termin i dawka (`recommendations/irrigation.py`)

Nawadnianie jest **ostatnim** krokiem (CLAUDE.md, zasada 2): rekomendacja `irrigation` ma kategorię `irrigation`,
więc silnik ustawia ją na końcu listy, za retencją i agrotechniką, a jej tekst o tym przypomina. Sekcja 7 raportu
(`IrrigationAdvice`) jest zawsze obecna i gdy nawadnianie nie dotyczy, mówi dlaczego.

**Kiedy nawadnianie nie dotyczy** (`applicable = false`): niepełna ocena · data poza okresem wegetacji 21.03–30.09 ·
uprawy nie ma na polu · faza dojrzewania (etap `late` FAO-56), chyba że trwa jeszcze okres krytyczny uprawy.
Bez danych o glebie (brak bilansu strefy korzeniowej) albo przy braku danych pogodowych z dnia analizy nie podajemy
dawki ani terminu i mówimy wprost, czego brakuje. Dla użytków zielonych koniec sezonu opisujemy jako koniec wzrostu łąki.

**Zasadność:** wyczerpanie wody w strefie korzeniowej `Dr` > `RAW` = `p·TAW` (FAO-56 równ. 83–84, czyli `Ks < 1`).

**Dawka:** uzupełnienie do polowej pojemności wodnej = `Dr` w dniu nawadniania (dawka **netto**, zaokrąglona do 1 mm),
podzielona na równe dawki jednorazowe nie większe niż limit dla kategorii gleby: I — 15 mm, II — 20 mm,
III — 30 mm, IV — 35 mm, nieznana — 20 mm (praktyka deszczowania w Polsce, Dzieżyc 1988). Lżejsza gleba → mniejsze
i częstsze dawki, bo nadmiar wsiąka poniżej korzeni. Objętość na działkę: `dawka [mm] · powierzchnia [ha] · 10` m³.
Raport zaznacza, że deszczownia traci część wody (dawka brutto jest większa). Objętość jest dowodem
`irrigation_volume_m3` ze źródłem powierzchni (ULDK).

**Termin** — tylko gdy istnieje prognoza wydana w dniu analizy (data analizy = dziś): `Dr` rzutujemy na
7 dni tym samym bilansem dobowym z prognozowanym opadem i ET0 (projekcja kończy się na pierwszym dniu bez prognozy).

| Stan w dniu analizy | Projekcja | Wynik |
|---|---|---|
| `Dr > RAW`, `Ks ≥ 0,5` | opad sprowadza `Dr ≤ RAW` w ciągu 3 dni | „poczekaj, prognozowany opad zmniejszy niedobór” |
| `Dr > RAW` | brak takiego opadu albo `Ks < 0,5` (gleba prawie sucha) | „nawadniaj jak najszybciej (1–2 dni)”, dawka = dzisiejsze `Dr` |
| `Dr ≤ RAW` | `Dr` przekroczy `RAW` w dniu N i opad nie sprowadzi go poniżej w ciągu kolejnych 3 dni | „nawadniaj najpóźniej za N dni”, dawka = rzutowane `Dr` z dnia N |
| `Dr ≤ RAW` | nie przekroczy (lub tylko na chwilę przed deszczem) | „nie nawadniaj” |

Przy `Ks < 0,5` rośliny tracą już ponad połowę transpiracji, więc czekanie kilku dni na deszcz kosztuje plon.
Tekst „nawadniaj teraz” podaje opad prognozowany tylko w tym samym 3-dniowym oknie.

Dla dat historycznych prognozy nie ma (nie używamy danych późniejszych niż data analizy): podajemy stan i dawkę na dzień
analizy z jawną informacją o braku prognozy. Prognoza wydana innego dnia niż data analizy jest pomijana.

**Czynniki nieuwzględnione (M5.2):** dostępność wody (studnia, rów, ciek, zbiornik) i wymagane zgody wodnoprawne
(Wody Polskie) — każda porada nawadniania zawiera te zastrzeżenia, a sekcja „Ograniczenia analizy” ma pozycję
`water_availability_and_permits`.


## 10. Zmiany klimatu na działce (`trends.py`)

Sezon wegetacyjny 1 IV – 30 IX, tylko sezony zakończone przed datą analizy (ostatnie 10). Dla każdego sezonu: średnia
temperatura, dni upalne (Tmax ≥ 30 °C), ET0, KBW = P − ET0, dni stresu wodnego uprawy (FAO-56 Ks < 1) ogółem i w miesiącach
krytycznych. Porównujemy średnią z 10 lat, z ostatnich 3 i z ostatnich 2 sezonów. Trend: nachylenie Theila–Sena (Sen 1968),
odporne na pojedynczy skrajny rok, na dekadę; „stabilny”, gdy |trend| jest poniżej progu właściwego dla wskaźnika.
„Ostatnie lata gorsze / krytyczne”: średnia z 2 ostatnich sezonów odbiega od średniej 10-letniej o ≥ 0,5 / ≥ 1 odchylenie
standardowe w niekorzystnym kierunku (i o co najmniej minimalną różnicę bezwzględną). Wniosek słowny powstaje z szablonu.

## 11. Plan wody na sezon (`water_plan.py`)

FAO-56: ETc = Kc · ET0 dla krzywej Kc uprawy; netto zapotrzebowanie na nawadnianie z dobowego bilansu strefy korzeni
z nawadnianiem przy dopuszczalnym ubytku (Dr > RAW → uzupełnienie do polowej pojemności wodnej). Liczone dla każdego
z 10 poprzednich lat, miesiące III–X. Pokazujemy medianę („rok typowy”) oraz 80. i 90. percentyl („rok suchy” raz na 5 lat,
„bardzo suchy” raz na 10 lat) — zalecenia planujemy na rok suchy, nie na średnią. Bez danych o glebie: max(0, ETc − P)
na miesiąc (przybliżenie). Przelicznik objętości roku suchego na staw o głębokości 2 m.

## 12. Symulator strategii 1–5 lat (`simulate.py`)

Zespół 10 sezonów pogody działki (październik–październik, start od polowej pojemności po zimie) z ET0 przeskalowanym
trendem ET0 działki (metoda delta-change); opadów nie zmieniamy. Strategie: bez działań · podlewanie ratunkowe (tylko
okresy krytyczne) · pełne nawadnianie · retencja glebowa (międzyplony 0,32 t C/ha/rok — Poeplau i Don 2015 — przeliczone
na zapas wody równaniami Saxtona i Rawlsa 2006; ściółka na ~50 % powierzchni −25 % parowania z gleby, FAO-56 rozdz. 11)
· retencja + podlewanie ratunkowe. Wynik: dni stresu i woda do nawadniania (mediana i 80. percentyl). Symulator pokazuje
z danych, że podlewanie nie zwiększa zapasu wody w glebie w kolejnej wiośnie (porównanie stanu 1 kwietnia w ciągłym
bilansie z nawadnianiem i bez), a wpływ próchnicy na zapas wody jest mały (Minasny i McBratney 2018).

## 13. Profil spadku (`profile.py`)

Linia przez środek działki wzdłuż średniego kierunku spadku (na płaskim terenie: wzdłuż dłuższego boku), przycięta do
działki, wysokości interpolowane dwuliniowo z siatki NMT (5 m) lub Copernicus (30 m). Obniżenia: miejsca, gdzie
powierzchnia po wypełnieniu zagłębień (priority-flood) jest ≥ 0,2 m wyżej niż teren.
