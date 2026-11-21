from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core import cache as cache_module
from app.core.cache import DiskCache


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Iterator[DiskCache]:
    c = DiskCache(tmp_path / "cache")
    previous = cache_module._cache
    cache_module._cache = c
    yield c
    cache_module._cache = previous
