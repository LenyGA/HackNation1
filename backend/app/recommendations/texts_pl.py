"""Polish plain-language texts of the recommendations, filled with computed values (str.format).

Kept out of the rule logic. Report step M6.2 may move them to Jinja templates; keys stay the same.
Derived placeholders (`*_pl`) are added by `render()` from the raw parameters.
"""

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
}

TEXTS: dict[str, str] = {
    "ditch_check_dam": (
        "Wzdłuż granicy działki biegnie rów (ok. {ditch_length_m} m). Zastawka lub próg piętrzący na rowie "
        "zatrzyma wodę wiosną i po deszczach, zamiast odprowadzać ją z okolicy. Piętrzenie na rowach "
        "melioracyjnych uzgodnij ze spółką wodną lub Wodami Polskimi."
    ),
    "depression_retention": (
        "Na działce {depressions_pl}. Do największego spływa woda z ok. {contributing_ha} ha{volume_pl}. "
        "Zostaw je jako okresowe rozlewisko lub oczko wodne zamiast zasypywać lub drenować."
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

KIND_PL = {"wetland": "mokradło", "water_body": "oczko lub zbiornik wodny"}


def fmt(value: ParamValue) -> str:
    """Polish number formatting: decimal comma, no trailing '.0'."""
    if isinstance(value, bool):
        return str(int(value))
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
    if template == "protect_wetlands":
        dist = float(params.get("distance_m", 0))
        out["distance_pl"] = (
            "Tuż przy działce lub na niej" if dist < NEAR_M else f"W odległości ok. {fmt(dist)} m od działki"
        )
    if template == "organic_matter":
        out["om_actions_pl"] = OM_ACTIONS_PL["grassland" if params.get("grassland") else "arable"]
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
    return out


def render(template: str, params: dict[str, ParamValue]) -> tuple[str, str]:
    return TITLES[template], TEXTS[template].format(**derived(template, params))
