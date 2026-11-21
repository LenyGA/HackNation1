"""End-to-end reports for the reference parcels (plan2 K0.3, plan M9.1–M9.2). Needs network, slow:

    pytest -m e2e tests/e2e/test_reports.py                              # check against baseline.json
    RSW_E2E_UPDATE_BASELINE=1 pytest -m e2e tests/e2e/test_reports.py    # rewrite baseline.json
    RSW_E2E_WARM=1 pytest -m e2e tests/e2e/test_reports.py               # reuse backend/.cache (quick rerun)

Every case runs on an empty cache (as for a parcel nobody analysed before; only the ULDK parcel lookup is
reused from the first date of the same parcel), through the same job pipeline as
`POST /api/analyses`. Checks: report within 30 s, all mandatory sections in order, every number with a source,
nothing dated after the analysis date, missing data stated explicitly.

The baseline is the reference for the module gates (plan2 rozdz. 3, W): for the historical date the
deficit level and the recommendation ids must stay the same unless a module changes them on purpose, which
is then recorded by rewriting the baseline in that module's commit. Live sources fail now and then; when
the weather or soil status differs from the baseline, the level is not compared, and when any source status
differs, the recommendations are not compared (a missing source legitimately changes advice). Each skipped
comparison is a `BaselineNote` warning in the pytest summary. For the current date the data change daily, so
differences are warnings only. The 30 s budget of a parcel's second date leaves out the ULDK lookup.
"""

import json
import os
import warnings
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.api import jobs
from app.api.schemas import AnalysisState
from app.core.cache import DiskCache
from app.core.config import get_settings
from app.core.models import SourceStatus
from app.report.models import SECTION_ORDER, EvidenceItem, Report
from app.sources import uldk
from tests.e2e.runner import BASELINE_PATH, CURRENT, Case, load_cases, run_analysis, summarize

BUDGET_S = 30.0
UPDATE_BASELINE = os.environ.get("RSW_E2E_UPDATE_BASELINE") == "1"
# Each cold case sends full 10-year requests to every source; Open-Meteo and GUGiK throttle a burst of them.
WARM = os.environ.get("RSW_E2E_WARM") == "1"
# ULDK blocks an address for minutes after a few dozen lookups (docs/DATA_SOURCES.md), so each parcel is
# looked up once per session and handed to the next case's cold cache; every other source stays cold.
_parcels: dict[str, Any] = {}

CASES = load_cases()
_results: dict[str, dict[str, Any]] = {}


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    data: dict[str, Any] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module", autouse=True)
def _baseline_writer() -> Iterator[None]:
    yield
    if UPDATE_BASELINE and _results:
        merged = {**_load_baseline(), **_results}
        BASELINE_PATH.write_text(
            json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


@pytest.fixture
def isolated_storage(
    case: Case, request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Cold disk cache (unless RSW_E2E_WARM=1) and a throwaway report database for every case."""
    monkeypatch.setattr(get_settings(), "db_path", tmp_path / "reports.sqlite3")
    if WARM:
        yield
        return
    cold: DiskCache = request.getfixturevalue("tmp_cache")
    key = {"id": case.parcel_id}
    if case.parcel_id in _parcels:
        cold.set(uldk.NAME, key, _parcels[case.parcel_id])
    yield
    found = cold.get(uldk.NAME, key)
    if found is not None:
        _parcels[case.parcel_id] = found


def _evidence(report: Report) -> Iterator[tuple[str, EvidenceItem]]:
    for section in report.sections:
        for item in section.indicators:
            yield f"section {section.id}", item
    for rec in report.recommendations:
        for item in rec.evidence:
            yield f"recommendation {rec.id}", item
    for item in report.irrigation.evidence:
        yield "irrigation", item


def _check_report(report: Report, analysis_date: date) -> None:
    assert report.analysis_date == analysis_date
    assert [s.id for s in report.sections] == SECTION_ORDER
    assert [s.number for s in report.sections] == list(range(1, len(SECTION_ORDER) + 1))

    # Every source is listed, and every non-OK one says why (rule 4).
    assert {s.name for s in report.sources} == set(jobs.SOURCE_NAMES)
    for s in report.sources:
        assert s.source.strip(), f"{s.name}: no source description"
        assert s.license.strip(), f"{s.name}: no licence"
        if s.status is not SourceStatus.OK:
            assert s.message_pl, f"{s.name} is {s.status.value} without an explanation"
    missing = [s for s in report.sources if s.status is SourceStatus.MISSING]
    assert len(report.missing_data_pl) >= len(missing), "a missing source is not stated in the report"

    # Every number has a source; nothing comes from after the analysis date (rules 3 and 5).
    for where, item in _evidence(report):
        assert item.source.strip(), f"{where}: {item.key} has no source"
        assert item.value_pl.strip(), f"{where}: {item.key} has no formatted value"
        if item.period is not None:
            assert item.period.end <= analysis_date, f"{where}: {item.key} ends {item.period.end}"
    if report.chart is not None:
        measured = [p.day for p in report.chart.points if (p.precip_mm, p.crop_need_mm) != (None, None)]
        assert all(d <= analysis_date for d in measured), "season chart has values after the analysis date"
    if report.satellite is not None:
        assert all(p.day <= analysis_date for p in report.satellite.points), "satellite scene after the date"

    # Without a complete assessment there is no advice (rule 2).
    if not report.complete:
        assert report.recommendations == []
    assert report.limitations_pl, "the report has no limitations section content"


class BaselineNote(UserWarning):
    """A baseline comparison that could not be made; listed in the pytest warnings summary."""


# The deficit level, completeness and the irrigation status come from weather and soil only
# (analysis/assessment.py); recommendations also read terrain, ditches, land cover, flood and groundwater.
LEVEL_SOURCES = ("open_meteo", "soilgrids")
LEVEL_KEYS = ("level", "complete", "irrigation")


def _compare_with_baseline(case: Case, summary: dict[str, Any]) -> None:
    if UPDATE_BASELINE:
        return
    expected = _load_baseline().get(case.case_id)
    if expected is None:
        warnings.warn(f"{case.case_id}: no baseline entry, nothing compared", BaselineNote, stacklevel=2)
        return
    if case.date_label == CURRENT:
        diff = {
            k: (expected.get(k), summary[k])
            for k in (*LEVEL_KEYS, "recommendations")
            if expected.get(k) != summary[k]
        }
        if diff:
            warnings.warn(f"{case.case_id} (data change daily) differs: {diff}", BaselineNote, stacklevel=2)
        return

    was, now = expected.get("sources", {}), summary["sources"]
    changed = {
        name: (was.get(name), now.get(name))
        for name in sorted(set(was) | set(now))
        if was.get(name) != now.get(name)
    }
    failures: list[str] = []
    if any(name in changed for name in LEVEL_SOURCES):
        warnings.warn(
            f"{case.case_id}: level not compared, weather/soil status changed {changed}",
            BaselineNote,
            stacklevel=2,
        )
    else:
        failures += [
            f"{k}: {expected.get(k)} -> {summary[k]}" for k in LEVEL_KEYS if expected.get(k) != summary[k]
        ]
    if changed:
        warnings.warn(
            f"{case.case_id}: recommendations not compared, source status changed {changed}",
            BaselineNote,
            stacklevel=2,
        )
    elif expected.get("recommendations") != summary["recommendations"]:
        failures.append(f"recommendations: {expected.get('recommendations')} -> {summary['recommendations']}")
    if failures:
        pytest.fail(
            f"{case.case_id} differs from baseline: {'; '.join(failures)}"
            " — if this module changed it on purpose, rewrite the baseline"
        )


@pytest.mark.e2e
@pytest.mark.parametrize("case", CASES, ids=[c.case_id for c in CASES])
async def test_reference_report(case: Case, isolated_storage: None) -> None:
    analysis_date = case.analysis_date
    outcome = await run_analysis(case.parcel_id, case.crop_id, analysis_date)
    summary = summarize(outcome)
    print(f"{case.case_id} ({case.parcel_id}, {case.crop_id}, {analysis_date}): {summary}")

    assert outcome.state is AnalysisState.DONE, outcome.error_pl
    assert outcome.report is not None
    assert outcome.elapsed_s < BUDGET_S, f"{outcome.elapsed_s:.1f} s"
    _check_report(outcome.report, analysis_date)

    _results[case.case_id] = summary
    _compare_with_baseline(case, summary)
