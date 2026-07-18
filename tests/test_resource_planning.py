"""Resource-planning engine tests (Phase 7 / Phase 14)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.resource_planning import plan_resources  # noqa: E402


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


def test_obgyn_minimum_coverage_is_two():
    plan = plan_resources(base_forecast())
    assert plan["staff"]["obgyn_doctors"]["required"] >= 2


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
