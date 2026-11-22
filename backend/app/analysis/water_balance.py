"""Daily root-zone water balance (FAO-56 ch. 8) and the climatic water balance KBW = P − ET0. Pure, no I/O.

FAO-56 eq. 85 without irrigation, capillary rise and runoff (no field data on them):
    Dr_i = Dr_{i-1} − P_i + ETc,adj_i,   0 ≤ Dr_i ≤ TAW   (excess above field capacity drains)
    ETc,adj = Ks · Kc · ET0
    Ks = 1                                 when Dr_{i-1} ≤ RAW
    Ks = (TAW − Dr_{i-1}) / ((1 − p)·TAW)  otherwise   (eq. 84),   RAW = p · TAW   (eq. 83)
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from app.analysis.series import Weather
from app.crops.catalog import Crop

# Outside the crop season the field is bare soil that still loses water by evaporation. FAO-56 Fig. 29 gives
# Kc_ini ≈ 0.3–0.5 for bare soil with infrequent light wetting at low ET0 (1–3 mm/day); the lower end is used.
BARE_SOIL_KC = 0.3
# Bare soil dries only its surface layer: evaporation stops once depletion reaches the total evaporable water
# TEW (FAO-56 Table 19: ≈ 6–29 mm for 0.10–0.15 m depending on texture; a middle value is used).
BARE_SOIL_TEW_MM = 20.0

KBW_WINDOW_DAYS = 60


@dataclass(frozen=True)
class BalanceDay:
    day: date
    precip_mm: float | None
    et0_mm: float | None
    kc: float  # crop coefficient used for ET on this day (bare-soil value outside the season)
    in_season: bool
    ks: float
    etc_mm: float | None  # actual evapotranspiration Ks·Kc·ET0; None on a day without data
    dr_mm: float  # root-zone depletion at the end of the day
    irrigation_mm: float = 0.0  # net irrigation applied at the start of the day (simulations only)

    @property
    def gap(self) -> bool:
        return self.etc_mm is None

    @property
    def stressed(self) -> bool:
        """Crop water stress (Ks < 1) on a day with a crop on the field."""
        return self.in_season and not self.gap and self.ks < 1.0


@dataclass(frozen=True)
class RootZoneBalance:
    taw_mm: float
    raw_mm: float
    p: float
    days: list[BalanceDay]
    _index: dict[date, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_index", {d.day: i for i, d in enumerate(self.days)})

    @property
    def gap_days(self) -> int:
        return sum(1 for d in self.days if d.gap)

    def at(self, day: date) -> BalanceDay | None:
        i = self._index.get(day)
        return None if i is None else self.days[i]

    def between(self, start: date, end: date) -> list[BalanceDay]:
        return [d for d in self.days if start <= d.day <= end]


def stress_coefficient(dr_mm: float, taw_mm: float, p: float) -> float:
    raw = p * taw_mm
    if dr_mm <= raw:
        return 1.0
    return max(0.0, (taw_mm - dr_mm) / ((1.0 - p) * taw_mm))


def root_zone_balance(
    days: Sequence[date],
    precip_mm: Sequence[float | None],
    et0_mm: Sequence[float | None],
    kc: Sequence[float],
    in_season: Sequence[bool],
    taw_mm: float,
    p: float,
    dr0_mm: float = 0.0,
    irrigate: Sequence[bool] | None = None,
    et0_factor: float = 1.0,
    dose_cap_mm: float | None = None,
    schedule_mm: Sequence[float] | None = None,
) -> RootZoneBalance:
    """Run the daily balance. A day without P or ET0 keeps the previous depletion and is marked as a gap.

    `irrigate` (simulations): on days marked True, when the depletion exceeds RAW the root zone is refilled to
    field capacity at the start of the day (FAO-56 ch. 8, irrigation at the management allowed depletion;
    the net dose equals Dr), or with at most `dose_cap_mm` per day (a realistic sprinkler application).
    `schedule_mm` (simulations): a fixed irrigation schedule instead of the RAW trigger — on each day at most
    the scheduled dose, never more than the depletion (the soil takes no water above field capacity).
    `et0_factor` scales ET0 (climate-change scenarios).
    """
    if taw_mm <= 0:
        raise ValueError("TAW must be positive")
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    if not len(days) == len(precip_mm) == len(et0_mm) == len(kc) == len(in_season):
        raise ValueError("all series must have the same length")
    if irrigate is not None and len(irrigate) != len(days):
        raise ValueError("irrigate must have the same length as days")
    if schedule_mm is not None and (len(schedule_mm) != len(days) or irrigate is not None):
        raise ValueError("schedule_mm must match days and cannot be combined with irrigate")
    dr = min(max(dr0_mm, 0.0), taw_mm)
    raw = p * taw_mm
    out: list[BalanceDay] = []
    for i, (d, rain, et0, k, season) in enumerate(zip(days, precip_mm, et0_mm, kc, in_season, strict=True)):
        irrigation = 0.0
        if irrigate is not None and irrigate[i] and dr > raw:
            irrigation = dr if dose_cap_mm is None else min(dr, dose_cap_mm)
            dr -= irrigation
        elif schedule_mm is not None and schedule_mm[i] > 0:
            irrigation = min(dr, schedule_mm[i])
            dr -= irrigation
        ks = stress_coefficient(dr, taw_mm, p)
        etc: float | None = None
        if rain is not None and et0 is not None:
            etc = ks * k * et0 * et0_factor
            if not season:
                # Bare soil: evaporation only from the surface layer, never below TEW of depletion.
                etc = min(etc, max(0.0, min(BARE_SOIL_TEW_MM, taw_mm) - max(dr - rain, 0.0)))
            dr = min(max(dr - rain + etc, 0.0), taw_mm)
        out.append(BalanceDay(d, rain, et0, k, season, ks, etc, dr, irrigation))
    return RootZoneBalance(taw_mm=taw_mm, raw_mm=raw, p=p, days=out)


def crop_calendar(weather: Weather, crop: Crop) -> tuple[list[float], list[bool]]:
    """Daily Kc and in-season flags for the weather dates (bare-soil Kc outside the season)."""
    kc: list[float] = []
    season: list[bool] = []
    for d in weather.dates:
        s = crop.in_season(d)
        season.append(s)
        kc.append(crop.kc(d) if s else max(crop.kc_off_season, BARE_SOIL_KC))
    return kc, season


def crop_root_zone_balance(weather: Weather, crop: Crop, taw_mm: float) -> RootZoneBalance:
    """Continuous balance over the whole weather series for the crop's calendar, starting at field capacity.

    The series starts on 1 October of year Y−11, about five months before the first analysed vegetation season
    (March Y−10); the assumed initial state is forgotten after that autumn–winter recharge (spin-up).
    """
    kc, season = crop_calendar(weather, crop)
    return root_zone_balance(weather.dates, weather.precip_mm, weather.et0_mm, kc, season, taw_mm, crop.p)


def kbw_mm(weather: Weather, end: date, days: int = KBW_WINDOW_DAYS) -> float | None:
    """Climatic water balance P − ET0 over `days` days ending on `end` (inclusive)."""
    start, end = weather.window(end, days)
    return weather.kbw_sum(start, end)
