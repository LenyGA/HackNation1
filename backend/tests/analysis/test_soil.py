import pytest

from app.analysis.soil import (
    SoilCategory,
    TextureClass,
    saxton_rawls,
    soil_category,
    soil_properties,
    usda_texture_class,
)
from app.sources.soilgrids import SoilLayer
from tests.analysis.builders import soil_data, soil_layers


def test_loose_sand_is_category_i_with_low_taw() -> None:
    props = soil_properties(soil_data(soil_layers(95, 3, 2, 3)), root_depth_m=1.0)
    assert props.texture is TextureClass.SAND
    assert props.category is SoilCategory.I
    assert props.taw_mm is not None and props.taw_mm < 60
    assert props.depth_covered_m == pytest.approx(1.0)


def test_heavy_clay_is_category_iv() -> None:
    props = soil_properties(soil_data(soil_layers(10, 25, 65, 15)), root_depth_m=1.0)
    assert props.texture is TextureClass.CLAY
    assert props.category is SoilCategory.IV
    sand = soil_properties(soil_data(soil_layers(95, 3, 2, 3)), root_depth_m=1.0)
    assert props.taw_mm is not None and sand.taw_mm is not None
    assert props.taw_mm > sand.taw_mm


@pytest.mark.parametrize(
    ("sand", "clay", "wp", "fc"),
    # Saxton & Rawls (2006) Table 3, OM = 2.5 %: wilting point and field capacity (% vol)
    [(88, 5, 0.05, 0.10), (40, 20, 0.14, 0.28), (25, 50, 0.30, 0.42), (20, 15, 0.11, 0.31)],
)
def test_saxton_rawls_matches_published_table(sand: float, clay: float, wp: float, fc: float) -> None:
    got_fc, got_wp = saxton_rawls(sand, clay, 2.5)
    assert got_wp == pytest.approx(wp, abs=0.01)
    assert got_fc == pytest.approx(fc, abs=0.01)


@pytest.mark.parametrize("sand", [5, 20, 40, 60, 80, 95])
@pytest.mark.parametrize("clay", [2, 10, 25, 45, 70])
@pytest.mark.parametrize("om", [0.0, 2.0, 12.0])
def test_saxton_rawls_sanity(sand: float, clay: float, om: float) -> None:
    if sand + clay > 100:
        return
    fc, wp = saxton_rawls(sand, clay, om)
    assert 0.0 <= wp < fc < 0.6
    assert 0.0 < fc - wp < 0.35


@pytest.mark.parametrize(
    ("sand", "silt", "clay", "expected"),
    [
        (92, 5, 3, TextureClass.SAND),
        (82, 12, 6, TextureClass.LOAMY_SAND),
        (65, 25, 10, TextureClass.SANDY_LOAM),
        (40, 40, 20, TextureClass.LOAM),
        (20, 65, 15, TextureClass.SILT_LOAM),
        (5, 88, 7, TextureClass.SILT),
        (60, 12, 28, TextureClass.SANDY_CLAY_LOAM),
        (33, 34, 33, TextureClass.CLAY_LOAM),
        (10, 56, 34, TextureClass.SILTY_CLAY_LOAM),
        (52, 6, 42, TextureClass.SANDY_CLAY),
        (6, 47, 47, TextureClass.SILTY_CLAY),
        (20, 20, 60, TextureClass.CLAY),
    ],
)
def test_usda_texture_triangle(sand: float, silt: float, clay: float, expected: TextureClass) -> None:
    assert usda_texture_class(sand, silt, clay) is expected


def test_category_from_fractions_and_renormalisation() -> None:
    assert soil_category(46, 1.5, 1) is SoilCategory.I  # sums to 48.5, renormalised
    assert soil_category(40, 40, 20) is SoilCategory.III
    with pytest.raises(ValueError):
        usda_texture_class(0, 0, 0)


def test_missing_layer_values_give_no_taw_and_no_crash() -> None:
    props = soil_properties(soil_data(soil_layers(None, None, None, None)), root_depth_m=1.0)
    assert props.taw_mm is None
    assert props.texture is None and props.category is None
    assert props.layers == []
    assert props.taw_per_m_mm is None


def test_only_topsoil_known_is_not_enough_for_taw() -> None:
    layers = soil_layers(60, 30, 10, 10)
    layers = [
        la if la.depth_bottom_cm <= 30 else la.model_copy(update={"sand_pct": None, "clay_pct": None})
        for la in layers
    ]
    props = soil_properties(soil_data(layers), root_depth_m=1.0)
    assert props.category is SoilCategory.III  # topsoil texture still known
    assert props.taw_mm is None  # 30 cm of 100 cm covered (< 60 %)


def test_missing_silt_keeps_taw_but_no_category() -> None:
    layers = [la.model_copy(update={"silt_pct": None}) for la in soil_layers(60, 30, 10, 10)]
    props = soil_properties(soil_data(layers), root_depth_m=1.0)
    assert props.category is None
    assert props.taw_mm is not None


def test_deep_roots_extend_deepest_layer() -> None:
    layers = soil_layers(40, 40, 20, 10)
    shallow = soil_properties(soil_data(layers), root_depth_m=1.0)
    deep = soil_properties(soil_data(layers), root_depth_m=1.5)
    assert shallow.taw_mm is not None and deep.taw_mm is not None
    assert deep.taw_mm == pytest.approx(1.5 * shallow.taw_mm, abs=0.2)
    assert shallow.taw_per_m_mm == pytest.approx(deep.taw_per_m_mm, abs=0.2)


def test_empty_layer_list() -> None:
    props = soil_properties(soil_data([]), root_depth_m=1.0)
    assert props.taw_mm is None and props.category is None


def test_single_layer_hand_value() -> None:
    fc, wp = saxton_rawls(40, 20, 10 / 10 * 1.724)
    layer = SoilLayer(
        depth_top_cm=0,
        depth_bottom_cm=100,
        sand_pct=40,
        silt_pct=40,
        clay_pct=20,
        soc_g_per_kg=10,
        bulk_density_g_per_cm3=1.4,
    )
    props = soil_properties(soil_data([layer]), root_depth_m=0.4)
    assert props.taw_mm == pytest.approx(1000 * (fc - wp) * 0.4, abs=0.1)


@pytest.mark.parametrize(
    ("sand", "silt", "clay", "expected"),
    [
        (95, 3, 2, SoilCategory.I),  # piasek luźny
        (80, 12, 8, SoilCategory.II),  # piasek gliniasty
        (55, 30, 15, SoilCategory.III),  # glina lekka
        (30, 30, 40, SoilCategory.IV),  # glina ciężka / ił
    ],
)
def test_iung_reference_soils(sand: float, silt: float, clay: float, expected: SoilCategory) -> None:
    assert soil_category(sand, silt, clay) is expected
