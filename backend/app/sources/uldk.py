"""GUGiK ULDK: parcel geometry and TERYT identifiers (https://uldk.gugik.gov.pl/).

Response format (plain text): first line is a status code ("0" = OK, "-1 ..." = no result / error), following
lines are records with `|`-separated fields in the order requested in `result`.
"""

import asyncio
import json
import logging
import time
from datetime import timedelta
from typing import Any

import httpx
from pydantic import ValidationError
from shapely import wkt
from shapely.errors import ShapelyError
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.core.cache import get_cache
from app.core.http import request
from app.core.models import Parcel, validate_parcel_id
from app.sources.base import METRIC_CRS, SourceError, to_crs

log = logging.getLogger(__name__)
# ULDK now and then answers with an empty body or a truncated record, sometimes several times in a row;
# such answers come back fast, so they are retried after a short pause. Timeouts, HTTP errors and records
# that parse but are invalid are not retried (retrying cannot fix them). Retries stop once RETRY_DEADLINE_S
# has passed, so a slow ULDK cannot eat the 30 s budget of the analysis.
# When it throttles a client it answers 302 to integracja01.gugik.gov.pl/resp/uldk.php, which drops the query
# and streams gigabytes of junk (seen 21.11.2026): redirects are never followed, only retried like the above.
READ_ATTEMPTS = 4
RETRY_PAUSE_S = 0.5
RETRY_DEADLINE_S = 10.0

NAME = "uldk"
URL = "https://uldk.gugik.gov.pl/"
SOURCE = "GUGiK, Usługa Lokalizacji Działek Katastralnych (ULDK), https://uldk.gugik.gov.pl/"
LICENSE = "Dane publiczne GUGiK, udostępniane bezpłatnie"
TIMEOUT_S = 8.0
# Cadastral geometry changes rarely; a day-long cache keeps repeated analyses of the same parcel fast.
CACHE_TTL = timedelta(days=1)

RESULT_FIELDS = ["geom_wkt", "teryt", "voivodeship", "county", "commune", "region", "parcel"]

MSG_NOT_FOUND_ID = (
    "Nie znaleziono działki o numerze {id}. Sprawdź numer (format: WWPPGG_R.OOOO.NR, np. 141201_1.0001.6509)."
)
MSG_NOT_FOUND_XY = "W tym miejscu nie znaleziono działki ewidencyjnej. Kliknij wewnątrz granic działki."
MSG_UNAVAILABLE = "Usługa wyszukiwania działek (GUGiK) chwilowo nie odpowiada. Spróbuj ponownie za chwilę."
MSG_BAD_RESPONSE = (
    "Usługa wyszukiwania działek (GUGiK) zwróciła nieczytelną odpowiedź. Spróbuj ponownie za chwilę."
)


class ParcelNotFound(SourceError):
    """The parcel does not exist (or no parcel at the clicked point)."""


class ParcelServiceError(SourceError):
    """ULDK did not answer or returned something we cannot parse."""


class _Redirected(ParcelServiceError):
    """ULDK redirected the request (it does so when it throttles a client) instead of answering."""


class _Unreadable(ParcelServiceError):
    """Empty or cut-off answer (no status line or record, broken geometry); a repeat usually works."""

    def __init__(self) -> None:
        super().__init__(MSG_BAD_RESPONSE)


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_response(text: str) -> list[list[str]] | None:
    """Return records (lists of fields) or None when ULDK reports no result ("-1"). Raises on garbage."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise _Unreadable()
    status = lines[0].strip()
    if status.startswith("-1"):
        return None
    if status != "0" and not status.isdigit():
        raise _Unreadable()
    records = [ln.split("|") for ln in lines[1:]]
    if not records:  # "no result" is "-1 ..."; a bare "0" is an answer cut off before the record
        raise _Unreadable()
    return records


def _parse_geometry(geom_wkt: str) -> BaseGeometry:
    if ";" in geom_wkt:  # EWKT prefix "SRID=4326;"
        geom_wkt = geom_wkt.split(";", 1)[1]
    try:
        geom = wkt.loads(geom_wkt)
    except (ShapelyError, ValueError) as exc:
        raise _Unreadable() from exc
    if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ParcelServiceError(MSG_BAD_RESPONSE)
    return geom


def record_to_parcel(record: list[str]) -> Parcel:
    if len(record) < len(RESULT_FIELDS):  # the answer was cut off inside the record
        raise _Unreadable()
    fields = dict(zip(RESULT_FIELDS, record, strict=False))
    geom = _parse_geometry(fields["geom_wkt"])
    metric = to_crs(geom, METRIC_CRS)
    centroid = to_crs(metric.centroid, 4326, src_crs=METRIC_CRS)
    parcel_id = fields["teryt"].strip()
    if not parcel_id:
        raise ParcelServiceError(MSG_BAD_RESPONSE)
    # JSON round-trip: plain lists instead of shapely tuples, identical to the cached form.
    geometry: dict[str, Any] = json.loads(json.dumps(mapping(geom)))
    try:
        return _build_parcel(fields, parcel_id, geometry, metric.area, centroid.x, centroid.y)
    except ValidationError as exc:
        raise ParcelServiceError(MSG_BAD_RESPONSE) from exc


def _build_parcel(
    fields: dict[str, str], parcel_id: str, geometry: dict[str, Any], area_m2: float, lon: float, lat: float
) -> Parcel:
    return Parcel(
        id=parcel_id,
        voivodeship=_clean(fields["voivodeship"]),
        county=_clean(fields["county"]),
        commune=_clean(fields["commune"]),
        precinct=_clean(fields["region"]),
        number=_clean(fields["parcel"]),
        area_ha=round(area_m2 / 10_000, 4),
        centroid_lat=round(lat, 6),
        centroid_lon=round(lon, 6),
        geometry=geometry,
    )


async def _query(params: dict[str, str]) -> str:
    try:
        resp = await request("GET", URL, params=params, timeout_s=TIMEOUT_S, follow_redirects=False)
    except httpx.HTTPStatusError as exc:
        if exc.response.is_redirect:
            raise _Redirected(MSG_UNAVAILABLE) from exc
        log.warning("ULDK request failed: HTTP %s", exc.response.status_code)
        raise ParcelServiceError(MSG_UNAVAILABLE) from exc
    except httpx.HTTPError as exc:
        log.warning("ULDK request failed: %s", type(exc).__name__)
        raise ParcelServiceError(MSG_UNAVAILABLE) from exc
    return resp.text


async def _lookup(params: dict[str, str]) -> Parcel | None:
    """First parcel of the answer, None when ULDK finds nothing; unreadable answers are retried."""
    started = time.monotonic()
    for attempt in range(READ_ATTEMPTS):
        try:
            records = parse_response(await _query(params))
            return None if records is None else record_to_parcel(records[0])
        except (_Redirected, _Unreadable) as exc:
            pause_s = RETRY_PAUSE_S * (attempt + 1)
            out_of_time = time.monotonic() - started + pause_s > RETRY_DEADLINE_S
            if attempt == READ_ATTEMPTS - 1 or out_of_time:
                raise
            what = "a redirect" if isinstance(exc, _Redirected) else "an unreadable answer"
            log.warning("ULDK returned %s, retrying", what)
            await asyncio.sleep(pause_s)
    raise AssertionError("unreachable")


async def get_parcel_by_id(parcel_id: str) -> Parcel:
    """Look up a parcel by its full identifier. Raises ParcelNotFound / ParcelServiceError / ValueError."""
    parcel_id = validate_parcel_id(parcel_id)
    cache = get_cache()
    cached = cache.get(NAME, {"id": parcel_id}, CACHE_TTL)
    if cached is not None:
        return Parcel.model_validate(cached)
    # httpx percent-encodes '/' in query values (e.g. '273/18' -> '273%2F18').
    params = {"request": "GetParcelById", "id": parcel_id, "result": ",".join(RESULT_FIELDS), "srid": "4326"}
    parcel = await _lookup(params)
    if parcel is None:
        raise ParcelNotFound(MSG_NOT_FOUND_ID.format(id=parcel_id))
    cache.set(NAME, {"id": parcel_id}, parcel.model_dump(mode="json"))
    return parcel


async def get_parcel_by_xy(lat: float, lon: float) -> Parcel:
    """Look up the parcel containing a WGS84 point."""
    parcel = await _lookup(
        {
            "request": "GetParcelByXY",
            "xy": f"{lon:.7f},{lat:.7f},4326",
            "result": ",".join(RESULT_FIELDS),
            "srid": "4326",
        }
    )
    if parcel is None:
        raise ParcelNotFound(MSG_NOT_FOUND_XY)
    return parcel
