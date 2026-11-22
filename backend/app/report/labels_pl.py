"""Polish labels used by the report (dictionaries, no logic). Sentences live in `templates/*.j2`."""

from app.recommendations.texts_pl import MONTHS_PL as MONTHS_PL_NOMINATIVE

__all__ = ["MONTHS_PL_NOMINATIVE"]

INDICATOR_LABELS: dict[str, str] = {
    "precip_30d_mm": "Suma opadów z ostatnich 30 dni",
    "precip_30d_pct": "Opad z 30 dni na tle 10 lat (% lat z mniejszym opadem)",
    "precip_90d_mm": "Suma opadów z ostatnich 90 dni",
    "precip_90d_pct": "Opad z 90 dni na tle 10 lat (% lat z mniejszym opadem)",
    "kbw_60d_mm": "Opad minus parowanie, ostatnie 60 dni",
    "kbw_60d_pct": "Opad minus parowanie z 60 dni na tle 10 lat (% lat bardziej suchych)",
    "kbw_iung_period_mm": "Opad minus parowanie w okresie progu suszy IUNG-PIB",
    "recharge_kbw_mm": "Opad minus parowanie od 1 października",
    "recharge_kbw_pct": "Opad minus parowanie od 1 października na tle 10 lat (% lat bardziej suchych)",
    "taw_mm": "Woda dostępna dla roślin w strefie korzeni przy pełnym nasyceniu",
    "taw_per_m_mm": "Woda dostępna dla roślin na 1 m gleby",
    "raw_mm": "Woda łatwo dostępna dla roślin",
    "root_zone_depletion_mm": "Ubytek wody w strefie korzeni",
    "root_zone_available_mm": "Woda, która została w glebie dla roślin",
    "root_zone_depletion_pct": "Ubytek wody w strefie korzeni",
    "ks": "Wskaźnik stresu wodnego roślin (1 = brak stresu)",
    "ndvi_current": "Kondycja roślin na dzień analizy (wskaźnik zieleni ze zdjęć satelitarnych)",
    "ndvi_history_median": "Typowa kondycja roślin w tym terminie w poprzednich latach",
    "ndvi_pct": "Kondycja roślin na tle lat poprzednich (% lat ze słabszą)",
    "ndvi_history_years": "Lata ze zdjęciami satelitarnymi do porównania",
    "last_season_stress_days": "Dni z niedoborem wody w ostatnim sezonie",
    "last_season_stress_pct": "Dni z niedoborem w ostatnim sezonie na tle lat (% lat z mniejszą liczbą)",
    "last_season_deficit_months": "Miesiące z niedoborem wody w ostatnim sezonie",
    "deficit_year_share_pct": "Lata z niedoborem wody (z 10 poprzednich)",
    "soil_category": "Kategoria gleby (I = najlżejsza, IV = najcięższa)",
    "groundwater_flooding_risk": "Obszar zagrożenia podtopieniami (PIG-PIB)",
    "flood_zone_risk": "Strefa zagrożenia powodziowego (ISOK)",
    "sand_topsoil_pct": "Piasek w wierzchniej warstwie gleby",
    "clay_topsoil_pct": "Ił w wierzchniej warstwie gleby",
    "soc_topsoil_g_per_kg": "Węgiel organiczny w wierzchniej warstwie gleby",
    "slope_mean_pct": "Średni spadek terenu na działce",
    "slope_max_pct": "Największy spadek terenu na działce",
    "main_outlet_area_m2": "Powierzchnia, z której woda spływa głównym wylotem z działki",
    "nearest_retention_element_m": "Odległość do najbliższego oczka, mokradła lub zadrzewienia",
    "nearest_wetland_or_pond_m": "Odległość do najbliższego oczka lub mokradła",
    "nearest_trees_m": "Odległość do najbliższego zadrzewienia",
    "trees_within_radius_count": "Zadrzewienia w pobliżu działki",
    "trees_share_surroundings_pct": "Udział drzew w promieniu 500 m od działki",
    "wetlands_and_ponds_count": "Oczka i mokradła w pobliżu działki",
    "ditch_length_along_boundary_m": "Długość rowów wzdłuż granicy działki",
    "depression_count": "Zagłębienia terenu na działce",
    "depression_max_depth_m": "Głębokość największego zagłębienia",
    "depression_volume_m3": "Woda, którą może zatrzymać zagłębienie",
    "depression_contributing_area_m2": "Powierzchnia, z której woda spływa do zagłębienia",
    "flow_path_contributing_area_m2": "Powierzchnia, z której woda spływa linią spływu",
    "tmax_30d_mean_c": "Średnia temperatura maksymalna z 30 dni",
    "tmax_30d_anomaly_c": "Odchylenie temperatury maksymalnej od lat poprzednich",
    "hot_days_30d": "Dni upalne (≥ 30 °C) w ostatnich 30 dniach",
    "hot_days_30d_history_mean": "Średnio dni upalnych w tym okresie w 10 latach",
    "forecast_precip_mm": "Prognozowany opad na najbliższe dni",
    "irrigation_dose_mm": "Dawka nawadniania (do pełnego uzupełnienia wody w glebie)",
    "irrigation_volume_m3": "Ilość wody na całą działkę",
}
MONTH_INDICATOR_PREFIX = "deficit_frequency_month_"
MONTH_INDICATOR_LABEL = "Lata z niedoborem wody w miesiącu: {month}"

UNIT_PL: dict[str, str] = {"lat": "lat", "dni": "dni", "mies.": "mies.", "kat.": ""}

SOURCE_LABELS: dict[str, str] = {
    "uldk": "Działka (ewidencja gruntów)",
    "open_meteo": "Pogoda (opady, temperatura, parowanie)",
    "sentinel2": "Zdjęcia satelitarne (kondycja roślin)",
    "soilgrids": "Gleba (skład, próchnica, zapas wody)",
    "dem": "Ukształtowanie terenu (spadki, spływ wody)",
    "hydro": "Rowy, cieki, oczka i zadrzewienia w okolicy",
    "landcover": "Użytkowanie terenu (pola, łąki, zabudowa)",
    "flood": "Zagrożenie powodziowe (mapy Wód Polskich)",
    "groundwater": "Wody podziemne w okolicy (monitoring PIG-PIB)",
}

LEVEL_LABELS: dict[str, str] = {
    "none": "Brak niedoboru wody",
    "light": "Lekki niedobór wody",
    "moderate": "Umiarkowany niedobór wody",
    "severe": "Silny niedobór wody",
    "unknown": "Brak oceny — za mało danych",
}

VULNERABILITY_LABELS: dict[str, str] = {
    "low": "niska",
    "medium": "średnia",
    "high": "wysoka",
}

CONFIDENCE_LABELS: dict[str, str] = {
    "high": "wysoka",
    "medium": "średnia",
    "low": "niska",
}

SECTION_TITLES: dict[str, str] = {
    "summary": "Podsumowanie",
    "current": "Sytuacja wodna na dzień {date}",
    "vulnerability": "Jak często brakowało wody w ostatnich 10 latach",
    "causes": "Dlaczego brakuje wody",
    "retention": "Zatrzymywanie wody na działce",
    "agrotech": "Zabiegi na polu",
    "irrigation": "Nawadnianie",
    "sources": "Źródła danych",
    "limitations": "Ograniczenia analizy i braki danych",
}

MAP_LEGEND: dict[str, str] = {
    "depression": "Miejsce, w którym zbiera się woda (zagłębienie terenu)",
    "flow_path": "Linia, którą po deszczu spływa woda",
    "outlet": "Miejsce, którym woda spływa z działki",
    "ditch": "Rów",
    "watercourse": "Rzeka lub strumień",
    "water_body": "Oczko lub zbiornik wodny",
    "wetland": "Mokradło",
    "trees": "Las lub zadrzewienie",
}

TEXTURE_PL: dict[str, str] = {
    "sand": "piasek",
    "loamy_sand": "piasek gliniasty",
    "sandy_loam": "glina piaszczysta",
    "loam": "glina",
    "silt_loam": "pył gliniasty",
    "silt": "pył",
    "sandy_clay_loam": "glina piaszczysto-ilasta",
    "clay_loam": "glina ilasta",
    "silty_clay_loam": "glina pylasto-ilasta",
    "sandy_clay": "ił piaszczysty",
    "silty_clay": "ił pylasty",
    "clay": "ił",
}

SOIL_CATEGORY_PL: dict[str, str] = {
    "I": "bardzo lekka",
    "II": "lekka",
    "III": "średnia",
    "IV": "ciężka",
}

COMPASS_FROM_PL: dict[str, str] = {
    "N": "północ",
    "NE": "północny wschód",
    "E": "wschód",
    "SE": "południowy wschód",
    "S": "południe",
    "SW": "południowy zachód",
    "W": "zachód",
    "NW": "północny zachód",
}

VULNERABILITY_COMPONENTS_PL: dict[str, str] = {
    "soil": "gleba",
    "deficit_frequency": "częstość niedoborów wody",
    "critical_period_risk": "ryzyko w okresie, gdy uprawa najbardziej potrzebuje wody",
    "slope": "spadki terenu",
    "retention_elements": "oczka, mokradła i zadrzewienia w okolicy",
}

CAUSE_TITLES: dict[str, str] = {
    "precipitation_deficit_heat": "Mało deszczu i wysoka temperatura",
    "low_soil_retention": "Gleba słabo zatrzymuje wodę",
    "excessive_runoff": "Woda szybko spływa z pola",
    "crop_sensitivity": "Uprawa jest wrażliwa na brak wody w tym okresie",
}

STATUS_PL: dict[str, str] = {
    "ok": "dane pobrane",
    "degraded": "dane pobrane z ograniczeniami",
    "missing": "brak danych",
}
