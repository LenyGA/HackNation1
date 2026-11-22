"""API contract. Mirrored by hand in frontend/src/api/types.ts — announce changes to the whole team."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.models import Parcel, SourceStatus
from app.crops.catalog import CropKind
from app.report.models import Report


class Health(BaseModel):
    status: str
    app: str
    version: str


class CropOut(BaseModel):
    id: str
    name_pl: str
    kind: CropKind


class ParcelOut(Parcel):
    pass


class AnalysisCreate(BaseModel):
    parcel_id: str
    crop_id: str
    analysis_date: date
    # Farm mode (G11): more parcels of the same farm; empty = single-parcel analysis, unchanged.
    # The hard cap only bounds the body; the limit the farmer sees is checked in AnalysisRequest.
    extra_parcel_ids: list[str] = Field(default_factory=list, max_length=20)


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
