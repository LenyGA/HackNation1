"""Assessment of the water situation: current deficit, structural vulnerability, causes, confidence.

Pure, no I/O. Order is mandatory (CLAUDE.md rule 2): without a complete assessment no recommendations are
generated, so `Assessment.complete` gates plan step M4. Weather is the critical source: without it the
assessment ends with an explicit "no data" result.

Current deficit level (none / light / moderate / severe):
- primary signal: FAO-56 root-zone stress coefficient Ks on analysis_date when soil data exist and the crop is
  on the field; otherwise the 10-year percentile of the 60-day climatic water balance (KBW = P − ET0);
  off-season the percentile of the water balance since 1 October (autumn–winter recharge),
- secondary signal (percentile of KBW, or of 30-day precipitation) may raise the level by at most one step,
- an IUNG critical KBW threshold, when published for the crop and soil category, sets at least "moderate",
- satellite (vegetation condition vs. this parcel's own history) only changes confidence, never the level.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Literal

from app.analysis.causes import Cause, assess_causes
from app.analysis.common import (
    DeficitLevel,
    Vulnerability,
    combine,
    confidence_from_points,
    indicator,
    level_from_ks,
    level_from_percentile,
    round_to,
)
from app.analysis.context import (
    AnalysisInputs,
    Context,
    build_context,
    computed_source,
    landcover_surroundings,
    surroundings_nearest_m,
)
from app.analysis.history import (
    MIN_YEARS_FOR_PERCENTILE,
    HistoryResult,
    empirical_percentile,
    season_stress_days,
    year_stat,
)
from app.analysis.series import same_day_in_year
from app.analysis.soil import SoilCategory, SoilProperties
from app.analysis.terrain import TerrainResult
from app.analysis.texts_pl import CONFIDENCE_REASONS
from app.analysis.water_balance import RootZoneBalance, stress_coefficient
from app.core.config import HISTORY_YEARS
from app.core.models import Confidence, Indicator, SourceStatus, Uncertainty
from app.crops.iung import IungMissing, IungThreshold, iung_lookup
from app.sources.hydro import HydroData

MIN_RECHARGE_DAYS = 30
NDVI_LOW_PCT = 25.0
RETENTION_RADIUS_M = 500.0
RETENTION_KINDS = ("water_body", "wetland", "trees")
IUNG_REGULATION_IN_FORCE = date(2019, 5, 1)  # Dz.U. 2019 poz. 739, § 3 (7 days after 23.04.2019)
IUNG_SOURCE = (
    "Rozporządzenie MRiRW z 11.04.2019 (Dz.U. 2019 poz. 739), System Monitoringu Suszy Rolniczej IUNG-PIB"
)
# Vulnerability level from the share of assessable points (with all 8 points: ≥ 5 high, ≥ 2 medium).
VULN_HIGH_RATIO = 0.6
VULN_MEDIUM_RATIO = 0.25
# Below this many assessable points no overall vulnerability level is given.
VULN_MIN_ASSESSABLE = 4

SatelliteStatus = Literal["agrees", "disagrees", "not_applicable", "missing"]


@dataclass(frozen=True)
class SatelliteCheck:
    status: SatelliteStatus
    indicators: list[Indicator]


@dataclass(frozen=True)
class LastSeason:
    year: int
    stress_days: int | None
    stress_days_pct: float | None  # percentile among the other years (high = more stress than usual)
    deficit_months: list[int]
    indicators: list[Indicator]


@dataclass(frozen=True)
class CurrentState:
    level: DeficitLevel
    in_vegetation: bool
    crop_on_field: bool
    basis: list[str]  # signals used: root_zone, kbw_percentile, precip_percentile, recharge_percentile, iung
    iung_threshold_used: bool
    indicators: list[Indicator]
    uncertainty: Uncertainty
    satellite: SatelliteCheck
    last_season: LastSeason | None  # off-season only
    # Official IUNG-PIB threshold (Dz.U. 2019 poz. 739): threshold and verdict if used, else the reason.
    iung: IungThreshold | None = None
    iung_below: bool | None = None  # KBW of the period at or below the critical value = agricultural drought
    iung_missing: IungMissing | None = None


@dataclass(frozen=True)
class VulnerabilityComponent:
    id: Literal["soil", "deficit_frequency", "critical_period_risk", "slope", "retention_elements"]
    points: int | None  # None = not assessed (missing data)
    indicators: list[Indicator]


@dataclass(frozen=True)
class StructuralVulnerability:
    level: Vulnerability | None  # None = too few factors assessable (missing data), stated in the report
    score: int
    max_score: int
    components: list[VulnerabilityComponent]
    uncertainty: Uncertainty


@dataclass(frozen=True)
class Assessment:
    complete: bool
    incomplete_reason_pl: str | None
    analysis_date: date
    crop_id: str
    current: CurrentState | None
    vulnerability: StructuralVulnerability | None
    causes: list[Cause]
    uncertainty: Uncertainty
    source_status: dict[str, SourceStatus]
    limitations: list[str]  # codes, rendered by report templates
    # Intermediate results reused by recommendations (M4), irrigation (M5) and the report (M6).
    soil: SoilProperties | None
    terrain: TerrainResult | None
    hydro: HydroData | None
    root_zone: RootZoneBalance | None
    history: HistoryResult | None


# --- current state --------------------------------------------------------------------------------


def _recharge_start(day: date) -> date:
    return date(day.year if day.month >= 10 else day.year - 1, 10, 1)


def _recharge(ctx: Context) -> tuple[float | None, float | None, date, date]:
    """Water balance P − ET0 since 1 October and its percentile among the same windows of previous years."""
    assert ctx.weather is not None
    start, end = _recharge_start(ctx.day), ctx.day
    if (end - start).days + 1 < MIN_RECHARGE_DAYS:
        start = end - timedelta(days=59)
    value = ctx.weather.kbw_sum(start, end)
    sample = []
    for k in range(1, HISTORY_YEARS + 1):
        s = same_day_in_year(start, start.year - k)
        e = same_day_in_year(end, end.year - k)
        sample.append(ctx.weather.kbw_sum(s, e))
    return value, empirical_percentile(value, sample), start, end


def _satellite(ctx: Context, level: DeficitLevel) -> SatelliteCheck:
    s2 = ctx.inputs.sentinel2
    if s2.data is None:
        return SatelliteCheck("missing", [])
    crop = ctx.crop
    canopy = crop.kc(ctx.day) >= (crop.kc_ini + crop.kc_mid) / 2
    if not ctx.crop_on_field or not canopy:
        # Low vegetation index on a field without a developed crop is normal, not drought.
        return SatelliteCheck("not_applicable", [])
    current = [s for s in s2.data.current if s.date <= ctx.day]
    history = [s for s in s2.data.history if s.date < ctx.day]
    if not current or len(history) < MIN_YEARS_FOR_PERCENTILE:
        return SatelliteCheck("not_applicable", [])
    now = median(s.ndvi_mean for s in current)
    hist = [s.ndvi_mean for s in history]
    pct = empirical_percentile(now, list(hist))
    src = computed_source(s2.source)
    lvl = s2.uncertainty.level
    first, last = min(s.date for s in current), max(s.date for s in current)
    indicators = [
        indicator(
            "ndvi_current", now, "", src, level=lvl, reason="satellite", step=0.01, start=first, end=last
        ),
        indicator("ndvi_history_median", median(hist), "", src, level=lvl, reason="satellite", step=0.01),
        indicator("ndvi_pct", pct, "%", src, level=lvl, reason="satellite", step=1),
        indicator("ndvi_history_years", len(history), "lat", src, level=lvl, reason="satellite"),
    ]
    if pct is None:
        return SatelliteCheck("not_applicable", indicators)
    low = pct <= NDVI_LOW_PCT
    deficit = level.rank >= DeficitLevel.LIGHT.rank
    return SatelliteCheck("agrees" if low == deficit else "disagrees", indicators)


def _last_season(ctx: Context) -> LastSeason | None:
    """Off-season: the most recent completed vegetation season (1 March – 30 September) vs. previous years.

    Every year is compared over the same window, so a partly elapsed October never enters the comparison.
    Without soil data the season cannot be assessed (no deficit-month method), so the result is None.
    """
    assert ctx.weather is not None and ctx.history is not None
    if ctx.balance is None:
        return None
    year = ctx.day.year if ctx.day.month >= 10 else ctx.day.year - 1
    start, end = date(year, 3, 1), date(year, 9, 30)
    stat = year_stat(ctx.weather, ctx.crop, ctx.balance, year, ctx.day)
    stress = season_stress_days(ctx.balance, ctx.crop, year, until=end)
    others = [
        season_stress_days(ctx.balance, ctx.crop, y.year, until=date(y.year, 9, 30))
        for y in ctx.history.years
        if y.year != year
    ]
    # High percentile = more stress days than in most previous years.
    pct = empirical_percentile(stress, [s for s in others if s is not None])
    src = ctx.water_source
    deficit_months = [m for m in stat.deficit_months if m <= 9]
    indicators = [
        indicator(
            "last_season_stress_days",
            stress,
            "dni",
            src,
            level=Confidence.MEDIUM,
            reason="root_zone",
            start=start,
            end=end,
        ),
        indicator("last_season_stress_pct", pct, "%", src, level=Confidence.MEDIUM, reason="percentile_10y"),
        indicator(
            "last_season_deficit_months",
            len(deficit_months),
            "mies.",
            src,
            level=Confidence.MEDIUM,
            reason="root_zone",
            start=start,
            end=end,
        ),
    ]
    return LastSeason(year, stress, pct, deficit_months, indicators)


def _current(ctx: Context) -> CurrentState | None:
    assert ctx.weather is not None and ctx.history is not None
    cur = ctx.history.current
    wsrc = ctx.weather_source
    wl = ctx.weather_confidence
    day = ctx.day
    indicators: list[Indicator] = [
        indicator(
            "precip_30d_mm", cur.precip_30d_mm, "mm", wsrc, level=wl, start=day - timedelta(days=29), end=day
        ),
        indicator("precip_30d_pct", cur.precip_30d_pct, "%", wsrc, level=wl, reason="percentile_10y"),
        indicator(
            "precip_90d_mm", cur.precip_90d_mm, "mm", wsrc, level=wl, start=day - timedelta(days=89), end=day
        ),
        indicator("precip_90d_pct", cur.precip_90d_pct, "%", wsrc, level=wl, reason="percentile_10y"),
        indicator(
            "kbw_60d_mm", cur.kbw_60d_mm, "mm", wsrc, level=wl, start=day - timedelta(days=59), end=day
        ),
        indicator("kbw_60d_pct", cur.kbw_60d_pct, "%", wsrc, level=wl, reason="percentile_10y"),
    ]
    basis: list[str] = []
    kbw_level = level_from_percentile(cur.kbw_60d_pct)
    precip_level = level_from_percentile(cur.precip_30d_pct)

    rz_level: DeficitLevel | None = None
    today = ctx.today
    if ctx.balance is not None and today is not None and ctx.crop_on_field and not today.gap:
        ks_end = stress_coefficient(today.dr_mm, ctx.balance.taw_mm, ctx.balance.p)
        rz_level = level_from_ks(ks_end)
        rsrc = ctx.water_source
        indicators += [
            indicator("taw_mm", ctx.balance.taw_mm, "mm", rsrc, level=Confidence.MEDIUM, reason="soil_map"),
            indicator("raw_mm", ctx.balance.raw_mm, "mm", rsrc, level=Confidence.MEDIUM, reason="soil_map"),
            indicator(
                "root_zone_depletion_mm",
                today.dr_mm,
                "mm",
                rsrc,
                level=Confidence.MEDIUM,
                reason="root_zone",
                start=day,
                end=day,
            ),
            indicator(
                "root_zone_available_mm",
                ctx.balance.taw_mm - today.dr_mm,
                "mm",
                rsrc,
                level=Confidence.MEDIUM,
                reason="root_zone",
                start=day,
                end=day,
            ),
            indicator(
                "root_zone_depletion_pct",
                100 * today.dr_mm / ctx.balance.taw_mm,
                "%",
                rsrc,
                level=Confidence.MEDIUM,
                reason="root_zone",
            ),
            indicator(
                "ks",
                ks_end,
                "",
                rsrc,
                level=Confidence.MEDIUM,
                reason="root_zone",
                step=0.01,
                start=day,
                end=day,
            ),
        ]

    last_season: LastSeason | None = None
    level: DeficitLevel | None
    if ctx.in_vegetation:
        meteo = kbw_level if kbw_level is not None else precip_level
        if rz_level is not None:
            level = combine(rz_level, meteo)
            basis.append("root_zone")
        elif meteo is not None:
            level = combine(meteo, precip_level if kbw_level is not None else None)
        else:
            level = None
        if kbw_level is not None:
            basis.append("kbw_percentile")
        if precip_level is not None and (rz_level is None or kbw_level is None):
            basis.append("precip_percentile")
    else:
        value, pct, start, end = _recharge(ctx)
        indicators += [
            indicator("recharge_kbw_mm", value, "mm", wsrc, level=wl, start=start, end=end),
            indicator("recharge_kbw_pct", pct, "%", wsrc, level=wl, reason="percentile_10y"),
        ]
        recharge_level = level_from_percentile(pct)
        meteo = recharge_level if recharge_level is not None else kbw_level
        if rz_level is not None:
            level = combine(rz_level, meteo)
            basis.append("root_zone")
        else:
            level = meteo
        if recharge_level is not None:
            basis.append("recharge_percentile")
        elif kbw_level is not None:
            basis.append("kbw_percentile")
        last_season = _last_season(ctx)
    if level is None:
        # No signal could be compared with history: no level rather than a fake "no deficit".
        return None

    # IUNG critical KBW (Dz.U. 2019 poz. 739): KBW summed over the exact six-dekad period of the threshold.
    # The comparison uses the value rounded as shown in the report, so text and verdict never disagree.
    iung_used = False
    iung: IungThreshold | None = None
    iung_below: bool | None = None
    category = ctx.soil.category.value if ctx.soil is not None and ctx.soil.category is not None else None
    found: IungThreshold | IungMissing = (
        iung_lookup(ctx.crop.id, category, day)
        if ctx.in_vegetation and ctx.crop_on_field
        else IungMissing.CROP_NOT_ON_FIELD
    )
    iung_missing: IungMissing | None = found if isinstance(found, IungMissing) else None
    if isinstance(found, IungThreshold):
        kbw_period = ctx.weather.kbw_sum(found.period_start, found.period_end)
        if kbw_period is None:
            iung_missing = IungMissing.NO_WEATHER
        else:
            kbw_rounded = round_to(kbw_period, 1.0)
            assert kbw_rounded is not None
            iung_used = True
            iung = found
            iung_below = kbw_rounded <= found.kbw_critical_mm
            if iung_below:
                basis.append("iung")
            indicators.append(
                indicator(
                    "kbw_iung_period_mm",
                    kbw_period,
                    "mm",
                    wsrc,
                    level=wl,
                    start=found.period_start,
                    end=found.period_end,
                )
            )
            indicators.append(
                indicator(
                    "kbw_iung_critical_mm",
                    found.kbw_critical_mm,
                    "mm",
                    IUNG_SOURCE,
                    level=Confidence.HIGH,
                    reason="iung_regulation",
                    start=found.period_start,
                    end=found.period_end,
                )
            )
            if iung_below:
                level = DeficitLevel.from_rank(max(level.rank, DeficitLevel.MODERATE.rank))

    satellite = _satellite(ctx, level)
    return CurrentState(
        level=level,
        in_vegetation=ctx.in_vegetation,
        crop_on_field=ctx.crop_on_field,
        basis=basis,
        iung_threshold_used=iung_used,
        indicators=indicators,
        uncertainty=_current_confidence(ctx, rz_level is not None, satellite, iung_used),
        satellite=satellite,
        last_season=last_season,
        iung=iung,
        iung_below=iung_below,
        iung_missing=iung_missing,
    )


def _current_confidence(ctx: Context, root_zone: bool, sat: SatelliteCheck, iung_used: bool) -> Uncertainty:
    points = 3
    reasons: list[str] = []
    if ctx.weather_confidence is Confidence.MEDIUM:
        points -= 1
        reasons.append(CONFIDENCE_REASONS["weather_degraded"])
    elif ctx.weather_confidence is Confidence.LOW:
        points -= 2
        reasons.append(CONFIDENCE_REASONS["weather_low"])
    if ctx.soil is None or ctx.soil.taw_mm is None:
        points -= 1
        reasons.append(CONFIDENCE_REASONS["soil_missing"])
    elif not root_zone and ctx.crop_on_field:
        points -= 1
        reasons.append(CONFIDENCE_REASONS["root_zone_unavailable"])
    if ctx.history is None or ctx.history.current.kbw_60d_pct is None:
        points -= 1
        reasons.append(CONFIDENCE_REASONS["few_years"])
    if sat.status == "disagrees":
        points -= 1
        reasons.append(CONFIDENCE_REASONS["satellite_disagrees"])
    elif sat.status == "agrees":
        reasons.append(CONFIDENCE_REASONS["satellite_agrees"])
    if not reasons:
        reasons.append(CONFIDENCE_REASONS["base"])
    text = "; ".join(reasons)
    return Uncertainty(level=confidence_from_points(points), reason_pl=text[0].upper() + text[1:] + ".")


# --- structural vulnerability ---------------------------------------------------------------------


def nearest_retention_m(hydro: HydroData) -> float | None:
    distances = [hydro.nearest_m.get(k) for k in RETENTION_KINDS]
    present = [d for d in distances if d is not None]
    return min(present) if present else None


def _vulnerability(ctx: Context) -> StructuralVulnerability:
    components: list[VulnerabilityComponent] = []
    ssrc = ctx.soil_source

    soil = ctx.soil
    if soil is not None and (soil.category is not None or soil.taw_mm is not None):
        cat_points = {SoilCategory.I: 2, SoilCategory.II: 1}.get(soil.category, 0) if soil.category else 0
        taw_points = 0
        if soil.taw_mm is not None:
            taw_points = 2 if soil.taw_mm < 60 else 1 if soil.taw_mm < 100 else 0
        ind = [indicator("taw_mm", soil.taw_mm, "mm", ssrc, level=Confidence.MEDIUM, reason="soil_map")]
        if soil.category is not None:
            cat_num = ["I", "II", "III", "IV"].index(soil.category.value) + 1
            ind.append(
                indicator(
                    "soil_category",
                    cat_num,
                    "kat.",
                    ssrc,
                    level=Confidence.LOW,
                    reason="soil_category_approx",
                )
            )
        components.append(VulnerabilityComponent("soil", max(cat_points, taw_points), ind))
    else:
        components.append(VulnerabilityComponent("soil", None, []))

    hist = ctx.history
    method_reason = "root_zone" if ctx.balance is not None else "history_crop_balance"
    hist_conf = Confidence.MEDIUM if ctx.balance is not None else Confidence.LOW
    if hist is not None and hist.deficit_year_share is not None:
        share = hist.deficit_year_share
        components.append(
            VulnerabilityComponent(
                "deficit_frequency",
                2 if share >= 0.5 else 1 if share >= 0.3 else 0,
                [
                    indicator(
                        "deficit_year_share_pct",
                        100 * share,
                        "%",
                        ctx.water_source,
                        level=hist_conf,
                        reason=method_reason,
                    )
                ],
            )
        )
        crit = hist.critical_risk_months
        freq = {f.month: f.frequency for f in hist.months}
        components.append(
            VulnerabilityComponent(
                "critical_period_risk",
                1 if crit else 0,
                [
                    indicator(
                        f"deficit_frequency_month_{m:02d}_pct",
                        100 * (freq.get(m) or 0.0),
                        "%",
                        ctx.water_source,
                        level=hist_conf,
                        reason=method_reason,
                    )
                    for m in crit
                ],
            )
        )
    else:
        components.append(VulnerabilityComponent("deficit_frequency", None, []))
        components.append(VulnerabilityComponent("critical_period_risk", None, []))

    terrain = ctx.terrain
    if terrain is not None:
        tsrc = computed_source(ctx.inputs.dem.source)
        treason = "terrain_nmt" if terrain.dataset == "gugik_nmt" else "terrain_cop"
        tconf = Confidence.HIGH if terrain.dataset == "gugik_nmt" else Confidence.MEDIUM
        components.append(
            VulnerabilityComponent(
                "slope",
                2 if terrain.slope_mean_pct >= 10 else 1 if terrain.slope_mean_pct >= 5 else 0,
                [
                    indicator(
                        "slope_mean_pct",
                        terrain.slope_mean_pct,
                        "%",
                        tsrc,
                        level=tconf,
                        reason=treason,
                        step=0.1,
                    )
                ],
            )
        )
    else:
        components.append(VulnerabilityComponent("slope", None, []))

    if ctx.hydro is not None:
        nearest = nearest_retention_m(ctx.hydro)
        components.append(
            VulnerabilityComponent(
                "retention_elements",
                1 if nearest is None or nearest > RETENTION_RADIUS_M else 0,
                [
                    indicator(
                        "nearest_retention_element_m",
                        nearest,
                        "m",
                        computed_source(ctx.inputs.hydro.source),
                        level=Confidence.LOW,
                        reason="osm",
                        step=10,
                    )
                ],
            )
        )
    elif (lc := landcover_surroundings(ctx.inputs)) is not None:
        present = [d for k in RETENTION_KINDS if (d := surroundings_nearest_m(lc, k)) is not None]
        nearest_lc = min(present) if present else None
        components.append(
            VulnerabilityComponent(
                "retention_elements",
                1 if nearest_lc is None or nearest_lc > RETENTION_RADIUS_M else 0,
                [
                    indicator(
                        "nearest_retention_element_m",
                        nearest_lc,
                        "m",
                        computed_source(ctx.inputs.landcover.source),
                        level=Confidence.LOW,
                        reason="worldcover",
                        step=10,
                    )
                ],
            )
        )
    else:
        components.append(VulnerabilityComponent("retention_elements", None, []))

    max_points = {
        "soil": 2,
        "deficit_frequency": 2,
        "critical_period_risk": 1,
        "slope": 2,
        "retention_elements": 1,
    }
    score = sum(c.points or 0 for c in components)
    max_score = sum(max_points[c.id] for c in components if c.points is not None)
    # Relative to the points that could be assessed, so missing components do not bias the result to "low".
    ratio = score / max_score if max_score else 0.0
    level: Vulnerability | None = (
        Vulnerability.HIGH
        if ratio >= VULN_HIGH_RATIO
        else Vulnerability.MEDIUM
        if ratio >= VULN_MEDIUM_RATIO
        else Vulnerability.LOW
    )

    unknown = [c.id for c in components if c.points is None]
    points = 3 - (1 if ctx.soil is None else 0) - (1 if ctx.balance is None else 0)
    reasons: list[str] = []
    if unknown:
        points -= 1 if len(unknown) == 1 else 2
        reasons.append(CONFIDENCE_REASONS["components_unknown"])
    if max_score < VULN_MIN_ASSESSABLE:
        # Too few factors could be assessed for an honest overall level.
        level = None
        points = 1
    if ctx.soil is None or ctx.soil.taw_mm is None:
        reasons.append(CONFIDENCE_REASONS["soil_missing"])
    if not reasons:
        reasons.append(CONFIDENCE_REASONS["base"])
    text = "; ".join(reasons)
    return StructuralVulnerability(
        level=level,
        score=score,
        max_score=max_score,
        components=components,
        uncertainty=Uncertainty(
            level=confidence_from_points(points), reason_pl=text[0].upper() + text[1:] + "."
        ),
    )


# --- limitations ----------------------------------------------------------------------------------


def _limitations(ctx: Context, current: CurrentState | None) -> list[str]:
    inp = ctx.inputs
    out: list[str] = ["weather_grid", "crop_calendar_typical", "balance_simplifications"]
    if current is not None and not current.iung_threshold_used:
        out.append("iung_thresholds_missing")
    elif current is not None:
        out.append("iung_etp_method")
        if ctx.inputs.analysis_date < IUNG_REGULATION_IN_FORCE:
            out.append("iung_backdated")
    if inp.weather.data is not None and inp.weather.data.provisional_from is not None:
        out.append("weather_provisional")
    if inp.weather.status is SourceStatus.DEGRADED:
        out.append("weather_degraded")
    if inp.soil.data is None:
        out.append("soil_missing")
    else:
        out += ["soil_resolution", "soil_category_approx"]
        if ctx.soil is not None and ctx.soil.taw_mm is None:
            out.append("soil_incomplete")
    if inp.sentinel2.data is None:
        out.append("satellite_missing")
    else:
        out.append("satellite_crop_history_unknown")
        if inp.sentinel2.status is SourceStatus.DEGRADED:
            out.append("satellite_degraded")
    if inp.dem.data is None or ctx.terrain is None:
        out.append("terrain_missing")
    elif ctx.terrain.dataset != "gugik_nmt":
        out.append("terrain_coarse")
    if ctx.terrain is not None and "small_parcel" in ctx.terrain.notes:
        out.append("small_parcel")
    if inp.hydro.data is None:
        out.append("hydro_missing")
    else:
        out += ["osm_incomplete", "maps_current_state"]
    if inp.landcover.data is None:
        out.append("landcover_missing")
    else:
        out.append("landcover_single_year")
        if not inp.landcover.data.looks_agricultural:
            out.append("landcover_not_agricultural")
    out.append("water_availability_and_permits")
    return out


# --- entry point ----------------------------------------------------------------------------------


def _weather_complete(ctx: Context) -> str | None:
    """None when weather supports a complete assessment, otherwise the Polish reason."""
    if ctx.weather is None or ctx.history is None:
        return "Brak danych pogodowych, więc nie da się ocenić sytuacji wodnej działki."
    if not ctx.weather.covers(ctx.day - timedelta(days=89), ctx.day):
        return "Dane pogodowe nie obejmują ostatnich 90 dni przed datą analizy, więc ocena nie jest możliwa."
    cur = ctx.history.current
    if cur.kbw_60d_mm is None or cur.precip_30d_mm is None:
        return "W danych pogodowych z ostatnich tygodni jest zbyt wiele braków, więc ocena nie jest możliwa."
    return None


def _incomplete(ctx: Context, reason: str) -> Assessment:
    inputs = ctx.inputs
    return Assessment(
        complete=False,
        incomplete_reason_pl=reason,
        analysis_date=inputs.analysis_date,
        crop_id=inputs.crop.id,
        current=None,
        vulnerability=None,
        causes=[],
        uncertainty=Uncertainty(level=Confidence.LOW, reason_pl=reason),
        source_status=inputs.statuses(),
        limitations=_limitations(ctx, None),
        soil=ctx.soil,
        terrain=ctx.terrain,
        hydro=ctx.hydro,
        root_zone=ctx.balance,
        history=ctx.history,
    )


NO_SIGNAL_PL = (
    "Za mało lat z kompletnymi danymi pogodowymi, żeby porównać obecną sytuację z poprzednimi latami, "
    "więc oceny niedoboru wody nie podajemy."
)


def assess(inputs: AnalysisInputs) -> Assessment:
    ctx = build_context(inputs)
    reason = _weather_complete(ctx)
    if reason is not None:
        return _incomplete(ctx, reason)
    current = _current(ctx)
    if current is None:
        return _incomplete(ctx, NO_SIGNAL_PL)
    vulnerability = _vulnerability(ctx)
    causes = assess_causes(ctx, current.level)
    worst = min(
        (current.uncertainty, vulnerability.uncertainty),
        key=lambda u: ["low", "medium", "high"].index(u.level.value),
    )
    return Assessment(
        complete=True,
        incomplete_reason_pl=None,
        analysis_date=inputs.analysis_date,
        crop_id=inputs.crop.id,
        current=current,
        vulnerability=vulnerability,
        causes=causes,
        uncertainty=worst,
        source_status=inputs.statuses(),
        limitations=_limitations(ctx, current),
        soil=ctx.soil,
        terrain=ctx.terrain,
        hydro=ctx.hydro,
        root_zone=ctx.balance,
        history=ctx.history,
    )
