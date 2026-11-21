"""QA probes for irrigation advice (plan step M5): catalogue sweep, stage boundaries, forecast edge cases,
dose splitting, Polish plurals, parcel areas, evidence provenance and rule ordering."""

import dataclasses
import math
import re
from datetime import date, timedelta

import pytest

from app.analysis.assessment import Assessment, assess
from app.analysis.context import AnalysisInputs
from app.crops.catalog import STAGES, load_crops, month_day
from app.recommendations import irrigation as irr
from app.recommendations.irrigation import (
    ADVISED,
    FORECAST_HORIZON_DAYS,
    ForecastUse,
    IrrigationAdvice,
    IrrigationStatus,
    irrigation_advice,
)
from app.recommendations.models import Category
from app.recommendations.texts_pl import date_pl, doses_pl
from app.sources.open_meteo import WeatherForecast
from tests.recommendations.builders import CLAY_LOAM_RICH, SUMMER, dry, ids, scenario, wet

FORBIDDEN = re.compile(r"\b(NDVI|NDMI|KBW|percentyl\w*|FAO|TAW|RAW|Ks|ET0|ETc|Dr)\b", re.IGNORECASE)
CROPS = sorted(load_crops())
NOT_APPLICABLE = {
    IrrigationStatus.NO_ASSESSMENT,
    IrrigationStatus.OFF_SEASON,
    IrrigationStatus.NO_CROP,
    IrrigationStatus.LATE_STAGE,
}


def forecast_on(
    inputs: AnalysisInputs,
    precip: list[float | None],
    et0: list[float | None],
    *,
    issued_on: date | None = None,
    first_offset: int = 1,
    dates: list[date] | None = None,
) -> AnalysisInputs:
    day = inputs.analysis_date
    assert inputs.weather.data is not None
    fc = WeatherForecast(
        issued_on=issued_on or day,
        dates=dates
        if dates is not None
        else [day + timedelta(days=i + first_offset) for i in range(len(precip))],
        precip_mm=precip,
        et0_mm=et0,
        tmax_c=[25.0] * len(precip),
    )
    data = inputs.weather.data.model_copy(update={"forecast": fc})
    return dataclasses.replace(inputs, weather=inputs.weather.model_copy(update={"data": data}))


def run(inputs: AnalysisInputs, today: date | None = None) -> tuple[Assessment, IrrigationAdvice]:
    a = assess(inputs)
    return a, irrigation_advice(a, inputs, today=today or inputs.analysis_date)


def check_text(adv: IrrigationAdvice) -> None:
    for t in [adv.text_pl, adv.title_pl, *adv.caveats_pl]:
        assert t and "{" not in t and "}" not in t, t
        assert not FORBIDDEN.search(t), t
        assert not re.search(r"\d\.\d", t), t  # no "1.0"-style decimals
        assert "  " not in t and " ." not in t, t
        assert "None" not in t, t


def check_consistency(adv: IrrigationAdvice) -> None:
    assert adv.applicable == (adv.status not in NOT_APPLICABLE)
    if adv.status in ADVISED:
        assert adv.dose_mm is not None and adv.dose_mm > 0
        assert adv.single_dose_max_mm is not None and adv.applications is not None
        assert adv.applications == max(1, math.ceil(adv.dose_mm / adv.single_dose_max_mm))
        single = float(adv.params["single_dose_mm"])
        assert single <= adv.single_dose_max_mm
        # applications × single dose ≈ total (each single dose rounded to 1 mm)
        assert abs(single * adv.applications - adv.dose_mm) <= 0.5 * adv.applications + 1e-9
        assert adv.volume_m3 is not None
        assert "ostatni krok" in adv.text_pl
        assert len(adv.caveats_pl) == 3
    else:
        assert adv.dose_mm is None and adv.applications is None and adv.volume_m3 is None
    if adv.status is IrrigationStatus.IRRIGATE_SOON:
        assert adv.within_days is not None and 1 <= adv.within_days <= FORECAST_HORIZON_DAYS
    if adv.forecast is not ForecastUse.USED:
        assert adv.within_days is None and adv.projection == []


# Evidence produced by the irrigation module itself, or a state on one day: must carry its period.
DATED_OWN = {"irrigation_dose_mm", "forecast_precip_mm", "root_zone_available_mm"}


def check_evidence(adv: IrrigationAdvice, analysis_date: date, historical: bool) -> None:
    for e in adv.evidence:
        assert e.value is not None, e.key
        assert e.source, e.key
        if e.key in DATED_OWN:
            assert e.period is not None, e.key
        if historical and e.period is not None:
            assert e.period.end <= analysis_date, (e.key, e.period)
    if adv.status in ADVISED:
        assert "irrigation_dose_mm" in {e.key for e in adv.evidence}


# --- whole catalogue across the season -------------------------------------------------------------

SWEEP_DATES = [date(2024, 3, 21) + timedelta(days=12 * i) for i in range(17)] + [
    date(2024, 1, 15),
    date(2024, 3, 20),
    date(2024, 9, 30),
    date(2024, 10, 1),
    date(2024, 12, 31),
]


@pytest.mark.parametrize("crop_id", CROPS)
@pytest.mark.parametrize("weather_kind", ["dry", "wet"])
def test_catalogue_sweep_never_raises_and_texts_clean(crop_id: str, weather_kind: str) -> None:
    seen: set[IrrigationStatus] = set()
    for day in SWEEP_DATES:
        a, inputs, recs = scenario(crop_id=crop_id, day=day, precip=dry if weather_kind == "dry" else wet)
        adv = irrigation_advice(a, inputs)
        seen.add(adv.status)
        check_text(adv)
        check_consistency(adv)
        check_evidence(adv, day, historical=True)
        assert adv.forecast is ForecastUse.HISTORICAL
        assert date_pl(day.isoformat()) in adv.text_pl or adv.status in (
            IrrigationStatus.NO_BALANCE,
            IrrigationStatus.WAIT_FOR_RAIN,
            IrrigationStatus.NO_ASSESSMENT,
        )
        if not (month_day("03-21", day.year) <= day <= month_day("09-30", day.year)):
            assert adv.status is IrrigationStatus.OFF_SEASON
        # recommendation list: irrigation present iff advised, and always last
        assert ("irrigation" in ids(recs)) == (adv.status in ADVISED)
        if "irrigation" in ids(recs):
            assert recs[-1].id == "irrigation" and recs[-1].category is Category.IRRIGATION
            assert recs[-1].text_pl == adv.text_pl
            assert all(e.value is not None for e in recs[-1].evidence)
    if weather_kind == "dry":
        assert seen & set(ADVISED), f"{crop_id}: dry season never triggers irrigation"


# --- Crop.stage boundaries -------------------------------------------------------------------------


@pytest.mark.parametrize("crop_id", CROPS)
def test_stage_boundaries(crop_id: str) -> None:
    c = load_crops()[crop_id]
    start = month_day(c.sowing, 2023)
    assert c.stage(start - timedelta(days=1)) is None
    assert c.stage(start) == "initial"
    bound = 0
    for i, length in enumerate(c.stages_days):
        bound += length
        last = start + timedelta(days=bound - 1)
        assert c.stage(last) == STAGES[i], (crop_id, last)
        if i < 3:
            assert c.stage(last + timedelta(days=1)) == STAGES[i + 1]
    assert c.stage(start + timedelta(days=c.season_days)) is None
    # agrees with in_season and the Kc curve for every day of two years
    d = date(2023, 1, 1)
    while d <= date(2024, 12, 31):
        s = c.stage(d)
        assert (s is not None) == c.in_season(d), d
        if s == "initial":
            assert c.kc(d) == c.kc_ini
        if s == "mid":
            assert c.kc(d) == c.kc_mid
        d += timedelta(days=1)


@pytest.mark.parametrize("crop_id", [c for c in CROPS if load_crops()[c].winter])
def test_winter_crop_stage_across_year_boundary(crop_id: str) -> None:
    c = load_crops()[crop_id]
    assert c.stage(date(2023, 12, 31)) == "initial"
    assert c.stage(date(2024, 1, 1)) == "initial"
    assert c.season_start(date(2024, 1, 1)) == month_day(c.sowing, 2023)
    assert c.stage(date(2024, 6, 1)) in ("mid", "development")


def test_winter_wheat_freshly_sown_late_september_is_handled() -> None:
    a, inputs, _ = scenario(crop_id="winter_wheat", day=date(2024, 9, 28))
    adv = irrigation_advice(a, inputs)
    assert inputs.crop.stage(date(2024, 9, 28)) == "initial"
    check_text(adv)
    check_consistency(adv)


# --- forecast edge cases ---------------------------------------------------------------------------


def test_empty_forecast_is_unavailable() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [], []))
    assert adv.forecast is ForecastUse.UNAVAILABLE and adv.projection == []
    assert adv.status is IrrigationStatus.IRRIGATE
    assert "nie była dostępna" in adv.text_pl
    check_text(adv)
    check_consistency(adv)


@pytest.mark.parametrize("n", [2, 3, 5])
def test_short_forecast_projects_only_available_days(n: int) -> None:
    _, inputs, _ = scenario(precip=wet)
    _, adv = run(forecast_on(inputs, [2.0] * n, [2.0] * n))
    assert adv.forecast is ForecastUse.USED and len(adv.projection) == n
    assert adv.params["forecast_days"] == n
    assert adv.status is IrrigationStatus.NOT_NEEDED
    assert f"na {n} dni" in adv.text_pl
    check_text(adv)


def test_one_day_forecast_plural_not_needed() -> None:
    _, inputs, _ = scenario(precip=wet)
    _, adv = run(forecast_on(inputs, [2.0], [2.0]))
    assert adv.status is IrrigationStatus.NOT_NEEDED and len(adv.projection) == 1
    assert "1 dni" not in adv.text_pl, adv.text_pl


def test_one_day_forecast_plural_irrigate() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [0.0], [5.0]))
    assert adv.status is IrrigationStatus.IRRIGATE and adv.within_days == 0
    assert "1 dni" not in adv.text_pl, adv.text_pl


def test_none_mid_forecast_truncates_projection() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [0.0, 0.0, None, 0.0, 0.0], [5.0] * 5))
    assert len(adv.projection) == 2 and adv.params["forecast_days"] == 2
    _, adv2 = run(forecast_on(inputs, [0.0] * 5, [5.0, None, 5.0, 5.0, 5.0]))
    assert len(adv2.projection) == 1


def test_forecast_starting_later_than_next_day_is_unusable() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [80.0] * 7, [1.0] * 7, first_offset=2))
    assert adv.forecast is ForecastUse.UNAVAILABLE and adv.projection == []
    assert adv.status is IrrigationStatus.IRRIGATE


def test_forecast_including_analysis_day_skips_it() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [0.0] * 8, [5.0] * 8, first_offset=0))
    assert adv.forecast is ForecastUse.USED and len(adv.projection) == 7
    assert adv.projection[0].day == inputs.analysis_date + timedelta(days=1)


def test_forecast_longer_than_horizon_is_capped() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [0.0] * 14, [5.0] * 14))
    assert len(adv.projection) == FORECAST_HORIZON_DAYS


def test_forecast_with_hole_stops_at_hole() -> None:
    _, inputs, _ = scenario()
    d = inputs.analysis_date
    dates = [d + timedelta(days=k) for k in (1, 2, 4, 5)]
    _, adv = run(forecast_on(inputs, [0.0] * 4, [5.0] * 4, dates=dates))
    assert [p.day for p in adv.projection] == dates[:2]


def test_forecast_issued_after_historical_date_is_never_used() -> None:
    _, inputs, _ = scenario()
    fc_inputs = forecast_on(inputs, [80.0] * 7, [1.0] * 7, issued_on=SUMMER + timedelta(days=1))
    _, adv = run(fc_inputs, today=date(2026, 11, 21))
    assert adv.forecast is ForecastUse.HISTORICAL and adv.projection == []
    assert adv.status is IrrigationStatus.IRRIGATE
    check_evidence(adv, SUMMER, historical=True)


def test_today_without_forecast_is_unavailable_not_historical() -> None:
    a, inputs, _ = scenario()
    adv = irrigation_advice(a, inputs, today=inputs.analysis_date)
    assert adv.forecast is ForecastUse.UNAVAILABLE
    assert adv.status is IrrigationStatus.IRRIGATE
    assert "nie była dostępna" in adv.text_pl and "przeszłości" not in adv.text_pl
    check_text(adv)


def test_today_without_forecast_text_not_past_tense() -> None:
    a, inputs, _ = scenario()
    adv = irrigation_advice(a, inputs, today=inputs.analysis_date)
    assert "brakowało" not in adv.text_pl and "było uzasadnione" not in adv.text_pl


def test_forecast_with_heavy_rain_beyond_horizon_ignored() -> None:
    _, inputs, _ = scenario()
    _, adv = run(forecast_on(inputs, [0.0] * 7 + [200.0], [5.0] * 8))
    assert adv.status is IrrigationStatus.IRRIGATE
    assert all(p.precip_mm == 0.0 for p in adv.projection)


# --- dose splitting and rounding -------------------------------------------------------------------


def _dry_advice(texture: tuple[float, float, float, float] | None = None) -> IrrigationAdvice:
    a, inputs, _ = scenario(texture=texture) if texture else scenario()
    return irrigation_advice(a, inputs)


def test_dose_exactly_at_cap_is_single_application(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _dry_advice()
    assert base.dose_mm is not None
    monkeypatch.setattr(irr, "single_dose_max_mm", lambda _c: base.dose_mm)
    adv = _dry_advice()
    assert adv.applications == 1 and adv.params["single_dose_mm"] == adv.dose_mm
    assert "Wystarczy jedna dawka" in adv.text_pl
    check_text(adv)
    monkeypatch.setattr(irr, "single_dose_max_mm", lambda _c: base.dose_mm - 1)
    adv2 = _dry_advice()
    assert adv2.applications == 2
    assert "2 dawki" in adv2.text_pl
    check_consistency(adv2)


@pytest.mark.parametrize("cap", [1.0, 3.0, 7.0, 11.0])
def test_many_small_doses_consistent_and_plural(monkeypatch: pytest.MonkeyPatch, cap: float) -> None:
    monkeypatch.setattr(irr, "single_dose_max_mm", lambda _c: cap)
    adv = _dry_advice()
    check_consistency(adv)
    check_text(adv)
    n = adv.applications
    assert n is not None and n > 1
    assert f"{n} {doses_pl(n)}" in adv.text_pl


@pytest.mark.parametrize(
    ("n", "word"),
    [
        (1, "dawkę"),
        (2, "dawki"),
        (4, "dawki"),
        (5, "dawek"),
        (11, "dawek"),
        (12, "dawek"),
        (14, "dawek"),
        (21, "dawek"),
        (22, "dawki"),
        (25, "dawek"),
        (112, "dawek"),
        (122, "dawki"),
    ],
)
def testdoses_plural(n: int, word: str) -> None:
    assert doses_pl(n) == word


def test_heavy_soil_dose_consistency() -> None:
    adv = _dry_advice(CLAY_LOAM_RICH)
    check_consistency(adv)
    assert adv.single_dose_max_mm in (30.0, 35.0)


# --- parcel area -----------------------------------------------------------------------------------


def _with_area(area_ha: float) -> IrrigationAdvice:
    a, inputs, _ = scenario()
    inputs = dataclasses.replace(inputs, parcel=inputs.parcel.model_copy(update={"area_ha": area_ha}))
    return irrigation_advice(a, inputs)


@pytest.mark.parametrize("area", [0.05, 0.3, 1.0, 250.0, 12345.678])
def test_volume_scales_with_area(area: float) -> None:
    adv = _with_area(area)
    assert adv.dose_mm is not None and adv.volume_m3 is not None
    assert adv.volume_m3 == round(adv.dose_mm * area * 10)
    check_text(adv)
    assert "e+" not in adv.text_pl


def test_tiny_parcel_volume_not_zero() -> None:
    adv = _with_area(0.0004)
    assert adv.volume_m3 and adv.volume_m3 > 0
    assert "ok. 0 m³" not in adv.text_pl


# --- grassland, soil category ----------------------------------------------------------------------


@pytest.mark.parametrize("day", [date(2024, 4, 20), date(2024, 6, 15), date(2024, 8, 10), date(2024, 9, 29)])
def test_grassland(day: date) -> None:
    a, inputs, _ = scenario(crop_id="grassland", day=day)
    adv = irrigation_advice(a, inputs)
    check_text(adv)
    check_consistency(adv)
    if inputs.crop.critical_period_at(day) is not None and adv.status in ADVISED:
        assert "najbardziej potrzebuje wody" in adv.text_pl


def test_missing_soil_category_but_taw_present() -> None:
    a, inputs, _ = scenario()
    assert a.soil is not None and a.root_zone is not None
    a2 = dataclasses.replace(a, soil=dataclasses.replace(a.soil, category=None))
    adv = irrigation_advice(a2, inputs)
    assert adv.status in ADVISED
    assert adv.single_dose_max_mm == irr.MAX_SINGLE_DOSE_UNKNOWN_MM
    assert adv.params["light_soil"] == 0
    assert "lekkiej" not in adv.text_pl
    check_text(adv)
    check_consistency(adv)


def test_soil_assessment_none_but_balance_present() -> None:
    a, inputs, _ = scenario()
    a2 = dataclasses.replace(a, soil=None)
    adv = irrigation_advice(a2, inputs)
    assert adv.single_dose_max_mm == irr.MAX_SINGLE_DOSE_UNKNOWN_MM
    check_consistency(adv)


# --- evidence with forecast ------------------------------------------------------------------------


def test_evidence_with_forecast_has_periods_and_sources() -> None:
    _, inputs, _ = scenario(precip=wet)
    _, adv = run(forecast_on(inputs, [0.0] * 7, [7.0] * 7))
    assert adv.status is IrrigationStatus.IRRIGATE_SOON
    check_evidence(adv, inputs.analysis_date, historical=False)
    by_key = {e.key: e for e in adv.evidence}
    assert by_key["forecast_precip_mm"].period is not None
    assert by_key["forecast_precip_mm"].period.start == inputs.analysis_date + timedelta(days=1)
    dose = by_key["irrigation_dose_mm"]
    assert dose.period is not None and dose.period.start == adv.irrigate_by
    assert "prognoz" in dose.source.lower() or "forecast" in dose.source.lower()


def test_depletion_and_ks_evidence_have_dates() -> None:
    a, inputs, _ = scenario()
    adv = irrigation_advice(a, inputs)
    by_key = {e.key: e for e in adv.evidence}
    assert by_key["root_zone_depletion_mm"].period is not None
    assert by_key["ks"].period is not None
