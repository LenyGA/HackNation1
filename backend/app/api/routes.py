import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from app.api import jobs
from app.api.ratelimit import limit_analyses, limit_parcels
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
from app.core.models import AnalysisRequest
from app.crops.catalog import get_crop, load_crops
from app.report.models import Report
from app.report.pdf import Variant, render_html, render_pdf
from app.report.storage import load_report
from app.sources import geocode, uldk

router = APIRouter(prefix="/api")

MSG_ANALYSIS_NOT_FOUND = "Nie ma takiej analizy albo wygasła. Uruchom analizę ponownie."
MSG_BUSY = "Serwer liczy teraz wiele analiz. Spróbuj ponownie za minutę."
BUSY_RETRY_AFTER_S = 60
MSG_REPORT_NOT_FOUND = "Nie znaleziono raportu. Sprawdź link."


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", app=APP_TITLE, version=APP_VERSION)


@router.get("/crops", response_model=list[CropOut])
async def crops() -> list[CropOut]:
    return [CropOut(id=c.id, name_pl=c.name_pl, kind=c.kind) for c in load_crops().values()]


@router.get(
    "/parcels",
    response_model=ParcelOut,
    responses={
        400: {"model": ErrorOut},
        404: {"model": ErrorOut},
        429: {"model": ErrorOut},
        503: {"model": ErrorOut},
    },
    dependencies=[Depends(limit_parcels)],
)
async def parcel(
    id: str | None = Query(default=None, max_length=64),
    lat: float | None = Query(default=None, ge=48.9, le=55.0),
    lon: float | None = Query(default=None, ge=14.0, le=24.2),
) -> ParcelOut:
    try:
        if id is not None:
            found = await uldk.get_parcel_by_id(id)
        elif lat is not None and lon is not None:
            found = await uldk.get_parcel_by_xy(lat, lon)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Podaj numer działki albo wskaż ją na mapie.")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except uldk.ParcelNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message_pl) from exc
    except uldk.ParcelServiceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.message_pl) from exc
    return ParcelOut.model_validate(found.model_dump())


@router.get(
    "/places",
    response_model=list[geocode.Place],
    responses={429: {"model": ErrorOut}, 503: {"model": ErrorOut}},
    dependencies=[Depends(limit_parcels)],
)
async def places(q: str = Query(min_length=2, max_length=120)) -> list[geocode.Place]:
    """Address search (M8.7): an address or village → points to fly the map to or pick a parcel at."""
    try:
        return await geocode.search(q)
    except geocode.GeocodeServiceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.message_pl) from exc


def _first_error_pl(exc: ValidationError) -> str:
    msg = str(exc.errors()[0].get("msg", "Nieprawidłowe dane."))
    return msg.removeprefix("Value error, ")


@router.post(
    "/analyses",
    response_model=AnalysisCreated,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorOut}, 429: {"model": ErrorOut}},
    dependencies=[Depends(limit_analyses)],
)
async def create_analysis(body: AnalysisCreate) -> AnalysisCreated:
    try:
        request = AnalysisRequest.model_validate(body.model_dump())
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _first_error_pl(exc)) from exc
    crop = get_crop(request.crop_id)
    if crop is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wybierz uprawę z listy.")
    try:
        job = jobs.start(request, crop)
    except jobs.QueueFull as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, MSG_BUSY, headers={"Retry-After": str(BUSY_RETRY_AFTER_S)}
        ) from exc
    return AnalysisCreated(id=job.id)


@router.get("/analyses/{analysis_id}", response_model=AnalysisStatus, responses={404: {"model": ErrorOut}})
async def analysis_status(analysis_id: str) -> AnalysisStatus:
    job = jobs.get_job(analysis_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MSG_ANALYSIS_NOT_FOUND)
    return job.status()


async def _report_or_404(report_id: str) -> Report:
    report = await load_report(report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MSG_REPORT_NOT_FOUND)
    return report


def _pdf_filename(report: Report, variant: Variant) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", report.parcel.id)
    suffix = "-podstawowy" if variant == "basic" else "-pelny"
    return f"raport-{safe}-{report.analysis_date.isoformat()}{suffix}.pdf"


@router.get(
    "/reports/{report_id}.pdf",
    response_class=Response,
    responses={404: {"model": ErrorOut}, 200: {"content": {"application/pdf": {}}}},
)
async def report_pdf(report_id: str, variant: Variant = "basic") -> Response:
    """`variant`: basic (1–2 pages, default) or full (every section with charts, map and tables)."""
    report = await _report_or_404(report_id)
    pdf = await render_pdf(report, variant)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_pdf_filename(report, variant)}"'},
    )


@router.get(
    "/reports/{report_id}.html",
    response_class=HTMLResponse,
    responses={404: {"model": ErrorOut}},
)
async def report_print(report_id: str, variant: Variant = "basic") -> HTMLResponse:
    """Print view: the same HTML and stylesheet as the PDF, for printing from the browser."""
    report = await _report_or_404(report_id)
    return HTMLResponse(await asyncio.to_thread(render_html, report, variant=variant))


@router.get("/reports/{report_id}", response_model=ReportOut, responses={404: {"model": ErrorOut}})
async def report(report_id: str) -> Report:
    return await _report_or_404(report_id)
