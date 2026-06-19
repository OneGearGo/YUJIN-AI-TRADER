"""Smoke /api/brokers/switch contract end-to-end (Polish #5.6).

Locks in three contracts enforced by api/routes_broker.py + switchBroker()
in static/index.html:
(a) typed 404 dict detail for unknown profile_id
    (Polish #5.3 deploy + Polish #5.5 helper hoist `_unknown_profile_detail`)
(b) Pydantic v2 422 list-detail for empty body
    (frontend Polish #5.4 Array.isArray branch trigger)
(c) 200 OK with {ok, profile_id, profile_name, message} for valid profile_id

Frontend `switchBroker()` in static/index.html (Polish #5.4) branches on
`response.detail.error / .available` for (a) and on
`Array.isArray(response.detail)` for (b). These tests guard that contract.
"""
from fastapi.testclient import TestClient

from app import app


def test_brokers_switch_typed_404():
    """(a) typed 404 detail = `_unknown_profile_detail()` output (Polish #5.5 helper)."""
    r = TestClient(app).post(
        "/api/brokers/switch", json={"profile_id": "this_does_not_exist_xyz"},
    )
    assert r.status_code == 404
    d = r.json()["detail"]
    assert d == {
        "error": "unknown_profile",
        "profile_id": "this_does_not_exist_xyz",
        "available": ["moneta"],
    }


def test_brokers_switch_empty_body_422():
    """(b) Pydantic v2 422 list-detail; frontend polish #5.4 Array.isArray branch."""
    r = TestClient(app).post("/api/brokers/switch", json={})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert len(detail) == 1
    err = detail[0]
    assert err["type"] == "missing"
    assert err["loc"] == ["body", "profile_id"]


def test_brokers_switch_valid_profile_200():
    """(c) 200 OK happy path; locks in switch_profile() payload shape."""
    r = TestClient(app).post("/api/brokers/switch", json={"profile_id": "moneta"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["profile_id"] == "moneta"
    assert "Moneta" in body["profile_name"]
    assert "symbol_count" in body
    assert "message" in body and "Moneta" in body["message"]
