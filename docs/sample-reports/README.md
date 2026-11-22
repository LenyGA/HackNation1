# Przykładowe raporty (Z6)

Raporty wygenerowane **22.11.2026 ok. 08:25** przez działającą wersję https://129.121.162.156.sslip.io dla 6 działek
referencyjnych z `backend/tests/e2e/parcels.yaml`, każda dla dwóch dat (bieżąca 22.11.2026 i historyczna 15.07.2019),
w obu wariantach: **Podstawowy** (1–2 strony) i **Pełny**. Każdy raport jest też zapisany w aplikacji pod linkiem
`https://129.121.162.156.sslip.io/raport/<ID>`.

Czas analizy liczony od wysłania zapytania do gotowego raportu; część danych historycznych była już w cache serwera
(z wcześniejszych serii od 06:35, gdy analizy na zimno trwały 2,6–18 s), dlatego teraz trwały tylko kilka sekund.

Nazwa pliku: `<działka>_<biezaca|historyczna>_<data>_<podstawowy|pelny>.pdf`.

| Działka | Numer | Uprawa | Data | Czas analizy | ID raportu | Źródła niepełne lub brak |
|---|---|---|---|---|---|---|
| Murowana Goślina (wielkopolskie), gleba lekka, płasko | `302111_4.0001.468/1` | żyto | 2026-11-22 | 17.6 s | `XR-i_VT5gw_d2yKoNMQZ_w` | pogoda: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: częściowe |
| Murowana Goślina (wielkopolskie), gleba lekka, płasko | `302111_4.0001.468/1` | żyto | 2019-07-15 | 4.4 s | `f9-FMYoJmbodr9RoJ8hOwQ` | satelita: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: brak |
| Tuja, Nowy Dwór Gdański (Żuławy), gleba ciężka, gęsta sieć rowów | `221002_5.0019.131/1` | pszenica ozima | 2026-11-22 | 4.4 s | `pIlqqxJCEGPmBiVfnOA3pA` | pogoda: częściowe, satelita: częściowe, hydrologia (OSM): brak |
| Tuja, Nowy Dwór Gdański (Żuławy), gleba ciężka, gęsta sieć rowów | `221002_5.0019.131/1` | pszenica ozima | 2019-07-15 | 4.5 s | `qAp8YZ-2lsTqQTmydCUymQ` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Kipszna, Ciężkowice (Pogórze), stok, mała działka | `121601_5.0007.53` | ziemniaki | 2026-11-22 | 2.6 s | `jhBBGoGlCLwiSTr98CBgnQ` | pogoda: częściowe, satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: częściowe |
| Kipszna, Ciężkowice (Pogórze), stok, mała działka | `121601_5.0007.53` | ziemniaki | 2019-07-15 | 4.5 s | `orEufd4cyjrC9sJGmnrvhA` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Dębówko Nowe (dolina Noteci), łąka z rowami | `301902_2.0002.364` | użytki zielone | 2026-11-22 | 2.6 s | `3pW-Tv0VzgyCcgF9hc5NtQ` | pogoda: częściowe, hydrologia (OSM): brak |
| Dębówko Nowe (dolina Noteci), łąka z rowami | `301902_2.0002.364` | użytki zielone | 2019-07-15 | 4.4 s | `GoeYwQYOVZToG16NiFQV3w` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Łuszczanowice, Kleszczów (przy kopalni Bełchatów) | `100104_2.0013.756/1` | kukurydza | 2026-11-22 | 2.6 s | `nLnW0txAd1f1tON7BbdLaA` | pogoda: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: częściowe |
| Łuszczanowice, Kleszczów (przy kopalni Bełchatów) | `100104_2.0013.756/1` | kukurydza | 2019-07-15 | 4.5 s | `Doi1dLUlcr-lsqZK69N7og` | satelita: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: brak |
| Pabierowice, Grójec (mazowieckie), sad jabłoniowy | `140605_5.0028.4/4` | sad – jabłonie, grusze | 2026-11-22 | 2.6 s | `b7VTffu_I8BTfnKVIAvr1A` | pogoda: częściowe, hydrologia (OSM): brak, wody gruntowe: częściowe |
| Pabierowice, Grójec (mazowieckie), sad jabłoniowy | `140605_5.0028.4/4` | sad – jabłonie, grusze | 2019-07-15 | 4.4 s | `otcZd_TcMHVXethccNESGQ` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |

Braki danych są w raportach podane wprost (sekcja „Ograniczenia analizy” i komunikaty przy sekcjach). W chwili
generowania publiczne serwery OpenStreetMap Overpass nie odpowiadały, więc rowy i cieki są „brak danych”, a zadrzewienia,
wody i mokradła w otoczeniu pochodzą z zapasowej mapy WorldCover. Dla dat historycznych zdjęcia satelitarne bywają
„częściowe” (mniej bezchmurnych scen), a wiele automatycznych stacji wód gruntowych PIG-PIB nie miało jeszcze pomiarów.
