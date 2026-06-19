"""Smoke /api/brokers/switch contract end-to-end (Polish #5.6 + #5.7).

Locks in contracts enforced by api/routes_broker.py + switchBroker()
in static/index.html:
(a) typed 404 dict detail for unknown profile_id
    (Polish #5.3 deploy + Polish #5.5 helper hoist `_unknown_profile_detail`)
(b) Pydantic v2 422 list-detail for empty body
    (frontend Polish #5.4 Array.isArray branch trigger)
(c) 200 OK with {ok, profile_id, profile_name, message} for valid profile_id

Polish #5.7 micro-cleanup: (d) helper-direct parity test on
`_unknown_profile_detail()` itself -- pins the helper parity that
Polish #5.5 hoist was designed for, addressing the 🟡 LOW #2
carry-over from #5.6 code-review.
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


def test_unknown_profile_detail_helper_parity():
    """(d) Polish #5.7: pin helper parity directly (🟡 LOW #2 #5.6 carry-over)."""
    from api.routes_broker import _unknown_profile_detail
    assert _unknown_profile_detail("xyz", ["a", "b"]) == {"error": "unknown_profile", "profile_id": "xyz", "available": ["a", "b"]}
    assert _unknown_profile_detail("xyz", ["a"], message="oops") == {"error": "unknown_profile", "profile_id": "xyz", "available": ["a"], "message": "oops"}


# Polish #5.9 micro-cleanup: KPI_LABEL[k] em-dash fallback assertion
def test_renderKpiPanel_kpi_label_has_emdash_fallback():
    src = open('static/index.html', encoding='utf-8').read()
    assert "KPI_LABEL[k]??'" + chr(0x2014) + "'" in src and src.count("KPI_LABEL[k]??'" + chr(0x2014) + "'") == 2
