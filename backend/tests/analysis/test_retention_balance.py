"""G9 / M4.2: main depression volume vs dry-year irrigation needs."""

from app.analysis.retention_balance import CoverageStatus, retention_coverage, share_pct
from tests.recommendations.builders import basin, flat, scenario


def test_share_from_review_notes() -> None:
    # Uwagi krytyczne: 2 320 m³ in the depression vs 12 090 m³ from the sprinkler → about 19 %,
    # vs 7 600 m³ of rescue irrigation → about 31 %.
    assert share_pct(2320, 12090) == 19
    assert share_pct(2320, 7600) == 31


def test_share_without_need_or_volume_is_none() -> None:
    assert share_pct(None, 12090) is None
    assert share_pct(2320, None) is None
    assert share_pct(2320, 0.0) is None


def test_coverage_with_depression() -> None:
    a = scenario(surface=basin)[0]
    c = retention_coverage(a.terrain, 12090.0, 7600.0)
    assert c.status is CoverageStatus.OK
    assert c.volume_m3 is not None and c.volume_m3 > 0
    assert c.full_pct == round(100 * c.volume_m3 / 12090)
    assert c.rescue_pct == round(100 * c.volume_m3 / 7600)
    assert c.area_m2 is not None and c.area_m2 > 0


def test_no_depression_is_stated_not_zero() -> None:
    a = scenario(surface=flat)[0]
    c = retention_coverage(a.terrain, 12090.0, 7600.0)
    assert c.status is CoverageStatus.NO_DEPRESSION
    assert c.volume_m3 is None and c.full_pct is None


def test_terrain_missing() -> None:
    a = scenario(dem=False)[0]
    c = retention_coverage(a.terrain, 12090.0, 7600.0)
    assert c.status is CoverageStatus.NO_TERRAIN
    assert c.full_pct is None


def test_plan_missing_and_no_need() -> None:
    a = scenario(surface=basin)[0]
    assert retention_coverage(a.terrain, None, None).status is CoverageStatus.NO_PLAN
    no_need = retention_coverage(a.terrain, 0.0, 0.0)
    assert no_need.status is CoverageStatus.NO_NEED
    assert no_need.full_pct is None
