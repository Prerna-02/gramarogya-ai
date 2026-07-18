"""API integration tests (Phase 14).

The health check below is active now so the test suite is green from Phase 1.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
