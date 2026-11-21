"""Jinja environment for the report texts (plan step M6.2) and Polish formatting filters.

Text templates (`templates/sections/*.j2`, `templates/missing/*.j2`, `limitations.j2`) produce plain text:
paragraphs are separated by blank lines, and a line `== details ==` starts the
"Szczegóły dla zainteresowanych" part, the only place where technical terms (NDVI, KBW,
percentyl) may appear (CLAUDE.md rule 9).
"""

import math
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.analysis.common import round_to
from app.core.config import LOCAL_TZ
from app.recommendations.texts_pl import MONTHS_GENITIVE_PL, MONTHS_PL
from app.report.labels_pl import CAUSE_TITLES

TEMPLATES_DIR = Path(__file__).parent / "templates"
DETAILS_MARK = "== details =="

# Words that must not appear in the main text of the report (only in the details part).
JARGON = ("NDVI", "NDMI", "KBW", "percentyl", "ewapotranspiracj", "TAW", "RAW")

MONTHS_LOCATIVE_PL = {
    1: "styczniu",
    2: "lutym",
    3: "marcu",
    4: "kwietniu",
    5: "maju",
    6: "czerwcu",
    7: "lipcu",
    8: "sierpniu",
    9: "wrześniu",
    10: "październiku",
    11: "listopadzie",
    12: "grudniu",
}


def num(value: float | int | None, step: float = 1.0) -> str:
    """Polish number: sensible rounding (rule 4), decimal comma, thin grouping of thousands."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "brak danych"
    rounded = round_to(float(value), step)
    if rounded is None:
        return "brak danych"
    digits = max(0, -int(f"{step:e}".split("e")[1]))
    if rounded == 0:
        rounded = 0.0  # no "-0"
    # No-break space between thousands so a number never wraps across lines.
    text = f"{rounded:,.{digits}f}".replace(",", "\u00a0").replace(".", ",")
    return text


def date_pl(value: date | datetime | str | None) -> str:
    """'2024-07-15' → '15 lipca 2024'."""
    if value is None:
        return "brak daty"
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    if isinstance(value, datetime):
        value = value.astimezone(LOCAL_TZ).date()
    return f"{value.day} {MONTHS_GENITIVE_PL[value.month]} {value.year}"


def day_month_pl(value: date) -> str:
    return f"{value.day} {MONTHS_GENITIVE_PL[value.month]}"


def month_pl(month: int) -> str:
    return MONTHS_PL[month]


def month_in_pl(month: int) -> str:
    """Locative: 'w czerwcu'."""
    return MONTHS_LOCATIVE_PL[month]


def join_pl(items: list[str], last: str = "i") -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {last} {items[-1]}"


def months_pl(months: list[int]) -> str:
    return join_pl([MONTHS_PL[m] for m in months])


def years_pl(n: int) -> str:
    """'1 rok', '3 lata', '5 lat'."""
    if n == 1:
        return "1 rok"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} lata"
    return f"{n} lat"


def plural(n: int, one: str, few: str, many: str) -> str:
    """Polish plural form for a count: 1 punkt, 2 punkty, 5 punktów."""
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def days_instr_pl(n: float) -> str:
    """Instrumental: 'z 1 dniem', 'z 5 dniami'."""
    n = round(n)
    return "1 dniem" if n == 1 else f"{n} dniami"


def days_pl(n: float) -> str:
    n = round(n)
    return "1 dzień" if n == 1 else f"{n} dni"


def wetness_pl(pct: float | None) -> str:
    """Empirical percentile of a precipitation / water-balance value, in plain words (no jargon)."""
    if pct is None:
        return "nie da się porównać z poprzednimi latami"
    if pct < 10:
        return "mniej niż w którymkolwiek z poprzednich lat"
    if pct <= 20:
        return "mniej niż zwykle, to jeden z najsuchszych takich okresów w ostatnich latach"
    if pct <= 30:
        return "mniej niż zwykle"
    if pct < 70:
        return "mniej więcej tyle, ile zwykle o tej porze roku"
    if pct <= 90:
        return "więcej niż zwykle"
    return "więcej niż w którymkolwiek z poprzednich lat"


def balance_pl(pct: float | None) -> str:
    """Percentile of the water balance (precipitation − evaporation), in plain words; low = drier."""
    if pct is None:
        return "nie da się porównać z poprzednimi latami"
    if pct < 10:
        return "to najbardziej sucho spośród wszystkich poprzednich lat"
    if pct <= 20:
        return "to wyraźnie bardziej sucho niż zwykle"
    if pct <= 30:
        return "to bardziej sucho niż zwykle"
    if pct < 70:
        return "to typowo dla tej pory roku"
    if pct <= 90:
        return "to bardziej wilgotno niż zwykle"
    return "to najbardziej wilgotno spośród wszystkich poprzednich lat"


# Short names of the data behind a computed number (the full citation is in the "sources" section).
SOURCE_SHORT_PL: list[tuple[str, str]] = [
    ("ULDK", "ewidencja gruntów"),
    ("Open-Meteo", "pogoda"),
    ("NASA POWER", "pogoda"),
    ("Sentinel-2", "zdjęcia satelitarne"),
    ("SoilGrids", "mapa gleb"),
    ("Copernicus DEM", "model terenu"),
    ("Numeryczny Model Terenu", "model terenu"),
    ("OpenStreetMap", "mapa OpenStreetMap"),
    ("WorldCover", "mapa użytkowania terenu"),
    ("Forecast", "prognoza pogody"),
]


def source_short(source: str) -> str:
    names: list[str] = []
    for needle, name in SOURCE_SHORT_PL:
        if needle.lower() in source.lower() and name not in names:
            names.append(name)
    return join_pl(names) if names else source


def capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _env(autoescape: bool) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        extensions=["jinja2.ext.do"],
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
        autoescape=autoescape,
    )
    env.filters.update(
        num=num,
        date_pl=date_pl,
        day_month_pl=day_month_pl,
        month_pl=month_pl,
        month_in_pl=month_in_pl,
        months_pl=months_pl,
        join_pl=join_pl,
        years_pl=years_pl,
        days_pl=days_pl,
        wetness_pl=wetness_pl,
        balance_pl=balance_pl,
        plural=plural,
        days_instr_pl=days_instr_pl,
        source_short=source_short,
        capitalize_first=capitalize,
        abs=abs,
        cause_title=lambda cause_id: CAUSE_TITLES[cause_id],
    )
    return env


@lru_cache
def text_env() -> Environment:
    return _env(autoescape=False)


@lru_cache
def html_env() -> Environment:
    return _env(autoescape=True)


_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:)])")


def _paragraphs(text: str) -> list[str]:
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        clean = _SPACE_BEFORE_PUNCT.sub(r"\1", _SPACES.sub(" ", block)).strip()
        if clean:
            out.append(clean)
    return out


def render_text(template: str, **context: Any) -> tuple[list[str], list[str]]:
    """Render a text template → (main paragraphs, details paragraphs)."""
    raw = text_env().get_template(template).render(**context)
    main, _, details = raw.partition(DETAILS_MARK)
    return _paragraphs(main), _paragraphs(details)


def render_line(template: str, **context: Any) -> str:
    """Render a template expected to produce one paragraph (or nothing)."""
    main, _ = render_text(template, **context)
    return " ".join(main)
