"""Which irrigation technology fits this parcel (G10, plan33 M5.2). Pure, no I/O.

Inputs are computed for the parcel: area and shape (ULDK geometry, `analysis/parcel_shape.py`), the crop and
the dry-year irrigation need (seasonal water plan, 80th percentile of 10 seasons).

Choice (first matching row):
1. dry-year need below NO_INSTALLATION_NEED_MM → no fixed installation (one or two doses a year at most);
2. field vegetables, orchards and fruit bushes → drip / micro-sprinklers (row crops; least water lost, FAO
   Training Manual 4; drip is the usual orchard system in Poland, plan2 L2.4);
3. at least PIVOT_MIN_AREA_HA and at least PIVOT_MIN_WIDTH_M wide → centre pivot (long fields: linear move);
4. otherwise → hose-reel travelling sprinkler (the common machine on Polish farms, any shape it can be pulled
   along).
The area and width thresholds are ASSUMPTIONS of the team (no open source found within the plan's time limit);
the report says so. The field application efficiency of the chosen method (sprinkler 75 %, drip 90 %, Brouwer
et al. 1989) replaces the fixed 75 % in the gross water of the seasonal plan.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.analysis.parcel_shape import ParcelShape
from app.crops.catalog import Crop
from app.crops.economics import load_economics

TechChoiceId = Literal["reel", "pivot", "drip", "none"]
TechReason = Literal["low_need", "row_crop", "fruit_rows", "large_compact", "large_long", "reel"]
TechNote = Literal["narrow", "long", "irregular", "small", "multipart", "no_shape", "no_plan"]

# ASSUMPTIONS (stated in the report): below one sprinkler dose on loam (25 mm, irrigation.MAX_SINGLE_DOSE_MM)
# in a dry year a fixed installation has nothing to do.
NO_INSTALLATION_NEED_MM = 25.0
PIVOT_MIN_AREA_HA = 20.0
PIVOT_MIN_WIDTH_M = 300.0  # the arm sweeps a circle: the field must be at least about its diameter wide
LINEAR_MIN_ELONGATION = 3.0
REEL_WETTED_WIDTH_M = 60.0  # one pass of a hose-reel gun wets a strip about this wide
REEL_HOSE_M = 400.0  # one setting irrigates about this length; longer fields need more settings
IRREGULAR_COMPACTNESS = 0.7
SMALL_AREA_HA = 1.0
DRIP_CROPS = frozenset({"field_vegetables"})
SPRINKLER_EFFICIENCY = 0.75  # Brouwer et al. 1989, also the default of the seasonal water plan


@dataclass(frozen=True)
class TechChoice:
    tech: TechChoiceId
    reason: TechReason
    efficiency: float
    notes: list[TechNote] = field(default_factory=list)
    shape: ParcelShape | None = None
    area_ha: float = 0.0
    need_mm: float | None = None


def efficiency_of(tech: TechChoiceId) -> float:
    if tech == "none":
        return SPRINKLER_EFFICIENCY
    return load_economics().technologies[tech].efficiency


def choose_technology(
    crop: Crop, area_ha: float, shape: ParcelShape | None, dry_year_need_mm: float | None
) -> TechChoice:
    notes: list[TechNote] = []
    if shape is None:
        notes.append("no_shape")
    elif shape.parts > 1:
        notes.append("multipart")
    if dry_year_need_mm is None:
        notes.append("no_plan")

    def choice(tech: TechChoiceId, reason: TechReason) -> TechChoice:
        return TechChoice(tech, reason, efficiency_of(tech), notes, shape, area_ha, dry_year_need_mm)

    if dry_year_need_mm is not None and dry_year_need_mm < NO_INSTALLATION_NEED_MM:
        return choice("none", "low_need")
    if crop.id in DRIP_CROPS or crop.is_fruit:
        if area_ha < SMALL_AREA_HA:
            notes.append("small")
        return choice("drip", "fruit_rows" if crop.is_fruit else "row_crop")
    if shape is not None and area_ha >= PIVOT_MIN_AREA_HA and shape.width_m >= PIVOT_MIN_WIDTH_M:
        reason: TechReason = "large_long" if shape.elongation >= LINEAR_MIN_ELONGATION else "large_compact"
        if shape.compactness < IRREGULAR_COMPACTNESS:
            notes.append("irregular")
        return choice("pivot", reason)
    if shape is not None:
        if shape.width_m < REEL_WETTED_WIDTH_M / 2:
            notes.append("narrow")
        if shape.length_m > 2 * REEL_HOSE_M:
            notes.append("long")
        if shape.compactness < IRREGULAR_COMPACTNESS:
            notes.append("irregular")
    if area_ha < SMALL_AREA_HA:
        notes.append("small")
    return choice("reel", "reel")
