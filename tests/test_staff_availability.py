"""Unit tests for date and shift-specific staff availability."""
from datetime import date
from types import SimpleNamespace

from backend.services.staff_availability import (
    availability_summaries,
    resource_availability_by_date,
    workforce_availability,
)


def _person(staff_id, name, designation, status="Active"):
    return SimpleNamespace(
        staff_id=staff_id,
        staff_name=name,
        designation=designation,
        active_status=status,
    )


def _record(staff_id, day, status, shift=None, reason="Test exception"):
    return SimpleNamespace(
        staff_id=staff_id,
        date=day,
        availability_status=status,
        shift=shift,
        reason=reason,
    )


def test_resource_capacity_uses_primary_role_and_full_day_exceptions():
    staff = [
        _person("gmo", "General Doctor", "General Medical Officer"),
        _person("super", "Superintendent", "Medical Superintendent"),
    ]
    records = [
        _record("gmo", date(2026, 1, 5), "leave"),
        _record("gmo", date(2026, 1, 6), "unavailable", shift="Night"),
    ]
    result = resource_availability_by_date(
        staff, records, [date(2026, 1, 5), date(2026, 1, 6)]
    )
    assert result["2026-01-05"]["general_doctors"] == 0
    assert result["2026-01-06"]["general_doctors"] == 1


def test_availability_summary_separates_full_day_and_shift_limit():
    staff = [_person("gmo", "General Doctor", "General Medical Officer")]
    records = [_record("gmo", date(2026, 1, 6), "unavailable", shift="Night")]
    summary = availability_summaries(staff, records, [date(2026, 1, 6)])["2026-01-06"]
    assert summary["available_count"] == 1
    assert summary["unavailable_count"] == 0
    assert summary["shift_limited_count"] == 1
    assert summary["exceptions"][0]["full_day"] is False


def test_workforce_contract_contains_day_and_shift_restrictions():
    records = [
        _record("gmo", date(2026, 1, 5), "training"),
        _record("gmo", date(2026, 1, 6), "unavailable", shift="Night"),
    ]
    result = workforce_availability(records)
    assert "2026-01-05" in result["leave"]["gmo"]
    assert ("2026-01-06", "Night") in result["unavailable_shifts"]["gmo"]
