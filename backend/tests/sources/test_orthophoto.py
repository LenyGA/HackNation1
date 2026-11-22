"""Q7: orthophoto background for the PDF map (Geoportal WMS GetMap), with a plain fallback."""

import asyncio
import base64

import httpx
import pytest
import respx

from app.core.cache import DiskCache
from app.report import pdf as pdf_module
from app.report.map_svg import map_frame, parcel_map_svg
from app.report.pdf import render_html
from tests.report.builders import rich_report

JPEG = b"\xff\xd8\xff" + b"0" * 2000
BOUNDS = (637000.0, 486000.0, 637600.0, 486400.0)


def _real_fetch():
    import importlib

    from app.sources import orthophoto

    return importlib.reload(orthophoto)


def test_getmap_keeps_frame_aspect_and_uses_epsg2180() -> None:
    o = _real_fetch()
    p = o.getmap_params(BOUNDS)
    assert p["SRS"] == "EPSG:2180" and p["VERSION"] == "1.1.1"
    assert p["BBOX"] == "637000.0,486000.0,637600.0,486400.0"
    assert (int(p["WIDTH"]), int(p["HEIGHT"])) == (900, 600)


def test_fetch_returns_data_uri_and_caches(tmp_cache: DiskCache) -> None:
    o = _real_fetch()
    with respx.mock() as mock:
        route = mock.get(o.WMS_URL).mock(
            return_value=httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        )
        uri = asyncio.run(o.fetch_data_uri(BOUNDS))
        again = asyncio.run(o.fetch_data_uri(BOUNDS))
    assert uri is not None and uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == JPEG
    assert again == uri and route.call_count == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, text="<ServiceException/>", headers={"content-type": "text/xml"}),
    ],
)
def test_fetch_failure_gives_none(tmp_cache: DiskCache, response: httpx.Response) -> None:
    o = _real_fetch()
    with respx.mock() as mock:
        mock.get(o.WMS_URL).mock(return_value=response)
        assert asyncio.run(o.fetch_data_uri(BOUNDS)) is None


def test_timeout_gives_none(tmp_cache: DiskCache) -> None:
    o = _real_fetch()
    with respx.mock() as mock:
        mock.get(o.WMS_URL).mock(side_effect=httpx.ReadTimeout("t"))
        assert asyncio.run(o.fetch_data_uri(BOUNDS)) is None


def test_map_with_and_without_background() -> None:
    r = rich_report()
    uri = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
    with_bg = parcel_map_svg(r, uri)
    assert "<image " in with_bg and uri in with_bg
    assert "<image " not in parcel_map_svg(r)
    assert "Bez podkładu ortofotomapy" in render_html(r)
    assert "ortofotomapa © GUGiK" in render_html(r, uri)


def test_pdf_embeds_background_without_external_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """The data URI passes WeasyPrint's fetcher; any http(s) URL is still blocked."""
    from app.sources import orthophoto

    seen: list[tuple[float, float, float, float]] = []

    async def fake(bounds: tuple[float, float, float, float]) -> str:
        seen.append(bounds)
        return "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()

    monkeypatch.setattr(orthophoto, "fetch_data_uri", fake)
    r = rich_report()
    pdf = asyncio.run(pdf_module.render_pdf(r))
    assert pdf.startswith(b"%PDF") and seen == [map_frame(r)]
    with pytest.raises(ValueError):
        pdf_module._no_fetch("https://example.org/x.png")
