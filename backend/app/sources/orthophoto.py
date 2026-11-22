"""Orthophoto background for the PDF parcel map: GUGiK Geoportal WMS GetMap for the map frame (Q7).

One image per report, requested by the server for the frame bbox in EPSG:2180 (WMS 1.1.1, x/y axis order),
embedded in the SVG as a data URI so the PDF never loads anything from outside. Short timeout: without an
answer the map is drawn as before, on a plain background, and says so.
"""

import base64
import logging
from datetime import timedelta

import httpx

from app.core.cache import get_cache
from app.core.http import request

log = logging.getLogger(__name__)

NAME = "orthophoto"
WMS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"
SOURCE = "Ortofotomapa GUGiK, usługa WMS Geoportal.gov.pl, https://www.geoportal.gov.pl/"
LICENSE = "dane PZGiK udostępniane bezpłatnie (ustawa Prawo geodezyjne i kartograficzne, art. 40a ust. 2)"
TIMEOUT_S = 5.0
CACHE_TTL_DAYS = 30
MAX_SIDE_PX = 900


def image_size(bounds: tuple[float, float, float, float]) -> tuple[int, int]:
    """Pixel size keeping the frame's aspect ratio, longer side MAX_SIDE_PX."""
    minx, miny, maxx, maxy = bounds
    w, h = maxx - minx, maxy - miny
    if w >= h:
        return MAX_SIDE_PX, max(1, round(MAX_SIDE_PX * h / w))
    return max(1, round(MAX_SIDE_PX * w / h)), MAX_SIDE_PX


def getmap_params(bounds: tuple[float, float, float, float]) -> dict[str, str]:
    width, height = image_size(bounds)
    return {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.1.1",
        "LAYERS": "Raster",
        "STYLES": "",
        "FORMAT": "image/jpeg",
        "SRS": "EPSG:2180",
        "BBOX": ",".join(f"{v:.1f}" for v in bounds),
        "WIDTH": str(width),
        "HEIGHT": str(height),
    }


async def fetch_data_uri(bounds: tuple[float, float, float, float]) -> str | None:
    """JPEG of the frame as a data URI, or None when the service does not answer in time."""
    params = getmap_params(bounds)
    cache = get_cache()
    cached = cache.get(NAME, params)
    if isinstance(cached, str):
        return cached
    try:
        resp = await request("GET", WMS_URL, params=params, timeout_s=TIMEOUT_S, retries=0)
    except httpx.HTTPError as exc:
        log.info("orthophoto WMS failed: %s", type(exc).__name__)
        return None
    ctype = resp.headers.get("content-type", "")
    if resp.status_code != 200 or not ctype.startswith("image/") or len(resp.content) < 1000:
        log.info("orthophoto WMS returned %s %s", resp.status_code, ctype)
        return None
    uri = f"data:{ctype.split(';')[0]};base64,{base64.b64encode(resp.content).decode('ascii')}"
    cache.set(NAME, params, uri, timedelta(days=CACHE_TTL_DAYS))
    return uri
