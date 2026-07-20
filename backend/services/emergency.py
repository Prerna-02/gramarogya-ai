"""Emergency coordination engine (Phase 12).

Two parts:
- `check_capacity` — the basic forward capacity/risk check (used by the dashboard
  and the Emergency tab's live view).
- `simulate_scenario` — the scenario planner: the admin picks a runtime scenario
  (from data/emergency_scenarios.json) + severity; the engine temporarily adds
  the surge on top of the baseline forecast, recomputes resource shortages,
  estimates overflow/risk, lists precautions, ranks nearby facilities for support,
  and drafts an alert. Scenarios are NEVER baked into the historical data.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from backend.services.forecasting import future_forecast, last_data_date
from backend.services.patient_routing import rank_facilities
from backend.services.resource_planning import plan_resources

SCENARIOS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "emergency_scenarios.json"

TARGETS = ["total_patient_arrivals", "general_opd_arrivals", "fever_infectious_arrivals",
           "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions"]
CATEGORIES = ["general_opd_arrivals", "fever_infectious_arrivals",
              "maternal_child_arrivals", "trauma_emergency_arrivals"]


# --------------------------------------------------------------- live capacity check
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


# --------------------------------------------------------------- scenario planner
@lru_cache(maxsize=1)
def _scenarios() -> dict:
    return {s["id"]: s for s in json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]}


def list_scenarios() -> list[dict]:
    return [{k: s[k] for k in ("id", "name", "icon", "category", "description", "duration_days")}
            for s in _scenarios().values()]


def _line(plan: dict, name: str) -> dict | None:
    if name.endswith("_beds"):                       # beds dict is keyed general/emergency/isolation
        return plan["beds"].get(name[:-5])
    if name in plan.get("staff", {}):
        return plan["staff"][name]
    if name in plan.get("medicines", {}):
        return plan["medicines"][name]
    if name == "oxygen_cylinders":
        return plan["oxygen"]
    if name == "ambulances":
        return plan["ambulances"]
    return None


def simulate_scenario(db: Session, scenario_id: str, severity: int = 3,
                      start_date: date | None = None, horizon: int = 7) -> dict:
    scen = _scenarios().get(scenario_id)
    if scen is None:
        raise ValueError(f"unknown scenario '{scenario_id}'")
    severity = max(1, min(5, int(severity)))
    if start_date is None:
        start_date = last_data_date() + timedelta(days=1)

    baseline = future_forecast(start_date, horizon)
    surge = scen["surge_per_severity"]
    surged = []
    for day in baseline:
        s = dict(day)
        for k, per in surge.items():
            s[k] = int(day[k] + round(per * severity))
        s["total_patient_arrivals"] = sum(s[c] for c in CATEGORIES)
        surged.append(s)

    forecast = [{"date": b["date"], "baseline_total": b["total_patient_arrivals"],
                 "surged_total": sr["total_patient_arrivals"],
                 "surge": sr["total_patient_arrivals"] - b["total_patient_arrivals"]}
                for b, sr in zip(baseline, surged)]
    extra_patients = sum(f["surge"] for f in forecast)

    peak_i = max(range(len(surged)), key=lambda i: surged[i]["total_patient_arrivals"])
    bplan = plan_resources({t: baseline[peak_i][t] for t in TARGETS})
    splan = plan_resources({t: surged[peak_i][t] for t in TARGETS})

    curated = list(dict.fromkeys(scen["stresses"] + ["general_beds", "emergency_beds",
                   "isolation_beds", "oxygen_cylinders", "ambulances"]))
    resources = []
    for name in curated:
        sl, bl = _line(splan, name), _line(bplan, name)
        if sl:
            resources.append({"resource": name, "baseline": bl["required"] if bl else 0,
                              "surged": sl["required"], "available": sl["available"],
                              "shortage": sl["shortage"]})

    overflow = sum(splan["beds"][b]["shortage"] for b in ("general", "emergency", "isolation"))
    risk = splan["summary"]["status"]
    if overflow > 0 and risk in ("Normal", "Watch"):
        risk = "High"
    if overflow > 0 and severity >= 4:
        risk = "Critical"

    support = scen["support_needed"]
    facilities = rank_facilities(db)
    for f in facilities:
        f["can_help"] = any(any(s.lower() in c.lower() for c in f["capabilities"]) for s in support)
    facilities.sort(key=lambda f: (not f["can_help"], {"Available": 0, "Limited": 1, "Busy": 2}.get(f["status"], 3)))

    deadline = {"emergency": 2, "event": 6, "outbreak": 24}.get(scen["category"], 12)
    alert = {"scenario": scen["name"], "severity": severity,
             "expected_surge": surged[peak_i]["total_patient_arrivals"] - baseline[peak_i]["total_patient_arrivals"],
             "requested_support": support, "deadline_hours": deadline, "status": "draft"}

    return {
        "scenario": {k: scen[k] for k in ("id", "name", "icon", "category", "description", "duration_days")},
        "severity": severity, "start_date": start_date.isoformat(), "horizon": horizon,
        "forecast": forecast,
        "impact": {"peak_baseline": baseline[peak_i]["total_patient_arrivals"],
                   "peak_surged": surged[peak_i]["total_patient_arrivals"],
                   "peak_date": surged[peak_i]["date"], "extra_patients": extra_patients,
                   "overflow_estimate": int(overflow), "risk_level": risk,
                   "shortage_count": splan["summary"]["shortage_count"]},
        "resources": resources,
        "precautions": scen["precautions"],
        "alert": alert,
        "facilities": facilities,
    }
