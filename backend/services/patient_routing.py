"""Patient facility-ranking service (Phase 9 basic; full version in Phase 11).

Ranks nearby facilities for the guest patient interface using service capability,
availability status, and road travel time. Does NOT diagnose; only guides.
Never exposes staff schedules or sensitive data. Surfaces the last-verified time.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models import DailyDemand, NearbyFacility

STATUS_RANK = {"Available": 0, "Limited": 1, "Busy": 2}
# Synthetic estimated waiting time (minutes) by readiness status.
WAIT_BASE = {"Available": 20, "Limited": 40, "Busy": 60}


def _waiting_time(f: NearbyFacility) -> int:
    base = WAIT_BASE.get(f.status, 30)
    return int(base + (f.id * 5) % 15 - min(f.beds_available, 10))


def rank_facilities(db: Session, service: str | None = None, urgency: str | None = None) -> list[dict]:
    facilities = db.scalars(select(NearbyFacility)).all()
    scored = []
    for f in facilities:
        caps = [c.strip() for c in f.capabilities.split("|")]
        capable = service is None or any(service.lower() in c.lower() for c in caps)
        scored.append({
            "id": f.id, "name": f.name, "type": f.facility_type,
            "latitude": f.latitude, "longitude": f.longitude,
            "distance_km": f.distance_km, "travel_time_min": f.travel_time_min,
            "waiting_time_min": _waiting_time(f),
            "beds_available": f.beds_available, "capabilities": caps, "status": f.status,
            "matches_service": capable,
            "data_last_verified_at": f.data_last_verified_at.isoformat() if f.data_last_verified_at else None,
            "advice": "Call before travelling to confirm availability.",
        })
    scored.sort(key=lambda x: (not x["matches_service"], STATUS_RANK.get(x["status"], 3), x["travel_time_min"]))
    for i, s in enumerate(scored):
        s["rank"] = i + 1
        s["best_match"] = i == 0 and s["matches_service"] and s["status"] != "Busy"
    return scored


def facility_detail(db: Session, facility_id: int) -> dict | None:
    f = db.get(NearbyFacility, facility_id)
    if f is None:
        return None
    return {
        "id": f.id, "name": f.name, "type": f.facility_type, "distance_km": f.distance_km,
        "travel_time_min": f.travel_time_min, "waiting_time_min": _waiting_time(f),
        "latitude": f.latitude, "longitude": f.longitude, "beds_available": f.beds_available,
        "capabilities": [c.strip() for c in f.capabilities.split("|")], "status": f.status,
        "data_last_verified_at": f.data_last_verified_at.isoformat() if f.data_last_verified_at else None,
        "advice": "Availability may change. Call the facility or emergency services before a long journey.",
    }


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
    "trauma": ["Trauma", "Emergency", "Surgery"],
    "fever": ["General", "Emergency"],
    "general": [],
}


def triage(db: Session, text: str) -> dict:
    """Symptom -> service routing. Never diagnoses or suggests treatment."""
    tl = (text or "").lower().strip()
    red = [kw for kw in RED_FLAGS if kw in tl]
    if red:
        category, emergency = "emergency", True
    else:
        category, emergency = "general", False
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in tl for kw in kws):
                category = cat
                break

    facilities = rank_facilities(db)
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
