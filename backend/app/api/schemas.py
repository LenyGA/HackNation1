"""API contract. Mirrored by hand in frontend/src/api/types.ts — announce changes to the whole team."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel

from app.core.models import Parcel, SourceStatus


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


class ReportSection(BaseModel):
    id: str
    title_pl: str
    paragraphs_pl: list[str]


class ReportOut(BaseModel):
    id: str
    created_at: datetime
    app: str
    parcel: Parcel
    crop: CropOut
    analysis_date: date
    sections: list[ReportSection]


class ErrorOut(BaseModel):
    detail: str
