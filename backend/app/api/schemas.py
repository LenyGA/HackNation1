"""API contract. Mirrored by hand in frontend/src/api/types.ts — announce changes to the whole team."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from app.core.models import Parcel, SourceStatus
from app.report.models import Report


class Health(BaseModel):
    status: str
    app: str
    version: str


class CropOut(BaseModel):
    id: str
    name_pl: str


class ParcelOut(Parcel):
    pass


class AnalysisCreate(BaseModel):
    parcel_id: str
    crop_id: str
    analysis_date: date


class AnalysisCreated(BaseModel):
    id: str


class AnalysisState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SourceProgressState(StrEnum):
    PENDING = "pending"
    OK = SourceStatus.OK.value
    DEGRADED = SourceStatus.DEGRADED.value
    MISSING = SourceStatus.MISSING.value


class SourceProgress(BaseModel):
    name: str
    label_pl: str
    status: SourceProgressState


class AnalysisStatus(BaseModel):
    id: str
    status: AnalysisState
    sources: list[SourceProgress]
    report_id: str | None = None
    error_pl: str | None = None


# The report model lives with the report builder; the API serves it unchanged.
ReportOut = Report


class ErrorOut(BaseModel):
    detail: str
