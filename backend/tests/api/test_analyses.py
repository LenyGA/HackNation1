"""Analysis jobs and report endpoints (plan M6.1/M6.3), with ULDK and every source replaced by
synthetic results (no network)."""

import dataclasses
import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import jobs
from app.core.config import get_settings, today_local
from app.core.models import Parcel, SourceResult
from app.main import app
from app.report.models import SECTION_ORDER
from app.report.storage import new_report_id
from app.sources import uldk
from tests.analysis.builders import make_inputs
from tests.recommendations.builders import basin, dem_result, hydro, soil_result

PARCEL_ID = "141201_1.0001.6509"
DAY = date(2024, 7, 15)


def _inputs_for(parcel: Parcel, day: date) -> dict[str, SourceResult[Any]]:
    inputs = make_inputs(
        day,
        "maize",
        precip=lambda _: 0.3,
        soil=soil_result((80.0, 12.0, 8.0, 8.0)),
        dem=dem_result(parcel, basin(parcel)),
        hydro=hydro(parcel, ditch_m=200.0, trees_m=300.0),
        parcel=parcel,
    )
    return {
        "open_meteo": inputs.weather,
        "sentinel2": inputs.sentinel2,
        "soilgrids": inputs.soil,
        "dem": inputs.dem,
        "hydro": inputs.hydro,
        "landcover": inputs.landcover,
    }


def _fake_fetch(name: str) -> Any:
    async def fetch(parcel: Parcel, analysis_date: date) -> SourceResult[Any]:
        return _inputs_for(parcel, analysis_date)[name]

    return fetch


@pytest.fixture
def fake_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    from tests.analysis.builders import default_parcel

    async def get_parcel(parcel_id: str) -> Parcel:
        if parcel_id.endswith(".9999"):
            raise uldk.ParcelNotFound(uldk.MSG_NOT_FOUND_ID.format(id=parcel_id))
        p = default_parcel()
        return p.model_copy(update={"id": parcel_id, "commune": "Testowo"})

    monkeypatch.setattr(uldk, "get_parcel_by_id", get_parcel)
    specs = {s.name: dataclasses.replace(s, fetch=_fake_fetch(s.name)) for s in jobs.SOURCES}
    monkeypatch.setattr(jobs, "SOURCES", list(specs.values()))
    monkeypatch.setattr(get_settings(), "db_path", tmp_path / "reports.sqlite3")
    return specs


@pytest.fixture
def client(fake_sources: dict[str, Any]) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, job_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = client.get(f"/api/analyses/{job_id}")
        assert r.status_code == 200
        body: dict[str, Any] = r.json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def _post(client: TestClient, **kw: Any) -> Any:
    payload = {"parcel_id": PARCEL_ID, "crop_id": "maize", "analysis_date": DAY.isoformat(), **kw}
    return client.post("/api/analyses", json=payload)


def test_full_flow_json_pdf_html(client: TestClient) -> None:
    r = _post(client)
    assert r.status_code == 202
    job_id = r.json()["id"]
    assert len(job_id) == 22
    status = _wait(client, job_id)
    assert status["status"] == "done", status
    assert status["error_pl"] is None
    assert {s["name"] for s in status["sources"]} == {"uldk", *(s.name for s in jobs.SOURCES)}
    assert all(s["status"] != "pending" for s in status["sources"])
    assert all(s["label_pl"] for s in status["sources"])
    report_id = status["report_id"]
    assert len(report_id) == 22

    rep = client.get(f"/api/reports/{report_id}")
    assert rep.status_code == 200
    body = rep.json()
    assert [s["id"] for s in body["sections"]] == SECTION_ORDER
    assert body["parcel"]["id"] == PARCEL_ID
    assert body["analysis_date"] == DAY.isoformat()
    assert body["recommendations"]

    pdf = client.get(f"/api/reports/{report_id}.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert f"raport-{PARCEL_ID}-{DAY.isoformat()}.pdf" in pdf.headers["content-disposition"]

    html = client.get(f"/api/reports/{report_id}.html")
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in html.text
    assert "Testowo" in html.text


def test_two_analyses_give_two_reports(client: TestClient) -> None:
    a = _wait(client, _post(client).json()["id"])
    b = _wait(client, _post(client, crop_id="winter_wheat").json()["id"])
    assert a["report_id"] != b["report_id"]
    ra = client.get(f"/api/reports/{a['report_id']}").json()
    rb = client.get(f"/api/reports/{b['report_id']}").json()
    assert ra["crop"]["id"] == "maize" and rb["crop"]["id"] == "winter_wheat"
    assert [x["id"] for x in ra["recommendations"]] != [x["id"] for x in rb["recommendations"]]


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"parcel_id": "abc"}, "Nieprawidłowy numer działki"),
        ({"parcel_id": "141201_1.0001.6509; DROP TABLE"}, "Nieprawidłowy numer działki"),
        ({"crop_id": "banana"}, "Wybierz uprawę z listy"),
        ({"analysis_date": (today_local() + timedelta(days=1)).isoformat()}, "Data analizy"),
        ({"analysis_date": (today_local() - timedelta(days=3700)).isoformat()}, "Data analizy"),
    ],
)
def test_bad_input_is_400_with_polish_detail(
    client: TestClient, override: dict[str, str], fragment: str
) -> None:
    r = _post(client, **override)
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str)
    assert fragment in r.json()["detail"]


def test_malformed_body_is_400_with_polish_detail(client: TestClient) -> None:
    r = _post(client, analysis_date="jutro")
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str)


def test_unknown_ids_are_404(client: TestClient) -> None:
    for path in (
        f"/api/analyses/{new_report_id()}",
        "/api/analyses/not-an-id",
        f"/api/reports/{new_report_id()}",
        f"/api/reports/{new_report_id()}.pdf",
        f"/api/reports/{new_report_id()}.html",
        "/api/reports/short",
        "/api/reports/short.pdf",
    ):
        r = client.get(path)
        assert r.status_code == 404, path
        assert isinstance(r.json()["detail"], str)


def test_failing_source_becomes_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(parcel: Parcel, analysis_date: date) -> SourceResult[Any]:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(
        jobs,
        "SOURCES",
        [dataclasses.replace(s, fetch=boom) if s.name == "soilgrids" else s for s in jobs.SOURCES],
    )
    status = _wait(client, _post(client).json()["id"])
    assert status["status"] == "done", status
    states = {s["name"]: s["status"] for s in status["sources"]}
    assert states["soilgrids"] == "missing"
    report = client.get(f"/api/reports/{status['report_id']}").json()
    soil = next(s for s in report["sources"] if s["name"] == "soilgrids")
    assert soil["status"] == "missing"
    assert any(line.startswith(soil["label_pl"]) for line in report["missing_data_pl"])
    assert [s["id"] for s in report["sections"]] == SECTION_ORDER


def test_weather_failure_still_finishes_without_recommendations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(parcel: Parcel, analysis_date: date) -> SourceResult[Any]:
        raise TimeoutError

    monkeypatch.setattr(
        jobs,
        "SOURCES",
        [dataclasses.replace(s, fetch=boom) if s.name == "open_meteo" else s for s in jobs.SOURCES],
    )
    status = _wait(client, _post(client).json()["id"])
    assert status["status"] == "done"
    report = client.get(f"/api/reports/{status['report_id']}").json()
    assert report["complete"] is False
    assert report["recommendations"] == []
    assert len(report["sections"]) == 9
    assert client.get(f"/api/reports/{status['report_id']}.pdf").status_code == 200


def test_parcel_not_found_fails_job_with_polish_message(client: TestClient) -> None:
    status = _wait(client, _post(client, parcel_id="141201_1.0001.9999").json()["id"])
    assert status["status"] == "failed"
    assert status["report_id"] is None
    assert "Nie znaleziono działki" in status["error_pl"]
    states = {s["name"]: s["status"] for s in status["sources"]}
    assert states["uldk"] == "missing"


def test_parcel_not_found_leaves_no_pending_sources(client: TestClient) -> None:
    status = _wait(client, _post(client, parcel_id="141201_1.0001.9999").json()["id"])
    assert all(s["status"] != "pending" for s in status["sources"])


def test_unexpected_error_fails_job(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(jobs, "build_report", broken)
    status = _wait(client, _post(client).json()["id"])
    assert status["status"] == "failed"
    assert status["error_pl"] == jobs.MSG_UNEXPECTED


def test_openapi_lists_report_endpoints(client: TestClient) -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/api/reports/{report_id}.html", "/api/reports/{report_id}.pdf", "/api/analyses"} <= paths


def test_queue_full_is_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import jobs

    monkeypatch.setattr(jobs, "MAX_PENDING_TASKS", 0)
    r = _post(client)
    assert r.status_code == 429
    assert isinstance(r.json()["detail"], str)


def test_unknown_api_path_is_not_spa(client: TestClient) -> None:
    assert client.get("/api/nonexistent").status_code == 404
