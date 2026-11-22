# Przykładowe raporty (Z6)

Raporty wygenerowane **22.11.2026 ok. 06:35–06:40** przez działającą wersję https://129.121.162.156.sslip.io dla 6 działek
referencyjnych z `backend/tests/e2e/parcels.yaml`, każda dla dwóch dat (bieżąca 22.11.2026 i historyczna 15.07.2019),
w obu wariantach: **Podstawowy** (1–2 strony) i **Pełny**. Każdy raport jest też zapisany w aplikacji pod linkiem
`https://129.121.162.156.sslip.io/raport/<ID>`.

Czas analizy liczony od wysłania zapytania do gotowego raportu; część danych historycznych była już w cache serwera
(m.in. po E2E i rozgrzaniu cache), dlatego niektóre analizy trwały tylko kilka sekund.

Nazwa pliku: `<działka>_<biezaca|historyczna>_<data>_<podstawowy|pelny>.pdf`.

| Działka | Numer | Uprawa | Data | Czas analizy | ID raportu | Źródła niepełne lub brak |
|---|---|---|---|---|---|---|
| Murowana Goślina (wielkopolskie), gleba lekka, płasko | `302111_4.0001.468/1` | żyto | 2026-11-22 | 18.3 s | `v1LhH583cUMULuaNsXe3qw` | hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: częściowe |
| Murowana Goślina (wielkopolskie), gleba lekka, płasko | `302111_4.0001.468/1` | żyto | 2019-07-15 | 6.3 s | `K2xPQMA0cDKV_LXxAVPs0A` | satelita: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: brak |
| Tuja, Nowy Dwór Gdański (Żuławy), gleba ciężka, gęsta sieć rowów | `221002_5.0019.131/1` | pszenica ozima | 2026-11-22 | 2.6 s | `iSGj29Ig_dlPYGPMK_4EGQ` | satelita: częściowe, hydrologia (OSM): brak |
| Tuja, Nowy Dwór Gdański (Żuławy), gleba ciężka, gęsta sieć rowów | `221002_5.0019.131/1` | pszenica ozima | 2019-07-15 | 4.5 s | `Ja-3kSM0cPFip-JrcvDzBw` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Kipszna, Ciężkowice (Pogórze), stok, mała działka | `121601_5.0007.53` | ziemniaki | 2026-11-22 | 10.0 s | `wD6wLgIYfBtTWMTsjvpRwA` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: częściowe |
| Kipszna, Ciężkowice (Pogórze), stok, mała działka | `121601_5.0007.53` | ziemniaki | 2019-07-15 | 4.5 s | `EDjLnEncKecCrgd9EpvgXQ` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Dębówko Nowe (dolina Noteci), łąka z rowami | `301902_2.0002.364` | użytki zielone | 2026-11-22 | 11.9 s | `MgfSg1SMVZ95PrBOI7I-fg` | hydrologia (OSM): brak |
| Dębówko Nowe (dolina Noteci), łąka z rowami | `301902_2.0002.364` | użytki zielone | 2019-07-15 | 4.5 s | `FMf5S9s1KA5NZInhaC1cWg` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |
| Łuszczanowice, Kleszczów (przy kopalni Bełchatów) | `100104_2.0013.756/1` | kukurydza | 2026-11-22 | 10.1 s | `pXjluNfQLC5NVLEsp--PsA` | hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: częściowe |
| Łuszczanowice, Kleszczów (przy kopalni Bełchatów) | `100104_2.0013.756/1` | kukurydza | 2019-07-15 | 4.5 s | `K2lfKd0psjJKjuup8EjwzA` | satelita: częściowe, hydrologia (OSM): brak, powodzie: częściowe, wody gruntowe: brak |
| Pabierowice, Grójec (mazowieckie), sad jabłoniowy | `140605_5.0028.4/4` | sad – jabłonie, grusze | 2026-11-22 | 12.2 s | `AkmVkzae7kI9aRBbZJbn5A` | hydrologia (OSM): brak, wody gruntowe: częściowe |
| Pabierowice, Grójec (mazowieckie), sad jabłoniowy | `140605_5.0028.4/4` | sad – jabłonie, grusze | 2019-07-15 | 6.4 s | `wEld5e9kdAG5M84-cjlyjw` | satelita: częściowe, hydrologia (OSM): brak, wody gruntowe: brak |

Braki danych są w raportach podane wprost (sekcja „Ograniczenia analizy” i komunikaty przy sekcjach). W chwili
generowania publiczne serwery OpenStreetMap Overpass nie odpowiadały, więc rowy i cieki są „brak danych”, a zadrzewienia,
wody i mokradła w otoczeniu pochodzą z zapasowej mapy WorldCover. Dla dat historycznych zdjęcia satelitarne bywają
„częściowe” (mniej bezchmurnych scen), a wiele automatycznych stacji wód gruntowych PIG-PIB nie miało jeszcze pomiarów.
