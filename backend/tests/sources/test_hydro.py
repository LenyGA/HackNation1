"""OSM water features. The Overpass payload is SYNTHETIC (tests/fixtures/hydro/overpass_synthetic.json)."""

import json
from datetime import date
from typing import Any

import httpx
import pytest
import respx
from shapely.geometry import box

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.sources import hydro
from tests.helpers import FIXTURES, parcel_from_polygon

DATE = date(2025, 6, 15)
PRIMARY, SECONDARY = hydro.SERVERS


def _payload() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "hydro" / "overpass_synthetic.json").read_text())
    return data


@pytest.fixture
def parcel() -> Parcel:
    return parcel_from_polygon(box(19.000, 52.000, 19.003, 52.0018))


async def test_features_distances_and_boundary_ditch(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        first = mock.post(PRIMARY).mock(return_value=httpx.Response(200, json=_payload()))
        mock.post(SECONDARY).mock(return_value=httpx.Response(200, json=_payload()))
        res = await hydro.fetch(parcel, DATE)

    query = first.calls.last.request.content.decode()
    assert "around%3A" in query or "around:" in query
    assert res.status is SourceStatus.OK
    assert res.message_pl is None
    assert "niepełna" in res.uncertainty.reason_pl
    d = res.data
    assert d is not None
    # Duplicate ditch and the unrelated track are ignored.
    assert d.counts == {"ditch": 1, "watercourse": 1, "water_body": 1, "wetland": 1, "trees": 2}
    near = d.nearest_m
    assert near["ditch"] == pytest.approx(5.6, abs=1.0)
    assert near["watercourse"] == pytest.approx(500, abs=15)
    assert near["water_body"] == pytest.approx(302, abs=10)
    assert near["trees"] == pytest.approx(34, abs=3)  # tree row beats the forest at ~343 m
    assert near["wetland"] == pytest.approx(801, abs=15)
    assert d.ditch_length_along_boundary_m == pytest.approx(206, abs=8)
    assert [f.distance_m for f in d.features] == sorted(f.distance_m for f in d.features)
    stream = next(f for f in d.features if f.kind == "watercourse")
    assert stream.name == "Struga Testowa"
    assert stream.geometry["type"] == "LineString"
    pond = next(f for f in d.features if f.kind == "water_body")
    assert pond.geometry["type"] == "Polygon"
    assert d.truncated is False


async def test_empty_result_is_ok_with_osm_note(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.post(PRIMARY).mock(return_value=httpx.Response(200, json={"elements": []}))
        mock.post(SECONDARY).mock(return_value=httpx.Response(200, json={"elements": []}))
        res = await hydro.fetch(parcel, DATE)

    assert res.status is SourceStatus.OK
    assert res.data is not None
    assert sum(res.data.counts.values()) == 0
    assert all(v is None for v in res.data.nearest_m.values())
    assert res.data.ditch_length_along_boundary_m == 0
    assert res.message_pl is not None and "niepełna" in res.message_pl


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(504),
        httpx.ConnectTimeout("t"),
        httpx.Response(200, json={"remark": "runtime error: timed out"}),
    ],
    ids=["http-504", "timeout", "remark-error"],
)
async def test_both_servers_down_is_missing(tmp_cache: DiskCache, parcel: Parcel, failure: Any) -> None:
    with respx.mock() as mock:
        for url in hydro.SERVERS:
            mock.post(url).mock(side_effect=[failure])
        res = await hydro.fetch(parcel, DATE)

    assert res.status is SourceStatus.MISSING
    assert res.data is None
    assert res.message_pl is not None and "nie odpowiedział" in res.message_pl


async def test_first_server_failing_second_ok(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock() as mock:
        mock.post(PRIMARY).mock(return_value=httpx.Response(429))
        mock.post(SECONDARY).mock(return_value=httpx.Response(200, json=_payload()))
        res = await hydro.fetch(parcel, DATE)

    assert res.status is SourceStatus.OK
    assert res.data is not None and res.data.counts["ditch"] == 1


async def test_second_call_served_from_cache(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        a = mock.post(PRIMARY).mock(return_value=httpx.Response(200, json=_payload()))
        b = mock.post(SECONDARY).mock(return_value=httpx.Response(200, json=_payload()))
        first = await hydro.fetch(parcel, DATE)
        calls = a.call_count + b.call_count
        second = await hydro.fetch(parcel, DATE)

    assert a.call_count + b.call_count == calls
    assert first.data == second.data


def test_classify() -> None:
    assert hydro.classify({"waterway": "drain"}) == "ditch"
    assert hydro.classify({"waterway": "river"}) == "watercourse"
    assert hydro.classify({"landuse": "reservoir"}) == "water_body"
    assert hydro.classify({"natural": "wetland"}) == "wetland"
    assert hydro.classify({"natural": "wood"}) == "trees"
    assert hydro.classify({"highway": "track"}) is None
