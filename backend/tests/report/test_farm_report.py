"""Farm mode (G11, plan33 M7) in the report: m³ over the summed area, wording, Report.farm, PDF HTML."""

import dataclasses
import json
from typing import Any

import pytest

from app.analysis.assessment import Assessment
from app.analysis.context import AnalysisInputs
from app.core.models import Parcel
from app.recommendations.engine import recommend
from app.recommendations.irrigation import irrigation_advice
from app.recommendations.retention_methods import DAYS_PER_YEAR, POND_MIN_VOLUME_M3
from app.report.builder import ParcelSource, build_report
from app.report.models import Report
from app.report.pdf import render_html
from tests.analysis.test_farm import near
from tests.recommendations.builders import basin, hydro, scenario
from tests.report.builders import CREATED

KW: dict[str, Any] = {"surface": basin, "hydro_data": lambda p: hydro(p, ditch_m=200.0)}


def _report(a: Assessment, inputs: AnalysisInputs) -> Report:
    recs = recommend(a, inputs)
    irr = irrigation_advice(a, inputs, today=inputs.analysis_date)
    return build_report(
        report_id="x" * 22,
        created_at=CREATED,
        inputs=inputs,
        assessment=a,
        recommendations=recs,
        irrigation=irr,
        parcel_source=ParcelSource(fetched_at=CREATED),
    )


def _build(extra: tuple[Parcel, ...] | None, **kw: Any) -> Report:
    a, inputs, _ = scenario(**{**KW, **kw})
    if extra is not None:
        inputs = dataclasses.replace(inputs, extra_parcels=extra)
    return _report(a, inputs)


def _extras(main: Parcel) -> tuple[Parcel, Parcel]:
    # 2 ha touching on the east + 1 ha 500 m north: the farm is 6 ha = 2 × the 3 ha main parcel.
    return near(main, 200, 0, 200, 100, "141201_1.0001.2"), near(main, 0, 650, 100, 100, "141201_1.0001.3")


@pytest.fixture(scope="module")
def pair() -> tuple[Report, Report]:
    single = _build(None)
    farm = _build(_extras(single.parcel))
    return single, farm


def _texts(r: Report) -> str:
    out: list[str] = [r.irrigation.text_pl]
    out += [p for s in r.sections for p in s.paragraphs_pl]
    if r.water_plan:
        out += r.water_plan.text_pl
    if r.simulation:
        out += r.simulation.text_pl
    if r.retention_plan:
        out.append(r.retention_plan.coverage.text_pl)
        out += [m.reason_pl for m in r.retention_plan.methods]
    if r.irrigation_economics:
        t = r.irrigation_economics.text_pl
        out += t if isinstance(t, list) else [t]
    return "\n".join(out)


def _dump(r: Report) -> dict[str, Any]:
    d = json.loads(r.model_dump_json())
    d.pop("id"), d.pop("created_at")
    return d


# --- regression: one parcel is exactly what it was ---------------------------------------------------


def test_single_parcel_has_no_farm(pair: tuple[Report, Report]) -> None:
    assert pair[0].farm is None


@pytest.mark.parametrize("kw", [{}, {"surface": None}, {"crop_id": "winter_wheat"}])
def test_empty_extra_parcels_is_identical_to_default(kw: dict[str, Any]) -> None:
    a, inputs, _ = scenario(**{**KW, **kw})  # same inputs (fetched_at), so only extra_parcels differs
    explicit = dataclasses.replace(inputs, extra_parcels=())
    assert inputs.water_area_ha == inputs.parcel.area_ha and inputs.farm_parcels == 1
    assert _dump(_report(a, inputs)) == _dump(_report(a, explicit))


def test_single_parcel_texts_say_na_dzialke(pair: tuple[Report, Report]) -> None:
    text = _texts(pair[0])
    assert "gospodarstwa" not in text and "Gospodarstwo" not in text
    assert "m³ wody na całą działkę" in pair[0].irrigation.text_pl
    assert pair[0].water_plan is not None
    assert "m³ na działkę" in "\n".join(pair[0].water_plan.text_pl)


def test_single_parcel_html_has_no_farm_block(pair: tuple[Report, Report]) -> None:
    for variant in ("full", "basic"):
        assert "Gospodarstwo" not in render_html(pair[0], variant=variant)  # type: ignore[arg-type]


# --- farm of 3 parcels --------------------------------------------------------------------------------


def test_farm_model(pair: tuple[Report, Report]) -> None:
    single, farm = pair
    f = farm.farm
    assert f is not None
    assert f.count == 3
    assert f.total_area_ha == pytest.approx(single.parcel.area_ha * 2, abs=0.01)
    assert [p.id for p in f.parcels] == ["141201_1.0001.2", "141201_1.0001.3"]
    assert f.parcels[0].distance_m == 0.0
    assert f.parcels[1].distance_m == 500.0
    assert f.parcels[0].area_ha == pytest.approx(2.0, abs=1e-3)
    assert f.text_pl and "3 działki" in f.text_pl[0]
    assert farm.parcel == single.parcel  # only the main parcel is analysed


def test_farm_irrigation_volume_scales_with_area(pair: tuple[Report, Report]) -> None:
    single, farm = pair
    s, f = single.irrigation, farm.irrigation
    assert s.dose_mm is not None and s.volume_m3 is not None and f.volume_m3 is not None
    assert f.dose_mm == s.dose_mm and f.applications == s.applications
    assert f.volume_m3 == pytest.approx(2 * s.volume_m3, abs=2)
    assert "m³ wody na 3 działki gospodarstwa" in f.text_pl
    assert "na całą działkę" not in f.text_pl


def test_farm_water_plan_scales_with_area(pair: tuple[Report, Report]) -> None:
    s, f = pair[0].water_plan, pair[1].water_plan
    assert s is not None and f is not None
    assert (s.season_median_mm, s.season_p80_mm, s.season_p90_mm, s.critical_p80_mm) == (
        f.season_median_mm,
        f.season_p80_mm,
        f.season_p90_mm,
        f.critical_p80_mm,
    )
    assert [m.deficit_p80_m3_ha for m in s.months] == [m.deficit_p80_m3_ha for m in f.months]
    for name in ("season_p80_m3_parcel", "season_p80_m3_parcel_gross", "critical_p80_m3_parcel_gross"):
        sv, fv = getattr(s, name), getattr(f, name)
        assert sv is not None and fv is not None, name
        assert fv == pytest.approx(2 * sv, abs=20), name
    assert "na 3 działki gospodarstwa" in "\n".join(f.text_pl)
    assert "na działkę" not in "\n".join(f.text_pl)


def test_farm_retention_coverage_needs_scale(pair: tuple[Report, Report]) -> None:
    s, f = pair[0].retention_plan, pair[1].retention_plan
    assert s is not None and f is not None
    sc, fc = s.coverage, f.coverage
    assert sc.full_need_m3 is not None and fc.full_need_m3 is not None
    assert fc.full_need_m3 == pytest.approx(2 * sc.full_need_m3, abs=20)
    if sc.rescue_need_m3 is not None:
        assert fc.rescue_need_m3 == pytest.approx(2 * sc.rescue_need_m3, abs=20)
    assert fc.volume_m3 == sc.volume_m3  # the depression is on the main parcel only
    assert "na 3 działki gospodarstwa" in fc.text_pl and "działce głównej" in fc.text_pl


def test_farm_simulation_m3_scale(pair: tuple[Report, Report]) -> None:
    s, f = pair[0].simulation, pair[1].simulation
    assert s is not None and f is not None
    for ss, fs in zip(s.strategies, f.strategies, strict=True):
        for sy, fy in zip(ss.years, fs.years, strict=True):
            assert sy.irrigation_mm_median == fy.irrigation_mm_median
            if sy.irrigation_m3_parcel_p80 is not None:
                assert fy.irrigation_m3_parcel_p80 == pytest.approx(2 * sy.irrigation_m3_parcel_p80, abs=20)


def test_farm_economics_use_summed_area(pair: tuple[Report, Report]) -> None:
    s, f = pair[0].irrigation_economics, pair[1].irrigation_economics
    assert s is not None and f is not None
    assert f.area_ha == pytest.approx(2 * s.area_ha, abs=1e-3)


def test_farm_well_permit_uses_farm_need(pair: tuple[Report, Report]) -> None:
    """The well supplies the farm need minus what the main parcel's depression holds (permit threshold)."""

    def check(r: Report) -> float:
        assert r.retention_plan is not None
        cov = r.retention_plan.coverage
        well = next(m for m in r.retention_plan.methods if m.id == "well")
        ev = next(e for e in well.evidence if e.key == "irrigation_avg_m3_per_day")
        assert ev.value is not None and cov.full_need_m3 is not None
        vol = cov.volume_m3 or 0.0
        kept = vol if vol >= POND_MIN_VOLUME_M3 else 0.0
        assert ev.value * DAYS_PER_YEAR == pytest.approx(cov.full_need_m3 - kept, rel=0.01)
        return ev.value

    assert check(pair[1]) > 2 * check(pair[0]) - 0.1


@pytest.mark.parametrize("variant", ["full", "basic"])
def test_farm_pdf_html_variants(pair: tuple[Report, Report], variant: str) -> None:
    html = render_html(pair[1], variant=variant)  # type: ignore[arg-type]
    assert "Gospodarstwo: <b>3 działki" in html
    assert "141201_1.0001.2" in html and "przylega do głównej" in html
    assert "141201_1.0001.3" in html and "500 m od głównej" in html


def test_farm_report_roundtrips_json(pair: tuple[Report, Report]) -> None:
    again = Report.model_validate_json(pair[1].model_dump_json())
    assert again.model_dump_json() == pair[1].model_dump_json()
    assert again.farm is not None and again.farm.count == 3
