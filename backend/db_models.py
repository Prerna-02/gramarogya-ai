"""SQLAlchemy ORM models (Phase 4).

Tables connect a full planning cycle via `planning_run_id`. Timestamps
(created_at / updated_at / data_last_verified_at) support operational
transparency. Only synthetic, non-identifiable data is stored.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


# ------------------------------------------------------------------ auth
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="administrator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ historical data
class DailyDemand(Base):
    """One row per day: demand predictors + patient targets (leakage-safe features)."""
    __tablename__ = "daily_demand"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_of_week: Mapped[str] = mapped_column(String(12))
    day_of_week_num: Mapped[int] = mapped_column(Integer)
    week_of_year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    season: Mapped[str] = mapped_column(String(16))
    is_weekend: Mapped[int] = mapped_column(Integer)
    public_holiday: Mapped[int] = mapped_column(Integer)
    festival_flag: Mapped[int] = mapped_column(Integer)
    weekly_market_day: Mapped[int] = mapped_column(Integer)
    vaccination_camp_flag: Mapped[int] = mapped_column(Integer)
    maternal_clinic_day: Mapped[int] = mapped_column(Integer)
    local_event_intensity: Mapped[int] = mapped_column(Integer)
    rainfall_mm: Mapped[float] = mapped_column(Float)
    temperature_max_c: Mapped[float] = mapped_column(Float)
    temperature_min_c: Mapped[float] = mapped_column(Float)
    humidity_pct: Mapped[float] = mapped_column(Float)
    outbreak_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    outbreak_severity_0_5: Mapped[int] = mapped_column(Integer)
    surveillance_alert: Mapped[int] = mapped_column(Integer)
    affected_villages: Mapped[int] = mapped_column(Integer)
    general_opd_arrivals: Mapped[int] = mapped_column(Integer)
    fever_infectious_arrivals: Mapped[int] = mapped_column(Integer)
    maternal_child_arrivals: Mapped[int] = mapped_column(Integer)
    trauma_emergency_arrivals: Mapped[int] = mapped_column(Integer)
    expected_admissions: Mapped[int] = mapped_column(Integer)
    total_patient_arrivals: Mapped[int] = mapped_column(Integer)
    patients_lag_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    patients_lag_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    patients_lag_7: Mapped[float | None] = mapped_column(Float, nullable=True)
    patients_lag_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_mean_7: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_std_7: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_mean_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResourceStatus(Base):
    """One row per day: current capacity / stock / risk (curated operational state)."""
    __tablename__ = "resource_status"
    date: Mapped[date] = mapped_column(Date, ForeignKey("daily_demand.date"), primary_key=True)
    emergency_scenario_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emergency_scenario_severity_0_5: Mapped[int] = mapped_column(Integer)
    total_general_beds: Mapped[int] = mapped_column(Integer)
    occupied_general_beds: Mapped[int] = mapped_column(Integer)
    available_general_beds: Mapped[int] = mapped_column(Integer)
    total_emergency_beds: Mapped[int] = mapped_column(Integer)
    occupied_emergency_beds: Mapped[int] = mapped_column(Integer)
    available_emergency_beds: Mapped[int] = mapped_column(Integer)
    total_isolation_beds: Mapped[int] = mapped_column(Integer)
    occupied_isolation_beds: Mapped[int] = mapped_column(Integer)
    available_isolation_beds: Mapped[int] = mapped_column(Integer)
    overflow_patients: Mapped[int] = mapped_column(Integer)
    closing_stock_iv_fluids: Mapped[int] = mapped_column(Integer)
    closing_stock_ors: Mapped[int] = mapped_column(Integer)
    closing_stock_diagnostic_test_kits: Mapped[int] = mapped_column(Integer)
    closing_stock_antipyretics: Mapped[int] = mapped_column(Integer)
    closing_stock_ppe_kits: Mapped[int] = mapped_column(Integer)
    available_oxygen_cylinders: Mapped[int] = mapped_column(Integer)
    available_ambulances: Mapped[int] = mapped_column(Integer)
    resource_shortage_count: Mapped[int] = mapped_column(Integer)
    emergency_risk_level: Mapped[str] = mapped_column(String(16))
    data_last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ workforce
class Staff(Base):
    __tablename__ = "staff"
    staff_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    staff_name: Mapped[str] = mapped_column(String(80))
    staff_category: Mapped[str] = mapped_column(String(40))
    designation: Mapped[str] = mapped_column(String(60), index=True)
    department: Mapped[str] = mapped_column(String(60))
    qualification: Mapped[str] = mapped_column(String(120))
    experience_years: Mapped[int] = mapped_column(Integer)
    skill_tags: Mapped[str] = mapped_column(Text)
    shift_eligibility: Mapped[str] = mapped_column(String(60))
    max_weekly_hours: Mapped[int] = mapped_column(Integer)
    max_consecutive_working_days: Mapped[int] = mapped_column(Integer)
    minimum_rest_hours: Mapped[int] = mapped_column(Integer)
    max_night_shifts_per_month: Mapped[int] = mapped_column(Integer)
    preferred_shift: Mapped[str] = mapped_column(String(16))
    emergency_on_call: Mapped[int] = mapped_column(Integer)
    employment_type: Mapped[str] = mapped_column(String(20))
    weekly_off_preference: Mapped[str] = mapped_column(String(20))
    active_status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffAvailability(Base):
    """Leave / unavailable / training records. No source data yet — populated later."""
    __tablename__ = "staff_availability"
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[str] = mapped_column(String(16), ForeignKey("staff.staff_id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    availability_status: Mapped[str] = mapped_column(String(20))   # available|leave|sick|training|unavailable
    shift: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ planning runs
class PlanningRun(Base):
    __tablename__ = "planning_runs"
    planning_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")   # queued|running|completed|failed
    start_date: Mapped[date] = mapped_column(Date)
    horizon_days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    resource_plans: Mapped[list["ResourcePlan"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    roster_entries: Mapped[list["RosterEntry"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    alerts: Mapped[list["EmergencyAlert"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    planning_run_id: Mapped[str] = mapped_column(String(40), ForeignKey("planning_runs.planning_run_id"), index=True)
    forecast_date: Mapped[date] = mapped_column(Date)
    target: Mapped[str] = mapped_column(String(40))
    predicted_value: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped["PlanningRun"] = relationship(back_populates="forecasts")


class ResourcePlan(Base):
    __tablename__ = "resource_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    planning_run_id: Mapped[str] = mapped_column(String(40), ForeignKey("planning_runs.planning_run_id"), index=True)
    plan_date: Mapped[date] = mapped_column(Date)
    resource: Mapped[str] = mapped_column(String(40))
    required: Mapped[int] = mapped_column(Integer)
    available: Mapped[int] = mapped_column(Integer)
    shortage: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped["PlanningRun"] = relationship(back_populates="resource_plans")


class RosterEntry(Base):
    __tablename__ = "roster_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    planning_run_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("planning_runs.planning_run_id"), nullable=True, index=True)
    roster_run_id: Mapped[str] = mapped_column(String(40), index=True)
    staff_id: Mapped[str] = mapped_column(String(16), ForeignKey("staff.staff_id"))
    work_date: Mapped[date] = mapped_column(Date)
    shift: Mapped[str] = mapped_column(String(16))
    department: Mapped[str] = mapped_column(String(60))
    assigned_role: Mapped[str] = mapped_column(String(60))
    assignment_status: Mapped[str] = mapped_column(String(16))
    confirmed_or_provisional: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped["PlanningRun"] = relationship(back_populates="roster_entries")


# ------------------------------------------------------------------ emergency network
class NearbyFacility(Base):
    __tablename__ = "nearby_facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    facility_type: Mapped[str] = mapped_column(String(24))     # PHC|CHC|Rural Hospital|District Hospital
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float] = mapped_column(Float)
    travel_time_min: Mapped[int] = mapped_column(Integer)
    beds_available: Mapped[int] = mapped_column(Integer)
    capabilities: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))            # Available|Busy|Limited
    data_last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    planning_run_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("planning_runs.planning_run_id"), nullable=True, index=True)
    scenario: Mapped[str] = mapped_column(String(40))
    severity: Mapped[int] = mapped_column(Integer)
    requested_support: Mapped[str | None] = mapped_column(Text, nullable=True)
    facility_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("nearby_facilities.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")   # draft|sent|acknowledged|accepted|partial|declined
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    run: Mapped["PlanningRun"] = relationship(back_populates="alerts")
