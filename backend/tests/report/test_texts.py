"""Polish formatting filters used by the report templates (plan M6.2)."""

from datetime import UTC, date, datetime

import pytest

from app.report.texts import (
    balance_pl,
    date_pl,
    days_pl,
    join_pl,
    months_pl,
    num,
    plural,
    render_text,
    source_short,
    wetness_pl,
    years_pl,
)


@pytest.mark.parametrize(
    ("value", "step", "expected"),
    [
        (12.345, 1.0, "12"),
        (0.456, 0.01, "0,46"),
        (0.5, 0.1, "0,5"),
        (1234.567, 1.0, "1\u00a0235"),
        (1234567.8, 0.1, "1\u00a0234\u00a0567,8"),
        (-0.2, 1.0, "0"),  # no "-0"
        (-3.6, 1.0, "-4"),
        (12, 5.0, "10"),
        (None, 1.0, "brak danych"),
        (float("nan"), 1.0, "brak danych"),
        (float("inf"), 1.0, "brak danych"),
    ],
)
def test_num(value: float | None, step: float, expected: str) -> None:
    assert num(value, step) == expected


def test_num_uses_decimal_comma_never_dot() -> None:
    assert "." not in num(3.14159, 0.01)
    assert num(3.14159, 0.01) == "3,14"


def test_date_pl() -> None:
    assert date_pl(date(2024, 7, 15)) == "15 lipca 2024"
    assert date_pl("2024-01-01") == "1 stycznia 2024"
    assert date_pl("2026-11-21T08:00:00+00:00") == "21 listopada 2026"
    # Late UTC evening is already the next day in Poland.
    assert date_pl(datetime(2024, 12, 31, 23, 30, tzinfo=UTC)) == "1 stycznia 2025"
    assert date_pl(None) == "brak daty"


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "punktów"),
        (1, "punkt"),
        (2, "punkty"),
        (4, "punkty"),
        (5, "punktów"),
        (11, "punktów"),
        (12, "punktów"),
        (14, "punktów"),
        (21, "punktów"),
        (22, "punkty"),
        (25, "punktów"),
        (112, "punktów"),
        (122, "punkty"),
    ],
)
def test_plural(n: int, expected: str) -> None:
    assert plural(n, "punkt", "punkty", "punktów") == expected


def test_years_pl() -> None:
    assert [years_pl(n) for n in (1, 2, 5, 10, 12, 22)] == [
        "1 rok",
        "2 lata",
        "5 lat",
        "10 lat",
        "12 lat",
        "22 lata",
    ]


def test_days_pl_accepts_float() -> None:
    assert days_pl(1.0) == "1 dzień"
    assert days_pl(1.4) == "1 dzień"
    assert days_pl(2.6) == "3 dni"
    assert days_pl(7) == "7 dni"
    assert "." not in days_pl(3.2)


@pytest.mark.parametrize(
    ("pct", "fragment"),
    [
        (None, "nie da się porównać"),
        (0.0, "mniej niż w którymkolwiek"),
        (9.9, "mniej niż w którymkolwiek"),
        (10.0, "mniej niż zwykle"),
        (30.0, "mniej niż zwykle"),
        (30.1, "mniej więcej tyle"),
        (69.9, "mniej więcej tyle"),
        (70.0, "więcej niż zwykle"),
        (90.0, "więcej niż zwykle"),
        (90.1, "więcej niż w którymkolwiek"),
        (100.0, "więcej niż w którymkolwiek"),
    ],
)
def test_wetness_pl_boundaries(pct: float | None, fragment: str) -> None:
    assert wetness_pl(pct).startswith(fragment)


@pytest.mark.parametrize(
    ("pct", "fragment"),
    [
        (None, "nie da się porównać"),
        (5.0, "to najbardziej sucho"),
        (10.0, "to wyraźnie bardziej sucho"),
        (30.0, "to bardziej sucho niż zwykle"),
        (20.0, "to wyraźnie bardziej sucho"),
        (50.0, "to typowo"),
        (70.0, "to bardziej wilgotno"),
        (90.0, "to bardziej wilgotno"),
        (95.0, "to najbardziej wilgotno"),
    ],
)
def test_balance_pl_boundaries(pct: float | None, fragment: str) -> None:
    assert balance_pl(pct).startswith(fragment)


def test_no_jargon_in_plain_word_filters() -> None:
    for pct in (None, 0, 20, 50, 80, 100):
        for text in (wetness_pl(pct), balance_pl(pct)):
            assert "percentyl" not in text.lower()


def test_join_and_months() -> None:
    assert join_pl([]) == ""
    assert join_pl(["a"]) == "a"
    assert join_pl(["a", "b", "c"]) == "a, b i c"
    assert join_pl(["a", "", "b"], last="lub") == "a lub b"
    assert months_pl([6, 7]) == "czerwiec i lipiec"


def test_source_short() -> None:
    assert source_short("Open-Meteo ERA5 archive; NASA POWER") == "pogoda"
    assert source_short("unknown provider") == "unknown provider"


def test_render_text_splits_main_and_details() -> None:
    main, details = render_text(
        "missing/soilgrids.j2", status="missing", message="Serwis nie odpowiada.", label="Gleba"
    )
    assert main and main[0].startswith("Gleba")
    assert details == []


def _causes_text(v: dict[str, float]) -> str:
    cause = {"id": "precipitation_deficit_heat", "flagged": True, "v": v, "context": {}}
    main, _ = render_text("sections/causes.j2", complete=True, causes=[cause], crop_name="kukurydza")
    return " ".join(main)


def test_causes_one_hot_day_grammar() -> None:
    text = _causes_text(
        {"precip_90d_mm": 40.0, "precip_90d_pct": 5.0, "tmax_30d_anomaly_c": 2.0, "hot_days_30d": 1}
    )
    assert "z 1 dzień" not in text


def test_flagged_precip_cause_does_not_say_typical() -> None:
    text = _causes_text(
        {"precip_90d_mm": 134.0, "precip_90d_pct": 50.0, "kbw_60d_mm": 10.0, "kbw_60d_pct": 20.0}
    )
    assert "ile zwykle" not in text
