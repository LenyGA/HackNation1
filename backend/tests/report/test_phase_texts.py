"""Q3: field phase from the crop calendar drives the "no crop" and satellite texts (not one generic sentence)."""

from datetime import date

import pytest

from app.analysis.assessment import assess
from app.recommendations.engine import recommend
from app.recommendations.irrigation import irrigation_advice
from app.report.builder import ParcelSource, build_report
from app.report.models import Report
from app.report.texts import date_dmy
from tests.analysis.builders import crop, make_inputs, ok, sentinel_data
from tests.report.builders import CREATED

GENERIC = (
    "nie zakryła jeszcze pola",
    "nie zakryło jeszcze pola",
    "nie rośnie jeszcze uprawa",
    "albo jest już po zbiorze",
)


def _report(crop_id: str, day: date, ndvi_now: float = 0.72) -> Report:
    inputs = make_inputs(day, crop_id, sentinel2=ok("sentinel2", sentinel_data(day, ndvi_now, 0.5)))
    a = assess(inputs)
    return build_report(
        report_id="t",
        created_at=CREATED,
        inputs=inputs,
        assessment=a,
        recommendations=recommend(a, inputs),
        irrigation=irrigation_advice(a, inputs, today=day),
        parcel_source=ParcelSource(fetched_at=CREATED),
    )


def _texts(r: Report) -> str:
    out = [p for s in r.sections for p in s.paragraphs_pl]
    out += [r.irrigation.text_pl]
    if r.satellite is not None:
        out.append(r.satellite.text_pl)
    return " ".join(out)


@pytest.mark.parametrize(
    ("crop_id", "month", "day", "phase"),
    [
        ("rye", 7, 22, "after_harvest"),
        ("rye", 6, 25, "ripening"),
        ("maize", 4, 15, "before_sowing"),
        ("maize", 5, 10, "establishment"),
        ("maize", 7, 22, "canopy"),
        ("winter_wheat", 8, 20, "after_harvest"),
        ("spring_barley", 3, 10, "before_sowing"),
    ],
)
def test_field_phase_from_calendar(crop_id: str, month: int, day: int, phase: str) -> None:
    assert crop(crop_id).field_phase(date(2025, month, day)) == phase


def test_rye_in_late_july_is_harvest_not_emergence() -> None:
    day = date(2025, 7, 22)
    text = _texts(_report("rye", day))
    assert "po zbiorze" in text
    for g in GENERIC:
        assert g not in text, g
    assert "nie zakrywają pola" not in text and "nie ma jeszcze na polu" not in text


def test_maize_in_mid_april_is_before_sowing() -> None:
    day = date(2025, 4, 15)
    text = _texts(_report("maize", day))
    assert "nie jest jeszcze wysiana" in text
    assert "po zbiorze" not in text
    for g in GENERIC:
        assert g not in text, g


def test_satellite_text_describes_the_actual_scene() -> None:
    day = date(2025, 7, 22)
    r = _report("rye", day, ndvi_now=0.72)
    assert r.satellite is not None
    scene_day = max(p.day for p in r.satellite.points if p.current)
    assert date_dmy(scene_day) in r.satellite.text_pl
    assert "powyżej zakresu" in r.satellite.text_pl  # 0.72 against a 0.50 history band
    assert "niski wynik byłby normalny" not in r.satellite.text_pl
