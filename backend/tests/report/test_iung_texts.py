"""Report texts for the official IUNG-PIB threshold (G1): verdict, missing reason, source and limitation."""

from datetime import date

from app.report.models import Report
from tests.report.builders import report_for


def _main(r: Report, sid: str) -> str:
    return "\n".join(next(s for s in r.sections if s.id == sid).paragraphs_pl)


def _section(r: Report, sid: str) -> str:
    s = next(s for s in r.sections if s.id == sid)
    return "\n".join(s.paragraphs_pl + s.details_pl)


def test_dry_maize_says_official_drought_with_numbers_and_source() -> None:
    r = report_for()  # dry summer, maize, loamy sand (category II), 15 VII 2024
    current = _section(r, "current")
    assert "Dz. U." not in _main(r, "current")  # the legal citation stays in the details
    assert "Oficjalny wskaźnik suszy rolniczej (IUNG-PIB)" in current
    assert "188 mm niedoboru" in current and "kategorii II" in current
    assert "jest susza rolnicza" in current
    assert "Dz. U. 2019 poz. 739" in current  # citation in the details
    sources = _section(r, "sources")
    assert "Dz. U. 2019 poz. 739" in sources and "wbudowana w aplikację" in sources
    limitations = _section(r, "limitations")
    assert "Nie użyto oficjalnych progów" not in limitations
    assert "susza.iung.pulawy.pl" in limitations


def test_wet_maize_says_no_official_drought() -> None:
    r = report_for(precip=lambda d: 12.0)
    current = _section(r, "current")
    assert "suszy rolniczej nie ma" in current
    assert "jest susza rolnicza" not in current


def test_grassland_says_there_is_no_official_threshold() -> None:
    r = report_for(crop_id="grassland")
    current = _section(r, "current")
    assert "nie ma oficjalnego progu suszy rolniczej IUNG-PIB" in current
    assert "Nie użyto oficjalnych progów" in _section(r, "limitations")
    assert "Dz. U. 2019 poz. 739" not in _section(r, "sources")


def test_off_season_says_iung_does_not_assess_now() -> None:
    r = report_for(crop_id="winter_wheat", day=date(2024, 11, 21))
    assert "nie ocenia tej uprawy w tym terminie" in _section(r, "current")
