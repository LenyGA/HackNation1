"""Polish plain-language texts of the recommendations, filled with computed values (str.format).

Kept out of the rule logic. Report step M6.2 may move them to Jinja templates; keys stay the same.
Derived placeholders (`*_pl`) are added by `render()` from the raw parameters.
"""

from datetime import date

from app.recommendations.models import ParamValue

TITLES: dict[str, str] = {
    "ditch_check_dam": "Zatrzymaj wodę w rowie przy działce",
    "depression_retention": "Wykorzystaj zagłębienie terenu do zatrzymania wody",
    "outlet_buffer_strip": "Pas zieleni tam, gdzie woda spływa z pola",
    "grassed_flow_path": "Zadarnij miejsce, którym płynie woda po deszczu",
    "midfield_trees": "Posadź pas drzew lub krzewów przy polu",
    "protect_wetlands": "Chroń pobliskie oczko lub mokradło",
    "organic_matter": "Zwiększ ilość próchnicy w glebie",
    "reduced_tillage_mulch": "Ogranicz orkę i zostaw mulcz na powierzchni",
    "contour_tillage": "Uprawiaj i siej w poprzek stoku",
    "crop_timing_variety": "Dopasuj odmianę lub termin siewu do suchych miesięcy",
    "winter_cover_crop": "Nie zostawiaj pola gołego na zimę",
    "crop_residues": "Chroń wilgoć w glebie po zbiorze",
    "grassland_cutting": "Koś wyżej i nie koś w czasie suszy",
    "orchard_mulch_sward": "Ściółkuj rzędy i ogranicz konkurencję trawy o wodę",
}

TEXTS: dict[str, str] = {
    "ditch_check_dam": (
        "Wzdłuż granicy działki biegnie rów (ok. {ditch_length_m} m). Zastawka lub próg piętrzący na rowie "
        "zatrzyma wodę wiosną i po deszczach, zamiast odprowadzać ją z okolicy. Piętrzenie na rowach "
        "melioracyjnych uzgodnij ze spółką wodną lub Wodami Polskimi."
    ),
    "depression_retention": (
        "Na działce {depressions_pl}. Do największego spływa woda z ok. {contributing_ha} ha{volume_pl}. "
        "{depression_action_pl}"
    ),
    "outlet_buffer_strip": (
        "Średni spadek pola to {slope_mean_pct} %, a woda po deszczu spływa z działki {direction_pl}. "
        "Pas trawy, miedza lub krzewy szerokości kilku metrów w poprzek spływu w tym miejscu spowolnią wodę, "
        "dadzą jej czas wsiąknąć i zatrzymają glebę."
    ),
    "grassed_flow_path": (
        "Przez działkę przebiega linia, którą po deszczu płynie woda z ok. {contributing_ha} ha. "
        "Zadarnienie tego pasa (trwała trawa zamiast uprawy) spowolni spływ i ograniczy rozmywanie gleby."
    ),
    "midfield_trees": (
        "{trees_pl} Gleba na polu jest lekka i słabo trzyma wodę. Pas drzew lub krzewów przy granicy pola "
        "osłabi wiatr, zmniejszy parowanie z gleby i pomoże zatrzymać śnieg zimą."
    ),
    "protect_wetlands": (
        "{distance_pl} jest {kind_pl}. "
        "Takie miejsca magazynują wodę dla okolicy. Nie odwadniaj ich i nie pogłębiaj rowów, "
        "które z nich odprowadzają wodę."
    ),
    "organic_matter": (
        "W wierzchniej warstwie gleby jest ok. {soc_g_per_kg} g węgla organicznego na kg, czyli mało "
        "(poniżej {threshold_g_per_kg} g/kg). {om_actions_pl} Gleba z większą ilością próchnicy "
        "zatrzymuje więcej wody."
    ),
    "reduced_tillage_mulch": (
        "Gleba jest lekka, a w ostatnich 10 latach wiosną ({months_pl}) roślinom często brakowało wody "
        "w glebie. Uprawa uproszczona bez orki i resztki roślin zostawione na powierzchni "
        "ograniczą parowanie wody z gleby."
    ),
    "contour_tillage": (
        "Średni spadek pola to {slope_mean_pct} %{aspect_pl}. Orka, uprawa i siew w poprzek stoku "
        "(wzdłuż poziomic) tworzą bruzdy, które zatrzymują wodę zamiast odprowadzać ją w dół pola."
    ),
    "crop_timing_variety": (
        "Najbardziej wrażliwy na brak wody okres uprawy ({crop}: {phase}) przypada na miesiące, w których "
        "w ostatnich 10 latach często brakowało wody ({months_pl}). {timing_pl}"
    ),
    "winter_cover_crop": (
        "Przed siewem lub sadzeniem uprawy jarej ({crop}) pole zimą często stoi bez roślin. Po zbiorze "
        "przedplonu wysiej międzyplon (np. żyto lub wykę ozimą, a gorczycę jako międzyplon ścierniskowy). "
        "Okrywa roślin chroni glebę przed wysychaniem i spływem, a jej resztki zwiększą próchnicę."
    ),
    "crop_residues": ("Latem ({months_pl}) w ostatnich 10 latach często brakowało wody. {residues_pl}"),
    "grassland_cutting": (
        "{grass_pl} Koś na wysokości 7–10 cm, nie koś w czasie suszy i nie wypasaj zbyt intensywnie — "
        "wyższa darń osłania glebę i szybciej odrasta po deszczu."
    ),
    "orchard_mulch_sward": (
        "{orchard_pl} Wyłóż w pasie rzędów ściółkę grubości 5–10 cm (kora, zrębki lub słoma) — ogranicza "
        "parowanie wody z gleby i chwasty. W czasie suszy koś murawę w międzyrzędziach często i nisko, "
        "żeby trawa nie zabierała wody {plants_pl}, i nie spulchniaj wtedy gleby w rzędach."
    ),
}

MONTHS_PL = {
    1: "styczeń",
    2: "luty",
    3: "marzec",
    4: "kwiecień",
    5: "maj",
    6: "czerwiec",
    7: "lipiec",
    8: "sierpień",
    9: "wrzesień",
    10: "październik",
    11: "listopad",
    12: "grudzień",
}

# Where the water leaves the parcel (outflow direction).
SIDE_PL = {
    "N": "po północnej stronie",
    "NE": "po północno-wschodniej stronie",
    "E": "po wschodniej stronie",
    "SE": "po południowo-wschodniej stronie",
    "S": "po południowej stronie",
    "SW": "po południowo-zachodniej stronie",
    "W": "po zachodniej stronie",
    "NW": "po północno-zachodniej stronie",
}
SIDE_UNKNOWN_PL = "w najniższym miejscu"

# Direction the slope faces.
ASPECT_PL = {
    "N": "północ",
    "NE": "północny wschód",
    "E": "wschód",
    "SE": "południowy wschód",
    "S": "południe",
    "SW": "południowy zachód",
    "W": "zachód",
    "NW": "północny zachód",
}

NEAR_M = 10.0

OM_ACTIONS_PL = {
    "arable": "Obornik, pocięta i wymieszana z glebą słoma oraz międzyplony zwiększą próchnicę.",
    "grassland": (
        "Nawożenie obornikiem lub gnojowicą i utrzymanie zwartej darni (bez zaorywania) zwiększą próchnicę."
    ),
    "fruit": (
        "Kompost lub obornik pod rzędy, ściółka z kory lub zrębków w pasie rzędów i zwarta murawa "
        "w międzyrzędziach zwiększą próchnicę."
    ),
}

TIMING_PL = {
    "sown": "Rozważ odmianę wcześniejszą lub wcześniejszy siew, żeby ten okres wypadł przed typową suszą.",
    "planted": (
        "Rozważ odmianę wcześniejszą lub wcześniejsze sadzenie, żeby ten okres wypadł przed typową suszą."
    ),
    "winter": (
        "Rozważ odmianę wcześniejszą lub bardziej odporną na suszę; "
        "termin siewu jesienią niewiele tu zmienia."
    ),
}

RESIDUES_PL = {
    "straw": (
        "Po zbiorze zostaw słomę i resztki na polu, a uprawę pożniwną rób płytko i szybko, "
        "żeby zatrzymać wilgoć w glebie."
    ),
    "no_straw": (
        "Po zbiorze nie zostawiaj gołej, spulchnionej gleby: szybko wysiej międzyplon ścierniskowy "
        "lub przykryj glebę resztkami roślin, żeby zatrzymać wilgoć."
    ),
}

KIND_PL = {
    "wetland": "mokradło",
    "water_body": "oczko lub zbiornik wodny",
    # WorldCover class 80 (fallback without OSM) does not tell a pond from a river or canal.
    "open_water": "woda powierzchniowa (oczko, zbiornik lub ciek)",
}


def fmt(value: ParamValue) -> str:
    """Polish number formatting: decimal comma, no trailing '.0', thin space between thousands (≥ 10 000)."""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (int, float)) and abs(value) >= 10_000 and float(value).is_integer():
        return f"{int(value):,}".replace(",", "\u00a0")
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value}".replace(".", ",")
    return str(value)


def _months(value: ParamValue) -> str:
    months = [int(m) for m in str(value).split(",") if m]
    return ", ".join(MONTHS_PL[m] for m in months)


def derived(template: str, params: dict[str, ParamValue]) -> dict[str, str]:
    out = {k: fmt(v) for k, v in params.items()}
    if "months" in params:
        out["months_pl"] = _months(params["months"])
    if "direction" in params:
        out["direction_pl"] = SIDE_PL.get(str(params["direction"]), SIDE_UNKNOWN_PL)
    if "aspect" in params:
        aspect = ASPECT_PL.get(str(params["aspect"]))
        out["aspect_pl"] = f", stok jest skierowany na {aspect}" if aspect else ""
    if "kind" in params:
        out["kind_pl"] = KIND_PL.get(str(params["kind"]), "teren podmokły")
    if template == "depression_retention":
        n = int(params.get("count", 1))
        out["depressions_pl"] = (
            "jest zagłębienie terenu, w którym zbiera się woda"
            if n == 1
            else f"są zagłębienia terenu (liczba: {n}), w których zbiera się woda"
        )
    if template == "depression_retention":
        vol = params.get("volume_m3")
        out["volume_pl"] = f" i może ono zatrzymać ok. {fmt(vol)} m³ wody" if vol else ""
        out["depression_action_pl"] = _depression_action(params)
    if template == "protect_wetlands":
        dist = float(params.get("distance_m", 0))
        out["distance_pl"] = (
            "Tuż przy działce lub na niej" if dist < NEAR_M else f"W odległości ok. {fmt(dist)} m od działki"
        )
    if template == "organic_matter":
        out["om_actions_pl"] = OM_ACTIONS_PL[
            "fruit" if params.get("fruit") else "grassland" if params.get("grassland") else "arable"
        ]
    if template == "crop_timing_variety":
        out["timing_pl"] = TIMING_PL[str(params.get("timing", "sown"))]
    if template == "crop_residues":
        out["residues_pl"] = RESIDUES_PL["straw" if params.get("straw") else "no_straw"]
    if template == "midfield_trees":
        nearest = params.get("nearest_trees_m", 0)
        out["trees_pl"] = (
            f"Najbliższe zadrzewienie jest ok. {fmt(nearest)} m od działki."
            if nearest
            else f"W promieniu {fmt(params.get('radius_m', 0))} m od działki mapa nie pokazuje zadrzewień."
        )
    if template == "grassland_cutting":
        parts = []
        if params.get("deficit_now"):
            parts.append("Na łące brakuje teraz wody.")
        if params.get("months"):
            parts.append(f"W ostatnich 10 latach wody często brakowało w miesiącach: {out['months_pl']}.")
        out["grass_pl"] = " ".join(parts)
    if template == "orchard_mulch_sward":
        parts = []
        if params.get("light_soil"):
            parts.append("Gleba jest lekka i słabo trzyma wodę.")
        if params.get("months"):
            parts.append(f"W ostatnich 10 latach wody często brakowało w miesiącach: {out['months_pl']}.")
        out["orchard_pl"] = " ".join(parts)
        out["plants_pl"] = "krzewom" if params.get("bushes") else "drzewom"
    if template == "irrigation":
        out["irrigation_pl"] = irrigation_text(params)
    return out


def render(template: str, params: dict[str, ParamValue]) -> tuple[str, str]:
    return TITLES[template], TEXTS[template].format(**derived(template, params))


# --- irrigation (plan step M5) ----------------------------------------------------------------------

TITLES["irrigation"] = "Nawadnianie: kiedy i ile wody"
TEXTS["irrigation"] = "{irrigation_pl}"

IRRIGATION_TITLES: dict[str, str] = {
    "no_assessment": "Nawadnianie: brak zaleceń",
    "off_season": "Nawadnianie nie dotyczy tego terminu",
    "no_crop": "Nawadnianie nie dotyczy tego terminu",
    "late_stage": "Nawadnianie nie jest już potrzebne",
    "no_balance": "Nawadnianie: nie da się policzyć dawki",
    "not_needed": "Nie nawadniaj",
    "wait_for_rain": "Poczekaj z nawadnianiem",
    "irrigate": "Nawadnianie: kiedy i ile wody",
    "irrigate_soon": "Nawadnianie: kiedy i ile wody",
}

NO_CROP_PL: dict[str, str] = {
    "after_harvest": (
        "W dniu analizy ({date}) uprawa ({crop}) jest zwykle już po zbiorze, "
        "więc jej nawadnianie nie dotyczy. "
        "Wodę w glebie warto teraz chronić dla międzyplonu lub następnej uprawy."
    ),
    "before_regrowth": (
        "W dniu analizy ({date}) użytki zielone jeszcze nie ruszyły z wegetacją po zimie, "
        "więc nawadnianie nie dotyczy."
    ),
    "before_sowing": (
        "W dniu analizy ({date}) uprawa ({crop}) nie jest jeszcze wysiana albo dopiero wschodzi, "
        "więc nawadnianie nie dotyczy."
    ),
    "fruit_dormant": (
        "W dniu analizy ({date}) drzewa i krzewy ({crop}) są jeszcze w spoczynku zimowym "
        "albo już zrzuciły liście, więc nawadnianie nie dotyczy."
    ),
}

IRRIGATION_PL: dict[str, str] = {
    "no_assessment": "Bez pełnej oceny sytuacji wodnej działki nie podajemy zaleceń nawadniania.",
    "off_season": (
        "Dzień analizy ({date}) wypada poza okresem wegetacji ({season_pl}), więc nawadnianie nie dotyczy."
    ),
    "no_crop": "{no_crop_pl}",
    "late_stage": "{late_pl}",
    "no_balance": "{no_balance_pl}",
    "not_needed": (
        "Nie nawadniaj. W dniu analizy ({date}) w glebie jest jeszcze ok. {available_mm} mm wody "
        "dostępnej dla roślin, a uprawa ({crop}) nie odczuwa jej braku.{outlook_pl}"
    ),
    "wait_for_rain": (
        "Poczekaj z nawadnianiem. Uprawie ({crop}) zaczyna brakować wody, ale prognoza zapowiada "
        "ok. {rain_until_relief_mm} mm deszczu do {relief_date}, co powinno zmniejszyć niedobór. "
        "Sprawdź ponownie po opadach."
    ),
    "irrigate": "{when_pl}{phase_pl} {dose_pl}{forecast_note_pl} {order_pl}",
    "irrigate_soon": "{when_pl}{phase_pl} {dose_pl} {order_pl}",
}

LATE_PL = {
    "crop": (
        "Uprawa ({crop}) jest w dniu analizy ({date}) w fazie dojrzewania. Podlewanie na tym etapie "
        "nie zwiększy już plonu."
    ),
    "grassland": (
        "W dniu analizy ({date}) łąka kończy już sezon wzrostu. Podlewanie na tym etapie "
        "nie zwiększy już plonu."
    ),
    "fruit": (
        "W dniu analizy ({date}) owoce są już zebrane, a drzewa i krzewy ({crop}) kończą sezon "
        "przed opadaniem liści. Podlewanie na tym etapie nie zwiększy już plonu — wystarczy, "
        "że gleba nie przeschnie przed zimą."
    ),
}

NO_BALANCE_PL = {
    "soil": (
        "Bez pełnych danych o glebie nie da się policzyć, ile wody zostało w glebie, więc nie podajemy "
        "terminu ani dawki nawadniania."
    ),
    "weather_gap": (
        "Brakuje danych pogodowych z dnia analizy, więc nie da się policzyć, ile wody zostało w glebie, "
        "ani podać terminu i dawki nawadniania."
    ),
}

IRRIGATION_ORDER_PL = (
    "Nawadnianie to ostatni krok — ratuje bieżący sezon, ale na dłuższą metę ważniejsze jest zatrzymywanie "
    "wody na działce i w glebie (pozostałe zalecenia w tym raporcie)."
)

FORECAST_NOTE_PL = {
    "historical": (
        " Dla daty z przeszłości nie ma prognozy pogody, dlatego podajemy tylko stan na dzień analizy, "
        "bez terminu nawadniania."
    ),
    "unavailable": (
        " Prognoza pogody nie była dostępna, dlatego nie sprawdziliśmy, "
        "czy w najbliższych dniach spadnie deszcz."
    ),
    "used": "",
}

NOT_NEEDED_OUTLOOK_PL = {
    "used": (
        " Według prognozy na {forecast_days_pl} zapas wody nie spadnie na dłużej do poziomu, przy którym "
        "rośliny zaczynają cierpieć."
    ),
    "historical": " Dla daty z przeszłości nie ma prognozy pogody, więc to ocena stanu na dzień analizy.",
    "unavailable": (
        " Prognoza pogody nie była dostępna, więc nie sprawdziliśmy, "
        "jak zapas wody zmieni się w najbliższych dniach."
    ),
}

# Prawo wodne (2017), art. 33: "ordinary use" of water excludes sprinkler irrigation with groundwater and
# abstraction above 5 m³/day, which need a water-law permit; "zwykle" because cases differ.
IRRIGATION_CAVEATS_PL = [
    "Analiza nie sprawdza, czy masz dostęp do wody do nawadniania (studnia, rów, ciek, zbiornik) ani czy "
    "wystarczy jej na całą dawkę.",
    "Nawadnianie deszczownią wodą podziemną, a także pobór wody ponad 5 m³ na dobę, zwykle wymaga pozwolenia "
    "wodnoprawnego Wód Polskich. Sprawdź to przed rozpoczęciem nawadniania — analiza tego nie uwzględnia.",
]
# FAO-56 ch. 7 / ch. 8: under drip only the wetted fraction fw of the surface loses water by evaporation and
# gets water; the dose here is for the whole area, so the real volume of a drip system is lower.
FRUIT_CAVEAT_PL = (
    "W sadach i na plantacjach krzewów zwykle nawadnia się kroplowo — woda trafia tylko do pasa rzędów, "
    "więc rzeczywista ilość wody jest mniejsza niż dawka podana dla całej powierzchni."
)
DOSE_CAVEAT_PL = (
    "Podana dawka to woda, która ma wsiąknąć w glebę. Deszczownia traci część wody na parowanie i znoszenie "
    "przez wiatr, więc trzeba wylać jej nieco więcej."
)

SPLIT_REASON_PL = {
    1: "bo lekka gleba nie zatrzyma więcej wody i nadmiar wsiąknie poniżej korzeni",
    0: "żeby woda zdążyła wsiąknąć, zamiast spływać po powierzchni lub uciekać poniżej korzeni",
}

MONTHS_GENITIVE_PL = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}
DATE_PARAMS = ("date", "relief_date", "irrigate_by")


def date_pl(iso: str) -> str:
    """'2024-07-15' → '15 lipca 2024'."""
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS_GENITIVE_PL[d.month]} {d.year}"


def day_month_pl(iso: str) -> str:
    """'2024-03-21' → '21 marca'."""
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS_GENITIVE_PL[d.month]}"


def days_pl(n: int) -> str:
    return "1 dnia" if n == 1 else f"{n} dni"


def days_nominative_pl(n: int) -> str:
    return "1 dzień" if n == 1 else f"{n} dni"


def doses_pl(n: int) -> str:
    if n == 1:
        return "dawkę"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "dawki"
    return "dawek"


def irrigation_title(status: str) -> str:
    return IRRIGATION_TITLES[status]


def irrigation_caveats(status: str, fruit: bool = False) -> list[str]:
    if status in ("irrigate", "irrigate_soon"):
        return [*IRRIGATION_CAVEATS_PL, DOSE_CAVEAT_PL, *([FRUIT_CAVEAT_PL] if fruit else [])]
    if status in ("not_needed", "wait_for_rain", "no_balance"):
        return list(IRRIGATION_CAVEATS_PL)
    return []


def _when_now(params: dict[str, ParamValue], out: dict[str, str]) -> str:
    crop = out["crop"]
    forecast = str(params.get("forecast"))
    if forecast == "historical":
        return (
            f"W dniu analizy ({out['date']}) uprawie ({crop}) brakowało wody i nawadnianie było uzasadnione."
        )
    lack = "bardzo brakuje" if params.get("severe") else "brakuje"
    text = f"Uprawie ({crop}) {lack} wody — nawadniaj jak najszybciej, najlepiej w ciągu 1–2 dni."
    if forecast != "used":
        return text
    rain = float(params.get("rain_soon_mm", 0))
    days = days_pl(int(params.get("wait_days", 0)))
    if rain < 1:
        return text + f" Prognoza nie zapowiada deszczu w ciągu najbliższych {days}."
    if params.get("severe"):
        return text + (
            f" Nie czekaj na zapowiadany deszcz (ok. {fmt(rain)} mm w ciągu najbliższych {days}) — "
            "w glebie prawie nie ma już wody dla roślin."
        )
    return text + (
        f" Deszcz zapowiadany w ciągu najbliższych {days} (ok. {fmt(rain)} mm) nie wystarczy, "
        "żeby pokryć niedobór."
    )


def _dose(params: dict[str, ParamValue], out: dict[str, str]) -> str:
    n = int(params.get("applications", 1))
    dose = (
        f"Do pełnego uzupełnienia wody w glebie brakuje ok. {out['dose_mm']} mm "
        f"(ok. {out['volume_m3']} m³ wody na całą działkę)."
    )
    if n > 1:
        light = int(params.get("light_soil", 0))
        soil = "lekkiej " if light else ""
        dose += (
            f" Na tej {soil}glebie podawaj jednorazowo najwyżej ok. {out['single_dose_max_mm']} mm — "
            f"rozłóż wodę na {n} {doses_pl(n)} po ok. {out['single_dose_mm']} mm co 2–3 dni, "
            f"{SPLIT_REASON_PL[light]}."
        )
    else:
        dose += f" Wystarczy jedna dawka ok. {out['dose_mm']} mm."
    if params.get("within_days") == 0:
        dose += " Jeśli nawodnisz później, dawka będzie nieco większa, bo rośliny dalej zużywają wodę."
    return dose


def _depression_action(params: dict[str, ParamValue]) -> str:
    """Q6: uncontrolled pool only where it cannot waterlog the field; otherwise a controlled pond / weir."""
    if not params.get("controlled"):
        return "Zostaw je jako okresowe rozlewisko lub oczko wodne zamiast zasypywać lub drenować."
    why: list[str] = []
    if params.get("heavy_soil"):
        why.append("gleba jest ciężka i słabo przepuszcza wodę")
    if params.get("groundwater_flooding"):
        why.append("działka leży na obszarze zagrożenia podtopieniami (PIG-PIB)")
    if params.get("flood_zone"):
        why.append("działka leży w strefie zagrożenia powodziowego (ISOK)")
    reason = " i ".join(why) if why else "teren jest narażony na nadmiar wody"
    return (
        f"Tu {reason}, więc niekontrolowane rozlewisko po mokrej zimie lub wiośnie grozi wymakaniem upraw "
        "(zwłaszcza ozimin). Lepszy jest kontrolowany staw lub zastawka z odpływem (przelewem): "
        "wiosną spuścisz nadmiar wody, a od maja zatrzymasz ją na suche tygodnie."
    )


def irrigation_text(params: dict[str, ParamValue]) -> str:
    """Polish text of the irrigation advice (report section 7 and the recommendation in the list)."""
    status = str(params["status"])
    out = {k: fmt(v) for k, v in params.items()}
    for key in DATE_PARAMS:
        if key in params:
            out[key] = date_pl(str(params[key]))
    if "season_start" in params and "season_end" in params:
        out["season_pl"] = (
            f"{day_month_pl(str(params['season_start']))} – {day_month_pl(str(params['season_end']))}"
        )
    forecast = str(params.get("forecast", "historical"))
    out["forecast_note_pl"] = FORECAST_NOTE_PL.get(forecast, "")
    out["order_pl"] = IRRIGATION_ORDER_PL
    phase = params.get("phase")
    out["phase_pl"] = f" To okres, w którym uprawa najbardziej potrzebuje wody ({phase})." if phase else ""
    if status == "late_stage":
        out["late_pl"] = LATE_PL[
            "fruit" if params.get("fruit") else "grassland" if params.get("grassland") else "crop"
        ].format(**out)
    if status == "no_crop":
        out["no_crop_pl"] = NO_CROP_PL[
            "fruit_dormant"
            if params.get("fruit")
            else "after_harvest"
            if params.get("after_harvest")
            else "before_regrowth"
            if params.get("grassland")
            else "before_sowing"
        ].format(**out)
    if status == "no_balance":
        out["no_balance_pl"] = NO_BALANCE_PL[str(params.get("reason", "soil"))]
    if status == "not_needed":
        out["forecast_days_pl"] = days_nominative_pl(int(params.get("forecast_days", 0)))
        out["outlook_pl"] = NOT_NEEDED_OUTLOOK_PL.get(forecast, "").format(**out)
    if status == "irrigate":
        out["when_pl"] = _when_now(params, out)
        out["dose_pl"] = _dose(params, out)
    if status == "irrigate_soon":
        out["when_pl"] = (
            "Według prognozy zapas wody w glebie spadnie do poziomu, przy którym "
            f"uprawie ({out['crop']}) zacznie brakować wody, w ciągu {days_pl(int(params['within_days']))} — "
            f"nawadniaj najpóźniej {out['irrigate_by']}."
        )
        out["dose_pl"] = _dose(params, out)
    return " ".join(IRRIGATION_PL[status].format(**out).split())
