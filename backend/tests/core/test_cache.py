from datetime import timedelta

import httpx
import respx

from app.core.cache import DiskCache
from app.core.http import request


async def test_second_call_hits_cache_not_network(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.test/data").mock(return_value=httpx.Response(200, json={"v": 1}))

        async def fetch() -> object:
            resp = await request("GET", "https://example.test/data", timeout_s=5)
            return resp.json()

        params = {"lat": 52.1, "lon": 21.0}
        first = await tmp_cache.get_or_fetch("demo", params, fetch, ttl=None)
        second = await tmp_cache.get_or_fetch("demo", params, fetch, ttl=None)

    assert first == second == {"v": 1}
    assert route.call_count == 1


def test_ttl_expiry(tmp_cache: DiskCache) -> None:
    tmp_cache.set("demo", {"a": 1}, [1, 2])
    assert tmp_cache.get("demo", {"a": 1}, ttl=timedelta(hours=1)) == [1, 2]
    assert tmp_cache.get("demo", {"a": 1}, ttl=timedelta(seconds=-1)) is None


def test_key_is_order_independent() -> None:
    assert DiskCache.key("s", {"a": 1, "b": 2}) == DiskCache.key("s", {"b": 2, "a": 1})
    assert DiskCache.key("s", {"a": 1}) != DiskCache.key("t", {"a": 1})


@respx.mock
async def test_http_retries_once_on_5xx() -> None:
    route = respx.get("https://example.test/flaky").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    resp = await request("GET", "https://example.test/flaky", timeout_s=5)
    assert resp.json() == {"ok": True}
    assert route.call_count == 2
    assert "RolnikSzukaWody" in route.calls[0].request.headers["User-Agent"]
