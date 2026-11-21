"""Open-Meteo / NASA POWER weather source.

The archive payloads are SYNTHETIC (archive-api.open-meteo.com answered HTTP 429 from the event network): they
are generated below in the documented `{"daily": {"time": [...], <var>: [...]}}` format, plus the hand-made
tail in tests/fixtures/open_meteo/archive_synthetic_tail_2026-11-21.json. The forecast and NASA POWER payloads
are recorded real responses.
"""

import json
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
import respx

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.sources import open_meteo
from tests.helpers import FIXTURES, parcel_from_uldk

TODAY = date(2026, 11, 21)  # the recorded forecast was issued on this day


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "open_meteo" / name).read_text(encoding="utf-8"))
    return data


def archive_payload(start: date, end: date) -> dict[str, Any]:
    """Synthetic complete archive response for start..end (inclusive)."""
    n = (end - start).days + 1
    times = [(start + timedelta(days=i)).isoformat() for i in range(n)]
    return {
        "latitude": 52.4,
        "longitude": 17.4,
        "daily": {
            "time": times,
            "precipitation_sum": [round(1.0 + (i % 7) * 0.3, 1) for i in range(n)],
            "et0_fao_evapotranspiration": [round(1.5 + (i % 5) * 0.2, 2) for i in range(n)],
            "temperature_2m_min": [4.0] * n,
            "temperature_2m_max": [14.0] * n,
            "temperature_2m_mean": [9.0] * n,
        },
    }


def archive_with_tail(start: date) -> dict[str, Any]:
    """Synthetic archive up to 2026-10-31 followed by the hand-made tail with nulls from 2026-11-15."""
    head = archive_payload(start, date(2026, 10, 31))
    tail = _load("archive_synthetic_tail_2026-11-21.json")
    for key, values in tail["daily"].items():
        head["daily"][key] = head["daily"][key] + values
    return head


@pytest.fixture
def parcel() -> Parcel:
    return parcel_from_uldk("by_id_slash_302108_5.0014.88-8.txt")


def test_history_window_and_grid_point() -> None:
    assert open_meteo.history_start(date(2025, 6, 15)) == date(2014, 10, 1)
    assert open_meteo.grid_point(52.40017, 17.35004) == (52.4, 17.4)


async def test_historical_date_ends_on_analysis_date(tmp_cache: DiskCache, parcel: Parcel) -> None:
    analysis_date = date(2025, 6, 15)
    start = open_meteo.history_start(analysis_date)
    with respx.mock(assert_all_called=False) as mock:
        # The provider returns more than asked: the module must drop everything after analysis_date.
        archive = mock.get(open_meteo.ARCHIVE_URL).mock(
            return_value=httpx.Response(200, json=archive_payload(start, analysis_date + timedelta(days=10)))
        )
        forecast = mock.get(open_meteo.FORECAST_URL)
        res = await open_meteo.fetch(parcel, analysis_date, today=TODAY)

    assert archive.calls.last.request.url.params["end_date"] == "2025-06-15"
    assert forecast.call_count == 0
    assert res.status is SourceStatus.OK
    assert res.data is not None
    daily = res.data.daily
    assert daily.dates[0] == start
    assert daily.dates[-1] == analysis_date
    assert all(d <= analysis_date for d in daily.dates)
    assert len(daily.dates) == len(daily.precip_mm) == (analysis_date - start).days + 1
    assert res.data.missing_days == 0
    assert res.data.provisional_from is None
    assert res.data.forecast is None
    assert res.period is not None and res.period.end == analysis_date


async def test_recent_date_tail_filled_from_forecast(tmp_cache: DiskCache, parcel: Parcel) -> None:
    analysis_date = date(2026, 11, 19)
    start = open_meteo.history_start(analysis_date)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(200, json=archive_with_tail(start)))
        forecast = mock.get(open_meteo.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=_load("forecast_2026-11-21.json"))
        )
        res = await open_meteo.fetch(parcel, analysis_date, today=TODAY)

    fc_params = forecast.calls.last.request.url.params
    assert fc_params["forecast_days"] == "1"  # no forecast ahead for a past analysis date
    assert int(fc_params["past_days"]) >= (TODAY - date(2026, 11, 15)).days
    assert res.data is not None
    daily = res.data.daily
    assert daily.dates[-1] == analysis_date
    assert res.data.provisional_from == date(2026, 11, 15)
    assert res.data.missing_days == 0
    # 2026-11-19 comes from the recorded forecast (precipitation 0.8 mm, ET0 0.76 mm).
    assert daily.precip_mm[-1] == 0.8
    assert daily.et0_mm[-1] == 0.76
    assert res.data.forecast is None
    assert res.status is SourceStatus.OK
    assert res.message_pl is not None and "wstępne" in res.message_pl


async def test_today_gets_seven_day_forecast(tmp_cache: DiskCache, parcel: Parcel) -> None:
    start = open_meteo.history_start(TODAY)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(200, json=archive_with_tail(start)))
        forecast = mock.get(open_meteo.FORECAST_URL).mock(
            return_value=httpx.Response(200, json=_load("forecast_2026-11-21.json"))
        )
        res = await open_meteo.fetch(parcel, TODAY, today=TODAY)

    assert forecast.calls.last.request.url.params["forecast_days"] == "8"
    assert res.data is not None
    assert res.data.daily.dates[-1] == TODAY
    assert all(d <= TODAY for d in res.data.daily.dates)
    fc = res.data.forecast
    assert fc is not None
    assert fc.issued_on == TODAY
    assert fc.dates == [TODAY + timedelta(days=i) for i in range(1, 8)]
    assert fc.precip_mm[0] == 3.42


async def test_recent_date_forecast_down_is_degraded(tmp_cache: DiskCache, parcel: Parcel) -> None:
    analysis_date = date(2026, 11, 19)
    start = open_meteo.history_start(analysis_date)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(200, json=archive_with_tail(start)))
        mock.get(open_meteo.FORECAST_URL).mock(side_effect=httpx.ConnectError("down"))
        res = await open_meteo.fetch(parcel, analysis_date, today=TODAY)

    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None
    assert res.data.daily.dates[-1] == analysis_date
    assert res.data.daily.precip_mm[-1] is None  # never filled with a default
    assert res.data.provisional_from is None
    assert res.message_pl is not None and "Brak danych" in res.message_pl


async def test_archive_429_falls_back_to_nasa_power(tmp_cache: DiskCache, parcel: Parcel) -> None:
    analysis_date = date(2025, 6, 30)
    with respx.mock(assert_all_called=False) as mock:
        archive = mock.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(429))
        power = mock.get(open_meteo.POWER_URL).mock(
            return_value=httpx.Response(200, json=_load("power_2025-06.json"))
        )
        res = await open_meteo.fetch(parcel, analysis_date, today=TODAY)

    assert archive.call_count >= 1
    assert power.calls.last.request.url.params["end"] == "20250630"
    assert res.status is SourceStatus.DEGRADED
    assert res.data is not None
    assert res.data.provider == "nasa_power"
    assert res.message_pl is not None and "NASA POWER" in res.message_pl
    assert "NASA POWER" in res.source
    daily = res.data.daily
    assert daily.dates[-1] == analysis_date
    june = [daily.et0_mm[i] for i, d in enumerate(daily.dates) if d >= date(2025, 6, 1)]
    assert len(june) == 30
    assert all(v is not None and 1.0 < v < 8.0 for v in june)
    first_june = daily.dates.index(date(2025, 6, 1))
    assert daily.precip_mm[first_june] == 1.39


async def test_both_providers_down_is_missing(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(429))
        mock.get(open_meteo.POWER_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
        res = await open_meteo.fetch(parcel, date(2025, 6, 30), today=TODAY)

    assert res.status is SourceStatus.MISSING
    assert res.data is None
    assert res.message_pl is not None and "Nie udało się pobrać danych pogodowych" in res.message_pl


async def test_second_call_served_from_cache(tmp_cache: DiskCache, parcel: Parcel) -> None:
    analysis_date = date(2025, 6, 15)
    start = open_meteo.history_start(analysis_date)
    with respx.mock(assert_all_called=False) as mock:
        archive = mock.get(open_meteo.ARCHIVE_URL).mock(
            return_value=httpx.Response(200, json=archive_payload(start, analysis_date))
        )
        first = await open_meteo.fetch(parcel, analysis_date, today=TODAY)
        second = await open_meteo.fetch(parcel, analysis_date, today=TODAY)

    assert archive.call_count == 1
    assert first.data == second.data
