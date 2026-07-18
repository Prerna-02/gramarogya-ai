"""API endpoint definitions.

Implemented in Phase 9 (Build the FastAPI Backend and API Coordination).

Planned endpoints:
    POST /api/auth/admin/login       Administrator login
    POST /api/planning-runs          Run the full orchestrated workflow
    GET  /api/planning-runs/{id}     Retrieve a complete run and its outputs
    GET  /api/dashboard/summary      Combined dashboard payload
    POST /api/forecast/run           Generate a 1-7 day forecast
    GET  /api/forecast/latest        Latest saved forecast
    POST /api/resources/plan         Calculate resource requirements
    POST /api/workforce/generate     Generate NSGA-II roster options
    POST /api/emergency/check        Evaluate overload / emergency conditions
    POST /api/emergency/alerts       Send approved facility alerts
    GET  /api/patient/facilities     Rank suitable facilities for patients
    GET  /api/patient/facilities/{id} Facility details
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")
