"""G10 / M5.2: irrigation technology from crop, area, shape and dry-year need."""

from app.analysis.parcel_shape import ParcelShape
from app.crops.catalog import load_crops
from app.recommendations.irrigation_tech import NO_INSTALLATION_NEED_MM, choose_technology

CROPS = load_crops()
STRIP = ParcelShape(length_m=950, width_m=80, compactness=1.0)
BIG = ParcelShape(length_m=600, width_m=500, compactness=0.95)
BIG_LONG = ParcelShape(length_m=1600, width_m=400, compactness=0.95)


def test_strip_gets_reel_with_long_note() -> None:
    c = choose_technology(CROPS["rye"], 7.6, STRIP, 120.0)
    assert c.tech == "reel" and c.efficiency == 0.75
    assert "long" in c.notes and "narrow" not in c.notes


def test_very_narrow_strip_note() -> None:
    c = choose_technology(CROPS["potato"], 1.5, ParcelShape(length_m=600, width_m=25, compactness=1.0), 120.0)
    assert c.tech == "reel" and "narrow" in c.notes


def test_large_wide_field_gets_pivot() -> None:
    c = choose_technology(CROPS["maize"], 30.0, BIG, 150.0)
    assert c.tech == "pivot" and c.reason == "large_compact"


def test_large_long_field_gets_linear_variant() -> None:
    c = choose_technology(CROPS["maize"], 64.0, BIG_LONG, 150.0)
    assert c.tech == "pivot" and c.reason == "large_long"


def test_large_but_narrow_field_is_not_pivot() -> None:
    c = choose_technology(
        CROPS["maize"], 30.0, ParcelShape(length_m=1500, width_m=200, compactness=1.0), 150.0
    )
    assert c.tech == "reel"


def test_small_area_is_not_pivot_even_if_wide() -> None:
    assert choose_technology(CROPS["maize"], 12.0, BIG, 150.0).tech == "reel"


def test_vegetables_get_drip() -> None:
    c = choose_technology(CROPS["field_vegetables"], 2.0, BIG, 150.0)
    assert c.tech == "drip" and c.efficiency == 0.9


def test_cereals_never_drip() -> None:
    assert choose_technology(CROPS["winter_wheat"], 2.0, BIG, 150.0).tech != "drip"


def test_low_need_means_no_installation() -> None:
    c = choose_technology(CROPS["potato"], 5.0, STRIP, NO_INSTALLATION_NEED_MM - 1)
    assert c.tech == "none" and c.reason == "low_need"


def test_need_at_threshold_keeps_installation() -> None:
    assert choose_technology(CROPS["potato"], 5.0, STRIP, NO_INSTALLATION_NEED_MM).tech == "reel"


def test_unknown_shape_and_plan_are_stated() -> None:
    c = choose_technology(CROPS["potato"], 5.0, None, None)
    assert c.tech == "reel" and {"no_shape", "no_plan"} <= set(c.notes)


def test_small_field_note() -> None:
    assert "small" in choose_technology(CROPS["potato"], 0.6, STRIP, 100.0).notes
    assert "small" not in choose_technology(CROPS["potato"], 3.0, STRIP, 100.0).notes
