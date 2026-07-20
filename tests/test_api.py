"""API integration tests (Phase 9).

DB-dependent tests skip automatically if PostgreSQL is not reachable, so the
suite stays green without a database. The health check always runs.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---- DB-dependent tests ----
def _db_available() -> bool:
    try:
        from sqlalchemy import text
        from backend.db import engine
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL not reachable")

TEST_ADMIN = ("pytest_admin", "pytest_pass_123")


@pytest.fixture(scope="module")
def admin_token():
    from sqlalchemy import select
    from backend.auth import hash_password
    from backend.db import SessionLocal
    from backend.db_models import User
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.username == TEST_ADMIN[0]))
        if u is None:
            db.add(User(username=TEST_ADMIN[0], password_hash=hash_password(TEST_ADMIN[1]),
                        role="administrator"))
            db.commit()
    resp = client.post("/api/auth/admin/login", data={"username": TEST_ADMIN[0], "password": TEST_ADMIN[1]})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@needs_db
def test_login_wrong_password_401():
    r = client.post("/api/auth/admin/login", data={"username": TEST_ADMIN[0], "password": "nope"})
    assert r.status_code == 401


@needs_db
def test_protected_route_requires_token():
    assert client.get("/api/dashboard/summary").status_code == 401


@needs_db
def test_patient_facilities_are_public(admin_token):
    r = client.get("/api/patient/facilities", params={"service": "Maternity"})
    assert r.status_code == 200
    facs = r.json()["facilities"]
    assert len(facs) >= 1
    assert all("rank" in f and "status" in f for f in facs)
    # never leak sensitive fields
    assert all("staff" not in f for f in facs)


@needs_db
def test_dashboard_summary_authed(admin_token):
    r = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["staff_count"] > 0 and body["nearby_facilities"] > 0


@needs_db
def test_triage_emergency_never_suggests_treatment():
    """Guardrail: a symptom + 'suggest a remedy' must NOT return treatment — it
    flags an emergency and points to a facility + the emergency number."""
    r = client.get("/api/patient/triage", params={"text": "I have chest pain, suggest a remedy"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_emergency"] is True
    assert body["emergency_number"] == "108"
    assert body["facilities"]                       # recommends a facility
    assert "not diagnose" in body["disclaimer"].lower()


@needs_db
def test_triage_routes_symptom_to_service():
    assert client.get("/api/patient/triage", params={"text": "high fever and cough"}).json()["category"] == "fever"
    assert client.get("/api/patient/triage", params={"text": "my wife is in labour"}).json()["category"] == "maternity"


@needs_db
def test_emergency_scenarios_and_simulation(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    scen = client.get("/api/emergency/scenarios", headers=h)
    if scen.status_code == 503:
        pytest.skip("model not trained")
    ids = [s["id"] for s in scen.json()["scenarios"]]
    assert "disease_outbreak" in ids and "mass_casualty" in ids

    low = client.post("/api/emergency/simulate", headers=h, json={"scenario_id": "disease_outbreak", "severity": 1}).json()
    high = client.post("/api/emergency/simulate", headers=h, json={"scenario_id": "disease_outbreak", "severity": 5}).json()
    # higher severity => bigger surge and never smaller peak
    assert high["impact"]["extra_patients"] > low["impact"]["extra_patients"]
    assert high["impact"]["peak_surged"] >= high["impact"]["peak_baseline"]
    assert high["resources"] and high["precautions"] and high["facilities"]
    assert high["alert"]["status"] == "draft"


@needs_db
def test_audit_trail_records_actions(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/audit", headers=h, json={"action": "roster_approved", "entity": "t", "reason": "ok"})
    entries = client.get("/api/audit", headers=h).json()["entries"]
    actions = {e["action"] for e in entries}
    assert "login" in actions          # the fixture logged in
    assert "roster_approved" in actions
    # override without a reason is rejected
    assert client.post("/api/audit", headers=h, json={"action": "override"}).status_code == 400


@needs_db
def test_no_protected_attributes_collected():
    import pandas as pd
    cols = {c.lower() for c in pd.read_csv(ROOT / "data" / "staff_master.csv").columns}
    protected = {"gender", "sex", "caste", "religion", "age", "race", "ethnicity"}
    assert not (cols & protected)


@needs_db
def test_fairness_report_within_groups(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/api/workforce/generate", headers=h, json={"horizon_days": 7, "roster_horizon_days": 7})
    if r.status_code == 503:
        pytest.skip("model not trained")
    fr = r.json()["fairness_report"]
    assert fr["no_protected_attributes"] is True
    assert fr["rest_compliance_pct"] == 100.0
    assert 0 <= fr["shift_equity_index"] <= 100
    from backend.services.scheduling_config import FAIRNESS_GROUPS
    valid = set(FAIRNESS_GROUPS.values())
    assert all(g["group"] in valid for g in fr["groups"])


@needs_db
def test_alert_dispatch_requires_privileged_role():
    """Least-privilege: a non-emergency role cannot send alerts."""
    from sqlalchemy import select
    from backend.auth import hash_password
    from backend.db import SessionLocal
    from backend.db_models import User
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.username == "pytest_inv")):
            db.add(User(username="pytest_inv", password_hash=hash_password("x"), role="inventory_manager"))
            db.commit()
    tok = client.post("/api/auth/admin/login", data={"username": "pytest_inv", "password": "x"}).json()["access_token"]
    r = client.post("/api/emergency/alerts", headers={"Authorization": f"Bearer {tok}"},
                    json={"scenario": "X", "severity": 1, "requested_support": [], "facility_ids": []})
    assert r.status_code == 403


@needs_db
def test_planning_run_creates_connected_outputs(admin_token):
    """Phase 9 completion check: one request -> forecast+resources+roster under one id."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/api/planning-runs", headers=h, json={"horizon_days": 5, "roster_horizon_days": 5})
    if r.status_code == 503:
        pytest.skip("forecast model not trained")
    assert r.status_code == 200
    run = r.json()
    assert run["status"] == "completed"
    assert len(run["forecast"]) == 5
    rid = run["planning_run_id"]
    got = client.get(f"/api/planning-runs/{rid}", headers=h).json()
    assert got["counts"]["forecasts"] == 30           # 6 targets x 5 days
    assert got["counts"]["resource_plan_lines"] > 0
    assert got["status"] == "completed"
