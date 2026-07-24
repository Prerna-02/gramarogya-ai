"""API endpoints (Phase 9)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import authenticate, create_access_token, require_admin, require_emergency_officer
from backend.config import settings
from backend.db import engine, get_db
from backend.db_models import (
    DailyDemand, NearbyFacility, PlanningRun, ResourceStatus, RosterEntry, Staff, StaffAvailability,
)
from backend.schemas import (
    AuditActionRequest, ForecastRequest, PlanningRunRequest, SendAlertRequest, SimulateRequest,
    TokenResponse,
)
from backend.services import (
    audit, dashboard_operations, emergency, llm_summary, patient_routing,
    staff_availability as staff_availability_ops,
)
from backend.services.forecasting import (
    ModelNotTrained, backtest_latest, future_forecast, is_ready, last_data_date,
    model_info as _model_info, model_metrics as _model_metrics, patterns as _patterns, total_series,
)
from backend.services.planning_orchestrator import get_run, run_planning_cycle
from backend.services.resource_planning import plan_resource_window, plan_resources
from backend.services.workforce_optimization import generate_roster

router = APIRouter(prefix="/api")

TARGETS = ["total_patient_arrivals", "general_opd_arrivals", "fever_infectious_arrivals",
           "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions"]


# ----------------------------------------------------------------- auth
@router.post("/auth/admin/login", response_model=TokenResponse, tags=["auth"])
def admin_login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow (form-encoded). Powers Swagger's Authorize button and
    the frontend login. Leave client_id/client_secret blank."""
    user = authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(401, "Invalid username or password")
    audit.record(db, user.username, "login")
    return TokenResponse(access_token=create_access_token(user.username, user.role),
                         role=user.role, username=user.username)


# ----------------------------------------------------------------- planning runs
@router.post("/planning-runs", tags=["planning"])
def create_planning_run(body: PlanningRunRequest, db: Session = Depends(get_db),
                        user=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained. Run scripts/train_forecast_model.py.")
    try:
        result = run_planning_cycle(db, body.start_date, body.horizon_days, body.roster_horizon_days)
        audit.record(db, user.username, "planning_run", entity=result["planning_run_id"],
                     detail=f"horizon {body.horizon_days}d")
        return result
    except ModelNotTrained as e:
        raise HTTPException(503, str(e))


@router.get("/planning-runs/{planning_run_id}", tags=["planning"])
def read_planning_run(planning_run_id: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    run = get_run(db, planning_run_id)
    if run is None:
        raise HTTPException(404, "planning run not found")
    return run


@router.get("/planning-runs", tags=["planning"])
def list_planning_runs(db: Session = Depends(get_db), _=Depends(require_admin)):
    runs = db.scalars(select(PlanningRun).order_by(PlanningRun.created_at.desc()).limit(20)).all()
    return [{"planning_run_id": r.planning_run_id, "status": r.status,
             "start_date": r.start_date.isoformat(), "horizon_days": r.horizon_days,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in runs]


# ----------------------------------------------------------------- forecasting
@router.post("/forecast/run", tags=["forecast"])
def forecast_run(body: ForecastRequest, _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    return {"forecast": future_forecast(body.start_date or _default_start(), body.horizon_days)}


@router.get("/forecast/latest", tags=["forecast"])
def forecast_latest(db: Session = Depends(get_db), _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    start = _latest(db)
    return {"backtest": backtest_latest(30),
            "future": future_forecast(start, 7)}


@router.get("/forecast/series", tags=["forecast"])
def forecast_series(start: date | None = Query(None), horizon: int = Query(14, ge=1, le=60),
                    context_days: int = Query(0, ge=0, le=30), _=Depends(require_admin)):
    """Total-patient series with per-category forecasts and an uncertainty band.
    Past dates carry actual+predicted; future dates carry predicted + [lower, upper]."""
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    return total_series(start or _default_start(), horizon, context_days)


@router.get("/forecast/patterns", tags=["forecast"])
def forecast_patterns(_=Depends(require_admin)):
    """Average arrivals by day-of-week and by month (for the pattern charts)."""
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    return _patterns()


@router.get("/forecast/model-metrics", tags=["forecast"])
def forecast_model_metrics(_=Depends(require_admin)):
    """Model comparison (Naive/Seasonal/RF/XGBoost) with R2/MAE/RMSE/WAPE."""
    try:
        return _model_metrics()
    except ModelNotTrained as e:
        raise HTTPException(503, str(e))


@router.get("/forecast/bounds", tags=["forecast"])
def forecast_bounds(_=Depends(require_admin)):
    """Date range picker bounds for the frontend."""
    return {"last_data_date": last_data_date().isoformat(), "min_date": "2020-01-15"}


@router.get("/forecast/explain", tags=["forecast"])
def forecast_explain(start: date | None = Query(None), horizon: int = Query(7, ge=1, le=30),
                     db: Session = Depends(get_db), _=Depends(require_admin)):
    """Grounded operational explanation for the exact selected forecast window."""
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    start_date = start or _default_start()
    forecast = future_forecast(start_date, horizon)
    totals = [day["total_patient_arrivals"] for day in forecast]
    resource = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
    staff = list(db.scalars(select(Staff).order_by(Staff.staff_name)).all())
    availability = dashboard_operations.availability_from_status(resource, staff)
    availability_by_date, _ = _staff_availability_window(db, staff, start_date, horizon)
    plans = plan_resource_window(
        [{"date": day["date"], **{target: day[target] for target in TARGETS}} for day in forecast],
        availability,
        availability_by_date=availability_by_date,
    )
    shortage_days: dict[str, int] = {}
    overload_days = []
    for day, plan in zip(forecast, plans):
        if plan["summary"]["status"] in {"High", "Critical"}:
            overload_days.append(day["date"])
        for shortage in plan["summary"]["shortages"]:
            shortage_days[shortage] = shortage_days.get(shortage, 0) + 1
    top_shortages = sorted(shortage_days, key=lambda key: (-shortage_days[key], key))[:4]
    categories = [
        ("General OPD", "general_opd_arrivals"),
        ("Fever / infectious", "fever_infectious_arrivals"),
        ("Maternal and child", "maternal_child_arrivals"),
        ("Trauma / emergency", "trauma_emergency_arrivals"),
    ]
    service_mix = []
    category_total = sum(sum(day[key] for day in forecast) for _, key in categories)
    for label, key in categories:
        value = sum(day[key] for day in forecast)
        service_mix.append({"service": label, "patients": value,
                            "share_pct": round(100 * value / category_total, 1) if category_total else 0})
    peak = max(forecast, key=lambda day: day["total_patient_arrivals"])
    actions = [f"Prepare staffing and consumables for the {peak['date']} peak."]
    if top_shortages:
        actions.append("Confirm availability for " + ", ".join(name.replace("_", " ") for name in top_shortages) + ".")
    else:
        actions.append("Maintain current capacity and monitor daily variance.")
    risk = "Critical" if any(p["summary"]["status"] == "Critical" for p in plans) else \
        "High" if any(p["summary"]["status"] == "High" for p in plans) else \
        "Watch" if any(p["summary"]["status"] == "Watch" for p in plans) else "Normal"
    context = {
        "period": f"{forecast[0]['date']} to {forecast[-1]['date']}",
        "horizon_days": horizon,
        "total_patients": sum(totals),
        "avg_total": round(sum(totals) / len(totals)),
        "peak_total": peak["total_patient_arrivals"],
        "peak_date": peak["date"],
        "overall_risk": risk,
        "overload_days": overload_days,
        "top_shortages": top_shortages,
        "service_mix": service_mix,
        "recommended_actions": actions,
    }
    return {**llm_summary.summarize(context), "context": context,
            "evidence": {"forecast_days": len(forecast), "resource_plans_checked": len(plans)}}


# ----------------------------------------------------------------- resources
@router.post("/resources/plan", tags=["resources"])
def resources_plan(body: ForecastRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    start = body.start_date or _default_start()
    forecast = future_forecast(start, body.horizon_days)
    resource = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
    staff = list(db.scalars(select(Staff).order_by(Staff.staff_name)).all())
    availability = dashboard_operations.availability_from_status(resource, staff)
    availability_by_date, availability_summaries = _staff_availability_window(
        db, staff, start, body.horizon_days
    )
    plans = plan_resource_window(
        [{"date": d["date"], **{t: d[t] for t in TARGETS}} for d in forecast],
        availability,
        availability_by_date=availability_by_date,
    )
    for plan in plans:
        plan["staff_availability"] = availability_summaries[plan["date"]]
    return {
        "source_forecast": {"start_date": start.isoformat(), "horizon_days": body.horizon_days},
        "plans": plans,
    }


# ----------------------------------------------------------------- workforce
@router.post("/workforce/generate", tags=["workforce"])
def workforce_generate(body: PlanningRunRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    from backend.services.planning_orchestrator import _nearest_roster_horizon, _staff_dataframe
    start = body.start_date or _default_start()
    roster_h = _nearest_roster_horizon(body.horizon_days, body.roster_horizon_days)
    forecast = future_forecast(start, roster_h)
    fbd = {d["date"]: {t: d[t] for t in TARGETS} for d in forecast}
    records = _staff_availability_records(db, start, roster_h)
    return generate_roster(
        fbd, _staff_dataframe(db), start, roster_h,
        availability=staff_availability_ops.workforce_availability(records),
        pop_size=24, n_gen=15,
    )


# ----------------------------------------------------------------- emergency
@router.post("/emergency/check", tags=["emergency"])
def emergency_check(body: ForecastRequest, _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    return emergency.check_capacity(body.start_date or _default_start(), body.horizon_days)


@router.get("/emergency/scenarios", tags=["emergency"])
def emergency_scenarios(_=Depends(require_admin)):
    return {"scenarios": emergency.list_scenarios()}


@router.post("/emergency/simulate", tags=["emergency"])
def emergency_simulate(body: SimulateRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    try:
        return emergency.simulate_scenario(db, body.scenario_id, body.severity,
                                           body.start_date, body.horizon_days)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/emergency/alerts", tags=["emergency"])
def emergency_send_alert(body: SendAlertRequest, db: Session = Depends(get_db),
                         user=Depends(require_emergency_officer)):
    """Persist an approved alert as 'sent' (human-approved, least-privilege). Facility
    responses are simulated in the prototype UI."""
    from backend.db_models import EmergencyAlert
    alert = EmergencyAlert(scenario=body.scenario, severity=body.severity,
                           requested_support=", ".join(body.requested_support), status="sent")
    db.add(alert)
    db.commit()
    audit.record(db, user.username, "alert_sent", entity=body.scenario,
                 detail=f"severity {body.severity}; facilities {body.facility_ids}",
                 reason="human-approved emergency dispatch")
    return {"alert_id": alert.id, "status": "sent", "scenario": body.scenario,
            "notified_facilities": body.facility_ids}


# ----------------------------------------------------------------- dashboard
@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(db: Session = Depends(get_db), _=Depends(require_admin)):
    latest_demand = db.scalar(select(DailyDemand).order_by(DailyDemand.date.desc()).limit(1))
    latest_res = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
    n_staff = len(db.scalars(select(Staff.staff_id)).all())
    n_fac = len(db.scalars(select(NearbyFacility.id)).all())
    out = {
        "as_of": latest_demand.date.isoformat() if latest_demand else None,
        "staff_count": n_staff, "nearby_facilities": n_fac,
        "latest_demand": None, "latest_resource_status": None,
        "backtest": backtest_latest(14) if is_ready() else [],
        "future_forecast": future_forecast(_latest(db), 7) if is_ready() else [],
    }
    if latest_demand:
        out["latest_demand"] = {"date": latest_demand.date.isoformat(),
                                "total_patient_arrivals": latest_demand.total_patient_arrivals,
                                "fever_infectious_arrivals": latest_demand.fever_infectious_arrivals}
    if latest_res:
        out["latest_resource_status"] = {
            "date": latest_res.date.isoformat(), "emergency_risk_level": latest_res.emergency_risk_level,
            "overflow_patients": latest_res.overflow_patients,
            "available_general_beds": latest_res.available_general_beds,
            "resource_shortage_count": latest_res.resource_shortage_count}
    return out


@router.get("/dashboard/operations", tags=["dashboard"])
def dashboard_operations_view(start: date | None = Query(None),
                              horizon: int = Query(7, ge=1, le=30),
                              db: Session = Depends(get_db), _=Depends(require_admin)):
    """Calculated current-state metrics, coverage, pressure, and rule alerts.

    Current metrics use the latest observed operational day. Forecast pressure
    uses the requested start date and horizon so it stays aligned with the
    forecasting and resource-planning screens. Wait time is an explainable
    estimate; all other inputs come from the demand, resource, staff, roster,
    or forecast services already used by the planner.
    """
    latest_demand = db.scalar(select(DailyDemand).order_by(DailyDemand.date.desc()).limit(1))
    latest_resource = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
    if latest_demand is None:
        raise HTTPException(404, "No demand data available")

    staff = list(db.scalars(select(Staff).order_by(Staff.staff_name)).all())
    observed = dashboard_operations.demand_dict(latest_demand)
    availability = dashboard_operations.availability_from_status(latest_resource, staff)
    current_plan = plan_resources(observed, availability)
    assignments = dashboard_operations.allocate_active_staff(staff, current_plan)
    coverage = dashboard_operations.department_coverage(staff, current_plan, assignments)
    treating = sum(a["status"] == "Treating patients" for a in assignments)
    active_staff = sum(str(s.active_status).lower() == "active" for s in staff)
    utilization = round(100 * len(assignments) / active_staff, 1) if active_staff else 0.0
    wait = dashboard_operations.estimate_wait_minutes(observed, latest_resource, treating)

    roster_planning_id = db.scalar(
        select(RosterEntry.planning_run_id)
        .where(RosterEntry.planning_run_id.is_not(None))
        .order_by(RosterEntry.created_at.desc())
        .limit(1)
    )
    roster_rows = [] if roster_planning_id is None else list(db.scalars(
        select(RosterEntry).where(RosterEntry.planning_run_id == roster_planning_id)
    ).all())
    fairness = dashboard_operations.schedule_fairness(staff, roster_rows, assignments)

    forecast_start = start or _latest(db)
    forecast = future_forecast(forecast_start, horizon) if is_ready() else []
    availability_by_date, _ = _staff_availability_window(db, staff, forecast_start, horizon)
    pressure = dashboard_operations.resource_pressure(
        forecast, availability, availability_by_date
    ) if forecast else []
    alerts = dashboard_operations.build_rule_alerts(
        wait_minutes=wait,
        utilization_pct=utilization,
        resource=latest_resource,
        coverage=coverage,
        pressure=pressure,
        forecast=forecast,
        fairness_index=fairness["shift_equity_index"],
    )

    recent_demand = list(db.scalars(
        select(DailyDemand).order_by(DailyDemand.date.desc()).limit(7)
    ).all())[::-1]
    resource_by_date = {r.date: r for r in db.scalars(
        select(ResourceStatus).where(ResourceStatus.date.in_([d.date for d in recent_demand]))
    ).all()}
    wait_trend = []
    for day in recent_demand:
        day_demand = dashboard_operations.demand_dict(day)
        day_resource = resource_by_date.get(day.date)
        day_plan = plan_resources(day_demand, dashboard_operations.availability_from_status(day_resource, staff))
        day_assignments = dashboard_operations.allocate_active_staff(staff, day_plan)
        day_treating = sum(a["status"] == "Treating patients" for a in day_assignments)
        wait_trend.append({
            "date": day.date.isoformat(),
            "wait_minutes": dashboard_operations.estimate_wait_minutes(
                day_demand, day_resource, day_treating
            ),
        })

    bed_occupancy = None
    if latest_resource and latest_resource.total_general_beds:
        bed_occupancy = round(
            100 * latest_resource.occupied_general_beds / latest_resource.total_general_beds, 1
        )
    return {
        "as_of": latest_demand.date.isoformat(),
        "last_updated": latest_demand.data_last_verified_at.isoformat()
        if latest_demand.data_last_verified_at else None,
        "metrics": {
            "today_patients": observed["total_patient_arrivals"],
            "today_patients_source": "observed",
            "current_wait_minutes": wait,
            "current_wait_source": "estimated from arrivals, treating capacity, and bed pressure",
            "active_treating_staff": treating,
            "active_staff_on_duty": len(assignments),
            "planned_staff_utilization_pct": utilization,
            "general_bed_occupancy_pct": bed_occupancy,
            "schedule_fairness_index": fairness["shift_equity_index"],
            "overtime_hours": fairness["overtime_hours"],
        },
        "active_staff": assignments,
        "department_coverage": coverage,
        "wait_time_trend": wait_trend,
        "resource_pressure": pressure,
        "forecast_selection": {
            "start": forecast_start.isoformat(),
            "horizon": horizon,
            "end": forecast[-1]["date"] if forecast else None,
        },
        "fairness": fairness,
        "alerts": alerts,
        "alert_engine": {
            "kind": "rule-driven",
            "generated_from": ["operational estimate", "staff allocation", "resource status",
                               "workforce plan", "demand forecast"],
        },
    }


@router.get("/dashboard/explain", tags=["dashboard"])
def dashboard_explain(_=Depends(require_admin)):
    """Plain-language briefing of the outlook (LLM if configured, else rule-based)."""
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    start = _default_start()
    forecast = future_forecast(start, 7)
    cap = emergency.check_capacity(start, 7)
    totals = [f["total_patient_arrivals"] for f in forecast]
    shortage_counter: dict[str, int] = {}
    for d in cap["days"]:
        for s in d["shortages"]:
            shortage_counter[s] = shortage_counter.get(s, 0) + 1
    top = sorted(shortage_counter, key=shortage_counter.get, reverse=True)[:4]
    context = {
        "period": f"{forecast[0]['date']} to {forecast[-1]['date']}",
        "avg_total": round(sum(totals) / len(totals)),
        "peak_total": max(totals),
        "overall_risk": cap["overall_risk"],
        "overload_days": cap["overload_days"],
        "top_shortages": top,
    }
    return {**llm_summary.summarize(context), "context": context}


# ----------------------------------------------------------------- governance / audit
@router.get("/audit", tags=["governance"])
def audit_log(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(require_admin)):
    return {"entries": audit.recent(db, limit)}


@router.get("/audit/activity", tags=["governance"])
def audit_activity(db: Session = Depends(get_db), _=Depends(require_admin)):
    return {"activity": audit.activity(db)}


@router.post("/audit", tags=["governance"])
def audit_action(body: AuditActionRequest, db: Session = Depends(get_db), user=Depends(require_admin)):
    """Record a human approval / override (reason required for overrides)."""
    if body.action == "override" and not body.reason:
        raise HTTPException(400, "override requires a reason")
    audit.record(db, user.username, body.action, entity=body.entity, reason=body.reason)
    return {"recorded": True}


@router.get("/system/status", tags=["governance"])
def system_status(_=Depends(require_admin)):
    """Component health for graceful-degradation transparency."""
    db_ok = True
    try:
        from sqlalchemy import text
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"model_ready": is_ready(), "database_connected": db_ok,
            "llm_configured": bool(settings.groq_api_key),
            "last_data_date": last_data_date().isoformat() if is_ready() else None}


@router.get("/system/model-info", tags=["governance"])
def system_model_info(_=Depends(require_admin)):
    try:
        return _model_info()
    except ModelNotTrained as e:
        raise HTTPException(503, str(e))


# ----------------------------------------------------------------- patient (guest, no auth)
@router.get("/patient/facilities", tags=["patient"])
def patient_facilities(service: str | None = Query(None), urgency: str | None = Query(None),
                       db: Session = Depends(get_db)):
    return {"facilities": patient_routing.rank_facilities(db, service, urgency)}


@router.get("/patient/facilities/{facility_id}", tags=["patient"])
def patient_facility_detail(facility_id: str, speciality: list[str] | None = Query(None),
                            db: Session = Depends(get_db)):
    detail = patient_routing.facility_detail(db, facility_id, speciality)
    if detail is None:
        raise HTTPException(404, "facility not found")
    return detail


@router.get("/patient/outbreak-alert", tags=["patient"])
def patient_outbreak_alert(db: Session = Depends(get_db)):
    """Public outbreak advisory (guest). No diagnosis; guidance only."""
    return patient_routing.outbreak_alert(db)


@router.get("/patient/triage", tags=["patient"])
def patient_triage(text: str = Query("", max_length=300), db: Session = Depends(get_db)):
    """Symptom -> facility routing (guest). NEVER diagnoses or suggests treatment;
    red-flag symptoms return an emergency prompt (call 108) + capable facilities."""
    return patient_routing.triage(db, text)


# ----------------------------------------------------------------- helpers
def _staff_availability_records(db: Session, start: date, horizon: int):
    end = start + timedelta(days=horizon - 1)
    return list(db.scalars(
        select(StaffAvailability)
        .where(StaffAvailability.date.between(start, end))
        .order_by(StaffAvailability.date, StaffAvailability.staff_id)
    ).all())


def _staff_availability_window(db: Session, staff, start: date, horizon: int):
    dates = [start + timedelta(days=offset) for offset in range(horizon)]
    records = _staff_availability_records(db, start, horizon)
    return (
        staff_availability_ops.resource_availability_by_date(staff, records, dates),
        staff_availability_ops.availability_summaries(staff, records, dates),
    )


def _latest(db: Session) -> date:
    d = db.scalar(select(DailyDemand.date).order_by(DailyDemand.date.desc()).limit(1))
    from datetime import timedelta
    return (d + timedelta(days=1)) if d else date.today()


def _default_start() -> date:
    from backend.db import SessionLocal
    with SessionLocal() as db:
        return _latest(db)
