"""NSGA-II workforce optimization and rostering (Phase 8).

Turns Phase 7 staffing requirements + `staff_master.csv` into a roster of named
staff assignments (date / shift / department / role), optimising competing
objectives with pymoo's NSGA-II and auto-selecting one **balanced** recommended
roster (plus up to two distinct alternatives).

Public entry points:
    generate_roster(forecast_by_date, staff_df, start_date, horizon, availability=None, ...)
    validate_override(roster, change, staff_records, availability=None)

Design notes
- Hard constraints are enforced by a **feasibility-preserving decode**: a slot is
  filled only if the chosen staff member satisfies every hard rule, otherwise it
  is left unfilled and reported as an unmet requirement (no fabricated staff, no
  invalid schedule).
- Leave / work-history fields are not in the repo; they are accepted via the
  optional `availability` argument with a documented all-available fallback.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize

from backend.services.resource_planning import plan_resources
from backend.services.scheduling_config import (
    CONFIRMED_DAYS, COVERAGE_TEMPLATE, DEFAULT_TARGET_WEEKLY_HOURS, ELIGIBLE_DESIGNATIONS,
    FAIRNESS_GROUPS, N_GEN, OBJECTIVES, POP_SIZE, RANKING_WEIGHTS, SEED, SHIFT_END_HOUR,
    SHIFT_HOURS, SHIFT_START_HOUR, SUPPORTED_HORIZONS, distribute_count,
)

MIN_SLOT_WEIGHT = 5.0   # penalty multiplier for an unfilled *mandatory* slot


# ------------------------------------------------------------------ data model
@dataclass
class ShiftRequirement:
    date: str
    shift: str
    department: str
    designation: str
    min_count: int
    preferred_count: int
    role_key: str
    skill: str | None = None
    specialist: str | None = None
    supervisory: bool = False


@dataclass
class Slot:
    req_idx: int
    date: str
    shift: str
    department: str
    designation: str
    role_key: str
    mandatory: bool
    specialist: str | None
    eligible: list = field(default_factory=list)


# ------------------------------------------------------------------ staff prep
def build_staff_records(staff_df: pd.DataFrame) -> dict:
    records = {}
    for _, r in staff_df.iterrows():
        records[r["staff_id"]] = {
            "staff_id": r["staff_id"],
            "staff_name": r["staff_name"],
            "designation": r["designation"],
            "department": r["department"],
            "skill_tags": {s.strip().lower() for s in str(r["skill_tags"]).split("|")},
            "shift_eligibility": {s.strip() for s in str(r["shift_eligibility"]).split("|")},
            "max_weekly_hours": int(r["max_weekly_hours"]),
            "minimum_rest_hours": int(r["minimum_rest_hours"]),
            "max_consecutive_working_days": int(r["max_consecutive_working_days"]),
            "max_night_shifts_per_month": int(r["max_night_shifts_per_month"]),
            "preferred_shift": r["preferred_shift"],
            "emergency_on_call": int(r["emergency_on_call"]),
            "active": str(r["active_status"]).lower() == "active",
            "group": FAIRNESS_GROUPS.get(r["designation"], "other"),
        }
    return records


def default_availability() -> dict:
    """Fallback when no leave / history is supplied: everyone available."""
    return {"leave": {}, "unavailable_shifts": {}, "locked": [], "completed": [], "history": {}}


# ------------------------------------------------------------ requirement build
def _default_forecast() -> dict:
    return {"general_opd_arrivals": 90, "fever_infectious_arrivals": 30,
            "maternal_child_arrivals": 8, "trauma_emergency_arrivals": 10,
            "total_patient_arrivals": 138, "expected_admissions": 8}


def build_shift_requirements(forecast_by_date: dict, dates: list[str], warnings: list) -> list[ShiftRequirement]:
    reqs = []
    for d in dates:
        fc = forecast_by_date.get(d)
        if fc is None:
            fc = _default_forecast()
            warnings.append(f"no forecast for {d}; used prototype default")
        plan = plan_resources(fc)
        staff_plan = plan["staff"]
        # ambulance crew requirement from the ambulance vehicle plan.
        counts = {k: v["required"] for k, v in staff_plan.items()}
        counts["ambulance_crew"] = max(1, plan["ambulances"]["required"])
        for role_key, tmpl in COVERAGE_TEMPLATE.items():
            need = counts.get(role_key)
            if need is None:
                continue
            shifts = list(tmpl["shifts"])
            around = tmpl.get("around_clock", False)
            per_shift = distribute_count(need, len(shifts), around)
            for shift, c in zip(shifts, per_shift):
                reqs.append(ShiftRequirement(
                    date=d, shift=shift, department=tmpl["department"],
                    designation=tmpl["designation"], min_count=max(1, c) if around else c,
                    preferred_count=max(1, c), role_key=role_key, skill=tmpl.get("skill"),
                    specialist=tmpl.get("specialist"), supervisory=tmpl.get("supervisory", False)))
            if tmpl.get("oncall_shift"):
                reqs.append(ShiftRequirement(
                    date=d, shift=tmpl["oncall_shift"], department=tmpl["department"],
                    designation=tmpl["designation"], min_count=1, preferred_count=1,
                    role_key=role_key, skill=tmpl.get("skill"), specialist=tmpl.get("specialist")))
    return reqs


def build_slots(reqs: list[ShiftRequirement], staff: dict) -> list[Slot]:
    slots = []
    for i, r in enumerate(reqs):
        acceptable = ELIGIBLE_DESIGNATIONS.get(r.role_key, [r.designation])
        eligible = [sid for sid, s in staff.items()
                    if s["active"] and s["designation"] in acceptable
                    and r.shift in s["shift_eligibility"]]
        for k in range(r.preferred_count):
            slots.append(Slot(req_idx=i, date=r.date, shift=r.shift, department=r.department,
                              designation=r.designation, role_key=r.role_key,
                              mandatory=k < r.min_count, specialist=r.specialist, eligible=eligible))
    # Process mandatory slots first, then chronologically.
    slots.sort(key=lambda s: (s.date, not s.mandatory, s.shift))
    return slots


# ------------------------------------------------------------------ decode
def _abs_hours(day_index: int, shift: str, end: bool) -> int:
    base = day_index * 24
    return base + (SHIFT_END_HOUR[shift] if end else SHIFT_START_HOUR[shift])


def decode_roster(x, ctx) -> tuple[list[dict], dict]:
    """Feasibility-preserving decode: fill each slot with the first feasible
    candidate (GA-preferred first), else leave it unfilled."""
    staff = ctx["staff"]
    slots = ctx["slots"]
    reqs = ctx["reqs"]
    dates = ctx["dates"]
    date_index = {d: i for i, d in enumerate(dates)}
    avail = ctx["availability"]
    target_week = ctx["target_weekly_hours"]

    sched = {sid: {} for sid in staff}          # staff -> {date: shift}
    hours_week = {sid: {} for sid in staff}      # staff -> {isoweek: hours}
    night_count = {sid: 0 for sid in staff}
    assigned_counts = {i: 0 for i in range(len(reqs))}
    assignments = []

    # Pre-place locked + completed assignments (immutable; occupy the staff).
    for a in avail.get("locked", []) + avail.get("completed", []):
        sid, d, sh = a["staff_id"], a["date"], a["shift"]
        if sid in staff and d in date_index:
            sched[sid][d] = sh
            iso = _isoweek(d)
            hours_week[sid][iso] = hours_week[sid].get(iso, 0) + SHIFT_HOURS[sh][2]
            if sh == "Night":
                night_count[sid] += 1

    def feasible(sid, d, shift):
        s = staff[sid]
        if shift not in s["shift_eligibility"]:
            return False
        if d in sched[sid]:                                  # one shift per day
            return False
        if d in avail.get("leave", {}).get(sid, set()):
            return False
        if (d, shift) in avail.get("unavailable_shifts", {}).get(sid, set()):
            return False
        iso = _isoweek(d)
        if hours_week[sid].get(iso, 0) + SHIFT_HOURS[shift][2] > s["max_weekly_hours"]:
            return False
        if shift == "Night" and night_count[sid] >= s["max_night_shifts_per_month"]:
            return False
        di = date_index[d]
        # minimum rest vs adjacent assigned days
        for nb in (di - 1, di + 1):
            if 0 <= nb < len(dates) and dates[nb] in sched[sid]:
                osh = sched[sid][dates[nb]]
                a_start, a_end = _abs_hours(di, shift, False), _abs_hours(di, shift, True)
                b_start, b_end = _abs_hours(nb, osh, False), _abs_hours(nb, osh, True)
                gap = a_start - b_end if di > nb else b_start - a_end
                if gap < s["minimum_rest_hours"]:
                    return False
        # consecutive working days
        run = 1
        j = di - 1
        while j >= 0 and dates[j] in sched[sid]:
            run += 1; j -= 1
        if run > s["max_consecutive_working_days"]:
            return False
        return True

    for k, slot in enumerate(slots):
        gene = float(x[k])
        elig = slot.eligible
        if not elig:
            continue
        # GA-preferred candidate first, then the rest of the eligible pool.
        idx = int(gene * len(elig))
        idx = min(idx, len(elig) - 1)
        order = [elig[idx]] + [e for e in elig if e != elig[idx]]
        for sid in order:
            if feasible(sid, slot.date, slot.shift):
                sched[sid][slot.date] = slot.shift
                iso = _isoweek(slot.date)
                hours_week[sid][iso] = hours_week[sid].get(iso, 0) + SHIFT_HOURS[slot.shift][2]
                if slot.shift == "Night":
                    night_count[sid] += 1
                assigned_counts[slot.req_idx] += 1
                assignments.append({
                    "staff_id": sid, "staff_name": staff[sid]["staff_name"],
                    "date": slot.date, "shift": slot.shift, "department": slot.department,
                    "assigned_role": slot.designation, "role_key": slot.role_key,
                    "specialist": slot.specialist})
                break

    metrics = _objectives(assignments, reqs, assigned_counts, staff, avail, dates, target_week)
    return assignments, metrics


def _isoweek(d: str) -> str:
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w}"


def _is_weekend(d: str) -> bool:
    return datetime.strptime(d, "%Y-%m-%d").date().weekday() >= 5


# ------------------------------------------------------------------ objectives
def _objectives(assignments, reqs, assigned_counts, staff, avail, dates, target_week) -> dict:
    # understaffing (service coverage)
    mand_gap = pref_gap = 0
    emergency_uncovered = 0
    for i, r in enumerate(reqs):
        a = assigned_counts.get(i, 0)
        mand_gap += max(0, r.min_count - a)
        pref_gap += max(0, r.preferred_count - a)
        if r.department == "Emergency" or r.shift == "On-call":
            emergency_uncovered += max(0, r.min_count - a)
    understaffing = mand_gap * MIN_SLOT_WEIGHT + (pref_gap - mand_gap)

    # per-staff aggregates
    hist = avail.get("history", {})
    load = {sid: {"night": 0, "weekend": 0, "oncall": 0, "hours": 0.0, "depts": set(), "nonpref": 0, "days": 0}
            for sid in staff}
    for a in assignments:
        sid, sh, d = a["staff_id"], a["shift"], a["date"]
        L = load[sid]
        L["hours"] += SHIFT_HOURS[sh][2]
        L["days"] += 1
        L["depts"].add(a["department"])
        if sh == "Night":
            L["night"] += 1
        if sh == "On-call":
            L["oncall"] += 1
        if _is_weekend(d):
            L["weekend"] += 1
        if sh != staff[sid]["preferred_shift"]:
            L["nonpref"] += 1

    # fairness within comparable groups (include prior history)
    groups = {}
    for sid, s in staff.items():
        groups.setdefault(s["group"], []).append(sid)
    unfairness = 0.0
    for gsids in groups.values():
        vals = []
        for sid in gsids:
            h = hist.get(sid, {})
            vals.append(load[sid]["night"] + load[sid]["weekend"] + load[sid]["oncall"]
                        + h.get("recent_night_shifts", 0) + h.get("recent_weekend_shifts", 0))
        if len(vals) > 1:
            unfairness += float(np.std(vals))

    # fatigue: nights, long runs, hours over target, prior fatigue
    fatigue = 0.0
    overtime = 0.0
    for sid, L in load.items():
        h = hist.get(sid, {})
        fatigue += 2 * L["night"] + max(0, L["hours"] - target_week) * 0.5 + h.get("fatigue_score", 0)
        overtime += max(0, L["hours"] - target_week) + h.get("overtime_hours", 0)

    # preference violations + unnecessary department changes
    pref_violation = sum(L["nonpref"] for L in load.values()) \
        + sum(max(0, len(L["depts"]) - 1) for L in load.values())

    return {
        "understaffing": float(understaffing),
        "unfairness": float(unfairness),
        "fatigue": float(fatigue),
        "overtime": float(overtime),
        "preference_violation": float(pref_violation),
        "mandatory_gap": int(mand_gap),
        "emergency_uncovered": int(emergency_uncovered),
        "coverage_pct": _coverage_pct(reqs, assigned_counts),
        "load": load,
    }


def _coverage_pct(reqs, assigned_counts) -> float:
    need = sum(r.min_count for r in reqs)
    got = sum(min(assigned_counts.get(i, 0), r.min_count) for i, r in enumerate(reqs))
    return round(100 * got / need, 1) if need else 100.0


# ------------------------------------------------------------------ pymoo problem
class RosterProblem(ElementwiseProblem):
    def __init__(self, ctx):
        self.ctx = ctx
        super().__init__(n_var=len(ctx["slots"]), n_obj=len(OBJECTIVES), n_constr=0, xl=0.0, xu=1.0)

    def _evaluate(self, x, out, *args, **kwargs):
        _, m = decode_roster(x, self.ctx)
        out["F"] = [m[o] for o in OBJECTIVES]


# ------------------------------------------------------------------ selection
def _rank_balanced(F: np.ndarray) -> int:
    norm = np.zeros_like(F, dtype=float)
    for j in range(F.shape[1]):
        col = F[:, j]
        rng = col.max() - col.min()
        norm[:, j] = 0.0 if rng == 0 else (col - col.min()) / rng
    w = np.array([RANKING_WEIGHTS["coverage"], RANKING_WEIGHTS["fairness"],
                  RANKING_WEIGHTS["fatigue"], RANKING_WEIGHTS["overtime"],
                  RANKING_WEIGHTS["preference"]])
    return int(np.argmin(norm @ w))


# ------------------------------------------------------------------ output build
def _roster_output(assignments, dates, confirmed_days, start_date):
    confirmed_cutoff = start_date + timedelta(days=confirmed_days - 1)
    out = []
    for a in assignments:
        d = datetime.strptime(a["date"], "%Y-%m-%d").date()
        out.append({
            "staff_id": a["staff_id"], "staff_name": a["staff_name"], "date": a["date"],
            "shift": a["shift"], "department": a["department"], "assigned_role": a["assigned_role"],
            "assignment_status": "scheduled",
            "confirmed_or_provisional": "confirmed" if d <= confirmed_cutoff else "provisional",
            "manually_overridden": False, "override_reason": None})
    out.sort(key=lambda a: (a["date"], a["shift"], a["department"]))
    return out


def _unmet(reqs, assignments) -> list[dict]:
    counts = {}
    for a in assignments:
        counts[(a["date"], a["shift"], a["department"], a["assigned_role"])] = \
            counts.get((a["date"], a["shift"], a["department"], a["assigned_role"]), 0) + 1
    unmet = []
    for r in reqs:
        got = counts.get((r.date, r.shift, r.department, r.designation), 0)
        if got < r.min_count:
            unmet.append({
                "date": r.date, "shift": r.shift, "department": r.department,
                "designation": r.designation, "skill": r.skill,
                "required": r.min_count, "assigned": got, "shortfall": r.min_count - got,
                "recommended_action": _shortage_action(r)})
    return unmet


def _shortage_action(r: ShiftRequirement) -> str:
    if r.specialist == "obgyn":
        return "activate on-call OBGYN or arrange obstetric referral"
    if r.department == "Emergency":
        return "activate emergency on-call / locum cover"
    if r.shift == "On-call":
        return "assign on-call standby or escalate to administrator"
    return "activate on-call, arrange locum support, or administrator intervention"


def _fairness_report(load, staff) -> dict:
    """Per-staff loads within comparable role groups + fairness indices.
    Uses only role/skill/availability — never protected attributes (none collected)."""
    groups = {}
    for sid, s in staff.items():
        groups.setdefault(s["group"], []).append(sid)
    report_groups, all_shifts, cvs = [], [], []
    for g, sids in groups.items():
        members = []
        for sid in sids:
            L = load[sid]
            if L["days"] > 0:
                members.append({"staff_name": staff[sid]["staff_name"], "nights": L["night"],
                                "weekends": L["weekend"], "oncall": L["oncall"], "shifts": L["days"]})
                all_shifts.append(L["days"])
        if len(members) >= 2:
            nw = [m["nights"] + m["weekends"] for m in members]
            mean = sum(nw) / len(nw)
            cvs.append(float(np.std(nw)) / (mean + 1))
            report_groups.append({"group": g, "members": sorted(members, key=lambda m: -m["nights"])})
    equity = max(0.0, min(100.0, round(100 * (1 - (sum(cvs) / len(cvs) if cvs else 0)), 1)))
    return {
        "shift_equity_index": equity,
        "workload_variance": round(float(np.var(all_shifts)), 2) if all_shifts else 0.0,
        "rest_compliance_pct": 100.0,          # enforced by the decode (min-rest hard constraint)
        "no_protected_attributes": True,
        "groups": report_groups,
    }


def _fairness_metrics(load, staff):
    groups = {}
    for sid, s in staff.items():
        groups.setdefault(s["group"], []).append(sid)
    out = {}
    for g, sids in groups.items():
        nights = [load[sid]["night"] for sid in sids]
        weekends = [load[sid]["weekend"] for sid in sids]
        if len(sids) > 1 and sum(load[sid]["days"] for sid in sids) > 0:
            out[g] = {"members": len(sids), "night_std": round(float(np.std(nights)), 2),
                      "weekend_std": round(float(np.std(weekends)), 2),
                      "max_nights": int(max(nights)), "min_nights": int(min(nights))}
    return out


# ------------------------------------------------------------------ main entry
def generate_roster(forecast_by_date: dict, staff_df: pd.DataFrame, start_date, horizon: int,
                    availability: dict | None = None, planning_run_id: str | None = None,
                    seed: int = SEED, pop_size: int = POP_SIZE, n_gen: int = N_GEN) -> dict:
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError(f"horizon must be one of {SUPPORTED_HORIZONS}, got {horizon}")
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    dates = [(start_date + timedelta(days=i)).isoformat() for i in range(horizon)]
    availability = availability or default_availability()
    warnings: list = []

    staff = build_staff_records(staff_df)
    reqs = build_shift_requirements(forecast_by_date, dates, warnings)
    slots = build_slots(reqs, staff)
    ctx = {"staff": staff, "slots": slots, "reqs": reqs, "dates": dates,
           "availability": availability, "target_weekly_hours": DEFAULT_TARGET_WEEKLY_HOURS}

    t0 = time.time()
    problem = RosterProblem(ctx)
    res = minimize(problem, NSGA2(pop_size=pop_size), ("n_gen", n_gen), seed=seed, verbose=False)
    exec_time = round(time.time() - t0, 2)

    X = np.atleast_2d(res.X)
    F = np.atleast_2d(res.F)
    # Decode every Pareto solution once (deterministic).
    decoded = [decode_roster(x, ctx) for x in X]

    balanced_idx = _rank_balanced(F)
    overtime_idx = int(np.argmin(F[:, OBJECTIVES.index("overtime")]))
    emergency_idx = int(np.argmin([m["emergency_uncovered"] for _, m in decoded]))

    b_assign, b_metrics = decoded[balanced_idx]
    recommended = _roster_output(b_assign, dates, CONFIRMED_DAYS, start_date)

    # locked/completed appear in the output too (immutable).
    for a in availability.get("completed", []):
        recommended.append({**_lock_row(a, "completed")})
    for a in availability.get("locked", []):
        recommended.append({**_lock_row(a, "locked")})

    alternatives = []
    for label, idx in [("Minimum Overtime Plan", overtime_idx), ("Emergency Readiness Plan", emergency_idx)]:
        if idx != balanced_idx and not np.array_equal(F[idx], F[balanced_idx]):
            a_assign, a_metrics = decoded[idx]
            alternatives.append({
                "label": label,
                "roster": _roster_output(a_assign, dates, CONFIRMED_DAYS, start_date),
                "scores": _score_block(a_metrics)})

    unmet = _unmet(reqs, b_assign)
    return {
        "roster_run_id": str(uuid.uuid4()),
        "planning_run_id": planning_run_id,
        "start_date": start_date.isoformat(),
        "scheduling_horizon_days": horizon,
        "recommended_roster": recommended,
        "recommended_roster_scores": _score_block(b_metrics),
        "recommendation_reason": _reason(b_metrics, balanced_idx, len(X)),
        "alternative_rosters": alternatives,
        "unmet_staffing_requirements": unmet,
        "hard_constraint_violations": [],   # feasibility-preserving decode => none
        "soft_constraint_warnings": warnings,
        "fairness_metrics": _fairness_metrics(b_metrics["load"], staff),
        "fairness_report": _fairness_report(b_metrics["load"], staff),
        "fatigue_metrics": {"total_fatigue_score": round(b_metrics["fatigue"], 2)},
        "overtime_metrics": {"total_overtime_hours": round(b_metrics["overtime"], 2)},
        "preference_satisfaction": _pref_satisfaction(b_metrics, b_assign),
        "optimization_metadata": {
            "seed": seed, "population_size": pop_size, "generations": n_gen,
            "execution_time_sec": exec_time, "feasible_solutions": int(len(X)),
            "objective_names": OBJECTIVES,
            "objective_values": [round(v, 3) for v in F[balanced_idx].tolist()]},
    }


def _lock_row(a, status):
    return {"staff_id": a["staff_id"], "staff_name": a.get("staff_name", a["staff_id"]),
            "date": a["date"], "shift": a["shift"], "department": a.get("department", ""),
            "assigned_role": a.get("assigned_role", a.get("designation", "")),
            "assignment_status": status,
            "confirmed_or_provisional": "confirmed",
            "manually_overridden": False, "override_reason": None}


def _score_block(m):
    return {"coverage_pct": m["coverage_pct"], "understaffing": round(m["understaffing"], 2),
            "unfairness": round(m["unfairness"], 2), "fatigue": round(m["fatigue"], 2),
            "overtime": round(m["overtime"], 2), "preference_violation": int(m["preference_violation"]),
            "mandatory_gap": m["mandatory_gap"]}


def _pref_satisfaction(m, assignments):
    total = len(assignments)
    non = sum(L["nonpref"] for L in m["load"].values())
    return {"assignments": total, "preferred_shift_matches": total - non,
            "satisfaction_pct": round(100 * (total - non) / total, 1) if total else 100.0}


def _reason(m, idx, n):
    return (f"Balanced plan selected from {n} feasible Pareto solution(s) using ranking weights "
            f"(coverage 35%, fairness 25%, fatigue 20%, overtime 10%, preference 10%). "
            f"Coverage {m['coverage_pct']}%, mandatory gap {m['mandatory_gap']}.")


# ------------------------------------------------------------------ overrides
def validate_override(roster: list[dict], change: dict, staff_records: dict,
                      availability: dict | None = None) -> dict:
    """Revalidate a manual assignment change. Returns warnings + an audit entry.

    `change` = {staff_id, date, shift, department, assigned_role, override_reason}.
    """
    availability = availability or default_availability()
    warnings = []
    sid = change["staff_id"]
    s = staff_records.get(sid)
    if s is None:
        warnings.append("unknown staff_id")
    else:
        if not s["active"]:
            warnings.append("staff is not active")
        if change["shift"] not in s["shift_eligibility"]:
            warnings.append(f"{sid} not eligible for {change['shift']} shift")
        if change["date"] in availability.get("leave", {}).get(sid, set()):
            warnings.append("staff is on approved leave that date")
        # designation / role mismatch
        if change.get("assigned_role") and s["designation"] != change["assigned_role"]:
            warnings.append(f"designation mismatch: {s['designation']} != {change['assigned_role']}")
        # double-booking / rest
        same_day = [a for a in roster if a["staff_id"] == sid and a["date"] == change["date"]]
        if same_day:
            warnings.append("staff already has a shift that day (overlap)")
        if change["shift"] == "Night" and s["max_night_shifts_per_month"] <= \
                sum(1 for a in roster if a["staff_id"] == sid and a["shift"] == "Night"):
            warnings.append("night-shift cap reached")

    requires_reason = bool(warnings)
    if requires_reason and not change.get("override_reason"):
        warnings.append("override_reason is required for this change")

    audit = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "manual_override",
        "change": change,
        "warnings": warnings,
        "accepted": not (requires_reason and not change.get("override_reason")),
    }
    return {"valid": not warnings, "warnings": warnings, "audit_log_entry": audit}
