"""Emergency capacity check (Phase 9 basic; full coordination engine in Phase 12).

Combines the forecast with the resource-planning status to flag likely overload.
The full engine (thresholds, nearby-facility ranking, alert workflow, runtime
`emergency_scenarios.json`) is built in Phase 12.
"""
from __future__ import annotations

from datetime import date

from backend.services.forecasting import future_forecast
from backend.services.resource_planning import plan_resources

TARGETS = ["total_patient_arrivals", "general_opd_arrivals", "fever_infectious_arrivals",
           "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions"]


def check_capacity(start_date: date | None = None, horizon_days: int = 7) -> dict:
    forecast = future_forecast(start_date, horizon_days)
    days = []
    for day in forecast:
        plan = plan_resources({t: day[t] for t in TARGETS})
        days.append({"date": day["date"], "status": plan["summary"]["status"],
                     "shortage_count": plan["summary"]["shortage_count"],
                     "shortages": plan["summary"]["shortages"]})
    overload = [d["date"] for d in days if d["status"] in ("High", "Critical")]
    overall = "Critical" if any(d["status"] == "Critical" for d in days) \
        else "High" if overload else "Watch" if any(d["shortage_count"] for d in days) else "Normal"
    return {"overall_risk": overall, "overload_days": overload, "days": days}
