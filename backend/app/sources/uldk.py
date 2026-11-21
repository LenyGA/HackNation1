"""GUGiK ULDK: parcel geometry and TERYT identifiers (https://uldk.gugik.gov.pl/).

Response format (plain text): first line is a status code ("0" = OK, "-1 ..." = no result / error), following
lines are records with `|`-separated fields in the order requested in `result`.
"""

import json
import logging
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


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_response(text: str) -> list[list[str]] | None:
    """Return records (lists of fields) or None when ULDK reports no result. Raises on garbage."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise ParcelServiceError(MSG_BAD_RESPONSE)
    status = lines[0].strip()
    if status.startswith("-1"):
        return None
    if status != "0" and not status.isdigit():
        raise ParcelServiceError(MSG_BAD_RESPONSE)
    records = [ln.split("|") for ln in lines[1:]]
    return records or None


def _parse_geometry(geom_wkt: str) -> BaseGeometry:
    if ";" in geom_wkt:  # EWKT prefix "SRID=4326;"
        geom_wkt = geom_wkt.split(";", 1)[1]
    try:
        geom = wkt.loads(geom_wkt)
    except (ShapelyError, ValueError) as exc:
        raise ParcelServiceError(MSG_BAD_RESPONSE) from exc
    if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ParcelServiceError(MSG_BAD_RESPONSE)
    return geom


def record_to_parcel(record: list[str]) -> Parcel:
    if len(record) < len(RESULT_FIELDS):
        raise ParcelServiceError(MSG_BAD_RESPONSE)
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
        resp = await request("GET", URL, params=params, timeout_s=TIMEOUT_S)
    except httpx.HTTPError as exc:
        log.warning("ULDK request failed: %s", type(exc).__name__)
        raise ParcelServiceError(MSG_UNAVAILABLE) from exc
    return resp.text


async def get_parcel_by_id(parcel_id: str) -> Parcel:
    """Look up a parcel by its full identifier. Raises ParcelNotFound / ParcelServiceError / ValueError."""
    parcel_id = validate_parcel_id(parcel_id)
    cache = get_cache()
    cached = cache.get(NAME, {"id": parcel_id}, CACHE_TTL)
    if cached is not None:
        return Parcel.model_validate(cached)
    # httpx percent-encodes '/' in query values (e.g. '273/18' -> '273%2F18').
    text = await _query(
        {"request": "GetParcelById", "id": parcel_id, "result": ",".join(RESULT_FIELDS), "srid": "4326"}
    )
    records = parse_response(text)
    if not records:
        raise ParcelNotFound(MSG_NOT_FOUND_ID.format(id=parcel_id))
    parcel = record_to_parcel(records[0])
    cache.set(NAME, {"id": parcel_id}, parcel.model_dump(mode="json"))
    return parcel


async def get_parcel_by_xy(lat: float, lon: float) -> Parcel:
    """Look up the parcel containing a WGS84 point."""
    text = await _query(
        {
            "request": "GetParcelByXY",
            "xy": f"{lon:.7f},{lat:.7f},4326",
            "result": ",".join(RESULT_FIELDS),
            "srid": "4326",
        }
    )
    records = parse_response(text)
    if not records:
        raise ParcelNotFound(MSG_NOT_FOUND_XY)
    return record_to_parcel(records[0])
