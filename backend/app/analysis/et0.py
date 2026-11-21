"""Reference evapotranspiration ET0, FAO-56 Penman-Monteith, daily time step (Allen et al. 1998, eq. 6).

Used only for the NASA POWER fallback, which (unlike Open-Meteo) does not publish ET0. Pure function, no I/O.
"""

import math
from datetime import date

SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1
STEFAN_BOLTZMANN = 4.903e-9  # MJ K-4 m-2 day-1
ALBEDO = 0.23  # grass reference crop


def saturation_vapour_pressure_kpa(t_c: float) -> float:
    """FAO-56 eq. 11."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def extraterrestrial_radiation_mj(lat_deg: float, day: date) -> float:
    """Ra, FAO-56 eq. 21-25."""
    j = day.timetuple().tm_yday
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)
    delta = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (
        24
        * 60
        / math.pi
        * SOLAR_CONSTANT
        * dr
        * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    )


def et0_fao56_mm(
    *,
    day: date,
    lat_deg: float,
    elevation_m: float,
    tmax_c: float,
    tmin_c: float,
    ea_kpa: float,
    wind_2m_ms: float,
    rs_mj: float,
) -> float:
    """Daily ET0 in mm.

    `ea_kpa` = actual vapour pressure, `rs_mj` = incoming shortwave radiation (MJ m-2 day-1).
    """
    t_mean = (tmax_c + tmin_c) / 2
    delta = 4098 * saturation_vapour_pressure_kpa(t_mean) / (t_mean + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    es = (saturation_vapour_pressure_kpa(tmax_c) + saturation_vapour_pressure_kpa(tmin_c)) / 2
    ra = extraterrestrial_radiation_mj(lat_deg, day)
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = (1 - ALBEDO) * rs_mj
    rel_rs = min(rs_mj / rso, 1.0) if rso > 0 else 0.0
    rnl = (
        STEFAN_BOLTZMANN
        * ((tmax_c + 273.16) ** 4 + (tmin_c + 273.16) ** 4)
        / 2
        * (0.34 - 0.14 * math.sqrt(max(ea_kpa, 0.0)))
        * (1.35 * rel_rs - 0.35)
    )
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * 900 / (t_mean + 273) * wind_2m_ms * max(es - ea_kpa, 0.0)
    den = delta + gamma * (1 + 0.34 * wind_2m_ms)
    return float(max(num / den, 0.0))
