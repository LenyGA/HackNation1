"""Run one full analysis in-process, through the same job pipeline as `POST /api/analyses` (plan2 K0.3).

Used by `test_reports.py` (`pytest -m e2e`) and usable from a shell to try new reference parcels:
    PYTHONPATH=. python -m tests.e2e.runner 141201_1.0001.6509 winter_wheat 2019-07-15
"""

import asyncio
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.api import jobs
from app.api.schemas import AnalysisState
from app.core.config import get_settings, today_local
from app.core.http import close_client
from app.core.models import AnalysisRequest
from app.crops.catalog import get_crop
from app.report.models import Report
from app.report.storage import load_report

PARCELS_PATH = Path(__file__).with_name("parcels.yaml")
BASELINE_PATH = Path(__file__).with_name("baseline.json")
CURRENT = "current"  # date label in parcels.yaml: the analysis runs for today's (Polish) date


@dataclass(frozen=True)
class Case:
    key: str
    parcel_id: str
    crop_id: str
    date_label: str
    purpose: str

    @property
    def analysis_date(self) -> date:
        return today_local() if self.date_label == CURRENT else date.fromisoformat(self.date_label)

    @property
    def case_id(self) -> str:
        return f"{self.key}@{self.date_label}"


def load_cases(path: Path = PARCELS_PATH) -> list[Case]:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Case(
            key=p["key"],
            parcel_id=p["id"],
            crop_id=p["crop"],
            date_label=str(d),
            purpose=p["purpose"],
        )
        for p in raw["parcels"]
        for d in raw["dates"]
    ]


@dataclass(frozen=True)
class Outcome:
    state: AnalysisState
    elapsed_s: float
    report: Report | None
    error_pl: str | None
    source_states: dict[str, str]


async def run_analysis(parcel_id: str, crop_id: str, analysis_date: date) -> Outcome:
    crop = get_crop(crop_id)
    if crop is None:
        raise ValueError(f"unknown crop {crop_id!r}")
    request = AnalysisRequest(parcel_id=parcel_id, crop_id=crop_id, analysis_date=analysis_date)
    job = jobs.Job(id="e2e", request=request, crop=crop)
    t0 = time.perf_counter()
    await jobs._run(job)
    elapsed = time.perf_counter() - t0
    report = await load_report(job.report_id) if job.report_id else None
    return Outcome(
        state=job.state,
        elapsed_s=elapsed,
        report=report,
        error_pl=job.error_pl,
        source_states={name: state.value for name, state in job.sources.items()},
    )


def summarize(outcome: Outcome) -> dict[str, Any]:
    """The baseline record of one case: what later modules may only change on purpose."""
    r = outcome.report
    return {
        "analysis_date": r.analysis_date.isoformat() if r else None,
        "level": r.headline.level if r else None,
        "complete": r.complete if r else None,
        "recommendations": sorted(rec.id for rec in r.recommendations) if r else [],
        "irrigation": r.irrigation.status if r else None,
        "sources": outcome.source_states,
        "elapsed_s": round(outcome.elapsed_s, 1),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    parcel_id, crop_id, day = argv
    get_settings().db_path = Path(".cache/e2e-reports.sqlite3")

    async def run_once() -> Outcome:
        try:
            return await run_analysis(parcel_id, crop_id, date.fromisoformat(day))
        finally:
            await close_client()

    outcome = asyncio.run(run_once())
    print(summarize(outcome))
    if outcome.report:
        for s in outcome.report.sources:
            print(f"  {s.name:12s} {s.status.value:9s} {s.message_pl or ''}")
    return 0 if outcome.state is AnalysisState.DONE else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
