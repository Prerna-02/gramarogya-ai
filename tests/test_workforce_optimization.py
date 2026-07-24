"""NSGA-II workforce optimization tests (Phase 8 / Phase 14)."""
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services import scheduling_config as cfg  # noqa: E402
from backend.services.workforce_optimization import (  # noqa: E402
    build_shift_requirements, build_staff_records, default_availability,
    generate_roster, validate_override,
)

STAFF_DF = pd.read_csv(ROOT / "data" / "staff_master.csv")
START = "2026-01-05"
FAST = dict(pop_size=10, n_gen=6)


def fc(fever=40, trauma=11, mat=9):
    return {"general_opd_arrivals": 90, "fever_infectious_arrivals": fever,
            "maternal_child_arrivals": mat, "trauma_emergency_arrivals": trauma,
            "total_patient_arrivals": 90 + fever + mat + trauma, "expected_admissions": 9}


def dates_for(h, start=START):
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    return [(d0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(h)]


def make(h=7, availability=None, start=START, **kw):
    fbd = {d: fc() for d in dates_for(h, start)}
    return generate_roster(fbd, STAFF_DF, start, h, availability=availability, **{**FAST, **kw})


@pytest.fixture(scope="module")
def roster():
    return make(7)


# ---- structure / selection ----
def test_output_schema_and_balanced_selection(roster):
    for k in ["roster_run_id", "recommended_roster", "recommended_roster_scores",
              "recommendation_reason", "alternative_rosters", "unmet_staffing_requirements",
              "hard_constraint_violations", "fairness_metrics", "optimization_metadata",
              "coverage_by_role", "coverage_by_date_shift", "baseline_comparison"]:
        assert k in roster
    assert roster["recommended_roster"]                      # a usable roster exists
    assert "Balanced" in roster["recommendation_reason"] or "balanced" in roster["recommendation_reason"]
    assert roster["optimization_metadata"]["seed"] == cfg.SEED
    assert roster["optimization_metadata"]["objective_values"]
    assert all({"role", "required", "assigned", "shortfall", "coverage_pct"} <= set(row)
               for row in roster["coverage_by_role"])
    assert all({"date", "shift", "required", "assigned", "shortfall", "coverage_pct"} <= set(row)
               for row in roster["coverage_by_date_shift"])
    assert set(roster["baseline_comparison"]) == {"baseline", "optimized", "baseline_method"}


def test_no_hard_constraint_violations(roster):
    assert roster["hard_constraint_violations"] == []


def test_no_fabricated_staff(roster):
    ids = set(STAFF_DF["staff_id"])
    assert all(a["staff_id"] in ids for a in roster["recommended_roster"])


# ---- hard constraints on the produced roster ----
def test_no_overlapping_shifts(roster):
    seen = Counter((a["staff_id"], a["date"]) for a in roster["recommended_roster"])
    assert all(v == 1 for v in seen.values())


def test_qualification_matching(roster):
    recs = build_staff_records(STAFF_DF)
    # union of acceptable designations for each assigned_role
    accept = defaultdict(set)
    for role_key, tmpl in cfg.COVERAGE_TEMPLATE.items():
        accept[tmpl["designation"]].update(cfg.ELIGIBLE_DESIGNATIONS.get(role_key, [tmpl["designation"]]))
    for a in roster["recommended_roster"]:
        if a["assignment_status"] in ("locked", "completed"):
            continue
        assert recs[a["staff_id"]]["designation"] in accept[a["assigned_role"]]


def test_shift_eligibility_respected(roster):
    recs = build_staff_records(STAFF_DF)
    for a in roster["recommended_roster"]:
        if a["assignment_status"] in ("locked", "completed"):
            continue
        assert a["shift"] in recs[a["staff_id"]]["shift_eligibility"]


def test_max_weekly_hours(roster):
    recs = build_staff_records(STAFF_DF)
    hours = defaultdict(lambda: defaultdict(float))
    start = datetime.strptime(roster["start_date"], "%Y-%m-%d").date()
    for a in roster["recommended_roster"]:
        day = datetime.strptime(a["date"], "%Y-%m-%d").date()
        planning_week = (day - start).days // 7
        hours[a["staff_id"]][planning_week] += cfg.SHIFT_HOURS[a["shift"]][2]
    for sid, weeks in hours.items():
        for h in weeks.values():
            assert h <= recs[sid]["max_weekly_hours"]


def test_min_rest_and_night_caps(roster):
    recs = build_staff_records(STAFF_DF)
    by_staff = defaultdict(dict)
    nights = Counter()
    for a in roster["recommended_roster"]:
        by_staff[a["staff_id"]][a["date"]] = a["shift"]
        if a["shift"] == "Night":
            nights[a["staff_id"]] += 1
    for sid, cnt in nights.items():
        assert cnt <= recs[sid]["max_night_shifts_per_month"]
    for sid, sched in by_staff.items():
        days = sorted(sched)
        di = {d: datetime.strptime(d, "%Y-%m-%d").date() for d in days}
        for a, b in zip(days, days[1:]):
            if (di[b] - di[a]).days == 1:
                end_a = cfg.SHIFT_END_HOUR[sched[a]]
                start_b = 24 + cfg.SHIFT_START_HOUR[sched[b]]
                assert start_b - end_a >= recs[sid]["minimum_rest_hours"]


def test_consecutive_day_limit(roster):
    recs = build_staff_records(STAFF_DF)
    by_staff = defaultdict(list)
    for a in roster["recommended_roster"]:
        by_staff[a["staff_id"]].append(datetime.strptime(a["date"], "%Y-%m-%d").date())
    for sid, ds in by_staff.items():
        ds = sorted(set(ds))
        run = maxrun = 1
        for a, b in zip(ds, ds[1:]):
            run = run + 1 if (b - a).days == 1 else 1
            maxrun = max(maxrun, run)
        assert maxrun <= recs[sid]["max_consecutive_working_days"]


# ---- coverage roles ----
def test_senior_nursing_and_emergency_coverage(roster):
    roles = {a["assigned_role"] for a in roster["recommended_roster"]}
    depts = {a["department"] for a in roster["recommended_roster"]}
    assert "Senior Nursing Officer" in roles
    assert "Emergency" in depts


def test_obgyn_two_level_requirement():
    reqs = build_shift_requirements({d: fc() for d in dates_for(7)}, dates_for(7), [])
    obgyn_shifts = {r.shift for r in reqs if r.designation == "Obstetrician and Gynecologist"}
    assert "On-call" in obgyn_shifts and "Morning" in obgyn_shifts   # active + backup


def test_pediatric_coverage_responds_to_demand():
    low = build_shift_requirements({d: fc(mat=4) for d in dates_for(7)}, dates_for(7), [])
    high = build_shift_requirements({d: fc(mat=16) for d in dates_for(7)}, dates_for(7), [])
    lo = sum(r.min_count for r in low if r.designation == "Pediatrician")
    hi = sum(r.min_count for r in high if r.designation == "Pediatrician")
    assert hi >= lo


# ---- shortages / fairness ----
def test_explicit_shortage_reporting(roster):
    unmet = roster["unmet_staffing_requirements"]
    assert unmet, "expected specialist/on-call shortages to be reported"
    for u in unmet:
        assert u["shortfall"] > 0 and u["recommended_action"]
        assert {"date", "shift", "department", "designation"} <= set(u)


def test_fairness_measured_within_groups(roster):
    valid_groups = set(cfg.FAIRNESS_GROUPS.values())
    assert set(roster["fairness_metrics"]).issubset(valid_groups)


# ---- leave / availability ----
def test_leave_worker_not_assigned():
    sid = STAFF_DF[STAFF_DF["designation"] == "Nursing Officer"]["staff_id"].iloc[0]
    avail = default_availability()
    avail["leave"] = {sid: set(dates_for(7))}
    r = make(7, availability=avail)
    assert all(a["staff_id"] != sid for a in r["recommended_roster"])


def test_completed_and_locked_unchanged():
    sid = STAFF_DF[STAFF_DF["designation"] == "Nursing Officer"]["staff_id"].iloc[0]
    avail = default_availability()
    completed = {"staff_id": sid, "date": dates_for(7)[0], "shift": "Morning",
                 "department": "Inpatient Ward", "assigned_role": "Nursing Officer"}
    avail["completed"] = [completed]
    r = make(7, availability=avail)
    kept = [a for a in r["recommended_roster"]
            if a["staff_id"] == sid and a["date"] == completed["date"]]
    assert any(a["assignment_status"] == "completed" for a in kept)
    # not double-booked that day
    assert len(kept) == 1


# ---- horizons ----
@pytest.mark.parametrize("h", [5, 7, 14, 21])
def test_horizon_produces_matching_roster(h):
    r = make(h, pop_size=8, n_gen=4)
    assert r["scheduling_horizon_days"] == h
    roster_dates = {a["date"] for a in r["recommended_roster"]}
    assert len(roster_dates) <= h and len(roster_dates) >= min(h, 3)


def test_days_after_seven_are_provisional():
    r = make(14, pop_size=8, n_gen=4)
    cutoff = datetime.strptime(START, "%Y-%m-%d").date() + pd.Timedelta(days=6)
    for a in r["recommended_roster"]:
        d = datetime.strptime(a["date"], "%Y-%m-%d").date()
        expected = "confirmed" if d <= cutoff else "provisional"
        if a["assignment_status"] == "scheduled":
            assert a["confirmed_or_provisional"] == expected


# ---- reproducibility ----
def test_fixed_seed_reproducibility():
    r1 = make(7)
    r2 = make(7)
    assert r1["recommended_roster_scores"] == r2["recommended_roster_scores"]
    key = lambda r: sorted((a["staff_id"], a["date"], a["shift"]) for a in r["recommended_roster"])
    assert key(r1) == key(r2)


# ---- overrides ----
def test_override_invalid_requires_reason_and_logs():
    recs = build_staff_records(STAFF_DF)
    # A pharmacist cannot fill an Obstetrician role -> designation mismatch.
    pharm = STAFF_DF[STAFF_DF["designation"] == "Pharmacist"]["staff_id"].iloc[0]
    change = {"staff_id": pharm, "date": dates_for(7)[0], "shift": "Morning",
              "department": "Maternal and Child Health",
              "assigned_role": "Obstetrician and Gynecologist", "override_reason": None}
    res = validate_override([], change, recs)
    assert not res["valid"]
    assert any("mismatch" in w for w in res["warnings"])
    assert res["audit_log_entry"]["action"] == "manual_override"
    assert res["audit_log_entry"]["accepted"] is False   # reason required but missing


def test_override_valid_when_reason_supplied():
    recs = build_staff_records(STAFF_DF)
    nurse = STAFF_DF[(STAFF_DF["designation"] == "Nursing Officer")]["staff_id"].iloc[0]
    change = {"staff_id": nurse, "date": dates_for(7)[0], "shift": "Morning",
              "department": "Inpatient Ward", "assigned_role": "Nursing Officer",
              "override_reason": "cover for absence"}
    res = validate_override([], change, recs)
    assert res["valid"] and res["audit_log_entry"]["accepted"] is True
