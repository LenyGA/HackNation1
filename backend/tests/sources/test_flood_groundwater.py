"""Flood maps (ISOK WMS, PIG-PIB groundwater flooding) and groundwater stations. Synthetic responses."""

import re
from datetime import date
from typing import Any

import httpx
import pytest
import respx
from shapely.geometry import box

from app.core.cache import DiskCache
from app.core.models import Parcel, SourceStatus
from app.report.outlook import flood_info, groundwater_info
from app.sources import flood, groundwater
from tests.helpers import parcel_from_polygon

DATE = date(2025, 6, 15)
IN_ZONE = (
    "Results for FeatureType 'NZ.Fluvial':\n--------------------------------------------\n"
    "loo_qualitativelikelihood = scenariusz Q 1% (raz na 100 lat)\nloo_ql_returnperiod = 100\n"
    "--------------------------------------------\nloo_ql_returnperiod = 500\n"
)


@pytest.fixture
def parcel() -> Parcel:
    return parcel_from_polygon(box(19.000, 52.000, 19.003, 52.0018))


def test_parse_return_periods() -> None:
    assert flood.parse_return_periods(IN_ZONE) == {100, 500}
    assert flood.parse_return_periods("no features were found") == set()


def test_sample_points_inside_parcel(parcel: Parcel) -> None:
    from app.sources.base import METRIC_CRS, parcel_shape, to_crs

    geom = to_crs(parcel_shape(parcel), METRIC_CRS)
    pts = flood.sample_points(geom)
    assert 2 <= len(pts) <= 1 + flood.MAX_EDGE_POINTS and all(geom.contains(p) for p in pts)


def _podtopienia(hit: bool) -> dict[str, Any]:
    return {"features": [{"attributes": {"NAZWA": "Podtopienia - doliny rzeczne"}}] if hit else []}


async def test_parcel_in_100_year_zone(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=re.escape(flood.MZP_WMS)).mock(return_value=httpx.Response(200, text=IN_ZONE))
        mock.get(url__regex=re.escape(flood.WORP_WMS)).mock(side_effect=httpx.ReadTimeout("slow"))
        mock.get(url__regex=re.escape(flood.PODTOPIENIA_URL)).mock(
            return_value=httpx.Response(200, json=_podtopienia(True))
        )
        res = await flood.fetch(parcel, DATE)
    assert res.status is SourceStatus.OK and res.data is not None
    assert res.data.zones == {"q10": False, "q1": True, "q02": True}
    assert res.data.historical is None and res.data.groundwater_flooding is True
    info = flood_info(res)
    assert info is not None and info.level == "medium"
    assert "stuletniej" in info.sentence_pl and "nie odpowiedziała" in info.sentence_pl
    assert info.wms_url == flood.MZP_WMS


async def test_outside_zones(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=re.escape(flood.MZP_WMS)).mock(
            return_value=httpx.Response(200, text="no features were found")
        )
        mock.get(url__regex=re.escape(flood.WORP_WMS)).mock(
            return_value=httpx.Response(200, text="no features were found")
        )
        mock.get(url__regex=re.escape(flood.PODTOPIENIA_URL)).mock(
            return_value=httpx.Response(200, json=_podtopienia(False))
        )
        res = await flood.fetch(parcel, DATE)
    info = flood_info(res)
    assert info is not None and info.level == "none" and info.status is SourceStatus.OK
    assert res.data is not None and res.data.historical is False


async def test_flood_service_down_is_missing_not_safe(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=r"https://(wody\.isok|cbdgmapa).*").mock(side_effect=httpx.ConnectError("down"))
        res = await flood.fetch(parcel, DATE)
    assert res.status is SourceStatus.MISSING
    info = flood_info(res)
    assert info is not None and info.level == "unknown" and all(z.hit is None for z in info.zones)


# --- groundwater ---------------------------------------------------------------------------------


def _stations(x: float, y: float) -> dict[str, Any]:
    return {
        "features": [
            {
                "attributes": {
                    "ID_PKT_MWP": 1,
                    "MIEJSCOWOSC": "Daleko",
                    "WSP_X_1992": x + 30_000,
                    "WSP_Y_1992": y,
                }
            },
            {
                "attributes": {
                    "ID_PKT_MWP": 2,
                    "MIEJSCOWOSC": "Blisko",
                    "WSP_X_1992": x + 5_000,
                    "WSP_Y_1992": y,
                }
            },
            {
                "attributes": {
                    "ID_PKT_MWP": 3,
                    "MIEJSCOWOSC": "Poza",
                    "WSP_X_1992": x + 90_000,
                    "WSP_Y_1992": y,
                }
            },
        ]
    }


def _means(depth_by_station_year: dict[tuple[int, int], float]):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        where = request.url.params["where"]
        sid = int(re.search(r"PSH_MONITORING_ID=(\d+)", where).group(1))  # type: ignore[union-attr]
        year = int(re.search(r"TIMESTAMP '(\d{4})", where).group(1))  # type: ignore[union-attr]
        m = depth_by_station_year.get((sid, year))
        attrs = {"m": m, "n": 500, "t0": 0, "t1": 58 * 86_400_000} if m is not None else {"m": None, "n": 0}
        return httpx.Response(200, json={"features": [{"attributes": attrs}]})

    return handler


async def test_nearest_station_with_history_and_falling_level(tmp_cache: DiskCache, parcel: Parcel) -> None:
    from app.sources.base import METRIC_CRS, parcel_shape, to_crs

    c = to_crs(parcel_shape(parcel), METRIC_CRS).centroid
    depths = {(2, 2025): 3.6, (2, 2022): 3.1, (1, 2025): 9.0, (1, 2022): 9.0}
    with respx.mock() as mock:
        mock.get(f"{groundwater.BASE}/0/query").mock(
            return_value=httpx.Response(200, json=_stations(c.x, c.y))
        )
        mock.get(f"{groundwater.BASE}/2/query").mock(side_effect=_means(depths))
        res = await groundwater.fetch(parcel, DATE)
    assert res.status is SourceStatus.OK and res.data is not None
    d = res.data
    assert d.station_name == "Blisko" and d.distance_km == pytest.approx(5.0, abs=0.1)
    assert d.trend == "falling" and d.change_m == pytest.approx(-0.5) and d.years_compared == 3
    info = groundwater_info(res)
    assert info is not None and "spada" in info.sentence_pl


async def test_station_without_history_gives_level_without_trend(
    tmp_cache: DiskCache, parcel: Parcel
) -> None:
    from app.sources.base import METRIC_CRS, parcel_shape, to_crs

    c = to_crs(parcel_shape(parcel), METRIC_CRS).centroid
    with respx.mock() as mock:
        mock.get(f"{groundwater.BASE}/0/query").mock(
            return_value=httpx.Response(200, json=_stations(c.x, c.y))
        )
        mock.get(f"{groundwater.BASE}/2/query").mock(side_effect=_means({(2, 2025): 2.0}))
        res = await groundwater.fetch(parcel, DATE)
    assert res.status is SourceStatus.DEGRADED and res.data is not None and res.data.trend is None
    info = groundwater_info(res)
    assert info is not None and "nie oceniamy" in info.sentence_pl


async def test_no_station_data_is_missing(tmp_cache: DiskCache, parcel: Parcel) -> None:
    with respx.mock() as mock:
        mock.get(f"{groundwater.BASE}/0/query").mock(return_value=httpx.Response(200, json={"features": []}))
        res = await groundwater.fetch(parcel, DATE)
    assert res.status is SourceStatus.MISSING and res.message_pl


def test_classify() -> None:
    assert groundwater.classify(0.05) == "stable"
    assert groundwater.classify(0.4) == "rising"
    assert groundwater.classify(-0.4) == "falling"


def test_edge_points_reach_near_the_boundary(parcel: Parcel) -> None:
    from app.sources.base import METRIC_CRS, parcel_shape, to_crs

    geom = to_crs(parcel_shape(parcel), METRIC_CRS)
    edge = [p for p in flood.sample_points(geom)[1:]]
    assert edge and all(geom.exterior.distance(p) < flood.EDGE_INSET_M + 0.5 for p in edge)


async def test_partial_answer_without_zone_is_not_reported_safe(tmp_cache: DiskCache, parcel: Parcel) -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] % 2:
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, text="no features were found")

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=re.escape(flood.MZP_WMS)).mock(side_effect=flaky)
        mock.get(url__regex=re.escape(flood.WORP_WMS)).mock(side_effect=httpx.ReadTimeout("slow"))
        mock.get(url__regex=re.escape(flood.PODTOPIENIA_URL)).mock(
            return_value=httpx.Response(200, json=_podtopienia(False))
        )
        res = await flood.fetch(parcel, DATE)
    assert res.status is SourceStatus.DEGRADED
    info = flood_info(res)
    assert info is not None and info.level == "unknown" and "nie wykluczamy" in info.sentence_pl


async def test_window_with_one_week_of_data_is_rejected(tmp_cache: DiskCache) -> None:
    with respx.mock() as mock:
        mock.get(f"{groundwater.BASE}/2/query").mock(
            return_value=httpx.Response(
                200, json={"features": [{"attributes": {"m": 16.7, "n": 164, "t0": 0, "t1": 6 * 86_400_000}}]}
            )
        )
        assert await groundwater._window_mean(1, DATE) is None


def test_groundwater_flooding_area_is_not_shown_as_safe() -> None:
    from app.core.models import Confidence, SourceStatus
    from app.sources.base import result, unc

    data = flood.FloodData(
        zones={"q10": False, "q1": False, "q02": False},
        points_checked=3,
        points_total=3,
        historical=False,
        groundwater_flooding=True,
    )
    res = result(
        flood.NAME, SourceStatus.OK, data, source="s", license="l", uncertainty=unc(Confidence.HIGH, "x")
    )
    info = flood_info(res)
    assert info is not None and info.level == "low" and info.label_pl == "Możliwe podtopienia"
    assert "podtopieniami" in info.sentence_pl
