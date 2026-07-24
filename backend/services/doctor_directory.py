"""Public-safe doctor directory and symptom-to-speciality matching.

Nearby-facility records are curated demo directory entries.  They intentionally
contain only information suitable for patients: doctor name, speciality,
availability status, and consultation window.
"""
from __future__ import annotations


EXTERNAL_DOCTORS = {
    "CHC Aheri": [
        ("AH-GM-01", "Dr. Neelam Atram", "General Medicine", "MBBS", "Available now", "08:00–14:00"),
        ("AH-OG-01", "Dr. Amit Tekam", "Obstetrics & Gynaecology", "MBBS, DGO", "Available later", "14:00–18:00"),
        ("AH-PD-01", "Dr. Pooja Madavi", "Paediatrics", "MBBS, DCH", "With patient", "Next opening 11:20"),
        ("AH-EM-01", "Dr. Rohan Naitam", "Emergency Medicine", "MBBS, Emergency Care", "On call", "24-hour on-call"),
    ],
    "PHC Bhamragad": [
        ("BH-GM-01", "Dr. Meena Pungati", "General Medicine", "MBBS", "Available now", "09:00–15:00"),
        ("BH-CM-01", "Dr. Ajay Hichami", "Community Medicine", "MBBS, MPH", "Available later", "12:00–16:00"),
        ("BH-FM-01", "Dr. Rakesh Korram", "Family Medicine", "MBBS", "On call", "Emergency on-call"),
    ],
    "District Hospital Gadchiroli": [
        ("DH-CD-01", "Dr. Shalini Wankhede", "Cardiology", "MBBS, MD, DM Cardiology", "Available now", "09:00–15:00"),
        ("DH-EM-01", "Dr. Vikram Meshram", "Emergency Medicine", "MBBS, MD Emergency Medicine", "Available now", "08:00–16:00"),
        ("DH-OG-01", "Dr. Kavita Gawande", "Obstetrics & Gynaecology", "MBBS, MS OBGYN", "With patient", "Next opening 11:40"),
        ("DH-PD-01", "Dr. Aakash Shende", "Paediatrics", "MBBS, MD Paediatrics", "Available now", "10:00–17:00"),
        ("DH-OR-01", "Dr. Farhan Sheikh", "Orthopaedics", "MBBS, MS Orthopaedics", "Available later", "13:00–18:00"),
        ("DH-IM-01", "Dr. Ritu Borkar", "Internal Medicine", "MBBS, MD Medicine", "Available now", "08:00–14:00"),
        ("DH-PM-01", "Dr. Sameera Khan", "Pulmonology", "MBBS, MD Pulmonary Medicine", "On call", "On-call until 20:00"),
    ],
    "Rural Hospital Etapalli": [
        ("ET-GM-01", "Dr. Nisha Uikey", "General Medicine", "MBBS", "Available now", "08:00–14:00"),
        ("ET-EM-01", "Dr. Sameer Potavi", "Emergency Medicine", "MBBS, Emergency Care", "On call", "24-hour on-call"),
        ("ET-OG-01", "Dr. Anjali Korram", "Obstetrics & Gynaecology", "MBBS, DGO", "Available later", "14:00–18:00"),
        ("ET-PD-01", "Dr. Vivek Alam", "Paediatrics", "MBBS, DCH", "With patient", "Next opening 12:10"),
    ],
}


STATUS_TONE = {
    "Available now": "available",
    "On call": "on-call",
    "With patient": "busy",
    "Available later": "later",
    "Unavailable today": "unavailable",
    "Unavailable this shift": "unavailable",
}


DEFAULT_SPECIALITIES = {
    "emergency": ["Emergency Medicine", "Internal Medicine"],
    "maternity": ["Obstetrics & Gynaecology"],
    "pediatric": ["Paediatrics"],
    "trauma": ["Orthopaedics", "Emergency Medicine"],
    "fever": ["Internal Medicine", "General Medicine"],
    "general": ["General Medicine", "Family Medicine", "Community Medicine"],
}


def speciality_requirements(text: str, category: str) -> list[str]:
    """Return ordered specialities for the described problem."""
    value = (text or "").lower()
    if any(term in value for term in (
        "pregnan", "labour", "labor", "delivery", "water broke", "obstetric", "antenatal"
    )):
        return ["Obstetrics & Gynaecology", "Emergency Medicine"]
    if any(term in value for term in ("chest pain", "heart", "cardiac")):
        return ["Cardiology", "Emergency Medicine", "Internal Medicine"]
    if any(term in value for term in ("breath", "asthma", "lung", "respiratory")):
        return ["Pulmonology", "Emergency Medicine", "Internal Medicine"]
    if any(term in value for term in ("child", "baby", "infant", "newborn", "pediatric", "paediatric")):
        return ["Paediatrics", "Emergency Medicine"]
    return DEFAULT_SPECIALITIES.get(category, DEFAULT_SPECIALITIES["general"])


def doctor_matches(speciality: str, required_specialities: list[str] | None) -> bool:
    return not required_specialities or speciality.casefold() in {
        item.casefold() for item in required_specialities
    }


def speciality_priority(speciality: str, required_specialities: list[str] | None) -> int:
    if not required_specialities:
        return 0
    normalized = [item.casefold() for item in required_specialities]
    try:
        return normalized.index(speciality.casefold())
    except ValueError:
        return len(normalized) + 1


def public_doctor(record, required_specialities: list[str] | None = None) -> dict:
    doctor_id, name, speciality, qualification, status, consultation_time = record
    return {
        "doctor_id": doctor_id,
        "name": name,
        "speciality": speciality,
        "qualification": qualification,
        "availability_status": status,
        "availability_tone": STATUS_TONE.get(status, "later"),
        "consultation_time": consultation_time,
        "matches_problem": doctor_matches(speciality, required_specialities),
    }


def external_doctors(facility_name: str, required_specialities: list[str] | None = None) -> list[dict]:
    doctors = [public_doctor(row, required_specialities) for row in EXTERNAL_DOCTORS.get(facility_name, [])]
    status_order = {"available": 0, "on-call": 1, "busy": 2, "later": 3, "unavailable": 4}
    return sorted(doctors, key=lambda doctor: (
        not doctor["matches_problem"],
        speciality_priority(doctor["speciality"], required_specialities),
        status_order.get(doctor["availability_tone"], 5),
        doctor["name"],
    ))
