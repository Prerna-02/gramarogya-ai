"""Shared staff-availability transformations for planning and rostering.

Availability records are operational inputs.  Resource Planning uses full-day
exceptions to calculate daily headcount, while Workforce also honours
shift-specific exceptions when assigning the roster.
"""
from __future__ import annotations

from collections import defaultdict

from backend.services.scheduling_config import COVERAGE_TEMPLATE


UNAVAILABLE_STATUSES = {"leave", "sick", "training", "outreach", "unavailable"}


def _value(row, name, default=None):
    return row.get(name, default) if isinstance(row, dict) else getattr(row, name, default)


def _date_text(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _is_active(person) -> bool:
    return str(_value(person, "active_status", "")).lower() == "active"


def _is_unavailable(record) -> bool:
    return str(_value(record, "availability_status", "")).lower() in UNAVAILABLE_STATUSES


def _is_full_day(record) -> bool:
    shift = _value(record, "shift")
    return shift is None or not str(shift).strip()


def resource_availability_by_date(staff, records, dates) -> dict[str, dict[str, int]]:
    """Return primary-role headcount for each requested date.

    Cross-cover is deliberately not counted as ordinary capacity here because
    one employee cannot simultaneously fill multiple resource pools.  The
    workforce optimizer may still use eligible cross-cover when it builds the
    shift roster.
    """
    active = [person for person in staff if _is_active(person)]
    records_by_date: dict[str, list] = defaultdict(list)
    for record in records:
        records_by_date[_date_text(_value(record, "date"))].append(record)

    result = {}
    for value in dates:
        day = _date_text(value)
        absent_ids = {
            str(_value(record, "staff_id"))
            for record in records_by_date.get(day, [])
            if _is_unavailable(record) and _is_full_day(record)
        }
        available_staff = [person for person in active if str(_value(person, "staff_id")) not in absent_ids]
        result[day] = {
            role: sum(_value(person, "designation") == template["designation"] for person in available_staff)
            for role, template in COVERAGE_TEMPLATE.items()
            if role != "ambulance_crew"
        }
    return result


def availability_summaries(staff, records, dates) -> dict[str, dict]:
    """Build administrator-facing daily availability summaries."""
    active = [person for person in staff if _is_active(person)]
    people = {str(_value(person, "staff_id")): person for person in active}
    records_by_date: dict[str, list] = defaultdict(list)
    for record in records:
        records_by_date[_date_text(_value(record, "date"))].append(record)

    summaries = {}
    for value in dates:
        day = _date_text(value)
        exceptions = []
        full_day_ids = set()
        limited_ids = set()
        for record in records_by_date.get(day, []):
            if not _is_unavailable(record):
                continue
            staff_id = str(_value(record, "staff_id"))
            person = people.get(staff_id)
            if person is None:
                continue
            full_day = _is_full_day(record)
            (full_day_ids if full_day else limited_ids).add(staff_id)
            exceptions.append({
                "staff_id": staff_id,
                "staff_name": _value(person, "staff_name"),
                "designation": _value(person, "designation"),
                "status": str(_value(record, "availability_status")).lower(),
                "shift": _value(record, "shift"),
                "reason": _value(record, "reason"),
                "full_day": full_day,
            })
        exceptions.sort(key=lambda item: (not item["full_day"], item["staff_name"]))
        summaries[day] = {
            "total_active": len(active),
            "available_count": len(active) - len(full_day_ids),
            "unavailable_count": len(full_day_ids),
            "shift_limited_count": len(limited_ids - full_day_ids),
            "exceptions": exceptions,
        }
    return summaries


def workforce_availability(records) -> dict:
    """Convert database availability rows into the optimizer contract."""
    leave = defaultdict(set)
    unavailable_shifts = defaultdict(set)
    for record in records:
        if not _is_unavailable(record):
            continue
        staff_id = str(_value(record, "staff_id"))
        day = _date_text(_value(record, "date"))
        shift = _value(record, "shift")
        if shift is None or not str(shift).strip():
            leave[staff_id].add(day)
        else:
            unavailable_shifts[staff_id].add((day, str(shift)))
    return {
        "leave": dict(leave),
        "unavailable_shifts": dict(unavailable_shifts),
        "locked": [],
        "completed": [],
        "history": {},
    }
