import httpx
import pytest
import respx
from pyproj import Geod
from shapely.geometry import shape

from app.core.cache import DiskCache
from app.sources import uldk
from tests.helpers import parcel_from_uldk, uldk_fixture


def _ok(name: str) -> httpx.Response:
    return httpx.Response(200, text=uldk_fixture(name))


async def test_get_by_id_parses_parcel(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(uldk.URL).mock(return_value=_ok("by_id_141201_1.0001.6509.txt"))
        parcel = await uldk.get_parcel_by_id("141201_1.0001.6509")
    params = route.calls.last.request.url.params
    assert params["request"] == "GetParcelById"
    assert params["srid"] == "4326"
    assert parcel.id == "141201_1.0001.6509"
    assert parcel.voivodeship == "mazowieckie"
    assert parcel.county == "powiat miński"
    assert parcel.commune == "Mińsk Mazowiecki (miasto)"
    assert parcel.precinct == "Mińsk Mazowiecki"
    assert parcel.number == "6509"
    assert parcel.geometry["type"] == "Polygon"
    assert 52.17 < parcel.centroid_lat < 52.18
    assert 21.58 < parcel.centroid_lon < 21.60


def test_area_in_hectares_is_plausible() -> None:
    parcel = parcel_from_uldk("by_id_141201_1.0001.6509.txt")
    # Independent check: geodesic area on the WGS84 ellipsoid.
    geodesic_m2 = abs(Geod(ellps="WGS84").geometry_area_perimeter(shape(parcel.geometry))[0])
    assert parcel.area_ha == pytest.approx(geodesic_m2 / 10_000, rel=0.01)
    assert 0.1 < parcel.area_ha < 1.0


async def test_id_with_slash_is_percent_encoded(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(uldk.URL).mock(return_value=_ok("by_id_slash_302108_5.0014.88-8.txt"))
        parcel = await uldk.get_parcel_by_id("302108_5.0014.88/8")
    raw_query = route.calls.last.request.url.query.decode()
    assert "id=302108_5.0014.88%2F8" in raw_query
    assert parcel.id == "302108_5.0014.88/8"
    assert parcel.number == "88/8"


async def test_click_lookup_uses_get_parcel_by_xy(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(uldk.URL).mock(return_value=_ok("by_id_slash_302108_5.0014.88-8.txt"))
        parcel = await uldk.get_parcel_by_xy(52.40017, 17.35004)
    params = route.calls.last.request.url.params
    assert params["request"] == "GetParcelByXY"
    assert params["xy"] == "17.3500400,52.4001700,4326"
    assert params["srid"] == "4326"
    assert parcel.id == "302108_5.0014.88/8"


async def test_not_found_gives_polish_message(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(uldk.URL).mock(return_value=_ok("not_found.txt"))
        with pytest.raises(uldk.ParcelNotFound) as exc_info:
            await uldk.get_parcel_by_id("141201_1.0001.99999")
        with pytest.raises(uldk.ParcelNotFound) as xy_info:
            await uldk.get_parcel_by_xy(52.0, 19.0)
    assert "Nie znaleziono działki" in exc_info.value.message_pl
    assert "141201_1.0001.99999" in exc_info.value.message_pl
    assert "nie znaleziono działki" in xy_info.value.message_pl


async def test_invalid_id_rejected_without_request(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL)
        with pytest.raises(ValueError, match="Nieprawidłowy numer działki"):
            await uldk.get_parcel_by_id("not-a-parcel")
    assert route.call_count == 0


@pytest.mark.parametrize(
    "response",
    [httpx.Response(503), httpx.ConnectTimeout("boom")],
    ids=["http-503", "timeout"],
)
async def test_service_failure_raises_service_error(
    tmp_cache: DiskCache, response: httpx.Response | Exception
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(uldk.URL).mock(side_effect=[response, response])
        with pytest.raises(uldk.ParcelServiceError) as exc_info:
            await uldk.get_parcel_by_id("141201_1.0001.6509")
    assert "GUGiK" in exc_info.value.message_pl


@pytest.fixture
def no_retry_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uldk, "RETRY_PAUSE_S", 0.0)


async def test_garbage_response_is_service_error(tmp_cache: DiskCache, no_retry_pause: None) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
        with pytest.raises(uldk.ParcelServiceError):
            await uldk.get_parcel_by_id("141201_1.0001.6509")
    assert route.call_count == uldk.READ_ATTEMPTS


@pytest.mark.parametrize(
    "bad_body", ["", "0\n", "0\nSRID=4326;POLYGON((1 2"], ids=["empty", "no_record", "garbled"]
)
async def test_unreadable_answers_are_retried(
    tmp_cache: DiskCache, no_retry_pause: None, bad_body: str
) -> None:
    """ULDK sometimes answers with an empty body twice in a row before a valid one (seen live, 21.11.2026)."""
    bad = httpx.Response(200, text=bad_body)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(uldk.URL).mock(side_effect=[bad, bad, _ok("by_id_141201_1.0001.6509.txt")])
        parcel = await uldk.get_parcel_by_id("141201_1.0001.6509")
    assert parcel.id == "141201_1.0001.6509"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(uldk.URL).mock(side_effect=[bad, _ok("by_id_slash_302108_5.0014.88-8.txt")])
        clicked = await uldk.get_parcel_by_xy(52.40017, 17.35004)
    assert clicked.id == "302108_5.0014.88/8"


async def test_not_found_is_not_retried(tmp_cache: DiskCache, no_retry_pause: None) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(return_value=_ok("not_found.txt"))
        with pytest.raises(uldk.ParcelNotFound):
            await uldk.get_parcel_by_xy(52.0, 19.0)
    assert route.call_count == 1


async def test_second_lookup_served_from_cache(tmp_cache: DiskCache) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(return_value=_ok("by_id_141201_1.0001.6509.txt"))
        first = await uldk.get_parcel_by_id("141201_1.0001.6509")
        second = await uldk.get_parcel_by_id("141201_1.0001.6509")
    assert route.call_count == 1
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


async def test_redirect_is_not_followed(tmp_cache: DiskCache, no_retry_pause: None) -> None:
    """A throttled ULDK answers 302 to an endpoint that streams junk; it must never be downloaded."""
    trap = "https://integracja01.gugik.gov.pl/resp/uldk.php"
    redirect = httpx.Response(302, headers={"Location": trap})
    with respx.mock(assert_all_called=False) as mock:
        trap_route = mock.get(trap).mock(return_value=httpx.Response(200, text="0\n0101"))
        route = mock.get(uldk.URL).mock(side_effect=[redirect, _ok("by_id_141201_1.0001.6509.txt")])
        parcel = await uldk.get_parcel_by_id("141201_1.0001.6509")
        assert parcel.id == "141201_1.0001.6509"
        route.mock(return_value=redirect)
        with pytest.raises(uldk.ParcelServiceError) as exc_info:
            await uldk.get_parcel_by_xy(52.0, 19.0)
    assert trap_route.call_count == 0
    assert route.call_count == 2 + uldk.READ_ATTEMPTS
    assert exc_info.value.message_pl == uldk.MSG_UNAVAILABLE


async def test_invalid_record_is_not_retried(tmp_cache: DiskCache, no_retry_pause: None) -> None:
    """A complete record that is invalid (a point, not a polygon) comes back the same on every try."""
    point = "0\nSRID=4326;POINT(17 52)|141201_1.0001.6509|mazowieckie|powiat|gmina|obręb|6509"
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(return_value=httpx.Response(200, text=point))
        with pytest.raises(uldk.ParcelServiceError) as exc_info:
            await uldk.get_parcel_by_id("141201_1.0001.6509")
    assert route.call_count == 1
    assert exc_info.value.message_pl == uldk.MSG_BAD_RESPONSE


async def test_retries_stop_at_deadline(tmp_cache: DiskCache, monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries end once the next pause would pass RETRY_DEADLINE_S, even with attempts left."""
    monkeypatch.setattr(uldk, "RETRY_PAUSE_S", 0.01)
    monkeypatch.setattr(uldk, "RETRY_DEADLINE_S", 0.025)  # room for the 1st pause (0.01), not the 2nd (0.02)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(uldk.URL).mock(return_value=httpx.Response(200, text=""))
        with pytest.raises(uldk.ParcelServiceError):
            await uldk.get_parcel_by_xy(52.0, 19.0)
    assert route.call_count == 2
