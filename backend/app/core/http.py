"""Shared async HTTP client: per-request timeout, one retry on transient failures, neutral User-Agent."""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import USER_AGENT

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None

RETRY_STATUS = {429, 500, 502, 503, 504}


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def request(
    method: str,
    url: str,
    *,
    timeout_s: float,
    retries: int = 1,
    client: httpx.AsyncClient | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Send a request; retry once on network errors or 429/5xx. Raises httpx errors on final failure."""
    c = client or get_client()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await c.request(method, url, timeout=timeout_s, **kwargs)
            if resp.status_code in RETRY_STATUS and attempt < retries:
                log.info("retrying %s (status %s)", url, resp.status_code)
                await asyncio.sleep(0.5)
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < retries:
                log.info("retrying %s (%s)", url, type(exc).__name__)
                await asyncio.sleep(0.5)
                continue
            raise
    assert last_exc is not None  # pragma: no cover
    raise last_exc  # pragma: no cover
