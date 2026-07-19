"""API endpoints (Phase 9)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import authenticate, create_access_token, require_admin
from backend.db import get_db
from backend.db_models import DailyDemand, NearbyFacility, PlanningRun, ResourceStatus, Staff
from backend.schemas import ForecastRequest, PlanningRunRequest, TokenResponse
from backend.services import emergency, llm_summary, patient_routing
from backend.services.forecasting import ModelNotTrained, backtest_latest, future_forecast, is_ready
from backend.services.planning_orchestrator import get_run, run_planning_cycle
from backend.services.resource_planning import plan_resources
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
    return TokenResponse(access_token=create_access_token(user.username, user.role),
                         role=user.role, username=user.username)


# ----------------------------------------------------------------- planning runs
@router.post("/planning-runs", tags=["planning"])
def create_planning_run(body: PlanningRunRequest, db: Session = Depends(get_db),
                        _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained. Run scripts/train_forecast_model.py.")
    try:
        return run_planning_cycle(db, body.start_date, body.horizon_days, body.roster_horizon_days)
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


# ----------------------------------------------------------------- resources
@router.post("/resources/plan", tags=["resources"])
def resources_plan(body: ForecastRequest, _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    forecast = future_forecast(body.start_date or _default_start(), body.horizon_days)
    return {"plans": [{"date": d["date"], **plan_resources({t: d[t] for t in TARGETS})}
                      for d in forecast]}


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
    return generate_roster(fbd, _staff_dataframe(db), start, roster_h, pop_size=24, n_gen=15)


# ----------------------------------------------------------------- emergency
@router.post("/emergency/check", tags=["emergency"])
def emergency_check(body: ForecastRequest, _=Depends(require_admin)):
    if not is_ready():
        raise HTTPException(503, "Forecast model not trained.")
    return emergency.check_capacity(body.start_date or _default_start(), body.horizon_days)


# ----------------------------------------------------------------- dashboard
@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(db: Session = Depends(get_db), _=Depends(require_admin)):
    latest_demand = db.scalar(select(DailyDemand).order_by(DailyDemand.date.desc()).limit(1))
    latest_res = db.scalar(select(ResourceStatus).order_by(ResourceStatus.date.desc()).limit(1))
    staff_count = db.scalar(select(Staff).order_by(Staff.staff_id)) is not None
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


# ----------------------------------------------------------------- patient (guest, no auth)
@router.get("/patient/facilities", tags=["patient"])
def patient_facilities(service: str | None = Query(None), urgency: str | None = Query(None),
                       db: Session = Depends(get_db)):
    return {"facilities": patient_routing.rank_facilities(db, service, urgency)}


@router.get("/patient/facilities/{facility_id}", tags=["patient"])
def patient_facility_detail(facility_id: int, db: Session = Depends(get_db)):
    detail = patient_routing.facility_detail(db, facility_id)
    if detail is None:
        raise HTTPException(404, "facility not found")
    return detail


# ----------------------------------------------------------------- helpers
def _latest(db: Session) -> date:
    d = db.scalar(select(DailyDemand.date).order_by(DailyDemand.date.desc()).limit(1))
    from datetime import timedelta
    return (d + timedelta(days=1)) if d else date.today()


def _default_start() -> date:
    from backend.db import SessionLocal
    with SessionLocal() as db:
        return _latest(db)
