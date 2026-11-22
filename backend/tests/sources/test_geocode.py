"""GUGiK address search (plan33 M8.7): parsing, the comma variant and errors, without network."""

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.cache import DiskCache
from app.main import app
from app.sources import geocode

ADDRESS = {
    "type": "address",
    "results": {
        "1": {
            "city": "Ksawerów",
            "street": None,
            "number": "12",
            "jednostka": "{Polska,wielkopolskie,koniński,Kramsk}",
            "x": "462613.24",
            "y": "483134.9",
        },
        "2": {
            "city": "Ksawerów",
            "street": None,
            "number": "12",
            "jednostka": '{Polska,łódzkie,"łódzki wschodni",Nowosolna}',
            "x": "546377.64",
            "y": "436647.57",
        },
    },
}
STREET = {
    "type": "street",
    "results": {
        "1": {
            "street": "Gdańska",
            "city": "Bydgoszcz",
            "jednostka": "{Bydgoszcz,046101}",
            "x": "434987.29",
            "y": "587573.42",
        }
    },
}
CITY_ADDRESS = {
    "type": "address",
    "results": {
        "1": {
            "city": "Bydgoszcz",
            "street": "Gdańska",
            "number": "10",
            "jednostka": "{Polska,kujawsko-pomorskie,Bydgoszcz,Bydgoszcz}",
            "x": "433337.14",
            "y": "584902.6",
        }
    },
}
EMPTY = {"type": "address", "results": None}


def test_parse_village_address() -> None:
    places = geocode.parse(ADDRESS)
    assert [p.label_pl for p in places] == ["Ksawerów 12", "Ksawerów 12"]
    assert places[0].detail_pl == "gm. Kramsk, pow. koniński, woj. wielkopolskie"
    assert places[1].detail_pl == "gm. Nowosolna, pow. łódzki wschodni, woj. łódzkie"
    # EPSG:2180 → lon/lat: Ksawerów (Kramsk) lies near 52.21 N, 18.45 E.
    assert places[0].lat == pytest.approx(52.213, abs=0.01) and places[0].lon == pytest.approx(
        18.453, abs=0.01
    )


def test_parse_street_without_admin_units() -> None:
    [p] = geocode.parse(STREET)
    assert p.kind == "street" and p.label_pl == "Bydgoszcz, Gdańska" and p.detail_pl == ""


def test_parse_city_address_skips_repeated_county() -> None:
    [p] = geocode.parse(CITY_ADDRESS)
    assert p.label_pl == "Bydgoszcz, Gdańska 10"
    assert p.detail_pl == "gm. Bydgoszcz, woj. kujawsko-pomorskie"


def test_parse_nothing_found() -> None:
    assert geocode.parse(EMPTY) == []


def test_parse_rejects_nonsense() -> None:
    with pytest.raises(geocode.GeocodeServiceError):
        geocode.parse(["not", "a", "dict"])


def test_variants_add_the_comma() -> None:
    assert geocode._variants("Bydgoszcz  Gdańska 10") == ["Bydgoszcz Gdańska 10", "Bydgoszcz, Gdańska 10"]
    assert geocode._variants("Ksawerów 12") == ["Ksawerów 12"]
    assert geocode._variants("Nowy Sącz Jagiellońska 1") == [
        "Nowy Sącz Jagiellońska 1",
        "Nowy, Sącz Jagiellońska 1",
        "Nowy Sącz, Jagiellońska 1",
    ]
    assert geocode._variants("00-001 Warszawa") == ["00-001 Warszawa"]
    assert geocode._variants("Bydgoszcz, Gdańska 10") == ["Bydgoszcz, Gdańska 10"]


@pytest.fixture
def client(tmp_cache: DiskCache) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_places_endpoint_tries_the_comma_variant(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(geocode.URL).mock(
            side_effect=[httpx.Response(200, json=EMPTY), httpx.Response(200, json=CITY_ADDRESS)]
        )
        r = client.get("/api/places", params={"q": "Bydgoszcz Gdańska 10"})
    assert r.status_code == 200
    assert r.json()[0]["label_pl"] == "Bydgoszcz, Gdańska 10"
    assert route.call_count == 2
    assert route.calls.last.request.url.params["address"] == "Bydgoszcz, Gdańska 10"


def test_places_endpoint_service_down_is_503(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(geocode.URL).mock(side_effect=httpx.ConnectTimeout("down"))
        r = client.get("/api/places", params={"q": "Ksawerów 12"})
    assert r.status_code == 503
    assert "GUGiK" in r.json()["detail"]


def test_places_endpoint_validates_length(client: TestClient) -> None:
    for q in ("a", "   ", "x" * 121):
        r = client.get("/api/places", params={"q": q})
        assert r.status_code == 400
        assert "adres" in r.json()["detail"]


def test_unreadable_query_is_nothing_found_not_an_outage(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(geocode.URL).mock(return_value=httpx.Response(200, text="Blad zapytania."))
        r = client.get("/api/places", params={"q": "00-001"})
    assert r.status_code == 200 and r.json() == []


def test_empty_answer_is_cached_briefly(tmp_cache: DiskCache) -> None:
    import asyncio
    import time

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(geocode.URL).mock(return_value=httpx.Response(200, json=EMPTY))
        assert asyncio.run(geocode.search("Ksawerów 12")) == []
        assert asyncio.run(geocode.search("Ksawerów 12")) == []
        assert route.call_count == 1  # cached
        # Past the short expiry of an empty answer the service is asked again.
        real = time.time
        try:
            time.time = lambda: real() + geocode.EMPTY_CACHE_TTL.total_seconds() + 5  # type: ignore[assignment]
            assert asyncio.run(geocode.search("Ksawerów 12")) == []
        finally:
            time.time = real  # type: ignore[assignment]
        assert route.call_count == 2
