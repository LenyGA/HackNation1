"""Per-client rate limiting (plan M8.2)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import ratelimit
from app.api.ratelimit import SlidingWindowLimiter
from app.core.config import get_settings
from app.main import app


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_limiter_allows_up_to_limit_then_refuses() -> None:
    clock = FakeClock()
    lim = SlidingWindowLimiter(limit=3, window_s=60.0, clock=clock)
    assert [lim.hit("a") for _ in range(3)] == [None, None, None]
    wait = lim.hit("a")
    assert wait is not None and 1.0 <= wait <= 60.0
    # Another client has its own bucket.
    assert lim.hit("b") is None


def test_limiter_window_slides() -> None:
    clock = FakeClock()
    lim = SlidingWindowLimiter(limit=2, window_s=60.0, clock=clock)
    lim.hit("a")
    clock.t += 30
    lim.hit("a")
    assert lim.hit("a") is not None
    clock.t += 31  # the first hit has left the window
    assert lim.hit("a") is None
    assert lim.hit("a") is not None


def test_refused_hits_do_not_extend_the_block() -> None:
    clock = FakeClock()
    lim = SlidingWindowLimiter(limit=1, window_s=10.0, clock=clock)
    lim.hit("a")
    for _ in range(5):
        clock.t += 1
        assert lim.hit("a") is not None
    clock.t += 5
    assert lim.hit("a") is None


def test_full_table_sweeps_stale_then_drops_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "MAX_TRACKED_CLIENTS", 3)
    clock = FakeClock()
    lim = SlidingWindowLimiter(limit=5, window_s=10.0, clock=clock)
    for key in ("a", "b", "c"):
        lim.hit(key)
    clock.t += 11
    lim.hit("d")  # a, b, c are stale and swept
    assert set(lim._hits) == {"d"}
    lim.hit("e")
    lim.hit("f")
    lim.hit("g")  # nothing stale (and swept recently): the oldest bucket goes
    assert set(lim._hits) == {"e", "f", "g"}


def test_limiter_rejects_zero_limit() -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(limit=0, window_s=10.0)


def test_ipv6_clients_share_a_64_bucket() -> None:
    assert ratelimit._network_key("2001:db8:1:2::1") == ratelimit._network_key("2001:db8:1:2:ffff::9")
    assert ratelimit._network_key("2001:db8:1:2::1") != ratelimit._network_key("2001:db8:1:3::1")
    assert ratelimit._network_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert ratelimit._network_key("testclient") == "testclient"


def test_client_key_is_not_the_raw_address() -> None:
    class Req:
        class client:  # noqa: N801 - mimics starlette's Request.client
            host = "203.0.113.7"

    key = ratelimit.client_key(Req())  # type: ignore[arg-type]
    assert "203.0.113.7" not in key
    assert key == ratelimit.client_key(Req())  # type: ignore[arg-type]


@pytest.fixture
def low_limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_analyses", 3)
    monkeypatch.setattr(settings, "rate_limit_analyses_burst", 2)
    monkeypatch.setattr(settings, "rate_limit_parcels", 1)
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_analyses_endpoint_returns_429_in_polish(low_limits: None) -> None:
    client = TestClient(app)
    # Invalid bodies still count: the limit protects the endpoint, not only successful analyses.
    body = {"parcel_id": "zly", "crop_id": "maize", "analysis_date": "2024-07-15"}
    assert client.post("/api/analyses", json=body).status_code == 400
    assert client.post("/api/analyses", json=body).status_code == 400
    resp = client.post("/api/analyses", json=body)
    assert resp.status_code == 429
    assert resp.json()["detail"] == ratelimit.MSG_TOO_MANY_ANALYSES
    assert int(resp.headers["Retry-After"]) >= 1


def test_sustained_analyses_limit(low_limits: None, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_analyses_burst", 10)
    ratelimit.reset()
    client = TestClient(app)
    body = {"parcel_id": "zly", "crop_id": "maize", "analysis_date": "2024-07-15"}
    codes = [client.post("/api/analyses", json=body).status_code for _ in range(4)]
    assert codes == [400, 400, 400, 429]


def test_parcels_endpoint_is_limited(low_limits: None) -> None:
    client = TestClient(app)
    assert client.get("/api/parcels").status_code == 400
    resp = client.get("/api/parcels")
    assert resp.status_code == 429
    assert resp.json()["detail"] == ratelimit.MSG_TOO_MANY_REQUESTS


def test_other_endpoints_are_not_limited(low_limits: None) -> None:
    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/health").status_code == 200
