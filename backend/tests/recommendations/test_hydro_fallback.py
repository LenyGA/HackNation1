"""Q4: when OSM (Overpass) is missing, trees, ponds and wetlands come from the WorldCover ring; only
ditches are unknown. When both are missing, behaviour is unchanged."""

import dataclasses

import numpy as np
from affine import Affine
from shapely.geometry import box

from app.analysis.assessment import assess
from app.recommendations.engine import recommend
from app.recommendations.irrigation import irrigation_advice
from app.report.builder import ParcelSource, build_report
from app.sources.base import METRIC_CRS, to_crs
from app.sources.landcover import LandCoverData, Surroundings, surroundings_from
from tests.analysis.builders import make_inputs, ok
from tests.recommendations.builders import SUMMER, dry, ids
from tests.report.builders import CREATED


def _landcover(nearest: dict[str, float | None], trees_pct: float = 0.0) -> LandCoverData:
    return LandCoverData(
        map_year=2021,
        pixels=500,
        shares_pct={"cropland": 100.0},
        cropland_pct=100.0,
        grassland_pct=0.0,
        trees_pct=0.0,
        built_up_pct=0.0,
        looks_agricultural=True,
        surroundings=Surroundings(
            radius_m=500,
            pixels=9000,
            shares_pct={"trees": trees_pct, "water": 0.0, "wetland": 0.0, "built_up": 0.0},
            nearest_m={"trees": None, "water": None, "wetland": None, "built_up": None, **nearest},
        ),
    )


def _run(landcover: LandCoverData | None, hydro: bool = False):
    inputs = make_inputs(SUMMER, "maize", precip=dry, hydro=hydro)
    if landcover is not None:
        inputs = dataclasses.replace(inputs, landcover=ok("landcover", landcover))
    a = assess(inputs)
    recs = recommend(a, inputs)
    report = build_report(
        report_id="t",
        created_at=CREATED,
        inputs=inputs,
        assessment=a,
        recommendations=recs,
        irrigation=irrigation_advice(a, inputs, today=inputs.analysis_date),
        parcel_source=ParcelSource(fetched_at=CREATED),
    )
    return a, recs, report


def test_osm_missing_worldcover_ok_trees_and_wetlands_rules_work() -> None:
    _, recs, report = _run(_landcover({"wetland": 120.0}))
    assert "midfield_trees" in ids(recs)  # light soil, no trees within 500 m in WorldCover
    assert "protect_wetlands" in ids(recs)  # wetland 120 m away
    rec = next(r for r in recs if r.id == "protect_wetlands")
    assert any("WorldCover" in e.uncertainty.reason_pl for e in rec.evidence)
    missing = " ".join(report.missing_data_pl)
    assert "Brakuje danych tylko o rowach" in missing
    assert "ditch_check_dam" not in ids(recs)


def test_osm_missing_worldcover_with_trees_nearby_no_tree_rule() -> None:
    _, recs, _ = _run(_landcover({"trees": 80.0}, trees_pct=12.0))
    assert "midfield_trees" not in ids(recs)
    assert "protect_wetlands" not in ids(recs)


def test_osm_and_worldcover_missing_unchanged() -> None:
    a, recs, report = _run(None)
    assert "midfield_trees" not in ids(recs) and "protect_wetlands" not in ids(recs)
    comp = next(c for c in a.vulnerability.components if c.id == "retention_elements")
    assert comp.points is None
    assert "Bez mapy rowów, cieków, oczek i zadrzewień" in " ".join(report.missing_data_pl)


def test_osm_present_ignores_worldcover() -> None:
    """Never mixed: with OSM available the WorldCover ring is not used."""
    _, with_osm, _ = _run(_landcover({"wetland": 50.0}), hydro=True)
    _, osm_only, _ = _run(None, hydro=True)
    assert ids(with_osm) == ids(osm_only)


def test_surroundings_from_counts_ring_and_nearest_distance() -> None:
    # 10 m pixels in EPSG:2180 would need reprojection; build a small WGS84 grid like WorldCover tiles.
    parcel = box(19.0, 52.0, 19.001, 52.001)
    parcel_m = to_crs(parcel, METRIC_CRS)
    ring = to_crs(parcel_m.buffer(200).difference(parcel_m), 4326, src_crs=METRIC_CRS)
    step = 0.0001
    minx, miny, maxx, maxy = ring.bounds
    w, h = int((maxx - minx) / step) + 1, int((maxy - miny) / step) + 1
    arr = np.full((h, w), 40, dtype=np.uint8)  # cropland
    transform = Affine(step, 0, minx, 0, -step, maxy)
    col = int((19.0015 - minx) / step)  # a tree column ~100 m east of the parcel
    arr[:, col] = 10
    counts, nearest = surroundings_from(arr, transform, ring, parcel_m)
    assert counts.get(10, 0) > 0 and counts.get(40, 0) > counts[10]
    assert nearest["trees"] is not None and 20 <= nearest["trees"] <= 60
    assert nearest["water"] is None
