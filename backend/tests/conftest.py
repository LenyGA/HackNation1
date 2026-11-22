from collections.abc import Iterator
from pathlib import Path

import pytest

from app.api import ratelimit
from app.core import cache as cache_module
from app.core import http as http_module
from app.core.cache import DiskCache
from app.report import pdf as pdf_module


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Iterator[DiskCache]:
    c = DiskCache(tmp_path / "cache")
    previous = cache_module._cache
    cache_module._cache = c
    yield c
    cache_module._cache = previous


@pytest.fixture(autouse=True)
def _fresh_http_client() -> Iterator[None]:
    """The shared httpx client is bound to an event loop; each test (own loop) gets a new one."""
    http_module._client = None
    yield
    http_module._client = None


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> Iterator[None]:
    """Rate-limit buckets are per process; tests must not share them."""
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture(autouse=True)
def _fresh_pdf_cache() -> Iterator[None]:
    """Rendered PDFs are cached per report id; tests reuse ids with different content."""
    pdf_module._pdf_cache.clear()
    yield
    pdf_module._pdf_cache.clear()


@pytest.fixture(autouse=True)
def _no_orthophoto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never call the Geoportal WMS; tests that need the background patch it themselves."""
    from app.sources import orthophoto

    async def _none(_bounds: tuple[float, float, float, float]) -> str | None:
        return None

    monkeypatch.setattr(orthophoto, "fetch_data_uri", _none)
