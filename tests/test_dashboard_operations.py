"""Unit tests for calculated dashboard operations and alert rules."""
from types import SimpleNamespace

from backend.services.dashboard_operations import (
    build_rule_alerts,
    estimate_wait_minutes,
    schedule_fairness,
)
from backend.services.llm_summary import _grounded


def _resource(occupied=20, total=30):
    return SimpleNamespace(occupied_general_beds=occupied, total_general_beds=total)


def _demand(total):
    return {
        "total_patient_arrivals": total,
        "general_opd_arrivals": max(0, total - 30),
        "fever_infectious_arrivals": 15,
        "maternal_child_arrivals": 8,
        "trauma_emergency_arrivals": 7,
        "expected_admissions": 6,
    }


def test_wait_estimate_responds_to_demand_and_capacity():
    normal = estimate_wait_minutes(_demand(90), _resource(), active_clinicians=15)
    surge = estimate_wait_minutes(_demand(180), _resource(), active_clinicians=8)
    more_staffed = estimate_wait_minutes(_demand(180), _resource(), active_clinicians=18)
    assert surge > normal
    assert more_staffed < surge


def test_rule_alerts_are_stable_deduplicated_and_actionable():
    kwargs = dict(
        wait_minutes=52,
        utilization_pct=94,
        resource=_resource(28, 30),
        coverage=[{"department": "Emergency", "required": 4, "assigned": 2, "gap": 2}],
        pressure=[{"date": "2026-01-02", "resource": "oxygen_cylinders", "shortage": 3}],
        forecast=[
            {"date": "2026-01-01", "total_patient_arrivals": 100},
            {"date": "2026-01-02", "total_patient_arrivals": 120},
        ],
    )
    first = build_rule_alerts(**kwargs)
    second = build_rule_alerts(**kwargs)
    assert first == second
    assert len({alert["id"] for alert in first}) == len(first)
    assert all(alert["action"] and alert["source"] and alert["status"] == "Open" for alert in first)
    assert first[0]["severity"] == "high"


def test_fairness_includes_unassigned_staff():
    staff = [
        SimpleNamespace(staff_id="a", active_status="Active", designation="Nursing Officer", max_weekly_hours=48),
        SimpleNamespace(staff_id="b", active_status="Active", designation="Nursing Officer", max_weekly_hours=48),
    ]
    assignments = [{"staff_id": "a", "shift": "Morning"}]
    report = schedule_fairness(staff, [], assignments)
    assert report["shift_equity_index"] < 100
    assert report["overtime_hours"] == 0


def test_llm_numeric_grounding_rejects_invented_values():
    evidence = {"avg_total": 120, "peak_total": 128, "horizon_days": 7}
    assert _grounded("Average 120, peak 128 across 7 days.", evidence)
    assert not _grounded("Average 120 with 12 extra beds.", evidence)
