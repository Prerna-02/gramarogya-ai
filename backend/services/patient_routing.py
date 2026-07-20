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
