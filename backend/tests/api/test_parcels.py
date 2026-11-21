from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.cache import DiskCache
from app.main import app
from app.sources import uldk
from tests.helpers import uldk_fixture


@pytest.fixture
def client(tmp_cache: DiskCache) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_parcel_by_id(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(uldk.URL).mock(
            return_value=httpx.Response(200, text=uldk_fixture("by_id_141201_1.0001.6509.txt"))
        )
        r = client.get("/api/parcels", params={"id": "141201_1.0001.6509"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "141201_1.0001.6509"
    assert body["area_ha"] > 0
    assert body["geometry"]["type"] == "Polygon"


def test_parcel_by_click(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(
            return_value=httpx.Response(200, text=uldk_fixture("by_id_slash_302108_5.0014.88-8.txt"))
        )
        r = client.get("/api/parcels", params={"lat": 52.40017, "lon": 17.35004})
    assert r.status_code == 200
    assert r.json()["id"] == "302108_5.0014.88/8"
    assert route.calls.last.request.url.params["request"] == "GetParcelByXY"


def test_invalid_id_is_400(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL)
        r = client.get("/api/parcels", params={"id": "abc"})
    assert r.status_code == 400
    assert "Nieprawidłowy numer działki" in r.json()["detail"]
    assert route.call_count == 0


def test_no_id_and_no_point_is_400(client: TestClient) -> None:
    r = client.get("/api/parcels")
    assert r.status_code == 400


def test_not_found_is_404_with_polish_message(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(uldk.URL).mock(return_value=httpx.Response(200, text=uldk_fixture("not_found.txt")))
        r = client.get("/api/parcels", params={"id": "141201_1.0001.99999"})
    assert r.status_code == 404
    assert "Nie znaleziono działki" in r.json()["detail"]


def test_service_down_is_503(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(uldk.URL).mock(side_effect=httpx.ConnectError("down"))
        r = client.get("/api/parcels", params={"id": "141201_1.0001.6509"})
    assert r.status_code == 503
    assert "GUGiK" in r.json()["detail"]
