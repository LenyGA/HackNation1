"""Daily weather: precipitation, reference evapotranspiration ET0 (FAO), temperature.

Primary: Open-Meteo Historical Weather API (ERA5 / ERA5-Land reanalysis), one request covering the whole
historical window up to `analysis_date`. The archive lags ~5 days behind real time, so for recent analysis
dates the missing tail is filled from the Open-Meteo Forecast API (`past_days`) and flagged as provisional.
A 7-day forecast is fetched only when `analysis_date` is today (needed for irrigation timing).

Fallback (status `degraded`): NASA POWER daily point data; ET0 is computed with FAO-56 Penman-Monteith.

Never returns a record dated after `analysis_date` in the observed series.
"""

import logging
from datetime import date, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from app.analysis.et0 import et0_fao56_mm, saturation_vapour_pressure_kpa
from app.core.cache import CURRENT_DATA_TTL, get_cache
from app.core.config import HISTORY_YEARS, today_local
from app.core.http import request
from app.core.models import Confidence, Parcel, Period, SourceResult, SourceStatus
from app.sources.base import SourceError, cache_ttl, missing, result, unc, within_budget

log = logging.getLogger(__name__)

NAME = "open_meteo"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

SOURCE_ARCHIVE = (
    "Open-Meteo Historical Weather API (reanaliza ERA5/ERA5-Land, Copernicus/ECMWF), https://open-meteo.com/"
)
SOURCE_FORECAST = "Open-Meteo Forecast API, https://open-meteo.com/"
SOURCE_POWER = (
    "NASA POWER (Prediction Of Worldwide Energy Resources), dane dobowe, https://power.larc.nasa.gov/"
)
LICENSE_OPEN_METEO = "CC BY 4.0 (darmowe API wyłącznie do użytku niekomercyjnego)"
LICENSE_POWER = "Dane NASA, bezpłatne, wymagane podanie źródła"

# Per request, no retry: worst case archive + POWER + forecast stays inside BUDGET_S.
TIMEOUT_S = 8.0
FORECAST_TIMEOUT_S = 6.0
BUDGET_S = 24.0
TIMEZONE = "Europe/Warsaw"
FORECAST_DAYS_AHEAD = 7
FORECAST_MAX_PAST_DAYS = 92
# Coordinates are rounded to ~the ERA5-Land grid so neighbouring parcels share one cached response.
GRID_DEG = 0.1
# More missing days than this (as a share of the window) downgrades the result.
MAX_MISSING_SHARE = 0.02

DAILY_VARS = [
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "temperature_2m_min",
    "temperature_2m_max",
    "temperature_2m_mean",
]
POWER_PARAMS = ["PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "T2MDEW", "WS2M", "ALLSKY_SFC_SW_DWN"]


class DailySeries(BaseModel):
    dates: list[date]
    precip_mm: list[float | None]
    et0_mm: list[float | None]
    tmin_c: list[float | None]
    tmax_c: list[float | None]
    tmean_c: list[float | None]


class WeatherForecast(BaseModel):
    """Forecast for the days after analysis_date. Present only when analysis_date is today."""

    issued_on: date
    dates: list[date]
    precip_mm: list[float | None]
    et0_mm: list[float | None]
    tmax_c: list[float | None]


class WeatherData(BaseModel):
    provider: str  # "open_meteo_archive" | "nasa_power"
    latitude: float
    longitude: float
    daily: DailySeries
    # First day taken from a forecast model run instead of reanalysis (preliminary values), if any.
    provisional_from: date | None = None
    missing_days: int
    forecast: WeatherForecast | None = None


def history_start(analysis_date: date) -> date:
    """Start of the requested window: 1 October before the oldest of the HISTORY_YEARS seasons.

    Covers HISTORY_YEARS full previous seasons plus the current one, each with its autumn-winter
    recharge period.
    """
    return date(analysis_date.year - HISTORY_YEARS - 1, 10, 1)


def grid_point(lat: float, lon: float) -> tuple[float, float]:
    return round(round(lat / GRID_DEG) * GRID_DEG, 2), round(round(lon / GRID_DEG) * GRID_DEG, 2)


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def parse_open_meteo_daily(
    payload: dict[str, Any], start: date, end: date
) -> dict[date, dict[str, float | None]]:
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise SourceError("Serwis pogodowy zwrócił niekompletną odpowiedź.")
    fields = {
        "precip_mm": "precipitation_sum",
        "et0_mm": "et0_fao_evapotranspiration",
        "tmin_c": "temperature_2m_min",
        "tmax_c": "temperature_2m_max",
        "tmean_c": "temperature_2m_mean",
    }
    out: dict[date, dict[str, float | None]] = {}
    try:
        times = list(daily["time"])
        cols = {k: list(daily.get(v) or []) for k, v in fields.items()}
        for i, t in enumerate(times):
            d = date.fromisoformat(t)
            if not start <= d <= end:
                continue
            out[d] = {k: _f(col[i]) if i < len(col) else None for k, col in cols.items()}
    except (TypeError, ValueError) as exc:
        raise SourceError("Serwis pogodowy zwrócił nieczytelną odpowiedź.") from exc
    return out


def parse_power_daily(
    payload: dict[str, Any], start: date, end: date, lat: float
) -> dict[date, dict[str, float | None]]:
    try:
        params = payload["properties"]["parameter"]
        fill = float(payload.get("header", {}).get("fill_value", -999.0))
        elevation = float(payload["geometry"]["coordinates"][2])
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise SourceError("Zapasowy serwis pogodowy (NASA POWER) zwrócił niekompletną odpowiedź.") from exc

    def val(name: str, key: str) -> float | None:
        v = params.get(name, {}).get(key)
        if v is None or float(v) <= fill + 1e-6:
            return None
        return float(v)

    out: dict[date, dict[str, float | None]] = {}
    for key in params.get("PRECTOTCORR", {}):
        d = date(int(key[:4]), int(key[4:6]), int(key[6:8]))
        if not start <= d <= end:
            continue
        tmax, tmin, tdew = val("T2M_MAX", key), val("T2M_MIN", key), val("T2MDEW", key)
        wind, rs = val("WS2M", key), val("ALLSKY_SFC_SW_DWN", key)
        et0: float | None = None
        if None not in (tmax, tmin, tdew, wind, rs):
            assert tmax is not None and tmin is not None and tdew is not None
            assert wind is not None and rs is not None
            et0 = et0_fao56_mm(
                day=d,
                lat_deg=lat,
                elevation_m=elevation,
                tmax_c=tmax,
                tmin_c=tmin,
                ea_kpa=saturation_vapour_pressure_kpa(tdew),
                wind_2m_ms=wind,
                rs_mj=rs,
            )
        out[d] = {
            "precip_mm": val("PRECTOTCORR", key),
            "et0_mm": None if et0 is None else round(et0, 2),
            "tmin_c": tmin,
            "tmax_c": tmax,
            "tmean_c": val("T2M", key),
        }
    return out


def _complete(row: dict[str, float | None] | None) -> bool:
    return row is not None and row["precip_mm"] is not None and row["et0_mm"] is not None


def build_series(
    rows: dict[date, dict[str, float | None]], start: date, end: date
) -> tuple[DailySeries, int]:
    """Contiguous daily series start..end; days without data stay None (never filled with defaults)."""
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    cols: dict[str, list[float | None]] = {
        k: [] for k in ("precip_mm", "et0_mm", "tmin_c", "tmax_c", "tmean_c")
    }
    n_missing = 0
    for d in dates:
        row = rows.get(d)
        if not _complete(row):
            n_missing += 1
        for k, col in cols.items():
            col.append(None if row is None else row[k])
    return DailySeries(dates=dates, **cols), n_missing


async def _get_json(
    url: str, params: dict[str, Any] | list[tuple[str, Any]], what_pl: str, timeout_s: float = TIMEOUT_S
) -> dict[str, Any]:
    try:
        resp = await request("GET", url, params=params, timeout_s=timeout_s, retries=0)
        payload = resp.json()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        log.warning("%s HTTP %s", url, code)
        if code == 429:
            raise SourceError(f"{what_pl} odmówił obsługi (przekroczony dzienny limit zapytań).") from exc
        raise SourceError(f"{what_pl} zwrócił błąd (HTTP {code}).") from exc
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("%s failed: %s", url, type(exc).__name__)
        raise SourceError(f"{what_pl} nie odpowiedział.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise SourceError(f"{what_pl} zwrócił błąd.")
    return payload


async def _fetch_archive(
    lat: float, lon: float, start: date, end: date
) -> dict[date, dict[str, float | None]]:
    payload = await _get_json(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY_VARS),
            "timezone": TIMEZONE,
        },
        "Serwis pogodowy Open-Meteo",
    )
    return parse_open_meteo_daily(payload, start, end)


async def _fetch_power(lat: float, lon: float, start: date, end: date) -> dict[date, dict[str, float | None]]:
    payload = await _get_json(
        POWER_URL,
        {
            "parameters": ",".join(POWER_PARAMS),
            "community": "AG",
            "latitude": lat,
            "longitude": lon,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        },
        "Zapasowy serwis pogodowy NASA POWER",
    )
    return parse_power_daily(payload, start, end, lat)


async def _fetch_forecast(lat: float, lon: float, past_days: int, forecast_days: int) -> dict[str, Any]:
    return await _get_json(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "past_days": past_days,
            "forecast_days": forecast_days,
            "daily": ",".join(DAILY_VARS),
            "timezone": TIMEZONE,
        },
        "Serwis prognozy pogody Open-Meteo",
        FORECAST_TIMEOUT_S,
    )


def _last_complete(rows: dict[date, dict[str, float | None]], end: date) -> date | None:
    complete = [d for d, r in rows.items() if d <= end and _complete(r)]
    return max(complete) if complete else None


async def _assemble(
    provider: str, lat: float, lon: float, analysis_date: date, today: date
) -> tuple[WeatherData, list[str]]:
    """Fetch the observed series (+ provisional tail and forecast when relevant). Returns data and notes."""
    start = history_start(analysis_date)
    fetch = _fetch_archive if provider == "open_meteo_archive" else _fetch_power
    rows = await fetch(lat, lon, start, analysis_date)
    if not any(_complete(r) for r in rows.values()):
        # An empty answer is treated as a failure so that the fallback provider is tried.
        raise SourceError("Serwis pogodowy nie zwrócił danych dla tej lokalizacji i okresu.")
    notes: list[str] = []
    provisional_from: date | None = None
    forecast: WeatherForecast | None = None

    last = _last_complete(rows, analysis_date)
    need_tail = last is None or last < analysis_date
    want_forecast = analysis_date == today
    tail_reachable = last is not None and (today - last).days <= FORECAST_MAX_PAST_DAYS
    if (need_tail and tail_reachable) or want_forecast:
        past_days = min(FORECAST_MAX_PAST_DAYS, max(1, (today - (last or analysis_date)).days + 1))
        try:
            fc = await _fetch_forecast(lat, lon, past_days, FORECAST_DAYS_AHEAD + 1 if want_forecast else 1)
            fc_rows = parse_open_meteo_daily(fc, start, today + timedelta(days=FORECAST_DAYS_AHEAD))
        except SourceError as exc:
            notes.append(f"{exc.message_pl} Brak danych z ostatnich dni i prognozy.")
        else:
            if need_tail and last is not None:
                for d, row in fc_rows.items():
                    if last < d <= analysis_date and _complete(row):
                        rows[d] = row
                        provisional_from = min(provisional_from or d, d)
            if want_forecast:
                ahead = sorted(d for d in fc_rows if d > analysis_date)
                if ahead:
                    forecast = WeatherForecast(
                        issued_on=today,
                        dates=ahead,
                        precip_mm=[fc_rows[d]["precip_mm"] for d in ahead],
                        et0_mm=[fc_rows[d]["et0_mm"] for d in ahead],
                        tmax_c=[fc_rows[d]["tmax_c"] for d in ahead],
                    )

    series, n_missing = build_series(rows, start, analysis_date)
    return (
        WeatherData(
            provider=provider,
            latitude=lat,
            longitude=lon,
            daily=series,
            provisional_from=provisional_from,
            missing_days=n_missing,
            forecast=forecast,
        ),
        notes,
    )


async def _cached_assemble(
    provider: str, lat: float, lon: float, analysis_date: date, today: date
) -> tuple[WeatherData, list[str]]:
    cache = get_cache()
    params = {"provider": provider, "lat": lat, "lon": lon, "date": analysis_date.isoformat(), "today": None}
    # The forecast block depends on "today", so cache entries for today's analyses are keyed by today as well.
    if analysis_date == today:
        params["today"] = today.isoformat()
    cached = cache.get(NAME, params)
    if cached is not None:
        return WeatherData.model_validate(cached["data"]), list(cached["notes"])
    data, notes = await _assemble(provider, lat, lon, analysis_date, today)
    # Expiry is decided now: provisional, incomplete or forecast-bearing data must be refreshed later,
    # final reanalysis for old dates never changes.
    final = (
        data.provisional_from is None
        and data.forecast is None
        and not notes
        and data.daily.precip_mm[-1] is not None
        and data.daily.et0_mm[-1] is not None
    )
    ttl = cache_ttl(analysis_date, today) if final else CURRENT_DATA_TTL
    cache.set(NAME, params, {"data": data.model_dump(mode="json"), "notes": notes}, ttl)
    return data, notes


def _summarise(data: WeatherData, notes: list[str], analysis_date: date) -> SourceResult[WeatherData]:
    total = len(data.daily.dates)
    period = Period(start=data.daily.dates[0], end=analysis_date)
    fallback = data.provider == "nasa_power"
    source = SOURCE_POWER if fallback else SOURCE_ARCHIVE
    if data.provisional_from or data.forecast:
        source += f"; {SOURCE_FORECAST}"
    license = LICENSE_POWER if fallback else LICENSE_OPEN_METEO
    if fallback and (data.provisional_from or data.forecast):
        license += f"; {LICENSE_OPEN_METEO} (prognoza)"

    if data.missing_days >= total:
        return missing(
            NAME,
            source=source,
            license=license,
            message_pl="Brak danych pogodowych dla tej lokalizacji i okresu.",
        )

    messages: list[str] = []
    status = SourceStatus.OK
    level = Confidence.HIGH
    reasons = ["dane z reanalizy meteorologicznej w siatce ok. 10 km, nie z pola"]
    if fallback:
        status = SourceStatus.DEGRADED
        level = Confidence.MEDIUM
        messages.append(
            "Główny serwis pogodowy nie odpowiedział, dlatego użyto zapasowych danych NASA POWER "
            "(siatka ok. 50 km, parowanie wyliczone ze wzoru FAO-56)."
        )
        reasons = ["dane zapasowe w grubej siatce ok. 50 km"]
    last = data.daily.dates[-1]
    last_has_data = data.daily.precip_mm[-1] is not None and data.daily.et0_mm[-1] is not None
    if not last_has_data:
        status = SourceStatus.DEGRADED
        level = Confidence.MEDIUM if level is Confidence.HIGH else level
        messages.append(f"Brak danych pogodowych z ostatnich dni przed {last.strftime('%d.%m.%Y')}.")
    if data.missing_days > MAX_MISSING_SHARE * total:
        status = SourceStatus.DEGRADED
        level = Confidence.LOW
        messages.append(f"Brakuje danych pogodowych z {data.missing_days} dni w okresie analizy.")
    if data.provisional_from:
        messages.append(
            f"Dane od {data.provisional_from.strftime('%d.%m.%Y')} są wstępne (model prognozy), "
            "mogą się jeszcze nieznacznie zmienić."
        )
        reasons.append("ostatnie dni to wartości wstępne")
    messages.extend(notes)
    return result(
        NAME,
        status,
        data,
        source=source,
        license=license,
        period=period,
        uncertainty=unc(level, "; ".join(reasons).capitalize() + "."),
        message_pl=" ".join(messages) or None,
    )


async def fetch(parcel: Parcel, analysis_date: date, today: date | None = None) -> SourceResult[WeatherData]:
    return await within_budget(
        NAME,
        _fetch(parcel, analysis_date, today or today_local()),
        BUDGET_S,
        lambda: missing(
            NAME,
            source=f"{SOURCE_ARCHIVE}; {SOURCE_POWER}",
            license=f"{LICENSE_OPEN_METEO}; {LICENSE_POWER}",
            message_pl="Serwisy pogodowe nie odpowiedziały na czas.",
        ),
    )


async def _fetch(parcel: Parcel, analysis_date: date, today: date) -> SourceResult[WeatherData]:
    lat, lon = grid_point(parcel.centroid_lat, parcel.centroid_lon)
    errors: list[str] = []
    for provider in ("open_meteo_archive", "nasa_power"):
        try:
            data, notes = await _cached_assemble(provider, lat, lon, analysis_date, today)
        except SourceError as exc:
            errors.append(exc.message_pl)
            continue
        return _summarise(data, notes, analysis_date)
    return missing(
        NAME,
        source=f"{SOURCE_ARCHIVE}; {SOURCE_POWER}",
        license=f"{LICENSE_OPEN_METEO}; {LICENSE_POWER}",
        message_pl="Nie udało się pobrać danych pogodowych: " + " ".join(errors),
    )
