"""Calculated operational metrics for the administration dashboard.

The dashboard is a decision-support view over existing demand, resource,
workforce, and forecast outputs.  It deliberately contains no timer-driven or
random alerts.  Metrics that are not directly observed (currently wait time)
carry an explicit ``estimated`` source and an explanation of the formula.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt

from backend.services.resource_planning import plan_resource_window, plan_resources
from backend.services.scheduling_config import (
    COVERAGE_TEMPLATE,
    DEFAULT_TARGET_WEEKLY_HOURS,
    ELIGIBLE_DESIGNATIONS,
    FAIRNESS_GROUPS,
    SHIFT_HOURS,
)


TARGETS = [
    "total_patient_arrivals",
    "general_opd_arrivals",
    "fever_infectious_arrivals",
    "maternal_child_arrivals",
    "trauma_emergency_arrivals",
    "expected_admissions",
]

CLINICAL_CATEGORIES = {"Doctor", "Nursing", "Nurse", "Medical"}
ROLE_PRIORITY = [
    "emergency_doctors",
    "obgyn_doctors",
    "pediatricians",
    "physicians",
    "general_doctors",
    "senior_nursing_officers",
    "nursing_officers",
    "anm_staff",
    "lab_technicians",
    "pharmacists",
    "ambulance_crew",
]


def demand_dict(row) -> dict:
    """Return the six planning targets from an ORM row or mapping."""
    if isinstance(row, dict):
        return {k: int(round(row.get(k, 0) or 0)) for k in TARGETS}
    return {k: int(round(getattr(row, k, 0) or 0)) for k in TARGETS}


def availability_from_status(resource, staff) -> dict:
    """Build planner availability from the latest resource and staff records."""
    active = [s for s in staff if str(s.active_status).lower() == "active"]
    availability = {}
    for role, designations in ELIGIBLE_DESIGNATIONS.items():
        availability[role] = sum(s.designation in designations for s in active)

    if resource is not None:
        availability.update({
            # Occupied + available is the usable in-service capacity and
            # excludes beds recorded as installed but temporarily out of use.
            "general_beds": resource.occupied_general_beds + resource.available_general_beds,
            "emergency_beds": resource.occupied_emergency_beds + resource.available_emergency_beds,
            "isolation_beds": resource.occupied_isolation_beds + resource.available_isolation_beds,
            "diagnostic_test_kits": resource.closing_stock_diagnostic_test_kits,
            "antipyretics": resource.closing_stock_antipyretics,
            "iv_fluids": resource.closing_stock_iv_fluids,
            "ors": resource.closing_stock_ors,
            "ppe_kits": resource.closing_stock_ppe_kits,
            "oxygen_cylinders": resource.available_oxygen_cylinders,
            "ambulances": resource.available_ambulances,
        })
    return availability


def _role_requirements(plan: dict) -> dict[str, int]:
    req = {role: int(line["required"]) for role, line in plan["staff"].items()}
    req["ambulance_crew"] = max(1, int(plan["ambulances"]["required"]))
    return req


def allocate_active_staff(staff, plan: dict, shift: str = "Morning") -> list[dict]:
    """Create a deterministic current-duty allocation from eligible staff.

    This is an operational view, not a replacement for NSGA-II rostering.  It
    selects eligible active staff for the current shift in priority order and
    never assigns the same person twice.
    """
    required = _role_requirements(plan)
    used: set[str] = set()
    assignments = []
    active = sorted(
        (s for s in staff if str(s.active_status).lower() == "active"),
        key=lambda s: (-int(s.experience_years), s.staff_name),
    )
    for role in ROLE_PRIORITY:
        template = COVERAGE_TEMPLATE[role]
        if shift not in template["shifts"]:
            continue
        eligible_designations = ELIGIBLE_DESIGNATIONS[role]
        candidates = [
            s for s in active
            if s.staff_id not in used
            and s.designation in eligible_designations
            and shift in {x.strip() for x in str(s.shift_eligibility).split("|")}
        ]
        for person in candidates[:required.get(role, 0)]:
            used.add(person.staff_id)
            if role == "ambulance_crew":
                status = "Emergency ready"
            elif role in {"lab_technicians", "pharmacists"}:
                status = "Supporting care"
            else:
                status = "Treating patients"
            assignments.append({
                "staff_id": person.staff_id,
                "name": person.staff_name,
                "role": person.designation,
                "department": template["department"],
                "shift": shift,
                "status": status,
                "shift_ends": SHIFT_HOURS[shift][1],
            })
    return assignments


def department_coverage(staff, plan: dict, assignments: list[dict]) -> list[dict]:
    """Aggregate required, assigned, and available people by department."""
    required = defaultdict(int)
    available_ids = defaultdict(set)
    assigned = defaultdict(int)
    role_req = _role_requirements(plan)
    active = [s for s in staff if str(s.active_status).lower() == "active"]

    for role, count in role_req.items():
        department = COVERAGE_TEMPLATE[role]["department"]
        required[department] += count
        eligible = ELIGIBLE_DESIGNATIONS[role]
        available_ids[department].update(s.staff_id for s in active if s.designation in eligible)
    for row in assignments:
        assigned[row["department"]] += 1

    rows = []
    for department in sorted(required):
        need = required[department]
        have = assigned[department]
        rows.append({
            "department": department,
            "required": need,
            "assigned": have,
            "available": len(available_ids[department]),
            "gap": max(0, need - have),
            "coverage_pct": round(100 * have / need, 1) if need else 100.0,
        })
    return rows


def estimate_wait_minutes(demand: dict, resource, active_clinicians: int) -> int:
    """Estimate wait from patient load, treating capacity, and bed pressure.

    The formula is intentionally simple and inspectable: a 12-minute service
    baseline, three minutes for each patient-per-clinician above six, and up to
    eight minutes of bed-pressure overhead.  It can later be replaced by queue
    timestamps without changing the dashboard contract.
    """
    clinicians = max(1, active_clinicians)
    load_per_clinician = demand["total_patient_arrivals"] / clinicians
    bed_pressure = 0.0
    if resource is not None and resource.total_general_beds:
        bed_pressure = resource.occupied_general_beds / resource.total_general_beds
    return max(5, int(round(12 + max(0.0, load_per_clinician - 6) * 3 + bed_pressure * 8)))


def schedule_fairness(staff, roster_rows, current_assignments: list[dict]) -> dict:
    """Measure workload equality within comparable role groups.

    All active staff are included, including people with zero assignments. This
    prevents an apparently perfect result caused by omitting unassigned staff.
    """
    by_id = {s.staff_id: s for s in staff if str(s.active_status).lower() == "active"}
    loads = defaultdict(lambda: {"shifts": 0, "hours": 0, "weekly_hours": defaultdict(int),
                                 "nights": 0, "weekends": 0})
    if roster_rows:
        for row in roster_rows:
            if row.staff_id not in by_id:
                continue
            load = loads[row.staff_id]
            load["shifts"] += 1
            load["hours"] += SHIFT_HOURS.get(row.shift, (None, None, 0))[2]
            load["weekly_hours"][row.work_date.isocalendar()[:2]] += SHIFT_HOURS.get(row.shift, (None, None, 0))[2]
            load["nights"] += int(row.shift == "Night")
            load["weekends"] += int(row.work_date.weekday() >= 5)
    else:
        for row in current_assignments:
            loads[row["staff_id"]]["shifts"] += 1
            loads[row["staff_id"]]["hours"] += SHIFT_HOURS[row["shift"]][2]
            loads[row["staff_id"]]["weekly_hours"][(0, 0)] += SHIFT_HOURS[row["shift"]][2]

    groups = defaultdict(list)
    overtime = 0
    for sid, person in by_id.items():
        group = FAIRNESS_GROUPS.get(person.designation, "other")
        groups[group].append(loads[sid]["shifts"])
        overtime += sum(max(0, hours - DEFAULT_TARGET_WEEKLY_HOURS)
                        for hours in loads[sid]["weekly_hours"].values())

    cvs = []
    for values in groups.values():
        if len(values) < 2 or sum(values) == 0:
            continue
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        cvs.append(sqrt(variance) / (mean + 1))
    inequality = sum(cvs) / len(cvs) if cvs else 0.0
    return {
        "shift_equity_index": round(max(0.0, min(100.0, 100 * (1 - inequality))), 1),
        "overtime_hours": int(overtime),
        "source": "latest optimized roster" if roster_rows else "current duty allocation",
    }


def resource_pressure(forecast: list[dict], availability: dict,
                      availability_by_date: dict[str, dict] | None = None) -> list[dict]:
    """Return normalized capacity pressure for each forecast day and resource."""
    curated = [
        "general_doctors", "emergency_doctors", "nursing_officers",
        "general_beds", "emergency_beds", "diagnostic_test_kits",
        "oxygen_cylinders", "ambulances",
    ]
    result = []
    plans = plan_resource_window(
        [{"date": day["date"], **{key: day[key] for key in TARGETS}} for day in forecast],
        availability,
        availability_by_date=availability_by_date,
    )
    for day, plan in zip(forecast, plans):
        sections = {
            **plan["staff"],
            "general_beds": plan["beds"]["general"],
            "emergency_beds": plan["beds"]["emergency"],
            "diagnostic_test_kits": plan["medicines"]["diagnostic_test_kits"],
            "oxygen_cylinders": plan["oxygen"],
            "ambulances": plan["ambulances"],
        }
        for name in curated:
            line = sections[name]
            available = int(line["available"])
            required = int(line["required"])
            result.append({
                "date": day["date"],
                "resource": name,
                "required": required,
                "available": available,
                "shortage": int(line["shortage"]),
                "pressure_pct": round(100 * required / available, 1) if available else 999.0,
            })
    return result


def build_rule_alerts(*, wait_minutes: int, utilization_pct: float, resource,
                      coverage: list[dict], pressure: list[dict], forecast: list[dict],
                      fairness_index: float | None = None) -> list[dict]:
    """Create stable, deduplicated alerts from calculated operational rules."""
    alerts = []

    def add(alert_id, severity, title, detail, action, source):
        alerts.append({"id": alert_id, "severity": severity, "title": title,
                       "detail": detail, "action": action, "source": source,
                       "status": "Open"})

    if wait_minutes >= 45:
        add("wait-time-high", "high", "Patient wait time above target",
            f"Estimated wait is {wait_minutes} minutes against a 30-minute target.",
            "Review the queue and redeploy an available clinician.", "operational estimate")
    elif wait_minutes >= 30:
        add("wait-time-watch", "warn", "Patient wait time approaching limit",
            f"Estimated wait is {wait_minutes} minutes.",
            "Monitor arrivals and prepare additional OPD coverage.", "operational estimate")

    if utilization_pct >= 90:
        add("staff-utilization-high", "high", "Workforce utilization is very high",
            f"{utilization_pct:.0f}% of active staff capacity is allocated.",
            "Check breaks, on-call cover, and fatigue exposure.", "staff allocation")
    elif utilization_pct >= 80:
        add("staff-utilization-watch", "warn", "Workforce capacity tightening",
            f"Planned staff utilization is {utilization_pct:.0f}%.",
            "Review department coverage before the next shift.", "staff allocation")

    gaps = [r for r in coverage if r["gap"] > 0]
    if gaps:
        biggest = max(gaps, key=lambda r: r["gap"])
        add(f"coverage-{biggest['department'].lower().replace(' ', '-')}", "high",
            f"Coverage gap in {biggest['department']}",
            f"{biggest['assigned']} assigned for {biggest['required']} required positions.",
            "Activate eligible on-call cover or arrange cross-coverage.", "workforce plan")

    if fairness_index is not None and fairness_index < 70:
        severity = "high" if fairness_index < 55 else "warn"
        add("schedule-fairness-watch", severity, "Schedule burden needs review",
            f"Shift equity is {fairness_index:.1f} out of 100.",
            "Review night, weekend, on-call, and overtime distribution within role groups.",
            "optimized roster")

    if resource is not None and resource.total_general_beds:
        occupancy = 100 * resource.occupied_general_beds / resource.total_general_beds
        if occupancy >= 90:
            add("general-bed-pressure", "high", "General beds near capacity",
                f"General bed occupancy is {occupancy:.0f}%.",
                "Review expected discharges and referral readiness.", "resource status")
        elif occupancy >= 80:
            add("general-bed-watch", "warn", "General bed pressure rising",
                f"General bed occupancy is {occupancy:.0f}%.",
                "Confirm discharge plans and available overflow space.", "resource status")

    shortages = [p for p in pressure if p["shortage"] > 0]
    if shortages:
        first_date = min(p["date"] for p in shortages)
        on_first = [p for p in shortages if p["date"] == first_date]
        names = ", ".join(p["resource"].replace("_", " ") for p in on_first[:3])
        add("forecast-resource-pressure", "warn", "Forecast resource pressure",
            f"Shortage pressure begins {first_date}: {names}.",
            "Review the selected resource-pressure view and prepare supplies or cover.", "forecast plan")

    if forecast:
        peak = max(forecast, key=lambda d: d["total_patient_arrivals"])
        avg = sum(d["total_patient_arrivals"] for d in forecast) / len(forecast)
        if peak["total_patient_arrivals"] >= avg * 1.08:
            add("forecast-peak", "info", "Demand peak ahead",
                f"{peak['total_patient_arrivals']} patients are forecast on {peak['date']}.",
                "Align OPD coverage and consumables with the peak day.", "demand forecast")

    severity_order = {"high": 0, "warn": 1, "info": 2}
    return sorted(alerts, key=lambda a: (severity_order[a["severity"]], a["id"]))
