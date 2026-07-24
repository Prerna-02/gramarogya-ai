"""Resource-planning engine tests (Phase 7 / Phase 14)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.resource_planning import plan_resource_window, plan_resources  # noqa: E402


def base_forecast(**overrides):
    f = {
        "general_opd_arrivals": 90, "fever_infectious_arrivals": 30,
        "maternal_child_arrivals": 8, "trauma_emergency_arrivals": 10,
        "total_patient_arrivals": 138, "expected_admissions": 8,
    }
    f.update(overrides)
    f["total_patient_arrivals"] = (f["general_opd_arrivals"] + f["fever_infectious_arrivals"]
                                   + f["maternal_child_arrivals"] + f["trauma_emergency_arrivals"])
    return f


def test_missing_keys_raises():
    with pytest.raises(ValueError):
        plan_resources({"general_opd_arrivals": 10})


def test_more_fever_needs_more_test_kits_and_physicians():
    low = plan_resources(base_forecast(fever_infectious_arrivals=20))
    high = plan_resources(base_forecast(fever_infectious_arrivals=80))
    assert high["medicines"]["diagnostic_test_kits"]["required"] > low["medicines"]["diagnostic_test_kits"]["required"]
    assert high["staff"]["physicians"]["required"] >= low["staff"]["physicians"]["required"]


def test_more_trauma_needs_more_ambulances():
    low = plan_resources(base_forecast(trauma_emergency_arrivals=5))
    high = plan_resources(base_forecast(trauma_emergency_arrivals=60))
    assert high["ambulances"]["required"] > low["ambulances"]["required"]


def test_obgyn_coverage_escalates_with_maternal_demand():
    routine = plan_resources(base_forecast(maternal_child_arrivals=8))
    busy = plan_resources(base_forecast(maternal_child_arrivals=18))
    assert routine["staff"]["obgyn_doctors"]["required"] == 1
    assert busy["staff"]["obgyn_doctors"]["required"] == 2


def test_shortage_detected_when_availability_low():
    plan = plan_resources(base_forecast(fever_infectious_arrivals=80),
                          availability={"diagnostic_test_kits": 0})
    kit = plan["medicines"]["diagnostic_test_kits"]
    assert kit["shortage"] > 0 and kit["status"] == "SHORTAGE"
    assert "diagnostic_test_kits" in plan["summary"]["shortages"]


def test_every_requirement_is_explainable():
    plan = plan_resources(base_forecast())
    groups = [plan["staff"], plan["beds"], plan["medicines"]]
    lines = [v for g in groups for v in g.values()] + [plan["oxygen"], plan["ambulances"]]
    for item in lines:
        assert item["explanation"] and isinstance(item["explanation"], str)


def test_consumables_expose_numeric_reorder_points():
    plan = plan_resources(base_forecast())
    assert all(isinstance(item["reorder_point"], int) and item["reorder_point"] > 0
               for item in plan["medicines"].values())


def test_status_escalates_with_shortages():
    # Starve every resource -> Critical.
    zero = {k: 0 for k in [
        "general_doctors", "physicians", "emergency_doctors", "obgyn_doctors", "pediatricians",
        "lab_technicians", "pharmacists", "anm_staff", "senior_nursing_officers", "nursing_officers",
        "general_beds", "emergency_beds", "isolation_beds", "diagnostic_test_kits",
        "antipyretics", "iv_fluids", "ors", "ppe_kits", "oxygen_cylinders", "ambulances"]}
    plan = plan_resources(base_forecast(fever_infectious_arrivals=80, trauma_emergency_arrivals=40),
                          availability=zero)
    assert plan["summary"]["status"] == "Critical"
    assert plan["summary"]["shortage_count"] >= 5


def test_window_planning_carries_consumable_stock_forward():
    forecasts = [{"date": f"2026-01-0{i}", **base_forecast(fever_infectious_arrivals=40)} for i in range(1, 4)]
    plans = plan_resource_window(forecasts, {"diagnostic_test_kits": 30})
    assert plans[0]["inventory_opening"]["diagnostic_test_kits"] == 30
    assert plans[1]["inventory_opening"]["diagnostic_test_kits"] == plans[0]["inventory_closing"]["diagnostic_test_kits"]
    assert plans[-1]["inventory_closing"]["diagnostic_test_kits"] < plans[0]["inventory_opening"]["diagnostic_test_kits"]


def test_window_uses_date_specific_staff_capacity():
    forecasts = [
        {"date": "2026-01-01", **base_forecast()},
        {"date": "2026-01-02", **base_forecast()},
    ]
    plans = plan_resource_window(
        forecasts,
        availability={"physicians": 1},
        availability_by_date={
            "2026-01-01": {"physicians": 1},
            "2026-01-02": {"physicians": 0},
        },
    )
    assert plans[0]["staff"]["physicians"]["shortage"] == 0
    assert plans[1]["staff"]["physicians"]["shortage"] == 1
