"""How much of the dry-year irrigation need the main depression could hold (G9, plan M4.2). Pure.

The depression volume comes from the terrain analysis (water held when the hollow is filled to its spill
level, `analysis/terrain.py`); the needs are the water to pump with a sprinkler in a dry year (about one year
in 5, the 80th percentile of 10 seasons), for full irrigation and for rescue irrigation in the critical
periods only — the same rounded values the seasonal water plan shows (`report/outlook.py`, Q2). Stored water
is pumped through the same sprinkler, so both sides are gross volumes. Losses from an open pond (evaporation,
seepage) are not deducted: the share is an upper estimate and the report says so.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.analysis.terrain import RetentionSite, TerrainResult, main_depressions

# Below this need there is nothing to cover (the water plan shows "no irrigation needed").
MIN_NEED_M3 = 1.0


class CoverageStatus(StrEnum):
    OK = "ok"
    NO_TERRAIN = "no_terrain"  # elevation model missing: depressions were not searched
    NO_DEPRESSION = "no_depression"  # terrain known, no main depression on the parcel
    NO_PLAN = "no_plan"  # dry-year need could not be computed (weather missing or too few years)
    NO_NEED = "no_need"  # even in a dry year rain and soil covered the crop's needs


@dataclass(frozen=True)
class RetentionCoverage:
    status: CoverageStatus
    volume_m3: float | None  # main depression, rounded like the recommendation text
    area_m2: float | None  # water surface of the filled depression (unrounded; templates round it)
    max_depth_m: float | None
    inside_share: float | None  # share of the depression inside the parcel
    full_need_m3: float | None  # gross, dry year, full irrigation
    rescue_need_m3: float | None  # gross, dry year, critical periods only
    full_pct: float | None  # volume / full need, %
    rescue_pct: float | None


def depression_volume_m3(site: RetentionSite) -> float | None:
    """Volume as the report states it: never a fake 0 m³, 1 m³ steps below 50 m³, 10 m³ above."""
    v = site.volume_m3
    if v is None or v < 1:
        return None
    return float(round(v, -1 if v >= 50 else 0))


def share_pct(volume_m3: float | None, need_m3: float | None) -> float | None:
    if volume_m3 is None or need_m3 is None or need_m3 < MIN_NEED_M3:
        return None
    pct = 100 * volume_m3 / need_m3
    # Below 1 % keep one decimal so the card says "less than 1 %", never a fake "0 %" (rule 4).
    return float(round(pct)) if pct >= 1 else max(0.1, round(pct, 1))


def retention_coverage(
    terrain: TerrainResult | None, full_need_m3: float | None, rescue_need_m3: float | None
) -> RetentionCoverage:
    sites = main_depressions(terrain) if terrain is not None else []
    top = sites[0] if sites else None  # sorted by volume in the terrain analysis
    volume = depression_volume_m3(top) if top is not None else None
    if terrain is None:
        status = CoverageStatus.NO_TERRAIN
    elif full_need_m3 is None:
        status = CoverageStatus.NO_PLAN
    elif full_need_m3 < MIN_NEED_M3:
        status = CoverageStatus.NO_NEED
    elif volume is None:
        status = CoverageStatus.NO_DEPRESSION
    else:
        status = CoverageStatus.OK
    ok = status is CoverageStatus.OK
    return RetentionCoverage(
        status=status,
        volume_m3=volume,
        area_m2=top.area_m2 if top is not None else None,
        max_depth_m=top.max_depth_m if top is not None else None,
        inside_share=top.inside_parcel_share if top is not None else None,
        full_need_m3=full_need_m3,
        rescue_need_m3=rescue_need_m3,
        full_pct=share_pct(volume, full_need_m3) if ok else None,
        rescue_pct=share_pct(volume, rescue_need_m3) if ok else None,
    )
