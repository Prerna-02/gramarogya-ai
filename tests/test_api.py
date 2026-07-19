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
    resp = client.post("/api/auth/admin/login", json={"username": TEST_ADMIN[0], "password": TEST_ADMIN[1]})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@needs_db
def test_login_wrong_password_401():
    r = client.post("/api/auth/admin/login", json={"username": TEST_ADMIN[0], "password": "nope"})
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
