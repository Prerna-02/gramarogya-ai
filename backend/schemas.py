"""Pydantic request/response schemas for the API (Phase 9)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# ---- auth ----
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ---- planning runs ----
class PlanningRunRequest(BaseModel):
    start_date: date | None = Field(None, description="Defaults to the day after the latest data")
    horizon_days: int = Field(7, ge=1, le=30)
    roster_horizon_days: int | None = Field(None, description="5/7/14/21; defaults to min(horizon, 7)")


class PlanningRunSummary(BaseModel):
    planning_run_id: str
    status: str
    start_date: date
    horizon_days: int
    created_at: str | None = None


# ---- forecasting ----
class ForecastRequest(BaseModel):
    start_date: date | None = None
    horizon_days: int = Field(7, ge=1, le=30)
