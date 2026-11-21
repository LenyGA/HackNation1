"""Disk cache for source responses.

Key = source name + SHA-256 of canonical JSON params. Historical data (fully before 'today') never expires;
current data is cached for a short TTL so the farmer does not get stale values.
"""

import hashlib
import json
import os
import threading
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

    def get(self, source: str, params: dict[str, Any], ttl: timedelta | None = None) -> Any | None:
        """Cached value or None. Honours the expiry stored at write time and, if given, a read-time `ttl`."""
        path = self._path(source, self.key(source, params))
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        now = time.time()
        expires_at = entry.get("expires_at")
        if expires_at is not None and now > expires_at:
            return None
        if ttl is not None and now - entry["stored_at"] > ttl.total_seconds():
            return None
        return entry["value"]

    def set(self, source: str, params: dict[str, Any], value: Any, ttl: timedelta | None = None) -> None:
        """Store a value. `ttl` is decided by the writer: provisional data expires, final data does not."""
        path = self._path(source, self.key(source, params))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        now = time.time()
        entry = {
            "stored_at": now,
            "expires_at": None if ttl is None else now + ttl.total_seconds(),
            "value": value,
        }
        tmp.write_text(json.dumps(entry, default=str), encoding="utf-8")
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
        self.set(source, params, value, ttl)
        return value


_cache: DiskCache | None = None


def get_cache() -> DiskCache:
    global _cache
    if _cache is None:
        _cache = DiskCache(get_settings().cache_dir / "sources")
    return _cache
