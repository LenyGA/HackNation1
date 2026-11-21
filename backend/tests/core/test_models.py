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
