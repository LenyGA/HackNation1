"""Disk cache for source responses.

Key = source name + SHA-256 of canonical JSON params. Historical data (fully before 'today') never expires;
current data is cached for a short TTL so the farmer does not get stale values.
"""

import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.core.config import get_settings

CURRENT_DATA_TTL = timedelta(hours=1)


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def key(source: str, params: dict[str, Any]) -> str:
        canonical = json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(f"{source}|{canonical}".encode()).hexdigest()

    def _path(self, source: str, key: str) -> Path:
        return self.root / source / key[:2] / f"{key}.json"

    def get(self, source: str, params: dict[str, Any], ttl: timedelta | None) -> Any | None:
        path = self._path(source, self.key(source, params))
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if ttl is not None and time.time() - entry["stored_at"] > ttl.total_seconds():
            return None
        return entry["value"]

    def set(self, source: str, params: dict[str, Any], value: Any) -> None:
        path = self._path(source, self.key(source, params))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"stored_at": time.time(), "value": value}, default=str), encoding="utf-8")
        tmp.replace(path)

    async def get_or_fetch(
        self,
        source: str,
        params: dict[str, Any],
        fetch: Callable[[], Awaitable[Any]],
        ttl: timedelta | None,
    ) -> Any:
        """Return cached JSON-serialisable value or call `fetch` and store it. ttl=None means no expiry."""
        cached = self.get(source, params, ttl)
        if cached is not None:
            return cached
        value = await fetch()
        self.set(source, params, value)
        return value


_cache: DiskCache | None = None


def get_cache() -> DiskCache:
    global _cache
    if _cache is None:
        _cache = DiskCache(get_settings().cache_dir / "sources")
    return _cache
