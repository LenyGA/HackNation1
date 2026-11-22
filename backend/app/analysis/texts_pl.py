"""Polish plain-language reasons attached to computed indicators (confidence explanations).

Kept out of the logic as a dictionary; farmer-facing report sentences live in report/templates (step M6.2).
"""

REASONS: dict[str, str] = {
    "weather_ok": "Dane pogodowe z reanalizy w siatce ok. 10 km, nie z pomiaru na polu.",
    "weather_degraded": "Dane pogodowe zapasowe lub niepełne, więc wynik jest mniej pewny.",
    "percentile_10y": "Porównanie z tymi samymi dniami w 10 poprzednich latach; 10 lat to krótka seria.",
    "percentile_few_years": "Za mało lat z kompletnymi danymi, żeby porównać z historią.",
    "root_zone": "Zapas wody w glebie policzony metodą FAO-56 z danych pogodowych i mapy gleb 250 m.",
    "soil_map": "Mapa gleb SoilGrids ma oczka 250 m, więc opisuje okolicę działki, nie każde jej miejsce.",
    "soil_category_approx": (
        "Kategorię gleby wyznaczono z uziarnienia mapy SoilGrids, a nie z mapy glebowej IUNG."
    ),
    "terrain_cop": "Model wysokości 30 m; drobne zagłębienia i rowy mogą nie być widoczne.",
    "terrain_nmt": "Numeryczny model terenu z pomiaru lotniczego.",
    "osm": "Mapa OpenStreetMap bywa niepełna, zwłaszcza dla rowów i małych oczek.",
    "worldcover": (
        "Z mapy pokrycia terenu ESA WorldCover 10 m (zastępczo, bo mapa OpenStreetMap nie odpowiedziała); "
        "małe oczka, wąskie rowy i pojedyncze drzewa mogą być niewidoczne."
    ),
    "satellite": (
        "Zdjęcia satelitarne porównane z historią tej działki; uprawa w poprzednich latach jest nieznana."
    ),
    "crop_calendar": (
        "Typowe terminy dla Polski; na Twoim polu fazy rozwoju mogą przesunąć się o 1–3 tygodnie."
    ),
    "history_crop_balance": (
        "Bez danych o glebie częstość niedoborów policzono z samego bilansu opadu i parowania."
    ),
    "forecast": "Prognoza pogody na najbliższe dni; może się jeszcze zmienić.",
    "irrigation_volume": "Dawka nawadniania razy powierzchnia działki z ewidencji gruntów (ULDK).",
    "computed": "Wartość wyliczona przez aplikację z danych źródłowych.",
    "iung_regulation": (
        "Wartość krytyczna z rozporządzenia (Dz.U. 2019 poz. 739) dla tej grupy upraw i kategorii gleby."
    ),
}

CONFIDENCE_REASONS: dict[str, str] = {
    "weather_degraded": "dane pogodowe są zapasowe lub niepełne",
    "weather_low": "w danych pogodowych są duże braki",
    "soil_missing": "brak danych o glebie, więc nie liczymy zapasu wody w glebie",
    "satellite_agrees": "zdjęcia satelitarne potwierdzają ocenę",
    "satellite_disagrees": "zdjęcia satelitarne nie potwierdzają oceny",
    "root_zone_unavailable": "zapasu wody w glebie nie udało się policzyć na dzień analizy",
    "few_years": "za mało lat z danymi do porównania z historią",
    "components_unknown": "część czynników nie została oceniona z powodu braku danych",
    "base": "ocena oparta na danych pogodowych, glebowych i 10-letniej historii",
}
