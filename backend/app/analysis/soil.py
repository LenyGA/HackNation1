"""Soil water retention from texture and organic carbon. Pure, no I/O.

- Field capacity (−33 kPa) and wilting point (−1500 kPa): pedotransfer functions of
  Saxton K.E., Rawls W.J. (2006) "Soil water characteristic estimates by texture and organic matter for
  hydrologic solutions",
  Soil Sci. Soc. Am. J. 70:1569–1578, eqs. 1–2 (valid for OM ≤ 8 %, clay ≤ 60 %).
- Organic matter = 1.724 · organic carbon (van Bemmelen factor).
- TAW = 1000 · (θFC − θWP) · Zr  [mm]  (FAO-56 eq. 82), integrated over the SoilGrids layers down to Zr.
- Soil category I–IV: IUNG-PIB drought monitoring groups soils by agronomic texture (I very light: sands;
  II light: loamy sands; III medium: sandy loams, loams, silts; IV heavy: clay loams and clays).
  SoilGrids gives USDA fractions, so the USDA texture class (USDA Soil Survey Manual triangle) of the topsoil
  is mapped to these groups. This approximates the Polish PTG classification and the report says so.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.sources.soilgrids import SoilData, SoilLayer

OM_PER_SOC = 1.724
SR_MAX_OM_PCT = 8.0
SR_MAX_CLAY = 0.60
TOPSOIL_DEPTH_CM = 30
# The parcel layers must cover at least this share of the rooting depth, otherwise TAW is not reported.
MIN_DEPTH_COVERAGE = 0.6


class TextureClass(StrEnum):
    SAND = "sand"
    LOAMY_SAND = "loamy_sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    SILT = "silt"
    SANDY_CLAY_LOAM = "sandy_clay_loam"
    CLAY_LOAM = "clay_loam"
    SILTY_CLAY_LOAM = "silty_clay_loam"
    SANDY_CLAY = "sandy_clay"
    SILTY_CLAY = "silty_clay"
    CLAY = "clay"


class SoilCategory(StrEnum):
    I = "I"  # noqa: E741 — official IUNG category name
    II = "II"
    III = "III"
    IV = "IV"


CATEGORY_BY_TEXTURE: dict[TextureClass, SoilCategory] = {
    TextureClass.SAND: SoilCategory.I,
    TextureClass.LOAMY_SAND: SoilCategory.II,
    TextureClass.SANDY_LOAM: SoilCategory.III,
    TextureClass.LOAM: SoilCategory.III,
    TextureClass.SILT_LOAM: SoilCategory.III,
    TextureClass.SILT: SoilCategory.III,
    TextureClass.SANDY_CLAY_LOAM: SoilCategory.IV,
    TextureClass.CLAY_LOAM: SoilCategory.IV,
    TextureClass.SILTY_CLAY_LOAM: SoilCategory.IV,
    TextureClass.SANDY_CLAY: SoilCategory.IV,
    TextureClass.SILTY_CLAY: SoilCategory.IV,
    TextureClass.CLAY: SoilCategory.IV,
}


def usda_texture_class(sand_pct: float, silt_pct: float, clay_pct: float) -> TextureClass:
    """USDA texture triangle. Fractions are renormalised to 100 %."""
    total = sand_pct + silt_pct + clay_pct
    if total <= 0:
        raise ValueError("texture fractions must be positive")
    sand, silt, clay = (100 * v / total for v in (sand_pct, silt_pct, clay_pct))
    if silt + 1.5 * clay < 15:
        return TextureClass.SAND
    if silt + 2 * clay < 30:
        return TextureClass.LOAMY_SAND
    if clay >= 40:
        if silt >= 40:
            return TextureClass.SILTY_CLAY
        if sand > 45:
            return TextureClass.SANDY_CLAY
        return TextureClass.CLAY
    if clay >= 35 and sand > 45:
        return TextureClass.SANDY_CLAY
    if clay >= 27:
        if sand <= 20:
            return TextureClass.SILTY_CLAY_LOAM
        if sand <= 45:
            return TextureClass.CLAY_LOAM
        return TextureClass.SANDY_CLAY_LOAM
    if clay >= 20 and silt < 28 and sand > 45:
        return TextureClass.SANDY_CLAY_LOAM
    if silt >= 80 and clay < 12:
        return TextureClass.SILT
    if silt >= 50:
        return TextureClass.SILT_LOAM
    if clay >= 7 and sand <= 52 and silt >= 28:
        return TextureClass.LOAM
    return TextureClass.SANDY_LOAM


def soil_category(sand_pct: float, silt_pct: float, clay_pct: float) -> SoilCategory:
    return CATEGORY_BY_TEXTURE[usda_texture_class(sand_pct, silt_pct, clay_pct)]


def saxton_rawls(sand_pct: float, clay_pct: float, om_pct: float) -> tuple[float, float]:
    """(θFC, θWP) in m³/m³, Saxton & Rawls (2006) eqs. 1–2. Inputs outside the fitted range are clipped."""
    s = min(max(sand_pct, 0.0), 100.0) / 100
    c = min(max(clay_pct, 0.0), 100.0) / 100
    c = min(c, SR_MAX_CLAY)
    om = min(max(om_pct, 0.0), SR_MAX_OM_PCT)
    t1500 = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om + 0.068 * s * c + 0.031
    wp = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om + 0.452 * s * c + 0.299
    fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    wp = max(wp, 0.0)
    fc = max(fc, wp)
    return fc, wp


@dataclass(frozen=True)
class LayerRetention:
    depth_top_cm: int
    depth_bottom_cm: int
    field_capacity: float  # m³/m³
    wilting_point: float  # m³/m³

    @property
    def available(self) -> float:
        return self.field_capacity - self.wilting_point


@dataclass(frozen=True)
class SoilProperties:
    texture: TextureClass | None
    category: SoilCategory | None
    topsoil_sand_pct: float | None
    topsoil_silt_pct: float | None
    topsoil_clay_pct: float | None
    topsoil_soc_g_per_kg: float | None
    layers: list[LayerRetention]
    taw_mm: float | None  # for the crop rooting depth
    root_depth_m: float
    depth_covered_m: float  # part of the rooting depth with complete layer data

    @property
    def taw_per_m_mm(self) -> float | None:
        return None if self.taw_mm is None else self.taw_mm / self.root_depth_m


def _layer_retention(layer: SoilLayer) -> LayerRetention | None:
    if layer.sand_pct is None or layer.clay_pct is None or layer.soc_g_per_kg is None:
        return None
    om_pct = layer.soc_g_per_kg / 10 * OM_PER_SOC
    fc, wp = saxton_rawls(layer.sand_pct, layer.clay_pct, om_pct)
    return LayerRetention(layer.depth_top_cm, layer.depth_bottom_cm, fc, wp)


def _weighted_topsoil(layers: list[SoilLayer], attr: str) -> float | None:
    """Thickness-weighted mean of a layer property over 0–30 cm; None when any topsoil layer lacks it."""
    total = 0.0
    weight = 0.0
    for layer in layers:
        overlap = min(layer.depth_bottom_cm, TOPSOIL_DEPTH_CM) - max(layer.depth_top_cm, 0)
        if overlap <= 0:
            continue
        value = getattr(layer, attr)
        if value is None:
            return None
        total += value * overlap
        weight += overlap
    return total / weight if weight else None


def soil_properties(soil: SoilData, root_depth_m: float) -> SoilProperties:
    sand = _weighted_topsoil(soil.layers, "sand_pct")
    silt = _weighted_topsoil(soil.layers, "silt_pct")
    clay = _weighted_topsoil(soil.layers, "clay_pct")
    soc = _weighted_topsoil(soil.layers, "soc_g_per_kg")
    texture: TextureClass | None = None
    if sand is not None and silt is not None and clay is not None and sand + silt + clay > 0:
        texture = usda_texture_class(sand, silt, clay)

    retention: list[LayerRetention] = []
    taw = 0.0
    covered_cm = 0.0
    root_cm = root_depth_m * 100
    for layer in sorted(soil.layers, key=lambda la: la.depth_top_cm):
        r = _layer_retention(layer)
        if r is None:
            continue
        retention.append(r)
        overlap = min(r.depth_bottom_cm, root_cm) - max(r.depth_top_cm, 0)
        if overlap > 0:
            taw += 10 * r.available * overlap  # 1000 mm/m · θ · (cm / 100)
            covered_cm += overlap
    # SoilGrids ends at 100 cm (deeper layers are not modelled). Deeper roots reuse the deepest layer's
    # retention, which is the FAO-56 practice of a homogeneous profile below the last horizon.
    deepest = max(retention, key=lambda r: r.depth_bottom_cm, default=None)
    enough = covered_cm >= MIN_DEPTH_COVERAGE * root_cm
    if deepest is not None and root_cm > deepest.depth_bottom_cm and enough:
        extra = root_cm - max(deepest.depth_bottom_cm, covered_cm)
        if extra > 0:
            taw += 10 * deepest.available * extra
            covered_cm += extra
    taw_mm = round(taw, 1) if covered_cm >= MIN_DEPTH_COVERAGE * root_cm and taw > 0 else None
    if taw_mm is not None and covered_cm < root_cm:
        taw_mm = round(taw * root_cm / covered_cm, 1)
    return SoilProperties(
        texture=texture,
        category=CATEGORY_BY_TEXTURE[texture] if texture is not None else None,
        topsoil_sand_pct=sand,
        topsoil_silt_pct=silt,
        topsoil_clay_pct=clay,
        topsoil_soc_g_per_kg=soc,
        layers=retention,
        taw_mm=taw_mm,
        root_depth_m=root_depth_m,
        depth_covered_m=min(covered_cm, root_cm) / 100,
    )
