"""Microsoft Planetary Computer: STAC search and anonymous SAS token signing; windowed COG reads.

Used by sentinel2.py, dem.py and landcover.py. Tokens are anonymous (no account, no key) and cached in memory
until shortly before expiry. Raster reads are synchronous (GDAL) and run in a shared thread pool.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import numpy as np
import rasterio
from affine import Affine
from rasterio.errors import RasterioError
from rasterio.windows import Window, from_bounds

from app.core.http import request
from app.sources.base import SourceError

log = logging.getLogger(__name__)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
SEARCH_TIMEOUT_S = 8.0
TOKEN_REFRESH_MARGIN_S = 300

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "VSI_CACHE": "TRUE",
    "GDAL_INGESTED_BYTES_AT_OPEN": "32768",
    "GDAL_HTTP_TIMEOUT": "10",
    "GDAL_HTTP_MAX_RETRY": "1",
    "GDAL_HTTP_RETRY_DELAY": "0.5",
}

# Blocking raster I/O pools. Sentinel-2 issues many reads per analysis, so it gets its own pool and cannot
# starve the terrain and land-cover reads of the same analysis.
RASTER_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="raster")
SENTINEL_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="s2")

_tokens: dict[str, tuple[str, float]] = {}
_token_locks: dict[str, asyncio.Lock] = {}


async def get_token(collection: str) -> str:
    lock = _token_locks.setdefault(collection, asyncio.Lock())
    async with lock:
        cached = _tokens.get(collection)
        if cached and cached[1] - TOKEN_REFRESH_MARGIN_S > time.time():
            return cached[0]
        try:
            resp = await request(
                "GET", TOKEN_URL.format(collection=collection), timeout_s=SEARCH_TIMEOUT_S, retries=0
            )
            body = resp.json()
            token = str(body["token"])
            expiry = datetime.fromisoformat(str(body["msft:expiry"]).replace("Z", "+00:00")).timestamp()
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("Planetary Computer token for %s failed: %s", collection, type(exc).__name__)
            raise SourceError("Serwis danych satelitarnych (Planetary Computer) nie odpowiedział.") from exc
        _tokens[collection] = (token, expiry)
        return token


def sign(href: str, token: str) -> str:
    """Append the SAS token to a blob URL. Local paths (tests) are returned unchanged."""
    if not href.startswith("http"):
        return href
    return f"{href}{'&' if '?' in href else '?'}{token}"


async def search(body: dict[str, Any]) -> list[dict[str, Any]]:
    """POST a STAC search and return the features of the first page."""
    try:
        resp = await request("POST", STAC_URL, json=body, timeout_s=SEARCH_TIMEOUT_S, retries=0)
        features = resp.json()["features"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("STAC search failed: %s", type(exc).__name__)
        raise SourceError("Katalog danych satelitarnych (Planetary Computer) nie odpowiedział.") from exc
    return list(features)


@dataclass
class WindowRead:
    array: np.ndarray
    transform: Any  # affine.Affine of the window
    crs: Any
    nodata: float | None
    # True when the requested bounds reach beyond the raster (e.g. parcel on a tile edge).
    clipped: bool = False


def read_window(
    href: str,
    bounds: tuple[float, float, float, float],
    *,
    out_shape: tuple[int, int] | None = None,
    resampling: Any = None,
) -> WindowRead:
    """Read band 1 of a COG inside `bounds` (expressed in the raster's CRS). Blocking; run in RASTER_POOL.

    Only the requested window is transferred (HTTP range requests), never the whole scene.
    """
    try:
        with rasterio.Env(**GDAL_ENV), rasterio.open(href) as ds:
            requested = from_bounds(*bounds, transform=ds.transform).round_offsets().round_lengths()
            win = requested.intersection(Window(0, 0, ds.width, ds.height))
            clipped = (win.col_off, win.row_off, win.width, win.height) != (
                requested.col_off,
                requested.row_off,
                requested.width,
                requested.height,
            )
            kwargs: dict[str, Any] = {"window": win, "boundless": False}
            if out_shape is not None:
                kwargs["out_shape"] = out_shape
                if resampling is not None:
                    kwargs["resampling"] = resampling
            arr = ds.read(1, **kwargs)
            transform = ds.window_transform(win)
            if out_shape is not None:
                transform = transform @ Affine.scale(win.width / out_shape[1], win.height / out_shape[0])
            return WindowRead(array=arr, transform=transform, crs=ds.crs, nodata=ds.nodata, clipped=clipped)
    except (RasterioError, ValueError) as exc:
        raise SourceError("Nie udało się odczytać fragmentu rastra.") from exc


async def run_in_pool[T](fn: Any, *args: Any, pool: ThreadPoolExecutor | None = None, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    result: T = await loop.run_in_executor(pool or RASTER_POOL, lambda: fn(*args, **kwargs))
    return result
