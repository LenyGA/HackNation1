"""Farm mode (G11, plan33 M7): pure helpers — summed area, outline distance, the "na N działki" wording."""

import pytest
from shapely.geometry import box

from app.analysis.farm import distance_m, farm_area_ha
from app.core.models import Parcel
from app.recommendations.texts_pl import farm_where_pl
from app.sources.base import METRIC_CRS, parcel_shape, to_crs
from tests.analysis.builders import default_parcel
from tests.helpers import parcel_from_polygon


def near(
    main: Parcel, dx: float, dy: float, w: float, h: float, parcel_id: str = "141201_1.0001.2"
) -> Parcel:
    """Rectangle w × h m whose lower-left corner is (dx, dy) m from the main parcel's lower-left corner."""
    x0, y0, _, _ = to_crs(parcel_shape(main), METRIC_CRS).bounds
    rect = box(x0 + dx, y0 + dy, x0 + dx + w, y0 + dy + h)
    return parcel_from_polygon(to_crs(rect, 4326, src_crs=METRIC_CRS), parcel_id)


def test_farm_area_is_the_sum() -> None:
    main = default_parcel()  # 200 × 150 m = 3 ha
    a = near(main, 200, 0, 200, 100)  # 2 ha
    b = near(main, 0, 650, 100, 100, "141201_1.0001.3")  # 1 ha
    assert farm_area_ha(main, []) == main.area_ha
    assert farm_area_ha(main, [a, b]) == pytest.approx(main.area_ha + 2.0 + 1.0, abs=1e-3)


def test_touching_parcels_are_zero_apart() -> None:
    main = default_parcel()
    assert distance_m(main, near(main, 200, 0, 200, 100)) == pytest.approx(0.0, abs=1e-3)
    assert distance_m(main, main) == 0.0


def test_distance_between_outlines_not_centroids() -> None:
    main = default_parcel()  # top edge at y0 + 150
    other = near(main, 0, 650, 100, 100)
    d = distance_m(main, other)
    assert d is not None
    assert d == pytest.approx(500.0, abs=1.0)


@pytest.mark.parametrize(
    "geometry",
    [
        {},
        {"type": "Polygon"},
        {"type": "Polygon", "coordinates": "oops"},
        {"type": "Nonsense", "coordinates": []},
    ],
)
def test_malformed_geometry_gives_none(geometry: dict[str, object]) -> None:
    main = default_parcel()
    bad = main.model_copy(update={"geometry": geometry})
    assert distance_m(main, bad) is None
    assert distance_m(bad, main) is None


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "na działkę"),
        (1, "na działkę"),
        (2, "na 2 działki gospodarstwa"),
        (4, "na 4 działki gospodarstwa"),
        (5, "na 5 działek gospodarstwa"),
        (12, "na 12 działek gospodarstwa"),
        (14, "na 14 działek gospodarstwa"),
        (22, "na 22 działki gospodarstwa"),
        (25, "na 25 działek gospodarstwa"),
    ],
)
def test_farm_where_plural_forms(n: int, expected: str) -> None:
    assert farm_where_pl(n) == expected


def test_farm_where_custom_single() -> None:
    assert farm_where_pl(1, "na całą działkę") == "na całą działkę"
    assert farm_where_pl(3, "na całą działkę") == "na 3 działki gospodarstwa"
