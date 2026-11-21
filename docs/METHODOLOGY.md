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
- Kategoria gleby I–IV: klasa uziarnienia USDA warstwy 0–30 cm przypisana do grup IUNG
  (I: piasek; II: piasek gliniasty; III: glina piaszczysta, glina, pył; IV: gliny ilaste i iły).
  To przybliżenie klasyfikacji PTG, raport mówi o tym wprost.

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
się porównać z historią (za mało lat z danymi), poziomu nie podajemy i ocena jest niekompletna. Próg IUNG (gdy jest
w tabeli `crops/iung_thresholds.yaml`) dotyczy ostatniego okresu IUNG kończącego się nie później niż data analizy;
KBW liczymy wtedy dla tego okresu, a przekroczenie progu ustawia co najmniej „umiarkowany”. **Tabela IUNG jest obecnie pusta**, bo nie mamy
opublikowanych wartości (krok M1.4 otwarty) — raport to zaznacza.

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
