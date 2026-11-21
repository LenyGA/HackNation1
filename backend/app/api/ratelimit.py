"""Per-client rate limiting (plan M8.2) without storing personal data.

The client address is only used as a key, and only as a keyed hash with a random per-process salt: the raw
address is never kept in memory, written to disk, logged or put into a report. Buckets live in memory and
disappear on restart. Behind Caddy, uvicorn runs with `--proxy-headers`, so `request.client` is the real
client and not the proxy (Caddy overwrites any X-Forwarded-For sent by the client, see deploy/Caddyfile).

The dependencies are `async def` on purpose: they then run on the event loop, one at a time, so the shared
buckets need no lock (a plain `def` dependency would run in FastAPI's thread pool).
"""

import hashlib
import ipaddress
import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

MSG_TOO_MANY_ANALYSES = (
    "Za dużo analiz w krótkim czasie z tego samego adresu. Spróbuj ponownie za kilka minut."
)
MSG_TOO_MANY_REQUESTS = "Za dużo zapytań w krótkim czasie. Odczekaj chwilę i spróbuj ponownie."

_SALT = secrets.token_bytes(16)
# Hard cap on tracked clients per limiter; above it the oldest buckets are dropped (bounded memory).
MAX_TRACKED_CLIENTS = 10_000


def _network_key(host: str) -> str:
    """IPv6 clients get a whole /64 (one household or phone); IPv4 the single address."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


def client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.blake2b(_network_key(host).encode(), key=_SALT, digest_size=12).hexdigest()


@dataclass
class SlidingWindowLimiter:
    """At most `limit` hits per `window_s` seconds per key."""

    limit: int
    window_s: float
    clock: Callable[[], float] = time.monotonic
    _hits: dict[str, deque[float]] = field(default_factory=dict)
    _last_sweep: float = float("-inf")

    def __post_init__(self) -> None:
        if self.limit < 1 or self.window_s <= 0:
            raise ValueError("rate limit needs limit >= 1 and window_s > 0")

    def hit(self, key: str) -> float | None:
        """Record a hit. Returns None when allowed, or the seconds to wait when the limit is reached."""
        now = self.clock()
        if len(self._hits) >= MAX_TRACKED_CLIENTS and key not in self._hits:
            self._make_room(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1.0, self.window_s - (now - hits[0]))
        hits.append(now)
        return None

    def _make_room(self, now: float) -> None:
        # Stale buckets are swept at most once per window, so a flood does not make every hit O(n).
        if now - self._last_sweep >= self.window_s:
            self._last_sweep = now
            for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window_s]:
                del self._hits[key]
        # Still full: drop the oldest-inserted buckets (dicts keep insertion order).
        excess = len(self._hits) - MAX_TRACKED_CLIENTS + 1
        for key in list(self._hits)[: max(0, excess)]:
            del self._hits[key]


_limiters: dict[str, SlidingWindowLimiter] = {}


def _limiter(name: str) -> SlidingWindowLimiter:
    lim = _limiters.get(name)
    if lim is None:
        s = get_settings()
        limit, window_s = {
            "analyses": (s.rate_limit_analyses, s.rate_limit_analyses_window_s),
            "analyses_burst": (s.rate_limit_analyses_burst, s.rate_limit_analyses_burst_window_s),
            "parcels": (s.rate_limit_parcels, s.rate_limit_parcels_window_s),
        }[name]
        lim = _limiters[name] = SlidingWindowLimiter(limit, window_s)
    return lim


def reset() -> None:
    """Forget every client (used by tests)."""
    _limiters.clear()


def _refuse(wait_s: float, message_pl: str) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, message_pl, headers={"Retry-After": str(int(wait_s + 0.999))}
    )


async def limit_analyses(request: Request) -> None:
    """FastAPI dependency for `POST /api/analyses` (each analysis fans out to every public source).

    Two windows: a short burst limit keeps one client from filling the shared queue (and pushing everyone
    else past 30 s), and a longer one caps sustained use.
    """
    key = client_key(request)
    for name in ("analyses_burst", "analyses"):
        wait_s = _limiter(name).hit(key)
        if wait_s is not None:
            raise _refuse(wait_s, MSG_TOO_MANY_ANALYSES)


async def limit_parcels(request: Request) -> None:
    """FastAPI dependency for `GET /api/parcels` (every map click is a call to the public ULDK service)."""
    wait_s = _limiter("parcels").hit(client_key(request))
    if wait_s is not None:
        raise _refuse(wait_s, MSG_TOO_MANY_REQUESTS)
