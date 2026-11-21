from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.api.schemas import (
    AnalysisCreate,
    AnalysisCreated,
    AnalysisStatus,
    CropOut,
    ErrorOut,
    Health,
    ParcelOut,
    ReportOut,
)
from app.core.config import APP_TITLE, APP_VERSION
from app.crops.catalog import load_crops

router = APIRouter(prefix="/api")

NOT_READY = "Ta funkcja jest w budowie."


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", app=APP_TITLE, version=APP_VERSION)


@router.get("/crops", response_model=list[CropOut])
async def crops() -> list[CropOut]:
    return [CropOut(id=c.id, name_pl=c.name_pl) for c in load_crops().values()]


@router.get(
    "/parcels", response_model=ParcelOut, responses={400: {"model": ErrorOut}, 404: {"model": ErrorOut}}
)
async def parcel(
    id: str | None = Query(default=None, max_length=64),
    lat: float | None = Query(default=None, ge=48.9, le=55.0),
    lon: float | None = Query(default=None, ge=14.0, le=24.2),
) -> ParcelOut:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_READY)


@router.post("/analyses", response_model=AnalysisCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(body: AnalysisCreate) -> AnalysisCreated:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_READY)


@router.get("/analyses/{analysis_id}", response_model=AnalysisStatus, responses={404: {"model": ErrorOut}})
async def analysis_status(analysis_id: str) -> AnalysisStatus:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_READY)


@router.get("/reports/{report_id}.pdf", response_class=Response, responses={404: {"model": ErrorOut}})
async def report_pdf(report_id: str) -> Response:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_READY)


@router.get("/reports/{report_id}", response_model=ReportOut, responses={404: {"model": ErrorOut}})
async def report(report_id: str) -> ReportOut:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, NOT_READY)
