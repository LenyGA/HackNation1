from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.models import (
    AnalysisRequest,
    Confidence,
    Period,
    SourceResult,
    SourceStatus,
    Uncertainty,
    validate_parcel_id,
)

UNC = Uncertainty(level=Confidence.HIGH, reason_pl="test")


def _result(
    status: SourceStatus, data: dict[str, float] | None, msg: str | None = None
) -> SourceResult[dict[str, float]]:
    return SourceResult[dict[str, float]](
        name="x",
        status=status,
        source="Test",
        license="CC BY 4.0",
        fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
        period=Period(start=date(2026, 1, 1), end=date(2026, 1, 31)),
        uncertainty=UNC,
        message_pl=msg,
        data=data,
    )


def test_source_result_roundtrip() -> None:
    r = _result(SourceStatus.OK, {"precip_mm": 12.0})
    again = SourceResult[dict[str, float]].model_validate_json(r.model_dump_json())
    assert again == r
    assert again.data == {"precip_mm": 12.0}


def test_missing_must_not_carry_data() -> None:
    with pytest.raises(ValidationError):
        _result(SourceStatus.MISSING, {"precip_mm": 0.0}, "brak")


def test_missing_without_data_and_with_message() -> None:
    r = _result(SourceStatus.MISSING, None, "Źródło nie odpowiedziało.")
    assert r.data is None


def test_ok_requires_data() -> None:
    with pytest.raises(ValidationError):
        _result(SourceStatus.OK, None)


def test_degraded_requires_message() -> None:
    with pytest.raises(ValidationError):
        _result(SourceStatus.DEGRADED, {"a": 1.0})


def test_period_order() -> None:
    with pytest.raises(ValidationError):
        Period(start=date(2026, 2, 1), end=date(2026, 1, 1))


@pytest.mark.parametrize(
    "pid",
    ["141201_1.0001.6509", "141201_1.0001.123/4", "026401_1.0012.AR_1.45/2", " 141201_1.0001.6509 "],
)
def test_parcel_id_valid(pid: str) -> None:
    assert validate_parcel_id(pid) == pid.strip()


@pytest.mark.parametrize("pid", ["", "abc", "141201.0001.6509", "141201_1.0001.", "141201_1.0001.12;DROP"])
def test_parcel_id_invalid(pid: str) -> None:
    with pytest.raises(ValueError):
        validate_parcel_id(pid)


def test_analysis_request_date_range() -> None:
    ok = AnalysisRequest(parcel_id="141201_1.0001.6509", crop_id="maize", analysis_date=date.today())
    assert ok.analysis_date == date.today()
    with pytest.raises(ValidationError):
        AnalysisRequest(
            parcel_id="141201_1.0001.6509", crop_id="maize", analysis_date=date.today() + timedelta(days=1)
        )
    with pytest.raises(ValidationError):
        AnalysisRequest(parcel_id="141201_1.0001.6509", crop_id="maize", analysis_date=date(2010, 1, 1))


# --- farm mode (G11, plan33 M7) ---------------------------------------------------------------------

MAIN = "141201_1.0001.6509"


def _req(extra: list[str]) -> AnalysisRequest:
    return AnalysisRequest(
        parcel_id=MAIN, crop_id="maize", analysis_date=date.today(), extra_parcel_ids=extra
    )


def test_extra_parcels_default_empty() -> None:
    r = AnalysisRequest(parcel_id=MAIN, crop_id="maize", analysis_date=date.today())
    assert r.extra_parcel_ids == []


def test_extra_parcels_valid_and_stripped() -> None:
    ids = [f"141201_1.0001.{n}" for n in range(1, 6)]
    assert _req(ids).extra_parcel_ids == ids
    assert _req([" 141201_1.0001.123/4 "]).extra_parcel_ids == ["141201_1.0001.123/4"]


@pytest.mark.parametrize(
    ("extra", "fragment"),
    [
        ([f"141201_1.0001.{n}" for n in range(1, 7)], "najwyżej 5 działek"),
        (["141201_1.0001.1", "141201_1.0001.1"], "dwa razy"),
        (["141201_1.0001.1", " 141201_1.0001.1"], "dwa razy"),  # duplicate after stripping
        (["abc"], "Nieprawidłowy numer działki"),
        (["141201_1.0001.12;DROP"], "Nieprawidłowy numer działki"),
        ([MAIN], "Działka główna nie może być"),
        ([f" {MAIN} "], "Działka główna nie może być"),
    ],
)
def test_extra_parcels_invalid(extra: list[str], fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        _req(extra)
