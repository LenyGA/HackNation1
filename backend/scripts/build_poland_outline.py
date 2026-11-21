"""Build the simplified outline of Poland used by the map to reject clicks abroad (plan2 L1.4).

One-off script, run by hand; the result is committed as `frontend/src/components/map/poland.json` and noted in
`docs/DATA_SOURCES.md` ("pobrane wcześniej", with the download date).

Source: PRG (Państwowy Rejestr Granic) GUGiK, WFS layers `A00_Granice_panstwa` (state border, EPSG:2180; it
includes the sea) minus `W02_Morze_terytorialne_RP` and `W03_Morskie_wody_wewnetrzne`, so the outline is land.
Steps: land → opening ±25 m (drops slivers left by the sea layers) → buffer 200 m outwards → simplify with a
tolerance below the buffer → WGS84 → round to 4 decimals. Douglas–Peucker moves the boundary by at most the
tolerance and rounding by ≤ ~8 m, so land stays inside the outline. Checked on 21.11.2026: outside are only
0,27 km² of strips narrower than 50 m (breakwaters at Świnoujście and Gdańsk); the outline reaches at most
~210 m past the land — a click there goes to ULDK, which decides.

    python scripts/build_poland_outline.py                                    # download from the WFS
    python scripts/build_poland_outline.py --gml panstwo.gml --sea morze.gml wody.gml  # saved WFS responses
"""

import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import transform
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union

WFS_URL = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
    "?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ms:{layer}&SRSNAME=EPSG:2180"
)
STATE_LAYER = "A00_Granice_panstwa"
SEA_LAYERS = ("W02_Morze_terytorialne_RP", "W03_Morskie_wody_wewnetrzne")
GML = "{http://www.opengis.net/gml/3.2}"
BUFFER_M = 200.0
TOLERANCE_M = 150.0  # < BUFFER_M, see the module docstring
SLIVER_M = 25.0
DECIMALS = 4
OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "map" / "poland.json"


def _ring(pos_list: str) -> list[tuple[float, float]]:
    vals = [float(v) for v in pos_list.split()]
    # urn:ogc:def:crs:EPSG::2180 has the axis order (northing, easting): swap to (x = easting, y = northing).
    return [(vals[i + 1], vals[i]) for i in range(0, len(vals), 2)]


def _polygons(gml: bytes) -> list[Polygon]:
    root = ET.fromstring(gml)
    out: list[Polygon] = []
    for poly in root.iter(f"{GML}Polygon"):
        ext = poly.find(f"{GML}exterior/{GML}LinearRing/{GML}posList")
        if ext is None or not ext.text:
            continue
        holes = [_ring(h.text) for h in poly.findall(f"{GML}interior/{GML}LinearRing/{GML}posList") if h.text]
        out.append(Polygon(_ring(ext.text), holes))
    if not out:
        raise SystemExit("no polygon in the WFS response")
    return out


def build(gml: bytes, sea_gmls: list[bytes]) -> dict[str, object]:
    sea = unary_union([p for g in sea_gmls for p in _polygons(g)])
    # The sea layers do not match the state border exactly and leave thin strips along the 12-mile line:
    # an opening (erode, then grow back) removes everything narrower than 2 × SLIVER_M.
    shape = unary_union(_polygons(gml)).difference(sea).buffer(-SLIVER_M).buffer(SLIVER_M)
    # Holes of the land (lakes, lagoons) are dropped before buffering; the buffer may still enclose water
    # between the mainland and islands — those holes stay (the map masks them too).
    parts = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    shape = unary_union([Polygon(p.exterior) for p in parts])
    shape = shape.buffer(BUFFER_M).simplify(TOLERANCE_M, preserve_topology=True)
    to_wgs = Transformer.from_crs(2180, 4326, always_xy=True)
    shape = transform(shape, lambda xy: np.column_stack(to_wgs.transform(xy[:, 0], xy[:, 1])))
    minx, miny, maxx, maxy = shape.bounds
    # Guard against a changed axis order of the WFS response (the swap in `_ring`): the result must be Poland.
    if not (13.5 < minx < 14.5 and 23.5 < maxx < 24.5 and 48.5 < miny < 49.5 and 54.5 < maxy < 55.2):
        raise SystemExit(f"outline bounds {shape.bounds} are not Poland — check the WFS axis order")
    geom = mapping(shape)

    def rnd(c: object) -> object:
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], float):
            return [round(float(v), DECIMALS) for v in c]
        return [rnd(x) for x in c] if isinstance(c, (list, tuple)) else c

    return {
        "type": "Feature",
        "properties": {
            "source": f"PRG GUGiK, WFS AdministrativeBoundaries: {STATE_LAYER} minus {', '.join(SEA_LAYERS)}",
            "license": "dane otwarte PZGiK (art. 40a ustawy Prawo geodezyjne i kartograficzne), bez opłat",
            "downloaded": datetime.now(UTC).date().isoformat(),
            "buffer_m": BUFFER_M,
            "tolerance_m": TOLERANCE_M,
        },
        "geometry": {"type": geom["type"], "coordinates": rnd(geom["coordinates"])},
    }


def _load(path: Path | None, layer: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    with urllib.request.urlopen(WFS_URL.format(layer=layer), timeout=120) as resp:  # noqa: S310 — fixed https URL
        data: bytes = resp.read()
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gml", type=Path, help=f"saved WFS GetFeature response for {STATE_LAYER} (GML 3.2)")
    ap.add_argument("--sea", type=Path, nargs=len(SEA_LAYERS), help=f"saved: {', '.join(SEA_LAYERS)}")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    seas = args.sea or [None] * len(SEA_LAYERS)
    sea = [_load(f, layer) for f, layer in zip(seas, SEA_LAYERS, strict=True)]
    feature = build(_load(args.gml, STATE_LAYER), sea)
    text = json.dumps(feature, separators=(",", ":"), ensure_ascii=False)
    args.out.write_text(text + "\n", encoding="utf-8")
    geom = feature["geometry"]
    assert isinstance(geom, dict)
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    n = sum(len(r) for p in polys for r in p)
    print(f"{args.out}: {len(text) / 1024:.0f} KB, {n} vertices")


if __name__ == "__main__":
    main()
