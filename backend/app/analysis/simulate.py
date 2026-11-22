"""1–5 year strategy simulator for this parcel: no action vs irrigation (rescue / full) vs building soil water
retention, under the parcel's own warming trend. Pure, no I/O.

How it works (delta-change ensemble, a standard way to build a climate scenario without a climate model):
- each of the last 10 years of this parcel's weather is one possible future season ("ensemble member");
- for future year k, ET0 is scaled by the parcel's own ET0 trend (Theil–Sen, % per year) from the middle of
  the
  10-year window to year k. Precipitation is not changed (no robust trend over 10 years);
- every member is run through the daily FAO-56 root-zone balance (October → October), starting from the soil
  water actually computed for 30 September of that year (dry autumns and winters that did not refill the
  root zone are kept);
- outputs per year and strategy: crop water-stress days and the irrigation water used, median ("typical") and
  80th percentile (a dry year, precautionary).

Strategies:
- none: no irrigation;
- rescue: irrigation only in the crop's critical periods, when the soil has dried below the stress threshold;
- full: irrigation on every in-season day with Dr > RAW (maximum yield);
- retention: no irrigation, soil retention built by cover crops, residues and reduced tillage:
  * organic carbon of the topsoil grows by COVER_CROP_SOC_T_HA_YR (cover crops, Poeplau & Don 2015,
    Agric. Ecosyst. Environ. 200:33–41: 0.32 ± 0.08 t C/ha/yr), turned into water capacity by the same
    Saxton & Rawls (2006) equations used for the soil assessment. The effect is small (Minasny & McBratney
    2018,
    Eur. J. Soil Sci. 69:39–47: "limited effect of organic matter on soil available water capacity");
  * a residue mulch covering ~MULCH_COVER of the surface cuts soil evaporation by 5 % per 10 % of cover
    (FAO-56 ch. 11). The cut applies to the soil-evaporation part of the crop coefficient: all of it on bare
    soil and in the initial stage, a share falling with canopy cover in the development stage (cover estimated
    linearly from Kc between Kc_ini and Kc_mid, a simplification of FAO-56 eq. 76), none under a full canopy.
    Reported separately as evaporation avoided (mm), so a small effect is visible even when the stress days
    do not change;
- retention_rescue: retention + rescue irrigation on the same days as the rescue strategy, each dose limited
  to what the (wetter) soil can take. Same trigger as "rescue": adding retention never shifts the irrigation
  later and never makes the result worse (it only saves water).

What the simulator shows on purpose: irrigation water does not stay in the soil until next year. The spring
(1 April) soil water of irrigated and non-irrigated runs of the real 10 years is reported side by side.
"""

from dataclasses import dataclass
from datetime import date
from statistics import median

from app.analysis.series import Weather
from app.analysis.soil import OM_PER_SOC, TOPSOIL_DEPTH_CM, SoilProperties, saxton_rawls
from app.analysis.trends import TrendResult
from app.analysis.water_balance import RootZoneBalance, crop_calendar, root_zone_balance
from app.analysis.water_plan import irrigated_balance, percentile, plan_years, season_members
from app.crops.catalog import Crop

YEARS_AHEAD = 5
COVER_CROP_SOC_T_HA_YR = 0.32
TOPSOIL_BULK_DENSITY_T_M3 = 1.4  # typical arable topsoil; converts t C/ha into g C/kg over 0–30 cm
MULCH_COVER = 0.5
MULCH_EVAPORATION_CUT = 0.05 * MULCH_COVER / 0.1  # FAO-56 ch. 11: 5 % less per 10 % cover
MAX_ET0_FACTOR_CHANGE = 0.25

STRATEGIES = ["none", "rescue", "full", "retention", "retention_rescue"]


@dataclass(frozen=True)
class StrategyYear:
    strategy: str
    year_ahead: int
    taw_mm: float
    stress_days_median: float | None
    stress_days_p80: float | None
    irrigation_mm_median: float | None
    irrigation_mm_p80: float | None
    evaporation_saved_mm_median: float | None = None  # soil evaporation avoided by the mulch, March–October


@dataclass(frozen=True)
class SimulationResult:
    members: int
    et0_change_pct_per_decade: float | None
    tmean_change_c_per_decade: float | None
    baseline_mid_year: float
    taw_now_mm: float
    taw_gain_5y_mm: float
    results: list[StrategyYear]
    spring_storage_none_mm: float | None  # median available water on 1 April, real 10 years, no irrigation
    spring_storage_full_mm: float | None  # same with full irrigation in every season


def _taw_with_extra_soc(soil: SoilProperties, extra_soc_g_kg: float) -> float | None:
    """TAW (mm) over the rooting depth when the topsoil (0–30 cm) gains `extra_soc_g_kg` of organic carbon.

    The change of (θFC − θWP) from Saxton & Rawls (2006) for the topsoil texture and organic matter is
    added to
    the topsoil layers; deeper layers are unchanged.
    """
    sand, clay, soc = soil.topsoil_sand_pct, soil.topsoil_clay_pct, soil.topsoil_soc_g_per_kg
    if soil.taw_mm is None or not soil.layers or sand is None or clay is None or soc is None:
        return None
    om0 = soc / 10 * OM_PER_SOC
    fc0, wp0 = saxton_rawls(sand, clay, om0)
    fc1, wp1 = saxton_rawls(sand, clay, om0 + extra_soc_g_kg / 10 * OM_PER_SOC)
    delta_theta = (fc1 - wp1) - (fc0 - wp0)
    root_cm = soil.root_depth_m * 100
    topsoil_cm = min(TOPSOIL_DEPTH_CM, root_cm)
    return soil.taw_mm + 10 * delta_theta * topsoil_cm


def extra_soc_after(years: int) -> float:
    """Extra topsoil organic carbon (g C per kg soil) after `years` of cover crops."""
    soil_mass_t_ha = TOPSOIL_BULK_DENSITY_T_M3 * (TOPSOIL_DEPTH_CM / 100) * 10_000
    return COVER_CROP_SOC_T_HA_YR * years / soil_mass_t_ha * 1000


def mulch_kc(weather: Weather, crop: Crop) -> list[float]:
    """Crop-coefficient curve with the residue mulch: soil evaporation cut by MULCH_EVAPORATION_CUT."""
    kc, season = crop_calendar(weather, crop)
    span = crop.kc_mid - crop.kc_ini
    out: list[float] = []
    for k, s, d in zip(kc, season, weather.dates, strict=True):
        stage = crop.stage(d) if s else None
        if not s or stage == "initial":
            bare = 1.0
        elif stage == "development" and span > 0:
            bare = 1 - min(max((k - crop.kc_ini) / span, 0.0), 1.0)
        else:
            bare = 0.0
        out.append(k * (1 - MULCH_EVAPORATION_CUT * bare))
    return out


@dataclass(frozen=True)
class _Run:
    balance: RootZoneBalance
    stress_days: int
    irrigation_mm: float
    evaporation_saved_mm: float


def _run(
    member: Weather,
    crop: Crop,
    taw: float,
    strategy: str,
    et0_factor: float,
    dr0_mm: float,
    dose_cap_mm: float | None = None,
    schedule: RootZoneBalance | None = None,
) -> _Run:
    """Stress days, irrigation and evaporation saved in March–October of the member's season.

    The run starts on 1 October with root-zone depletion `dr0_mm`. `schedule` (retention_rescue): the rescue
    run of the same member, whose irrigation days and doses are replayed on the retention soil.
    """
    mulch = strategy.startswith("retention")
    base_kc, season = crop_calendar(member, crop)
    kc = mulch_kc(member, crop) if mulch else base_kc
    dr0 = min(dr0_mm, taw)
    if strategy in ("none", "retention"):
        balance = root_zone_balance(
            member.dates,
            member.precip_mm,
            member.et0_mm,
            kc,
            season,
            taw,
            crop.p,
            dr0_mm=dr0,
            et0_factor=et0_factor,
        )
    elif strategy == "retention_rescue" and schedule is not None:
        balance = root_zone_balance(
            member.dates,
            member.precip_mm,
            member.et0_mm,
            kc,
            season,
            taw,
            crop.p,
            dr0_mm=dr0,
            et0_factor=et0_factor,
            schedule_mm=[b.irrigation_mm for b in schedule.days],
        )
    else:
        balance = irrigated_balance(
            member,
            crop,
            taw,
            only_critical=strategy.endswith("rescue"),
            kc=kc,
            et0_factor=et0_factor,
            dr0_mm=dr0,
            dose_cap_mm=dose_cap_mm,
        )
    year = member.last.year
    window = date(year, 3, 1), date(year, 10, 31)
    days = balance.between(*window)
    saved = 0.0
    if mulch:
        base = dict(zip(member.dates, base_kc, strict=True))
        for b in days:
            if b.etc_mm is not None and b.kc > 0:
                saved += b.etc_mm * (base[b.day] / b.kc - 1)
    return _Run(balance, sum(1 for b in days if b.stressed), sum(b.irrigation_mm for b in days), saved)


def _spring_storage(balance: RootZoneBalance, years: list[int]) -> float | None:
    vals = [balance.taw_mm - b.dr_mm for y in years if (b := balance.at(date(y, 4, 1))) is not None]
    return median(vals) if vals else None


def simulate(
    weather: Weather,
    crop: Crop,
    analysis_date: date,
    soil: SoilProperties | None,
    trends: TrendResult | None,
    dose_cap_mm: float | None = None,
) -> SimulationResult | None:
    if soil is None or soil.taw_mm is None:
        return None
    years = plan_years(weather, analysis_date)
    taw0 = soil.taw_mm
    kc_all, season_all = crop_calendar(weather, crop)
    dry = root_zone_balance(
        weather.dates, weather.precip_mm, weather.et0_mm, kc_all, season_all, taw0, crop.p
    )
    # The same seasons and starting soil water as the water plan (one value for "rescue in a dry year", Q2).
    members = [(m.weather, m.dr0_mm) for m in season_members(weather, crop, years, taw0)]
    if len(members) < 5:
        return None
    mid_year = sum(years) / len(years)
    # "In 1 year" = the next season that has not started yet (before March: this year's season).
    first_season = (
        analysis_date.year if analysis_date < date(analysis_date.year, 3, 1) else analysis_date.year + 1
    )

    et0_trend = trends.get("et0_mm") if trends is not None else None
    t_trend = trends.get("tmean_c") if trends is not None else None
    rel_per_year = 0.0
    et0_pct_dec: float | None = None
    # Only a significant ET0 trend (Mann–Kendall, analysis/trends.py) is extrapolated; otherwise the future
    # seasons are the past ones unchanged, as the trends block says "no clear change" (review M1, Q5).
    if (
        et0_trend is not None
        and et0_trend.significant
        and et0_trend.slope_per_decade is not None
        and et0_trend.mean_all
    ):
        rel_per_year = et0_trend.slope_per_decade / 10 / et0_trend.mean_all
        et0_pct_dec = 100 * rel_per_year * 10

    results: list[StrategyYear] = []
    for k in range(1, YEARS_AHEAD + 1):
        factor = 1 + rel_per_year * (first_season + k - 1 - mid_year)
        factor = min(max(factor, 1 - MAX_ET0_FACTOR_CHANGE), 1 + MAX_ET0_FACTOR_CHANGE)
        taw_ret = _taw_with_extra_soc(soil, extra_soc_after(k)) or taw0
        rescue_runs: list[_Run] = []
        for strategy in STRATEGIES:
            taw = taw_ret if strategy.startswith("retention") else taw0
            runs = [
                _run(
                    m,
                    crop,
                    taw,
                    strategy,
                    factor,
                    dr0,
                    dose_cap_mm,
                    schedule=rescue_runs[i].balance if strategy == "retention_rescue" else None,
                )
                for i, (m, dr0) in enumerate(members)
            ]
            if strategy == "rescue":
                rescue_runs = runs
            stress = [float(r.stress_days) for r in runs]
            water = [r.irrigation_mm for r in runs]
            results.append(
                StrategyYear(
                    strategy=strategy,
                    year_ahead=k,
                    taw_mm=taw,
                    stress_days_median=percentile(stress, 50),
                    stress_days_p80=percentile(stress, 80),
                    irrigation_mm_median=percentile(water, 50),
                    irrigation_mm_p80=percentile(water, 80),
                    evaporation_saved_mm_median=percentile([r.evaporation_saved_mm for r in runs], 50)
                    if strategy.startswith("retention")
                    else None,
                )
            )

    wet = irrigated_balance(weather, crop, taw0, dose_cap_mm=dose_cap_mm)
    spring_years = [y for y in years if y > years[0]]  # the first spring follows the start at field capacity
    taw5 = _taw_with_extra_soc(soil, extra_soc_after(YEARS_AHEAD)) or taw0
    return SimulationResult(
        members=len(members),
        et0_change_pct_per_decade=et0_pct_dec,
        tmean_change_c_per_decade=t_trend.slope_per_decade if t_trend is not None else None,
        baseline_mid_year=mid_year,
        taw_now_mm=taw0,
        taw_gain_5y_mm=taw5 - taw0,
        results=results,
        spring_storage_none_mm=_spring_storage(dry, spring_years),
        spring_storage_full_mm=_spring_storage(wet, spring_years),
    )
