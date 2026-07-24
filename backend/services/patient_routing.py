"""Patient facility-ranking service (Phase 9 basic; full version in Phase 11).

Ranks nearby facilities for the guest patient interface using service capability,
availability status, and road travel time. Does NOT diagnose; only guides.
Never exposes staff schedules or sensitive data. Surfaces the last-verified time.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models import DailyDemand, NearbyFacility, RosterEntry, Staff, StaffAvailability
from backend.services.doctor_directory import (
    STATUS_TONE, doctor_matches, external_doctors, speciality_priority, speciality_requirements,
)

STATUS_RANK = {"Available": 0, "Limited": 1, "Busy": 2}
# Synthetic estimated waiting time (minutes) by readiness status.
WAIT_BASE = {"Available": 20, "Limited": 40, "Busy": 60}

PRIMARY_FACILITY = {
    "id": "gramarogya-primary",
    "name": "Gadchiroli Rural Hospital",
    "type": "Rural Hospital",
    "latitude": 20.1849,
    "longitude": 79.9948,
    "distance_km": 6.0,
    "travel_time_min": 15,
    "beds_available": 10,
    "capabilities": ["General", "Emergency", "Maternity", "Paediatrics", "Laboratory", "Ambulance"],
    "status": "Available",
}

DESIGNATION_SPECIALITY = {
    "Medical Superintendent": "General Medicine",
    "General Medical Officer": "General Medicine",
    "Emergency Medical Officer": "Emergency Medicine",
    "Physician": "Internal Medicine",
    "Public Health Medical Officer": "Community Medicine",
    "Anesthetist": "Anaesthesiology",
    "Obstetrician and Gynecologist": "Obstetrics & Gynaecology",
    "Pediatrician": "Paediatrics",
}

SHIFT_WINDOWS = {
    "Morning": ("08:00", "16:00"),
    "Evening": ("16:00", "24:00"),
    "Night": ("00:00", "08:00"),
    "On-call": ("00:00", "24:00"),
}


def _now_india() -> datetime:
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def _current_shift(now: datetime) -> str:
    if 8 <= now.hour < 16:
        return "Morning"
    if 16 <= now.hour < 24:
        return "Evening"
    return "Night"


def _primary_doctors(db: Session, required_specialities: list[str] | None = None) -> list[dict]:
    """Return public-safe availability from staff, roster, and exception data."""
    now = _now_india()
    shift = _current_shift(now)
    doctors = list(db.scalars(
        select(Staff)
        .where(Staff.staff_category == "Doctor", Staff.active_status == "Active")
        .order_by(Staff.staff_name)
    ).all())
    exceptions = list(db.scalars(
        select(StaffAvailability).where(StaffAvailability.date == now.date())
    ).all())
    exceptions_by_staff = {}
    for exception in exceptions:
        exceptions_by_staff.setdefault(exception.staff_id, []).append(exception)
    on_duty_ids = set(db.scalars(
        select(RosterEntry.staff_id).where(
            RosterEntry.work_date == now.date(),
            RosterEntry.shift == shift,
            RosterEntry.assignment_status.in_(["assigned", "locked", "completed"]),
        )
    ).all())

    result = []
    for person in doctors:
        speciality = DESIGNATION_SPECIALITY.get(person.designation)
        if speciality is None:
            continue
        staff_exceptions = exceptions_by_staff.get(person.staff_id, [])
        full_day = next((item for item in staff_exceptions if not item.shift), None)
        shift_exception = next((item for item in staff_exceptions if item.shift == shift), None)
        eligible = {item.strip() for item in str(person.shift_eligibility).split("|")}
        if full_day:
            status = "Unavailable today"
            consultation = full_day.reason or "Not available today"
        elif shift_exception:
            status = "Unavailable this shift"
            consultation = shift_exception.reason or f"Not available during {shift.lower()} shift"
        elif person.staff_id in on_duty_ids or shift in eligible:
            status = "Available now"
            start, end = SHIFT_WINDOWS[shift]
            consultation = f"{start}–{end} · {shift} duty"
        elif "On-call" in eligible:
            status = "On call"
            consultation = "Contact hospital for on-call consultation"
        else:
            next_shift = next((name for name in ("Morning", "Evening", "Night") if name in eligible), None)
            status = "Available later"
            consultation = "Schedule not available" if next_shift is None else \
                f"{SHIFT_WINDOWS[next_shift][0]}–{SHIFT_WINDOWS[next_shift][1]} · {next_shift} duty"
        result.append({
            "doctor_id": person.staff_id,
            "name": f"Dr. {person.staff_name}",
            "speciality": speciality,
            "qualification": person.qualification,
            "availability_status": status,
            "availability_tone": STATUS_TONE.get(status, "later"),
            "consultation_time": consultation,
            "matches_problem": doctor_matches(speciality, required_specialities),
        })
    status_order = {"available": 0, "on-call": 1, "busy": 2, "later": 3, "unavailable": 4}
    return sorted(result, key=lambda doctor: (
        not doctor["matches_problem"],
        speciality_priority(doctor["speciality"], required_specialities),
        status_order.get(doctor["availability_tone"], 5),
        doctor["name"],
    ))


def _attach_doctors(payload: dict, doctors: list[dict], required_specialities: list[str] | None) -> dict:
    matched = [doctor for doctor in doctors if doctor["matches_problem"]]
    return {
        **payload,
        "doctors": doctors,
        "matched_doctors": matched,
        "doctor_match_available": any(
            doctor["availability_tone"] in {"available", "on-call"} for doctor in matched
        ),
        "doctor_match_rank": min(
            (speciality_priority(doctor["speciality"], required_specialities)
             for doctor in matched),
            default=999,
        ),
        "required_specialities": required_specialities or [],
    }


def _waiting_time(f: NearbyFacility) -> int:
    base = WAIT_BASE.get(f.status, 30)
    return int(base + (f.id * 5) % 15 - min(f.beds_available, 10))


def rank_facilities(db: Session, service: str | None = None, urgency: str | None = None,
                    required_specialities: list[str] | None = None) -> list[dict]:
    facilities = db.scalars(select(NearbyFacility)).all()
    primary = _attach_doctors({
        **PRIMARY_FACILITY,
        "waiting_time_min": 18,
        "matches_service": service is None or any(
            service.lower() in capability.lower() for capability in PRIMARY_FACILITY["capabilities"]
        ),
        "data_last_verified_at": _now_india().isoformat(),
        "advice": "Call before travelling to confirm availability.",
    }, _primary_doctors(db, required_specialities), required_specialities)
    scored = [primary]
    for f in facilities:
        caps = [c.strip() for c in f.capabilities.split("|")]
        capable = service is None or any(service.lower() in c.lower() for c in caps)
        payload = {
            "id": f.id, "name": f.name, "type": f.facility_type,
            "latitude": f.latitude, "longitude": f.longitude,
            "distance_km": f.distance_km, "travel_time_min": f.travel_time_min,
            "waiting_time_min": _waiting_time(f),
            "beds_available": f.beds_available, "capabilities": caps, "status": f.status,
            "matches_service": capable,
            "data_last_verified_at": f.data_last_verified_at.isoformat() if f.data_last_verified_at else None,
            "advice": "Call before travelling to confirm availability.",
        }
        scored.append(_attach_doctors(
            payload, external_doctors(f.name, required_specialities), required_specialities
        ))
    scored.sort(key=lambda item: (
        not item["matches_service"],
        bool(required_specialities) and not item["doctor_match_available"],
        item["doctor_match_rank"] if required_specialities else 0,
        STATUS_RANK.get(item["status"], 3),
        item["travel_time_min"],
    ))
    for i, s in enumerate(scored):
        s["rank"] = i + 1
        s["best_match"] = i == 0 and s["matches_service"] and s["status"] != "Busy"
    return scored


def facility_detail(db: Session, facility_id: int | str,
                    required_specialities: list[str] | None = None) -> dict | None:
    if str(facility_id) == PRIMARY_FACILITY["id"]:
        return _attach_doctors({
            **PRIMARY_FACILITY,
            "waiting_time_min": 18,
            "data_last_verified_at": _now_india().isoformat(),
            "advice": "Availability may change. Call the hospital before a long journey.",
        }, _primary_doctors(db, required_specialities), required_specialities)
    try:
        numeric_id = int(facility_id)
    except (TypeError, ValueError):
        return None
    f = db.get(NearbyFacility, numeric_id)
    if f is None:
        return None
    return _attach_doctors({
        "id": f.id, "name": f.name, "type": f.facility_type, "distance_km": f.distance_km,
        "travel_time_min": f.travel_time_min, "waiting_time_min": _waiting_time(f),
        "latitude": f.latitude, "longitude": f.longitude, "beds_available": f.beds_available,
        "capabilities": [c.strip() for c in f.capabilities.split("|")], "status": f.status,
        "data_last_verified_at": f.data_last_verified_at.isoformat() if f.data_last_verified_at else None,
        "advice": "Availability may change. Call the facility or emergency services before a long journey.",
    }, external_doctors(f.name, required_specialities), required_specialities)


# ------------------------------------------------------------------ triage (safety)
# PROTOTYPE keyword rules — must be clinician-reviewed before real use.
# Red flags route to emergency (call 108). The engine NEVER returns a remedy or
# diagnosis; it only points to a facility that can help + the emergency number.
RED_FLAGS = [
    "chest pain", "heart attack", "cardiac", "breathless", "can't breathe", "cant breathe",
    "difficulty breathing", "shortness of breath", "not breathing", "blue lips",
    "unconscious", "faint", "collapse", "severe bleeding", "heavy bleeding", "bleeding a lot",
    "stroke", "paralysis", "slurred", "seizure", "convulsion", "fits", "snake bite", "snakebite",
    "poison", "overdose", "severe injury", "major accident", "severe burn", "electric shock",
    "drowning", "water broke", "pregnancy bleeding", "labour pain", "labor pain",
    "छाती", "दम", "साँस", "बेहोश", "सांप", "रक्तस्राव",  # hi
    "छातीत", "श्वास", "बेशुद्ध", "साप",                  # mr
]
CATEGORY_KEYWORDS = {
    "pediatric": ["child", "baby", "infant", "newborn", "pediatric", "paediatric"],
    "maternity": ["pregnan", "delivery", "labour", "labor", "antenatal", "newborn", "obstetric",
                  "गर्भ", "प्रसूती", "प्रसूत"],
    "trauma": ["injur", "fracture", "broken", "wound", "cut", "fell", "fall", "burn", "accident",
               "चोट", "फ्रैक्चर", "दुखाप", "जखम"],
    "fever": ["fever", "cough", "cold", "dengue", "malaria", "typhoid", "diarr", "vomit", "flu",
              "infection", "बुखार", "खांसी", "ताप", "खोकला", "सर्दी"],
}
CATEGORY_CAPS = {
    "emergency": ["Emergency", "ICU", "Trauma", "Surgery"],
    "maternity": ["Maternity"],
    "pediatric": ["Paediatrics", "General", "Emergency"],
    "trauma": ["Trauma", "Emergency", "Surgery"],
    "fever": ["General", "Emergency"],
    "general": [],
}


def triage(db: Session, text: str) -> dict:
    """Symptom -> service routing. Never diagnoses or suggests treatment."""
    tl = (text or "").lower().strip()
    red = [kw for kw in RED_FLAGS if kw in tl]
    if red:
        maternity_emergency = any(term in tl for term in (
            "pregnan", "labour", "labor", "delivery", "water broke", "obstetric"
        ))
        category, emergency = ("maternity" if maternity_emergency else "emergency"), True
    else:
        category, emergency = "general", False
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in tl for kw in kws):
                category = cat
                break

    required_specialities = speciality_requirements(tl, category)
    facilities = rank_facilities(db, required_specialities=required_specialities)
    caps = CATEGORY_CAPS[category]
    if caps:
        matched = [f for f in facilities
                   if any(any(c.lower() in cap.lower() for cap in f["capabilities"]) for c in caps)]
        facilities = matched or facilities

    if emergency:
        message = ("This may be a medical emergency. Call 108 now. The facilities below can provide "
                   "emergency care.")
    else:
        message = ("Based on what you described, here are suitable nearby facilities. If symptoms are "
                   "severe or worsening, call 108.")
    return {
        "input": text,
        "category": category,
        "required_specialities": required_specialities,
        "is_emergency": emergency,
        "matched_red_flags": red,
        "message": message,
        "emergency_number": "108",
        "disclaimer": "This app does not diagnose illness or suggest any treatment or remedy.",
        "facilities": facilities[:4],
    }


def outbreak_alert(db: Session) -> dict:
    """Public-safe outbreak advisory from recent surveillance signals (guest)."""
    rows = db.scalars(select(DailyDemand).order_by(DailyDemand.date.desc()).limit(14)).all()
    active = [r for r in rows if (r.outbreak_type and str(r.outbreak_type) != "None") or r.surveillance_alert]
    if active:
        latest = active[0]
        return {"active": True, "type": latest.outbreak_type,
                "affected_villages": latest.affected_villages,
                "message": f"{latest.outbreak_type or 'Disease'} activity reported in the area. "
                           "Take precautions and seek care early if symptoms appear.",
                "as_of": rows[0].date.isoformat()}
    return {"active": False, "type": None,
            "message": "No active outbreak alerts in your area right now.",
            "as_of": rows[0].date.isoformat() if rows else None}
