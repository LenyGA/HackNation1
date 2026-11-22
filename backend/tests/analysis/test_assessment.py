from datetime import date, timedelta

import pytest

from app.analysis.assessment import Assessment, assess
from app.analysis.common import (
    DeficitLevel,
    combine,
    confidence_from_points,
    level_from_ks,
    level_from_percentile,
    round_to,
)
from app.core.models import Confidence
from app.sources.open_meteo import history_start
from tests.analysis.builders import (
    daily_series,
    make_inputs,
    ok,
    random_precip,
    sentinel_data,
    weather_result,
)

SUMMER = date(2024, 7, 15)
CONF = ["low", "medium", "high"]


def _causes(a: Assessment) -> dict[str, bool | None]:
    return {c.id: c.flagged for c in a.causes}


def _check_complete(a: Assessment) -> None:
    assert a.complete and a.incomplete_reason_pl is None
    assert a.current is not None and a.vulnerability is not None
    assert [c.id for c in a.causes] == [
        "precipitation_deficit_heat",
        "low_soil_retention",
        "excessive_runoff",
        "crop_sensitivity",
    ]
    for ind in a.current.indicators:
        assert ind.source and ind.uncertainty.reason_pl


def test_all_sources_ok() -> None:
    a = assess(make_inputs(SUMMER, sentinel2=ok("sentinel2", sentinel_data(SUMMER, 0.7))))
    _check_complete(a)
    assert a.current is not None
    assert "root_zone" in a.current.basis
    assert a.current.in_vegetation and a.current.crop_on_field
    assert a.root_zone is not None and a.soil is not None and a.terrain is not None
    assert all(f is not None for f in _causes(a).values())
    assert _causes(a)["low_soil_retention"] is True  # loamy sand, SOC 8 g/kg
    assert a.current.satellite.status in {"agrees", "disagrees"}
    keys = {i.key for i in a.current.indicators}
    assert {"ks", "root_zone_depletion_mm", "kbw_60d_mm", "precip_30d_pct"} <= keys
    assert "satellite_missing" not in a.limitations


def test_soil_missing() -> None:
    full = assess(make_inputs(SUMMER))
    a = assess(make_inputs(SUMMER, soil=False))
    _check_complete(a)
    assert a.current is not None and a.vulnerability is not None
    assert a.root_zone is None and a.soil is None
    assert "root_zone" not in a.current.basis
    assert "kbw_percentile" in a.current.basis
    assert _causes(a)["low_soil_retention"] is None
    soil_comp = next(c for c in a.vulnerability.components if c.id == "soil")
    assert soil_comp.points is None
    assert "soil_missing" in a.limitations
    assert full.current is not None
    assert CONF.index(a.current.uncertainty.level) < CONF.index(full.current.uncertainty.level)


def test_soil_with_incomplete_layers_does_not_crash() -> None:
    from tests.analysis.builders import soil_data, soil_layers

    a = assess(make_inputs(SUMMER, soil=ok("soilgrids", soil_data(soil_layers(None, None, None, None)))))
    _check_complete(a)
    assert a.root_zone is None
    assert "soil_incomplete" in a.limitations


def test_satellite_missing() -> None:
    a = assess(make_inputs(SUMMER))
    _check_complete(a)
    assert a.current is not None
    assert a.current.satellite.status == "missing"
    assert "satellite_missing" in a.limitations


@pytest.mark.parametrize("analysis_date", [SUMMER, date(2024, 4, 10), date(2024, 11, 21)])
def test_satellite_never_changes_the_level(analysis_date: date) -> None:
    base = assess(make_inputs(analysis_date))
    assert base.current is not None
    for ndvi in (0.05, 0.95):
        a = assess(make_inputs(analysis_date, sentinel2=ok("sentinel2", sentinel_data(analysis_date, ndvi))))
        assert a.current is not None
        assert a.current.level == base.current.level
        assert a.current.basis == base.current.basis
        if a.current.satellite.status == "disagrees":
            assert CONF.index(a.current.uncertainty.level) <= CONF.index(base.current.uncertainty.level)


def test_satellite_both_directions_on_summer_maize() -> None:
    statuses = set()
    for ndvi in (0.05, 0.95):
        a = assess(make_inputs(SUMMER, sentinel2=ok("sentinel2", sentinel_data(SUMMER, ndvi))))
        assert a.current is not None
        statuses.add(a.current.satellite.status)
    assert statuses == {"agrees", "disagrees"}


def test_satellite_not_applicable_on_maize_in_april() -> None:
    d = date(2024, 4, 10)
    a = assess(make_inputs(d, sentinel2=ok("sentinel2", sentinel_data(d, 0.1))))
    assert a.current is not None
    assert a.current.satellite.status == "not_applicable"


def test_weather_missing() -> None:
    a = assess(make_inputs(SUMMER, weather=False))
    assert not a.complete
    assert a.current is None and a.vulnerability is None
    assert a.causes == []
    assert a.incomplete_reason_pl is not None and "Brak danych pogodowych" in a.incomplete_reason_pl
    assert a.uncertainty.level is Confidence.LOW
    assert a.soil is not None  # other sources are still computed for the report


def test_weather_too_short() -> None:
    daily = daily_series(SUMMER - timedelta(days=30), SUMMER, random_precip())
    a = assess(make_inputs(SUMMER, weather=weather_result(daily)))
    assert not a.complete and a.causes == []
    assert a.incomplete_reason_pl and "90 dni" in a.incomplete_reason_pl


def test_weather_only_future_data() -> None:
    daily = daily_series(SUMMER + timedelta(days=1), SUMMER + timedelta(days=100), random_precip())
    a = assess(make_inputs(SUMMER, weather=weather_result(daily)))
    assert not a.complete and a.causes == []


def test_weather_with_many_recent_gaps() -> None:
    daily = daily_series(history_start(SUMMER), SUMMER, random_precip())
    p = [None if (SUMMER - d).days < 20 else v for d, v in zip(daily.dates, daily.precip_mm, strict=True)]
    a = assess(make_inputs(SUMMER, weather=weather_result(daily.model_copy(update={"precip_mm": p}))))
    assert not a.complete
    assert a.incomplete_reason_pl and "braków" in a.incomplete_reason_pl


def test_weather_with_sparse_gaps_still_complete() -> None:
    daily = daily_series(history_start(SUMMER), SUMMER, random_precip())
    p = [None if i % 25 == 0 else v for i, v in enumerate(daily.precip_mm)]
    e = [None if i % 31 == 0 else v for i, v in enumerate(daily.et0_mm)]
    a = assess(
        make_inputs(SUMMER, weather=weather_result(daily.model_copy(update={"precip_mm": p, "et0_mm": e})))
    )
    _check_complete(a)
    assert a.root_zone is not None and a.root_zone.gap_days > 0


def test_off_season_basis() -> None:
    d = date(2024, 11, 21)
    a = assess(make_inputs(d, "maize"))
    _check_complete(a)
    assert a.current is not None
    assert not a.current.in_vegetation and not a.current.crop_on_field
    assert "recharge_percentile" in a.current.basis
    keys = {i.key: i for i in a.current.indicators}
    assert keys["recharge_kbw_pct"].value is not None
    rec = keys["recharge_kbw_mm"]
    assert rec.period is not None and rec.period.start == date(2024, 10, 1) and rec.period.end == d
    ls = a.current.last_season
    assert ls is not None and ls.year == 2024
    assert ls.stress_days is not None
    assert {i.key for i in ls.indicators} >= {"last_season_stress_days", "last_season_deficit_months"}


def test_off_season_winter_wheat_on_field_uses_root_zone() -> None:
    d = date(2026, 11, 21)
    a = assess(make_inputs(d, "winter_wheat"))
    _check_complete(a)
    assert a.current is not None
    assert a.current.crop_on_field and not a.current.in_vegetation
    assert a.current.basis[0] == "root_zone"
    assert "recharge_percentile" in a.current.basis
    assert a.current.last_season is not None


def test_off_season_without_soil() -> None:
    a = assess(make_inputs(date(2024, 11, 21), soil=False))
    _check_complete(a)
    assert a.current is not None
    assert "recharge_percentile" in a.current.basis
    assert a.current.last_season is None  # no deficit-month method without soil (assessment._last_season)


def test_missing_dem_and_hydro_give_unknown_causes() -> None:
    a = assess(make_inputs(SUMMER, dem=False, hydro=False))
    _check_complete(a)
    assert _causes(a)["excessive_runoff"] is None
    assert a.vulnerability is not None
    unknown = {c.id for c in a.vulnerability.components if c.points is None}
    assert unknown == {"slope", "retention_elements"}
    assert {"terrain_missing", "hydro_missing"} <= set(a.limitations)


def test_everything_but_weather_missing() -> None:
    a = assess(make_inputs(SUMMER, soil=False, dem=False, hydro=False))
    _check_complete(a)
    c = _causes(a)
    assert c["low_soil_retention"] is None and c["excessive_runoff"] is None
    assert c["precipitation_deficit_heat"] is not None
    assert a.uncertainty.level is Confidence.LOW


def test_poison_after_analysis_date_does_not_change_assessment() -> None:
    clean = assess(make_inputs(SUMMER))
    rp = random_precip()

    def poisoned_p(d: date) -> float:
        return 9999.0 if d > SUMMER else rp(d)

    def poisoned_e(d: date) -> float:
        return 0.0 if d > SUMMER else make_et0(d)

    from tests.analysis.builders import seasonal_et0 as make_et0

    p = make_inputs(SUMMER, precip=poisoned_p, et0=poisoned_e, weather_end=SUMMER + timedelta(days=200))
    poisoned = assess(p)
    assert clean.current is not None and poisoned.current is not None
    assert poisoned.current.level == clean.current.level
    assert [(i.key, i.value) for i in poisoned.current.indicators] == [
        (i.key, i.value) for i in clean.current.indicators
    ]
    assert [(c.id, c.flagged, [e.value for e in c.evidence]) for c in poisoned.causes] == [
        (c.id, c.flagged, [e.value for e in c.evidence]) for c in clean.causes
    ]
    assert poisoned.root_zone is not None and poisoned.root_zone.days[-1].day == SUMMER


@pytest.mark.parametrize(
    "analysis_date",
    [
        date(2024, 2, 29),
        date(2024, 10, 1),
        date(2024, 10, 2),
        date(2024, 10, 3),
        date(2024, 9, 30),
        date(2024, 3, 21),
        date(2024, 1, 1),
        date(2023, 12, 31),
    ],
)
@pytest.mark.parametrize("crop_id", ["maize", "winter_wheat", "winter_rapeseed", "grassland", "potato"])
def test_edge_dates_do_not_crash(analysis_date: date, crop_id: str) -> None:
    s2 = ok("sentinel2", sentinel_data(analysis_date, 0.4))
    a = assess(make_inputs(analysis_date, crop_id, sentinel2=s2))
    _check_complete(a)
    assert a.current is not None
    assert a.current.basis


@pytest.mark.parametrize("size_m", [8.0, 15.0])
def test_tiny_parcel(size_m: float) -> None:
    from app.sources.base import METRIC_CRS
    from tests.helpers import metric_square_parcel

    parcel = metric_square_parcel(17.35, 52.4, size_m, size_m, METRIC_CRS)
    a = assess(make_inputs(SUMMER, parcel=parcel))
    _check_complete(a)
    assert a.terrain is not None and "small_parcel" in a.limitations


def test_dry_summer_is_a_deficit() -> None:
    """Dry 90 days before the analysis date, normal weather in previous years -> at least moderate."""
    rp = random_precip()

    def precip(d: date) -> float:
        return 0.0 if 0 <= (SUMMER - d).days < 90 else rp(d) + 1.0

    a = assess(make_inputs(SUMMER, precip=precip))
    _check_complete(a)
    assert a.current is not None
    assert a.current.level.rank >= DeficitLevel.MODERATE.rank
    assert _causes(a)["precipitation_deficit_heat"] is True
    assert _causes(a)["crop_sensitivity"] is True  # maize in tasselling (critical period) with a deficit


def test_wet_summer_is_no_deficit() -> None:
    rp = random_precip()

    def precip(d: date) -> float:
        return 12.0 if 0 <= (SUMMER - d).days < 90 else rp(d)

    a = assess(make_inputs(SUMMER, precip=precip))
    _check_complete(a)
    assert a.current is not None and a.current.level is DeficitLevel.NONE


def test_common_helpers() -> None:
    assert level_from_percentile(None) is None
    assert level_from_percentile(5) is DeficitLevel.SEVERE
    assert level_from_percentile(20) is DeficitLevel.MODERATE
    assert level_from_percentile(30) is DeficitLevel.LIGHT
    assert level_from_percentile(31) is DeficitLevel.NONE
    assert level_from_ks(1.0) is DeficitLevel.NONE
    assert level_from_ks(0.8) is DeficitLevel.LIGHT
    assert level_from_ks(0.6) is DeficitLevel.MODERATE
    assert level_from_ks(0.1) is DeficitLevel.SEVERE
    assert combine(DeficitLevel.NONE, DeficitLevel.SEVERE) is DeficitLevel.LIGHT
    assert combine(DeficitLevel.SEVERE, DeficitLevel.NONE) is DeficitLevel.SEVERE
    assert combine(DeficitLevel.MODERATE, None) is DeficitLevel.MODERATE
    assert confidence_from_points(-2) is Confidence.LOW
    assert confidence_from_points(5) is Confidence.HIGH
    assert round_to(12.345, 0.01) == 12.35 or round_to(12.345, 0.01) == 12.34
    assert round_to(12.6, 1.0) == 13
    assert round_to(1234.0, 100) == 1200
    assert round_to(None, 1.0) is None


@pytest.mark.parametrize("crop_id", ["winter_wheat", "grassland"])
def test_last_season_stress_days_early_october(crop_id: str) -> None:
    a = assess(make_inputs(date(2024, 10, 2), crop_id))
    assert a.current is not None and a.current.last_season is not None
    assert a.current.last_season.stress_days is not None


def test_satellite_scene_after_analysis_date_is_ignored() -> None:
    from tests.analysis.builders import scene

    data = sentinel_data(SUMMER, 0.05)
    data = data.model_copy(update={"current": [scene(SUMMER + timedelta(days=5), 0.05)]})
    a = assess(make_inputs(SUMMER, sentinel2=ok("sentinel2", data)))
    assert a.current is not None
    assert a.current.satellite.status == "not_applicable"


# --- official IUNG-PIB threshold (G1) ---------------------------------------------------------------
# SUMMER (15 VII) on loamy sand (category II), maize: period 11 V – 10 VII, critical KBW −188 mm.
IUNG_START, IUNG_END = date(2024, 5, 11), date(2024, 7, 10)


def _in_iung_period(d: date) -> bool:
    return IUNG_START <= d <= IUNG_END


def test_iung_below_threshold_is_agricultural_drought() -> None:
    rp = random_precip()
    a = assess(make_inputs(SUMMER, precip=lambda d: 0.0 if _in_iung_period(d) else rp(d) + 1.0))
    _check_complete(a)
    cur = a.current
    assert cur is not None and cur.iung is not None
    assert (cur.iung.period_start, cur.iung.period_end, cur.iung.kbw_critical_mm) == (
        IUNG_START,
        IUNG_END,
        -188,
    )
    assert cur.iung_below is True and cur.iung_missing is None
    assert "iung" in cur.basis and cur.iung_threshold_used
    assert cur.level.rank >= DeficitLevel.MODERATE.rank
    values = {i.key: i for i in cur.indicators}
    assert values["kbw_iung_period_mm"].value is not None and values["kbw_iung_period_mm"].value < -188
    assert values["kbw_iung_critical_mm"].value == -188
    assert "Dz.U. 2019 poz. 739" in values["kbw_iung_critical_mm"].source
    assert "iung_etp_method" in a.limitations and "iung_thresholds_missing" not in a.limitations


def test_iung_above_threshold_is_not_drought_and_does_not_change_level() -> None:
    rp = random_precip()

    def precip(d: date) -> float:
        return 12.0 if 0 <= (SUMMER - d).days < 90 else rp(d)

    a = assess(make_inputs(SUMMER, precip=precip))
    assert a.current is not None
    assert a.current.iung_below is False and a.current.iung_threshold_used
    assert "iung" not in a.current.basis  # the threshold did not set the level
    assert a.current.level is DeficitLevel.NONE


def test_iung_compares_the_rounded_value_shown_in_the_report() -> None:
    # Raw KBW −187.6 mm is shown as −188 mm, which equals the threshold → drought, consistently with the text.
    days = (IUNG_END - IUNG_START).days + 1
    a = assess(
        make_inputs(
            SUMMER, precip=lambda d: 4.0 - 187.6 / days if _in_iung_period(d) else 2.0, et0=lambda d: 4.0
        )
    )
    assert a.current is not None
    assert {i.key: i.value for i in a.current.indicators}["kbw_iung_period_mm"] == -188
    assert a.current.iung_below is True


def test_iung_missing_reason_for_grassland() -> None:
    from app.crops.iung import IungMissing

    a = assess(make_inputs(SUMMER, "grassland"))
    assert a.current is not None
    assert a.current.iung is None and a.current.iung_missing is IungMissing.CROP_NOT_COVERED
    assert "iung" not in a.current.basis
    assert "iung_thresholds_missing" in a.limitations and "iung_etp_method" not in a.limitations


def test_iung_missing_reason_without_soil() -> None:
    from app.crops.iung import IungMissing

    a = assess(make_inputs(SUMMER, soil=False))
    assert a.current is not None
    assert a.current.iung_missing is IungMissing.NO_SOIL_CATEGORY


@pytest.mark.parametrize(
    ("crop_id", "day"),
    [("field_vegetables", date(2024, 9, 5)), ("maize", date(2024, 10, 5)), ("rye", date(2024, 8, 5))],
)
def test_iung_does_not_fire_after_harvest_or_after_vegetation(crop_id: str, day: date) -> None:
    from app.crops.iung import IungMissing

    rp = random_precip()
    a = assess(make_inputs(day, crop_id, precip=lambda d: 0.0 if 0 <= (day - d).days < 120 else rp(d) + 1.0))
    assert a.current is not None
    assert not (a.current.in_vegetation and a.current.crop_on_field)
    assert a.current.iung is None and a.current.iung_missing is IungMissing.CROP_NOT_ON_FIELD
    assert "iung" not in a.current.basis
    assert "kbw_iung_period_mm" not in {i.key for i in a.current.indicators}


def test_iung_no_weather_in_the_period() -> None:
    from app.crops.iung import IungMissing

    rp = random_precip()
    # 8 missing days at the start of the 61-day period (> 10 % gap) but only 2 inside the 60-day window.
    gap = (date(2024, 5, 11), date(2024, 5, 18))

    def precip(d: date) -> float | None:
        return None if gap[0] <= d <= gap[1] else rp(d)

    a = assess(make_inputs(SUMMER, precip=precip))  # type: ignore[arg-type]
    assert a.complete and a.current is not None
    assert a.current.iung is None and a.current.iung_missing is IungMissing.NO_WEATHER
    assert "iung" not in a.current.basis
