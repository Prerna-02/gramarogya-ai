"""Planning orchestrator (Phase 9).

Backs POST /api/planning-runs: creates a `planning_run_id`, then runs the
services in order and stores every output under that id.

    forecast -> resource plans -> roster -> capacity/risk check

Services are called as in-process functions (never via HTTP). Run status is
tracked (queued/running/completed/failed); if a downstream module fails, prior
valid outputs are preserved.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models import (
    DailyDemand, Forecast, PlanningRun, ResourcePlan, ResourceStatus, RosterEntry, Staff,
    StaffAvailability,
)
from backend.services.forecasting import future_forecast
from backend.services import dashboard_operations, staff_availability as staff_availability_ops
from backend.services.resource_planning import plan_resource_window
from backend.services.scheduling_config import SUPPORTED_HORIZONS
from backend.services.workforce_optimization import generate_roster

TARGETS = ["total_patient_arrivals", "general_opd_arrivals", "fever_infectious_arrivals",
           "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions"]


def _latest_data_date(db: Session) -> date:
    return db.scalar(select(DailyDemand.date).order_by(DailyDemand.date.desc()).limit(1))


def _staff_dataframe(db: Session) -> pd.DataFrame:
    rows = db.scalars(select(Staff)).all()
    cols = ["staff_id", "staff_name", "staff_category", "designation", "department",
            "qualification", "experience_years", "skill_tags", "shift_eligibility",
            "max_weekly_hours", "max_consecutive_working_days", "minimum_rest_hours",
            "max_night_shifts_per_month", "preferred_shift", "emergency_on_call",
            "employment_type", "weekly_off_preference", "active_status"]
    database_staff = pd.DataFrame([[getattr(r, c) for c in cols] for r in rows], columns=cols)
    # Include newly contracted/on-call records from the maintained workforce
    # source even before the next full database seed. Database rows remain the
    # authoritative version whenever the same staff_id exists in both places.
    source_path = Path(__file__).resolve().parents[2] / "data" / "staff_master.csv"
    source_staff = pd.read_csv(source_path)[cols]
    missing = source_staff[~source_staff["staff_id"].isin(set(database_staff["staff_id"]))]
    if not missing.empty:
        # Incrementally synchronize newly contracted staff without truncating
        # operational tables. This also preserves roster-entry foreign keys.
        for record in missing.where(pd.notna(missing), None).to_dict("records"):
            db.add(Staff(**record))
        db.flush()
    return pd.concat([database_staff, missing], ignore_index=True)


def _nearest_roster_horizon(forecast_horizon: int, requested: int | None) -> int:
    if requested in SUPPORTED_HORIZONS:
        return requested
    feasible = [h for h in SUPPORTED_HORIZONS if h <= forecast_horizon] or [SUPPORTED_HORIZONS[0]]
    return max(feasible)


def run_planning_cycle(db: Session, start_date: date | None = None, horizon_days: int = 7,
                       roster_horizon_days: int | None = None) -> dict:
    if start_date is None:
        start_date = _latest_data_date(db) + timedelta(days=1)
    roster_h = _nearest_roster_horizon(horizon_days, roster_horizon_days)

    run = PlanningRun(planning_run_id=str(uuid.uuid4()), status="running",
                      start_date=start_date, horizon_days=horizon_days)
    db.add(run)
    db.commit()

    warnings: list[str] = []
    try:
        # 1) Forecast
        forecast = future_forecast(start_date, horizon_days)
        for day in forecast:
            for t in TARGETS:
                db.add(Forecast(planning_run_id=run.planning_run_id,
                                forecast_date=datetime.strptime(day["date"], "%Y-%m-%d").date(),
                                target=t, predicted_value=float(day[t]), model="XGBoost"))

        # 2) Resource plans (per day) + daily risk
        staff_rows = list(db.scalars(select(Staff).order_by(Staff.staff_name)).all())
        latest_resource = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
        availability_records = list(db.scalars(
            select(StaffAvailability)
            .where(StaffAvailability.date.between(
                start_date, start_date + timedelta(days=horizon_days - 1)
            ))
        ).all())
        planning_dates = [start_date + timedelta(days=offset) for offset in range(horizon_days)]
        daily_staff_availability = staff_availability_ops.resource_availability_by_date(
            staff_rows, availability_records, planning_dates
        )
        resource_plans = plan_resource_window(
            forecast,
            dashboard_operations.availability_from_status(latest_resource, staff_rows),
            availability_by_date=daily_staff_availability,
        )
        daily_status = []
        for day, plan in zip(forecast, resource_plans):
            d = datetime.strptime(day["date"], "%Y-%m-%d").date()
            lines = list(plan["staff"].values()) + list(plan["beds"].values()) \
                + list(plan["medicines"].values()) + [plan["oxygen"], plan["ambulances"]]
            for ln in lines:
                db.add(ResourcePlan(planning_run_id=run.planning_run_id, plan_date=d,
                                    resource=ln["resource"], required=ln["required"],
                                    available=ln["available"], shortage=ln["shortage"],
                                    status=ln["status"]))
            daily_status.append({"date": day["date"], "status": plan["summary"]["status"],
                                 "shortage_count": plan["summary"]["shortage_count"],
                                 "shortages": plan["summary"]["shortages"]})

        # 3) Roster (preserve forecast/resources if this fails)
        roster_result = None
        try:
            fbd = {day["date"]: {t: day[t] for t in TARGETS} for day in forecast[:roster_h]}
            staff_df = _staff_dataframe(db)
            roster_result = generate_roster(fbd, staff_df, start_date, roster_h,
                                            availability=staff_availability_ops.workforce_availability(
                                                [record for record in availability_records
                                                 if record.date < start_date + timedelta(days=roster_h)]
                                            ),
                                            planning_run_id=run.planning_run_id,
                                            pop_size=24, n_gen=15)
            for a in roster_result["recommended_roster"]:
                if a["assignment_status"] in ("locked", "completed"):
                    continue
                db.add(RosterEntry(
                    planning_run_id=run.planning_run_id, roster_run_id=roster_result["roster_run_id"],
                    staff_id=a["staff_id"], work_date=datetime.strptime(a["date"], "%Y-%m-%d").date(),
                    shift=a["shift"], department=a["department"], assigned_role=a["assigned_role"],
                    assignment_status=a["assignment_status"],
                    confirmed_or_provisional=a["confirmed_or_provisional"]))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"roster generation failed: {e}")

        # 4) Capacity / risk check (basic; full engine in Phase 12)
        overload_days = [s["date"] for s in daily_status if s["status"] in ("High", "Critical")]
        overall = "Critical" if any(s["status"] == "Critical" for s in daily_status) \
            else "High" if overload_days else "Watch" if any(s["shortage_count"] for s in daily_status) \
            else "Normal"

        run.status = "completed"
        db.commit()
    except Exception as e:  # noqa: BLE001
        run.status = "failed"
        db.commit()
        raise

    return {
        "planning_run_id": run.planning_run_id,
        "status": run.status,
        "start_date": start_date.isoformat(),
        "horizon_days": horizon_days,
        "roster_horizon_days": roster_h,
        "forecast": forecast,
        "resource_status_by_day": daily_status,
        "capacity_check": {"overall_risk": overall, "overload_days": overload_days},
        "roster_summary": None if roster_result is None else {
            "roster_run_id": roster_result["roster_run_id"],
            "assignments": len(roster_result["recommended_roster"]),
            "coverage_pct": roster_result["recommended_roster_scores"]["coverage_pct"],
            "unmet_requirements": len(roster_result["unmet_staffing_requirements"]),
            "recommendation_reason": roster_result["recommendation_reason"],
        },
        "warnings": warnings,
    }


def get_run(db: Session, planning_run_id: str) -> dict | None:
    run = db.get(PlanningRun, planning_run_id)
    if run is None:
        return None
    forecasts = db.scalars(select(Forecast).where(Forecast.planning_run_id == planning_run_id)).all()
    plans = db.scalars(select(ResourcePlan).where(ResourcePlan.planning_run_id == planning_run_id)).all()
    roster = db.scalars(select(RosterEntry).where(RosterEntry.planning_run_id == planning_run_id)).all()
    return {
        "planning_run_id": run.planning_run_id, "status": run.status,
        "start_date": run.start_date.isoformat(), "horizon_days": run.horizon_days,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "counts": {"forecasts": len(forecasts), "resource_plan_lines": len(plans),
                   "roster_entries": len(roster)},
        "roster_shortages": sum(1 for p in plans if p.shortage > 0),
    }
