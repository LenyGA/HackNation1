"""Asynchronous analysis jobs (plan, decision 1): `POST /api/analyses` returns an id at once, the
frontend polls `GET /api/analyses/{id}` and sees the state of every source.

Flow: ULDK parcel → all sources in parallel (each with its own time budget) → assessment → recommendations →
irrigation → report → SQLite. A failing source never stops the analysis: it becomes `missing` and the report
says so. Jobs live in memory only (no personal data, no IP address); reports are persisted.
"""

import asyncio
import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.analysis.assessment import assess
from app.analysis.context import AnalysisInputs
from app.api.schemas import AnalysisState, AnalysisStatus, SourceProgress, SourceProgressState
from app.core.config import get_settings
from app.core.models import AnalysisRequest, Parcel, SourceResult
from app.crops.catalog import Crop
from app.recommendations.engine import recommend
from app.recommendations.irrigation import irrigation_advice
from app.report.builder import ParcelSource, build_report
from app.report.labels_pl import SOURCE_LABELS
from app.report.storage import new_report_id, save_report
from app.sources import dem, flood, groundwater, hydro, landcover, open_meteo, sentinel2, soilgrids, uldk
from app.sources.base import missing, now_utc

log = logging.getLogger(__name__)

JOB_ID_BYTES = 16
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")
JOB_TTL_S = 3600.0
MAX_JOBS = 1000
# Analyses queued or running at once; further requests are refused (HTTP 429) instead of piling up.
MAX_PENDING_TASKS = 50

MSG_UNEXPECTED = "Wystąpił nieoczekiwany błąd podczas analizy. Spróbuj ponownie za chwilę."
MSG_SOURCE_ERROR = "Nie udało się pobrać tych danych z powodu błędu po stronie serwisu."

Fetcher = Callable[[Parcel, date], Awaitable[SourceResult[Any]]]


@dataclass(frozen=True)
class SourceSpec:
    name: str
    fetch: Fetcher
    source: str  # used only for the fallback `missing` result after an unexpected exception
    license: str


SOURCES: list[SourceSpec] = [
    SourceSpec(
        open_meteo.NAME,
        open_meteo.fetch,
        f"{open_meteo.SOURCE_ARCHIVE}; {open_meteo.SOURCE_POWER}",
        f"{open_meteo.LICENSE_OPEN_METEO}; {open_meteo.LICENSE_POWER}",
    ),
    SourceSpec(sentinel2.NAME, sentinel2.fetch, sentinel2.SOURCE, sentinel2.LICENSE),
    SourceSpec(soilgrids.NAME, soilgrids.fetch, soilgrids.SOURCE, soilgrids.LICENSE),
    SourceSpec(dem.NAME, dem.fetch, dem.SOURCE_COP, dem.LICENSE_COP),
    SourceSpec(hydro.NAME, hydro.fetch, hydro.SOURCE, hydro.LICENSE),
    SourceSpec(landcover.NAME, landcover.fetch, landcover.SOURCE, landcover.LICENSE),
    SourceSpec(flood.NAME, flood.fetch, flood.SOURCE, flood.LICENSE),
    SourceSpec(groundwater.NAME, groundwater.fetch, groundwater.SOURCE, groundwater.LICENSE),
]
SOURCE_NAMES = [uldk.NAME, *(s.name for s in SOURCES)]


@dataclass
class Job:
    id: str
    request: AnalysisRequest
    crop: Crop
    created: float = field(default_factory=time.monotonic)
    state: AnalysisState = AnalysisState.QUEUED
    sources: dict[str, SourceProgressState] = field(
        default_factory=lambda: dict.fromkeys(SOURCE_NAMES, SourceProgressState.PENDING)
    )
    report_id: str | None = None
    error_pl: str | None = None

    def status(self) -> AnalysisStatus:
        return AnalysisStatus(
            id=self.id,
            status=self.state,
            sources=[
                SourceProgress(name=name, label_pl=SOURCE_LABELS[name], status=state)
                for name, state in self.sources.items()
            ],
            report_id=self.report_id,
            error_pl=self.error_pl,
        )


_jobs: dict[str, Job] = {}
_tasks: set[asyncio.Task[None]] = set()
_semaphore: asyncio.Semaphore | None = None


def _limit() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().max_concurrent_analyses)
    return _semaphore


def valid_job_id(job_id: str) -> bool:
    return bool(JOB_ID_RE.match(job_id))


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id) if valid_job_id(job_id) else None


class QueueFull(Exception):
    """Too many analyses waiting; the client should retry later."""


_ACTIVE = (AnalysisState.QUEUED, AnalysisState.RUNNING)


def _prune() -> None:
    """Drop finished jobs older than the TTL, then the oldest finished ones above MAX_JOBS.

    Queued or running jobs are never dropped, so a polling client never sees a live job "expire".
    """
    now = time.monotonic()
    finished = [j for j in _jobs.values() if j.state not in _ACTIVE]
    for job in finished:
        if now - job.created > JOB_TTL_S:
            _jobs.pop(job.id, None)
    for job in [j for j in finished if j.id in _jobs][: max(0, len(_jobs) - MAX_JOBS + 1)]:
        _jobs.pop(job.id, None)


def start(request: AnalysisRequest, crop: Crop) -> Job:
    if len(_tasks) >= MAX_PENDING_TASKS:
        raise QueueFull
    _prune()
    job = Job(id=secrets.token_urlsafe(JOB_ID_BYTES), request=request, crop=crop)
    _jobs[job.id] = job
    task = asyncio.create_task(_run(job))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


async def _fetch_source(job: Job, spec: SourceSpec, parcel: Parcel) -> SourceResult[Any]:
    try:
        result = await spec.fetch(parcel, job.request.analysis_date)
    except Exception:  # a source must never break the whole analysis (CLAUDE.md, module boundaries)
        log.exception("source %s failed", spec.name)
        result = missing(spec.name, source=spec.source, license=spec.license, message_pl=MSG_SOURCE_ERROR)
    job.sources[spec.name] = SourceProgressState(result.status.value)
    return result


def _compute(job: Job, parcel: Parcel, parcel_source: ParcelSource, results: dict[str, Any]) -> Any:
    """CPU part of the analysis (pure functions), run in a worker thread."""
    inputs = AnalysisInputs(
        parcel=parcel,
        crop=job.crop,
        analysis_date=job.request.analysis_date,
        weather=results[open_meteo.NAME],
        soil=results[soilgrids.NAME],
        sentinel2=results[sentinel2.NAME],
        dem=results[dem.NAME],
        hydro=results[hydro.NAME],
        landcover=results[landcover.NAME],
        flood=results.get(flood.NAME),
        groundwater=results.get(groundwater.NAME),
    )
    assessment = assess(inputs)
    recommendations = recommend(assessment, inputs)
    irrigation = irrigation_advice(assessment, inputs)
    return build_report(
        report_id=new_report_id(),
        created_at=now_utc(),
        inputs=inputs,
        assessment=assessment,
        recommendations=recommendations,
        irrigation=irrigation,
        parcel_source=parcel_source,
    )


async def _run(job: Job) -> None:
    async with _limit():
        job.state = AnalysisState.RUNNING
        try:
            try:
                parcel = await uldk.get_parcel_by_id(job.request.parcel_id)
            except (uldk.ParcelNotFound, uldk.ParcelServiceError) as exc:
                # Without the parcel nothing else is fetched: no source stays "pending".
                job.sources = dict.fromkeys(SOURCE_NAMES, SourceProgressState.MISSING)
                job.state, job.error_pl = AnalysisState.FAILED, exc.message_pl
                return
            job.sources[uldk.NAME] = SourceProgressState.OK
            parcel_source = ParcelSource(fetched_at=now_utc())
            fetched = await asyncio.gather(*(_fetch_source(job, spec, parcel) for spec in SOURCES))
            results = {spec.name: r for spec, r in zip(SOURCES, fetched, strict=True)}
            report = await asyncio.to_thread(_compute, job, parcel, parcel_source, results)
            await save_report(report)
            job.report_id = report.id
            job.state = AnalysisState.DONE
        except Exception:
            log.exception("analysis %s failed", job.id)
            job.state, job.error_pl = AnalysisState.FAILED, MSG_UNEXPECTED
        finally:
            # A finished job never shows a source as still being fetched.
            for name, state in job.sources.items():
                if state is SourceProgressState.PENDING:
                    job.sources[name] = SourceProgressState.MISSING
