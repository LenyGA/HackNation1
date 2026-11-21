from datetime import date

import pytest

from app.analysis.et0 import et0_fao56_mm, extraterrestrial_radiation_mj, saturation_vapour_pressure_kpa


def test_fao56_example_18_brussels() -> None:
    """FAO-56 Example 18: Brussels, 6 July, 50°48'N, 100 m a.s.l. -> ET0 = 3.9 mm/day."""
    et0 = et0_fao56_mm(
        day=date(2025, 7, 6),
        lat_deg=50 + 48 / 60,
        elevation_m=100,
        tmax_c=21.5,
        tmin_c=12.3,
        ea_kpa=1.409,
        wind_2m_ms=2.078,
        rs_mj=22.07,
    )
    assert et0 == pytest.approx(3.9, abs=0.1)


def test_fao56_example_8_extraterrestrial_radiation() -> None:
    """FAO-56 Example 8: 20°S on 3 September -> Ra = 32.2 MJ m-2 day-1."""
    assert extraterrestrial_radiation_mj(-20.0, date(2025, 9, 3)) == pytest.approx(32.2, abs=0.2)


@pytest.mark.parametrize(("t_c", "es"), [(1.0, 0.657), (21.5, 2.564), (35.0, 5.623)])
def test_saturation_vapour_pressure_table(t_c: float, es: float) -> None:
    """FAO-56 Annex 2, Table 2.3."""
    assert saturation_vapour_pressure_kpa(t_c) == pytest.approx(es, abs=0.002)


def test_et0_never_negative_in_winter() -> None:
    et0 = et0_fao56_mm(
        day=date(2025, 1, 10),
        lat_deg=54.0,
        elevation_m=10,
        tmax_c=-5.0,
        tmin_c=-12.0,
        ea_kpa=0.3,
        wind_2m_ms=0.5,
        rs_mj=1.0,
    )
    assert et0 >= 0.0
