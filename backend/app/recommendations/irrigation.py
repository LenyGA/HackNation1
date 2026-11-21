"""Irrigation: whether, when and how much (plan step M5). Pure, no I/O.

Mandatory order (CLAUDE.md rule 2): irrigation is the last resort, after retention and field practices; the
recommendation is sorted last by the engine and its text says so.

- Justified when the FAO-56 root-zone depletion Dr exceeds the readily available water RAW (Ks < 1) on
  analysis_date, in a stage in which the crop still responds to water (not during ripening, unless a
  water-critical period lasts into it), inside the vegetation period.
- Dose: refill to field capacity (= Dr, net water that has to reach the soil), split into single applications
  capped by soil category (light soils hold little water: smaller, more frequent doses).
- Timing: only when a forecast issued on analysis_date exists (analysis_date = today), Dr is projected over
  the next days with the same balance, forecast precipitation and forecast ET0. Rain that brings Dr back to
  ≤ RAW within WAIT_MAX_DAYS means "wait"; otherwise "irrigate now", or "within N days" when Dr is
  projected to pass RAW.
  For historical dates there is no forecast: the state on analysis_date only, said explicitly.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from app.analysis.assessment import Assessment
from app.analysis.common import indicator, round_to
from app.analysis.context import VEGETATION_END, VEGETATION_START, AnalysisInputs, computed_source
from app.analysis.soil import SoilCategory
from app.analysis.water_balance import (
    BARE_SOIL_KC,
    BalanceDay,
    RootZoneBalance,
    root_zone_balance,
    stress_coefficient,
)
from app.core.config import today_local
from app.core.models import Confidence, Indicator
from app.recommendations.models import Category, ParamValue, Rule, RuleContext
from app.recommendations.texts_pl import irrigation_caveats, irrigation_text, irrigation_title
from app.sources.open_meteo import SOURCE_FORECAST, WeatherForecast

# Largest single net dose per soil category (mm). Light soils store little water above field capacity and lose
# the excess by drainage, so they get smaller, more frequent doses. Typical Polish sprinkler practice
# (Dzieżyc 1988; IUNG-PIB irrigation guidelines): sands 15–20 mm, loams 25–30 mm, clays 30–35 mm.
MAX_SINGLE_DOSE_MM: dict[SoilCategory, float] = {
    SoilCategory.I: 15.0,
    SoilCategory.II: 20.0,
    SoilCategory.III: 30.0,
    SoilCategory.IV: 35.0,
}
# Soil category unknown (texture incomplete): the cautious light-soil value.
MAX_SINGLE_DOSE_UNKNOWN_MM = 20.0
FORECAST_HORIZON_DAYS = 7
# Forecast rain that brings Dr back to ≤ RAW within this many days is worth waiting for ...
WAIT_MAX_DAYS = 3
# ... but only while the crop is at most moderately stressed (FAO-56 Ks ≥ 0.5, ET reduced by ≤ 50 %); with
# almost dry soil waiting days for rain costs yield.
WAIT_MIN_KS = 0.5


class IrrigationStatus(StrEnum):
    NO_ASSESSMENT = "no_assessment"  # assessment incomplete: no irrigation advice (rule 2)
    OFF_SEASON = "off_season"  # analysis_date outside the vegetation period
    NO_CROP = "no_crop"  # vegetation period, but the crop is not on the field yet / any more
    LATE_STAGE = "late_stage"  # ripening: water no longer raises the yield
    NO_BALANCE = (
        "no_balance"  # no soil data (or a gap on analysis_date): no dose without the root-zone balance
    )
    NOT_NEEDED = "not_needed"
    WAIT_FOR_RAIN = "wait_for_rain"
    IRRIGATE = "irrigate"  # Dr > RAW on analysis_date
    IRRIGATE_SOON = "irrigate_soon"  # Dr projected to pass RAW within the forecast horizon


ADVISED = (IrrigationStatus.IRRIGATE, IrrigationStatus.IRRIGATE_SOON)


class ForecastUse(StrEnum):
    USED = "used"
    HISTORICAL = "historical"  # analysis_date in the past: no forecast exists for it
    UNAVAILABLE = "unavailable"  # analysis_date is today but the forecast could not be fetched


class ProjectedDay(BaseModel):
    day: date
    precip_mm: float
    et0_mm: float
    depletion_mm: float = Field(description="Projected root-zone depletion Dr at the end of the day.")


class IrrigationAdvice(BaseModel):
    """Section 7 of the report. Always present, also when irrigation does not apply (it says why)."""

    status: IrrigationStatus
    applicable: bool = Field(description="False when irrigation does not apply on this date (season, stage).")
    title_pl: str
    text_pl: str
    caveats_pl: list[str] = Field(description="Factors not covered by the analysis (water access, permits).")
    params: dict[str, ParamValue]
    dose_mm: float | None = Field(None, description="Net water to refill the root zone to field capacity.")
    single_dose_max_mm: float | None = None
    applications: int | None = None
    volume_m3: float | None = Field(None, description="dose_mm over the whole parcel area.")
    within_days: int | None = Field(None, description="0 = now; None = no timing (no forecast).")
    irrigate_by: date | None = None
    forecast: ForecastUse
    projection: list[ProjectedDay] = Field(default_factory=list)
    evidence: list[Indicator] = Field(default_factory=list)


@dataclass(frozen=True)
class _Decision:
    status: IrrigationStatus
    depletion_mm: float | None = None  # Dr to refill (on the irrigation day)
    within_days: int | None = None
    relief_day: date | None = None
    rain_until_relief_mm: float | None = None


def single_dose_max_mm(category: SoilCategory | None) -> float:
    return (
        MAX_SINGLE_DOSE_MM.get(category, MAX_SINGLE_DOSE_UNKNOWN_MM)
        if category
        else MAX_SINGLE_DOSE_UNKNOWN_MM
    )


def project(
    balance: RootZoneBalance,
    today: BalanceDay,
    forecast: WeatherForecast,
    inputs: AnalysisInputs,
    horizon_days: int = FORECAST_HORIZON_DAYS,
) -> list[ProjectedDay]:
    """Dr over the forecast days after analysis_date; stops at the first day without forecast P or ET0."""
    crop = inputs.crop
    end = inputs.analysis_date + timedelta(days=horizon_days)
    days: list[date] = []
    precip: list[float] = []
    et0: list[float] = []
    if not len(forecast.dates) == len(forecast.precip_mm) == len(forecast.et0_mm):
        return []  # malformed forecast: no projection rather than a crash
    for d, p, e in zip(forecast.dates, forecast.precip_mm, forecast.et0_mm, strict=True):
        if d <= inputs.analysis_date:
            continue
        if d > end or p is None or e is None:
            break
        if days and d != days[-1] + timedelta(days=1):
            break  # a hole in the forecast: no projection beyond it
        days.append(d)
        precip.append(p)
        et0.append(e)
    if not days or days[0] != inputs.analysis_date + timedelta(days=1):
        return []
    season = [crop.in_season(d) for d in days]
    kc = [
        crop.kc(d) if s else max(crop.kc_off_season, BARE_SOIL_KC) for d, s in zip(days, season, strict=True)
    ]
    run = root_zone_balance(
        days, list(precip), list(et0), kc, season, balance.taw_mm, balance.p, dr0_mm=today.dr_mm
    )
    return [
        ProjectedDay(day=b.day, precip_mm=p, et0_mm=e, depletion_mm=b.dr_mm)
        for b, p, e in zip(run.days, precip, et0, strict=True)
    ]


def _relief(
    projection: list[ProjectedDay], after: date, raw: float, days: int = WAIT_MAX_DAYS
) -> tuple[date, float] | None:
    """First day in (after, after + days] when rain brings Dr back to ≤ RAW, and the rain until then."""
    rain = 0.0
    for pd in projection:
        if pd.day <= after:
            continue
        if (pd.day - after).days > days:
            break
        rain += pd.precip_mm
        if pd.depletion_mm <= raw:
            return pd.day, rain
    return None


def _rain_within(projection: list[ProjectedDay], after: date, days: int = WAIT_MAX_DAYS) -> float:
    return sum(pd.precip_mm for pd in projection if 0 < (pd.day - after).days <= days)


def _decide(balance: RootZoneBalance, dr0: float, projection: list[ProjectedDay], day: date) -> _Decision:
    """Decision table of METHODOLOGY section 9."""
    raw = balance.raw_mm
    if dr0 > raw:
        if projection and stress_coefficient(dr0, balance.taw_mm, balance.p) >= WAIT_MIN_KS:
            relief = _relief(projection, day, raw)
            if relief is not None:
                return _Decision(
                    IrrigationStatus.WAIT_FOR_RAIN, relief_day=relief[0], rain_until_relief_mm=relief[1]
                )
        return _Decision(IrrigationStatus.IRRIGATE, depletion_mm=dr0, within_days=0 if projection else None)
    for pd in projection:
        # Passing RAW counts only when no forecast rain brings Dr back within WAIT_MAX_DAYS (as for today).
        if pd.depletion_mm > raw and _relief(projection, pd.day, raw) is None:
            return _Decision(
                IrrigationStatus.IRRIGATE_SOON, depletion_mm=pd.depletion_mm, within_days=(pd.day - day).days
            )
    return _Decision(IrrigationStatus.NOT_NEEDED)


def _forecast_use(inputs: AnalysisInputs, today: date) -> tuple[ForecastUse, WeatherForecast | None]:
    data = inputs.weather.data
    fc = data.forecast if data is not None else None
    # Only a forecast issued on analysis_date itself may be used (rule 3: nothing known later than that day).
    if fc is not None and fc.issued_on == inputs.analysis_date:
        return ForecastUse.USED, fc
    if inputs.analysis_date < today:
        return ForecastUse.HISTORICAL, None
    return ForecastUse.UNAVAILABLE, None


def _advice(
    status: IrrigationStatus,
    inputs: AnalysisInputs,
    forecast: ForecastUse,
    params: dict[str, ParamValue] | None = None,
    **fields: object,
) -> IrrigationAdvice:
    p: dict[str, ParamValue] = {
        "status": status.value,
        "crop": inputs.crop.name_pl.lower(),
        "date": inputs.analysis_date.isoformat(),
        "forecast": forecast.value,
        "season_start": f"{inputs.analysis_date.year}-{VEGETATION_START}",
        "season_end": f"{inputs.analysis_date.year}-{VEGETATION_END}",
        "grassland": int(inputs.crop.id == "grassland"),
        **(params or {}),
    }
    applicable = status not in (
        IrrigationStatus.NO_ASSESSMENT,
        IrrigationStatus.OFF_SEASON,
        IrrigationStatus.NO_CROP,
        IrrigationStatus.LATE_STAGE,
    )
    return IrrigationAdvice(
        status=status,
        applicable=applicable,
        title_pl=irrigation_title(status.value),
        text_pl=irrigation_text(p),
        caveats_pl=irrigation_caveats(status.value),
        params=p,
        forecast=forecast,
        **fields,
    )


def _responsive(inputs: AnalysisInputs) -> bool:
    """The crop still turns water into yield: not ripening, unless a water-critical period lasts into it."""
    crop, day = inputs.crop, inputs.analysis_date
    return crop.stage(day) != "late" or crop.critical_period_at(day) is not None


def irrigation_advice(
    assessment: Assessment, inputs: AnalysisInputs, today: date | None = None
) -> IrrigationAdvice:
    today = today or today_local()
    forecast_use, forecast = _forecast_use(inputs, today)
    if not assessment.complete or assessment.current is None:
        return _advice(IrrigationStatus.NO_ASSESSMENT, inputs, forecast_use)
    current = assessment.current
    if not current.in_vegetation:
        return _advice(IrrigationStatus.OFF_SEASON, inputs, forecast_use)
    if not current.crop_on_field:
        return _advice(IrrigationStatus.NO_CROP, inputs, forecast_use)
    if not _responsive(inputs):
        return _advice(IrrigationStatus.LATE_STAGE, inputs, forecast_use)
    balance = assessment.root_zone
    bday = balance.at(inputs.analysis_date) if balance is not None else None
    if balance is None or bday is None or bday.gap:
        reason = "soil" if balance is None else "weather_gap"
        return _advice(IrrigationStatus.NO_BALANCE, inputs, forecast_use, {"reason": reason})

    projection = project(balance, bday, forecast, inputs) if forecast is not None else []
    if forecast is not None and not projection:
        # Forecast present but unusable (a gap right after analysis_date).
        forecast_use = ForecastUse.UNAVAILABLE
    decision = _decide(balance, bday.dr_mm, projection, inputs.analysis_date)
    available = balance.taw_mm - bday.dr_mm

    evidence = _evidence(assessment)
    params: dict[str, ParamValue] = {"available_mm": round_to(available, 1.0) or 0.0}
    fields: dict[str, object] = {"projection": projection}
    critical = inputs.crop.critical_period_at(inputs.analysis_date)
    if critical is not None:
        params["phase"] = critical.name_pl

    if projection:
        fsrc = SOURCE_FORECAST
        horizon_rain = sum(pd.precip_mm for pd in projection)
        params["forecast_days"] = len(projection)
        params["forecast_precip_mm"] = round_to(horizon_rain, 1.0) or 0.0
        params["rain_soon_mm"] = round_to(_rain_within(projection, inputs.analysis_date), 1.0) or 0.0
        params["wait_days"] = WAIT_MAX_DAYS
        evidence.append(
            indicator(
                "forecast_precip_mm",
                horizon_rain,
                "mm",
                fsrc,
                level=Confidence.LOW,
                reason="forecast",
                start=projection[0].day,
                end=projection[-1].day,
            )
        )

    if decision.status is IrrigationStatus.WAIT_FOR_RAIN:
        assert decision.relief_day is not None and decision.rain_until_relief_mm is not None
        params["relief_date"] = decision.relief_day.isoformat()
        params["rain_until_relief_mm"] = round_to(decision.rain_until_relief_mm, 1.0) or 0.0

    if decision.status in ADVISED:
        assert decision.depletion_mm is not None
        category = assessment.soil.category if assessment.soil is not None else None
        cap = single_dose_max_mm(category)
        dose = round_to(decision.depletion_mm, 1.0) or 0.0
        applications = max(1, math.ceil(dose / cap))
        single = round_to(dose / applications, 1.0) or 0.0
        raw_volume = dose * inputs.parcel.area_ha * 10.0  # 1 mm on 1 ha = 10 m³
        volume = round_to(raw_volume, 1.0 if raw_volume >= 10 else 0.1)
        params.update(
            {
                "dose_mm": dose,
                "single_dose_mm": single,
                "single_dose_max_mm": cap,
                "applications": applications,
                "light_soil": int(category in (SoilCategory.I, SoilCategory.II)),
                "volume_m3": volume or 0.0,
                "severe": int(stress_coefficient(bday.dr_mm, balance.taw_mm, balance.p) < WAIT_MIN_KS),
            }
        )
        fields.update(
            dose_mm=dose,
            single_dose_max_mm=cap,
            applications=applications,
            volume_m3=volume,
            within_days=decision.within_days,
        )
        src = computed_source(inputs.weather.source, inputs.soil.source)
        dose_start = inputs.analysis_date
        if decision.within_days is not None:
            irrigate_by = inputs.analysis_date + timedelta(days=decision.within_days)
            fields["irrigate_by"] = irrigate_by
            params["within_days"] = decision.within_days
            params["irrigate_by"] = irrigate_by.isoformat()
            dose_start = irrigate_by
            src = f"{src}; {SOURCE_FORECAST}" if decision.within_days > 0 else src
        evidence.append(
            indicator(
                "irrigation_dose_mm",
                dose,
                "mm",
                src,
                level=Confidence.MEDIUM if not decision.within_days else Confidence.LOW,
                reason="root_zone" if not decision.within_days else "forecast",
                start=dose_start,
                end=dose_start,
            )
        )
        evidence.append(
            indicator(
                "irrigation_volume_m3",
                volume,
                "m³",
                f"{src}; powierzchnia działki: GUGiK ULDK",
                level=Confidence.MEDIUM if not decision.within_days else Confidence.LOW,
                reason="irrigation_volume",
                start=dose_start,
                end=dose_start,
            )
        )
    return _advice(decision.status, inputs, forecast_use, params, evidence=evidence, **fields)


def _evidence(assessment: Assessment) -> list[Indicator]:
    """Root-zone indicators already computed by the assessment (same value, source, period)."""
    assert assessment.current is not None
    keys = ("root_zone_depletion_mm", "raw_mm", "taw_mm", "root_zone_available_mm", "ks")
    by_key = {i.key: i for i in assessment.current.indicators if i.value is not None}
    return [by_key[k] for k in keys if k in by_key]


# --- rule for the recommendation list (category irrigation, sorted last) ----------------------------


def _advice_for(ctx: RuleContext) -> IrrigationAdvice:
    return irrigation_advice(ctx.assessment, ctx.inputs)


def _condition(ctx: RuleContext) -> bool:
    return _advice_for(ctx).status in ADVISED


def _rule_evidence(ctx: RuleContext) -> list[Indicator]:
    return _advice_for(ctx).evidence


def _rule_params(ctx: RuleContext) -> dict[str, ParamValue]:
    return _advice_for(ctx).params


IRRIGATION_RULES: list[Rule] = [
    Rule("irrigation", Category.IRRIGATION, 1, _condition, _rule_evidence, _rule_params),
]
