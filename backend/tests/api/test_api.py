from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["app"] == "GeoSatel"


def test_crops_list() -> None:
    r = client.get("/api/crops")
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert len(ids) == 13
    assert "maize" in ids
    kinds = {c["id"]: c["kind"] for c in r.json()}
    assert kinds["maize"] == "arable"
    assert kinds["grassland"] == "grassland"
    assert kinds["orchard_pome"] == "fruit"


def test_openapi_lists_all_endpoints() -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/api/health",
        "/api/crops",
        "/api/parcels",
        "/api/analyses",
        "/api/analyses/{analysis_id}",
        "/api/reports/{report_id}",
        "/api/reports/{report_id}.pdf",
    } <= paths
