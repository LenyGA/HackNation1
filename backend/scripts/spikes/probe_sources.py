"""M1 spike: probe external data sources, measure latency, print a short summary. Run: python scripts/spikes/probe_sources.py"""

import asyncio
import time
from typing import Any

import httpx

UA = {"User-Agent": "RolnikSzukaWody/0.1 (HackNation 2026 prototype)"}
LAT, LON = 52.2297, 21.0122  # central Poland sample point
POINTS = [(52.40, 16.92), (54.20, 19.10), (51.25, 22.57), (50.05, 21.99), (53.13, 18.00)]


async def timed(name: str, coro: Any) -> None:
    t0 = time.perf_counter()
    try:
        info = await coro
        print(f"[OK]   {name:<28} {time.perf_counter() - t0:6.2f}s  {info}")
    except Exception as exc:  # noqa: BLE001 - spike script
        print(f"[FAIL] {name:<28} {time.perf_counter() - t0:6.2f}s  {type(exc).__name__}: {str(exc)[:160]}")


async def uldk(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://uldk.gugik.gov.pl/",
        params={"request": "GetParcelById", "id": "141201_1.0001.6509", "result": "geom_wkt,teryt,voivodeship,commune", "srid": "4326"},
    )
    return r.text[:120].replace("\n", " | ")


async def uldk_xy(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://uldk.gugik.gov.pl/",
        params={"request": "GetParcelByXY", "xy": f"{LON},{LAT},4326", "result": "teryt", "srid": "4326"},
    )
    return r.text[:80].replace("\n", " | ")


async def open_meteo(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": LAT, "longitude": LON, "start_date": "2015-11-01", "end_date": "2025-11-01",
            "daily": "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min,temperature_2m_mean",
            "timezone": "Europe/Warsaw",
        },
    )
    r.raise_for_status()
    d = r.json()["daily"]
    return f"{len(d['time'])} days, last={d['time'][-1]}"


async def earth_search(c: httpx.AsyncClient) -> str:
    r = await c.post(
        "https://earth-search.aws.element84.com/v1/search",
        json={
            "collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [LON, LAT]},
            "datetime": "2016-01-01T00:00:00Z/2016-12-31T23:59:59Z", "limit": 5,
            "query": {"eo:cloud_cover": {"lt": 30}},
        },
    )
    r.raise_for_status()
    feats = r.json()["features"]
    assets = sorted(feats[0]["assets"]) if feats else []
    return f"2016 scenes={len(feats)} assets={[a for a in assets if a in ('red','nir','swir16','scl')]}"


async def soilgrids(c: httpx.AsyncClient, lat: float, lon: float) -> str:
    r = await c.get(
        "https://rest.isric.org/soilgrids/v2.0/properties/query",
        params={"lon": lon, "lat": lat, "property": ["sand", "clay", "soc"], "depth": ["0-5cm", "30-60cm"], "value": "mean"},
        timeout=15,
    )
    r.raise_for_status()
    layers = r.json()["properties"]["layers"]
    return ", ".join(f"{l['name']}={l['depths'][0]['values']['mean']}" for l in layers)


async def overpass(c: httpx.AsyncClient, url: str) -> str:
    q = f"""[out:json][timeout:20];
(way["waterway"~"ditch|drain|stream|river|canal"](around:1000,{LAT},{LON});
 way["natural"~"water|wetland|wood"](around:1000,{LAT},{LON});
 way["landuse"="forest"](around:1000,{LAT},{LON}););out tags center;"""
    r = await c.post(url, data={"data": q}, timeout=25)
    r.raise_for_status()
    return f"elements={len(r.json()['elements'])}"


async def nmt_wcs(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF",
        params={"SERVICE": "WCS", "REQUEST": "GetCapabilities", "VERSION": "2.0.1"},
        timeout=15,
    )
    r.raise_for_status()
    import re
    ids = re.findall(r"<wcs:CoverageId>([^<]+)</wcs:CoverageId>", r.text)
    return f"coverages={ids[:5]}"


async def main() -> None:
    async with httpx.AsyncClient(headers=UA, timeout=20, follow_redirects=True) as c:
        await asyncio.gather(
            timed("ULDK GetParcelById", uldk(c)),
            timed("ULDK GetParcelByXY", uldk_xy(c)),
            timed("Open-Meteo archive 10y", open_meteo(c)),
            timed("Earth Search STAC 2016", earth_search(c)),
            timed("Overpass main", overpass(c, "https://overpass-api.de/api/interpreter")),
            timed("Overpass mirror (kumi)", overpass(c, "https://overpass.kumi.systems/api/interpreter")),
            timed("NMT WCS GetCapabilities", nmt_wcs(c)),
            *[timed(f"SoilGrids {lat},{lon}", soilgrids(c, lat, lon)) for lat, lon in POINTS],
        )


if __name__ == "__main__":
    asyncio.run(main())
