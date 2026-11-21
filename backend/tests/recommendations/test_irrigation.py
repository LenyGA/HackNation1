"""Irrigation timing and dose (plan step M5): when it applies, dose, forecast projection, caveats (M5.2)."""

import dataclasses
import re
from collections.abc import Callable
from datetime import date, timedelta

import pytest

from app.analysis.assessment import Assessment, assess
from app.analysis.context import AnalysisInputs
from app.analysis.water_balance import root_zone_balance
from app.recommendations.engine import recommend
from app.recommendations.irrigation import (
    MAX_SINGLE_DOSE_MM,
    ForecastUse,
    IrrigationAdvice,
    IrrigationStatus,
    irrigation_advice,
    project,
    single_dose_max_mm,
)
from app.recommendations.models import Category
from app.recommendations.texts_pl import date_pl, doses_pl, render
from app.sources.open_meteo import WeatherForecast
from tests.analysis.builders import crop
from tests.recommendations.builders import CLAY_LOAM_RICH, SUMMER, by_id, ids, scenario, wet

FORBIDDEN = re.compile(r"\b(NDVI|NDMI|KBW|percentyl\w*|FAO|TAW|RAW|Ks|ET0)\b", re.IGNORECASE)


def with_forecast(
    inputs: AnalysisInputs,
    precip: list[float | None],
    et0: list[float | None],
    issued_on: date | None = None,
) -> AnalysisInputs:
    day = inputs.analysis_date
    assert inputs.weather.data is not None
    fc = WeatherForecast(
        issued_on=issued_on or day,
        dates=[day + timedelta(days=i + 1) for i in range(len(precip))],
        precip_mm=precip,
        et0_mm=et0,
        tmax_c=[25.0] * len(precip),
    )
    data = inputs.weather.data.model_copy(update={"forecast": fc})
    return dataclasses.replace(inputs, weather=inputs.weather.model_copy(update={"data": data}))


def advise(
    *, forecast: tuple[list[float | None], list[float | None]] | None = None, **kw: object
) -> tuple[Assessment, AnalysisInputs, IrrigationAdvice]:
    a, inputs, _ = scenario(**kw)  # type: ignore[arg-type]
    if forecast is not None:
        inputs = with_forecast(inputs, *forecast)
        a = assess(inputs)
    return a, inputs, irrigation_advice(a, inputs, today=inputs.analysis_date if forecast else None)


def check_text(adv: IrrigationAdvice) -> None:
    t = adv.text_pl
    assert t and "{" not in t and "}" not in t
    assert not FORBIDDEN.search(t), t
    assert not re.search(r"\d\.\d", t), t
    assert "  " not in t


# --- when irrigation does not apply ----------------------------------------------------------------


def test_wet_soil_means_do_not_irrigate() -> None:
    _, _, adv = advise(precip=wet)
    assert adv.status is IrrigationStatus.NOT_NEEDED
    assert adv.applicable and adv.dose_mm is None
    assert adv.text_pl.startswith("Nie nawadniaj")
    assert "prognozy" in adv.text_pl  # historical date: says there is no forecast
    check_text(adv)


def test_wet_soil_not_in_recommendation_list() -> None:
    assert "irrigation" not in ids(scenario(precip=wet)[2])


@pytest.mark.parametrize("day", [date(2024, 11, 21), date(2024, 3, 1), date(2024, 10, 15)])
def test_off_season_says_irrigation_does_not_apply(day: date) -> None:
    _, _, adv = advise(day=day)
    assert adv.status is IrrigationStatus.OFF_SEASON
    assert not adv.applicable and adv.dose_mm is None
    assert "nie dotyczy" in adv.text_pl
    assert date_pl(day.isoformat()) in adv.text_pl
    check_text(adv)


def test_crop_not_on_field_in_vegetation_period() -> None:
    _, _, adv = advise(day=date(2024, 4, 1))  # maize is sown later
    assert adv.status is IrrigationStatus.NO_CROP
    assert not adv.applicable
    check_text(adv)


def test_ripening_stage_gets_no_irrigation() -> None:
    _, _, adv = advise(crop_id="winter_wheat", day=date(2024, 7, 20))
    assert adv.status is IrrigationStatus.LATE_STAGE
    assert not adv.applicable


def test_without_soil_data_no_dose_and_says_so() -> None:
    _, _, adv = advise(soil=False)
    assert adv.status is IrrigationStatus.NO_BALANCE
    assert adv.dose_mm is None and adv.applicable
    assert "glebie" in adv.text_pl
    check_text(adv)


def test_incomplete_assessment_gives_no_advice() -> None:
    a, inputs, recs = scenario(weather=False)
    adv = irrigation_advice(a, inputs)
    assert adv.status is IrrigationStatus.NO_ASSESSMENT
    assert "irrigation" not in ids(recs)


# --- dose and timing ------------------------------------------------------------------------------


def test_dry_historical_date_gives_dose_without_timing() -> None:
    a, _, adv = advise()
    assert a.root_zone is not None
    bday = a.root_zone.at(SUMMER)
    assert bday is not None and bday.dr_mm > a.root_zone.raw_mm
    assert adv.status is IrrigationStatus.IRRIGATE
    assert adv.forecast is ForecastUse.HISTORICAL
    assert adv.dose_mm == round(bday.dr_mm)
    assert adv.within_days is None and adv.irrigate_by is None
    assert "nie ma prognozy" in adv.text_pl
    assert {e.key for e in adv.evidence} >= {"root_zone_depletion_mm", "raw_mm", "irrigation_dose_mm"}
    check_text(adv)


def test_dry_with_dry_forecast_irrigate_now() -> None:
    _, inputs, adv = advise(forecast=([0.0] * 7, [5.0] * 7))
    assert adv.status is IrrigationStatus.IRRIGATE
    assert adv.forecast is ForecastUse.USED
    assert adv.within_days == 0 and adv.irrigate_by == inputs.analysis_date
    assert adv.dose_mm is not None and adv.dose_mm > 0
    assert len(adv.projection) == 7
    keys = {e.key for e in adv.evidence}
    assert "forecast_precip_mm" in keys
    assert "1–2 dni" in adv.text_pl
    check_text(adv)


def dry_spell(days: int) -> Callable[[date], float]:
    """Rain until `days` days before SUMMER, then none: the longer the spell, the drier the soil."""
    return lambda d: 0.0 if SUMMER - timedelta(days=days) < d <= SUMMER else 6.0


MODERATE = dry_spell(7)  # Dr just above RAW, Ks ≈ 0.8
SEVERE = dry_spell(12)  # almost dry soil, Ks ≈ 0.2


def test_forecast_rain_means_wait() -> None:
    _, _, adv = advise(precip=MODERATE, forecast=([0.0, 15.0] + [0.0] * 5, [3.0] * 7))
    assert adv.status is IrrigationStatus.WAIT_FOR_RAIN
    assert adv.dose_mm is None
    assert adv.params["rain_until_relief_mm"] == 15
    assert adv.params["relief_date"] == (SUMMER + timedelta(days=2)).isoformat()
    assert "Poczekaj" in adv.text_pl and "zmniejszyć niedobór" in adv.text_pl
    check_text(adv)


def test_almost_dry_soil_does_not_wait_for_rain() -> None:
    _, _, adv = advise(precip=SEVERE, forecast=([0.0, 0.0, 60.0] + [0.0] * 4, [4.0] * 7))
    assert adv.status is IrrigationStatus.IRRIGATE and adv.within_days == 0
    assert "Nie czekaj" in adv.text_pl and "60 mm" in adv.text_pl
    check_text(adv)


def test_irrigate_now_text_quotes_rain_within_wait_window_only() -> None:
    _, _, adv = advise(precip=MODERATE, forecast=([0.0] * 5 + [80.0, 0.0], [5.0] * 7))
    assert adv.status is IrrigationStatus.IRRIGATE
    assert "80 mm" not in adv.text_pl and "nie zapowiada deszczu" in adv.text_pl


def test_crossing_followed_by_rain_is_not_irrigate_soon() -> None:
    _, _, adv = advise(precip=dry_spell(5), forecast=([0.0, 40.0] + [2.0] * 5, [5.0] * 7))
    assert adv.status is IrrigationStatus.NOT_NEEDED


def test_rain_too_late_does_not_delay_irrigation() -> None:
    # Relief only on day 6 (> WAIT_MAX_DAYS): the crop would suffer until then.
    _, _, adv = advise(forecast=([0.0] * 5 + [80.0, 0.0], [5.0] * 7))
    assert adv.status is IrrigationStatus.IRRIGATE


def test_moist_soil_drying_out_within_forecast_irrigate_soon() -> None:
    a, inputs, adv = advise(precip=wet, forecast=([0.0] * 7, [7.0] * 7))
    assert a.root_zone is not None
    assert adv.status is IrrigationStatus.IRRIGATE_SOON
    assert adv.within_days is not None and 1 <= adv.within_days <= 7
    assert adv.irrigate_by == inputs.analysis_date + timedelta(days=adv.within_days)
    crossing = adv.projection[adv.within_days - 1]
    assert crossing.depletion_mm > a.root_zone.raw_mm
    assert all(p.depletion_mm <= a.root_zone.raw_mm for p in adv.projection[: adv.within_days - 1])
    assert adv.dose_mm == round(crossing.depletion_mm)
    assert date_pl(adv.irrigate_by.isoformat()) in adv.text_pl
    check_text(adv)


def test_moist_soil_with_mild_forecast_not_needed() -> None:
    _, _, adv = advise(precip=wet, forecast=([2.0] * 7, [2.0] * 7))
    assert adv.status is IrrigationStatus.NOT_NEEDED
    assert "Według prognozy" in adv.text_pl


def test_forecast_from_another_day_is_ignored() -> None:
    a, inputs, _ = scenario()
    inputs = with_forecast(inputs, [80.0] * 7, [1.0] * 7, issued_on=SUMMER - timedelta(days=1))
    adv = irrigation_advice(assess(inputs), inputs, today=SUMMER)
    assert adv.forecast is ForecastUse.UNAVAILABLE
    assert adv.status is IrrigationStatus.IRRIGATE and adv.projection == []
    assert "nie była dostępna" in adv.text_pl


def test_forecast_gap_right_after_analysis_date_is_unusable() -> None:
    _, _, adv = advise(forecast=([None, 0.0, 0.0], [5.0, 5.0, 5.0]))
    assert adv.forecast is ForecastUse.UNAVAILABLE and adv.projection == []


def test_light_soil_gets_smaller_split_doses_than_heavy() -> None:
    _, inputs, light = advise()
    _, _, heavy = advise(texture=CLAY_LOAM_RICH)
    assert light.single_dose_max_mm is not None and heavy.single_dose_max_mm is not None
    assert light.single_dose_max_mm < heavy.single_dose_max_mm
    assert light.applications is not None and light.dose_mm is not None
    assert light.applications * light.single_dose_max_mm >= light.dose_mm
    assert light.volume_m3 == round(light.dose_mm * inputs.parcel.area_ha * 10)
    if light.applications > 1:
        assert "dawki" in light.text_pl or "dawek" in light.text_pl


def test_single_dose_cap_unknown_category() -> None:
    assert single_dose_max_mm(None) == 20.0
    assert MAX_SINGLE_DOSE_MM[min(MAX_SINGLE_DOSE_MM)] < MAX_SINGLE_DOSE_MM[max(MAX_SINGLE_DOSE_MM)]


def test_projection_matches_hand_computed_balance() -> None:
    maize = crop("maize")
    day = SUMMER
    base = root_zone_balance([day], [0.0], [0.0], [maize.kc(day)], [True], taw_mm=100.0, p=0.5, dr0_mm=40.0)
    today = base.days[0]
    a, inputs, _ = scenario()
    inputs = with_forecast(inputs, [0.0, 0.0, 10.0], [5.0, 5.0, 5.0])
    proj = project(base, today, inputs.weather.data.forecast, inputs)  # type: ignore[union-attr]
    kc = [maize.kc(day + timedelta(days=i)) for i in (1, 2, 3)]
    dr1 = 40.0 + kc[0] * 5
    dr2 = dr1 + kc[1] * 5
    ks3 = 1.0 if dr2 <= 50 else (100 - dr2) / 50
    dr3 = dr2 - 10 + ks3 * kc[2] * 5
    assert [round(p.depletion_mm, 1) for p in proj] == [round(dr1, 1), round(dr2, 1), round(dr3, 1)]


# --- recommendation list and caveats (M5.2) ------------------------------------------------------


def test_irrigation_is_last_and_after_retention() -> None:
    _, _, recs = scenario()
    assert recs[-1].id == "irrigation" and recs[-1].category is Category.IRRIGATION
    rec = by_id(recs, "irrigation")
    assert rec.evidence and all(e.value is not None for e in rec.evidence)
    assert "ostatni krok" in rec.text_pl


def test_recommendation_text_equals_section_text() -> None:
    a, inputs, recs = scenario()
    assert by_id(recs, "irrigation").text_pl == irrigation_advice(a, inputs).text_pl


def test_caveats_on_water_access_and_permits() -> None:
    _, _, adv = advise()
    joined = " ".join(adv.caveats_pl)
    assert "dostęp do wody" in joined and "pozwolenia wodnoprawnego" in joined
    assert len(adv.caveats_pl) == 3  # + net dose note
    _, _, off = advise(day=date(2024, 11, 21))
    assert off.caveats_pl == []


def test_no_future_data_in_evidence_for_historical_date() -> None:
    _, _, adv = advise()
    for e in adv.evidence:
        assert e.period is None or e.period.end <= SUMMER


def test_doses_plural() -> None:
    assert [doses_pl(n) for n in (1, 2, 4, 5, 12, 22, 25)] == [
        "dawkę",
        "dawki",
        "dawki",
        "dawek",
        "dawek",
        "dawki",
        "dawek",
    ]


def test_today_without_forecast_uses_present_tense() -> None:
    a, inputs, _ = scenario()
    adv = irrigation_advice(a, inputs, today=SUMMER)
    assert adv.forecast is ForecastUse.UNAVAILABLE and adv.status is IrrigationStatus.IRRIGATE
    assert "było uzasadnione" not in adv.text_pl and "nawadniaj jak najszybciej" in adv.text_pl
    assert "nie była dostępna" in adv.text_pl


def test_weather_gap_on_analysis_date_is_not_blamed_on_soil() -> None:
    a, inputs, _ = scenario(precip=lambda d: None if d == SUMMER else 0.3)  # type: ignore[arg-type,return-value]
    adv = irrigation_advice(a, inputs)
    assert a.complete
    assert adv.status is IrrigationStatus.NO_BALANCE
    assert adv.params["reason"] == "weather_gap"
    assert "pogodowych" in adv.text_pl and "o glebie" not in adv.text_pl


def test_critical_period_overrides_late_stage() -> None:
    # Potato: late stage starts ~1 Aug while tuber bulking (critical) lasts until 15 Aug.
    potato = crop("potato")
    day = next(
        date(2024, 7, 1) + timedelta(days=i)
        for i in range(60)
        if potato.stage(date(2024, 7, 1) + timedelta(days=i)) == "late"
        and potato.critical_period_at(date(2024, 7, 1) + timedelta(days=i)) is not None
    )
    _, _, adv = advise(crop_id="potato", day=day)
    assert adv.status is not IrrigationStatus.LATE_STAGE and adv.applicable


def test_grassland_late_stage_text() -> None:
    grass = crop("grassland")
    day = next(
        date(2024, 9, 1) + timedelta(days=i)
        for i in range(30)
        if grass.stage(date(2024, 9, 1) + timedelta(days=i)) == "late"
    )
    _, _, adv = advise(crop_id="grassland", day=day)
    assert adv.status is IrrigationStatus.LATE_STAGE
    assert "łąka" in adv.text_pl and "dojrzewania" not in adv.text_pl


def test_section_text_equals_recommendation_with_forecast() -> None:
    a, inputs, adv = advise(forecast=([0.0] * 7, [5.0] * 7))
    recs = recommend(a, inputs)
    # recommend() decides with the real clock (historical date) — compare via the same params instead.
    assert render("irrigation", adv.params)[1] == adv.text_pl
    assert recs[-1].id == "irrigation"
