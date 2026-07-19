"""Single source of truth for roster scheduling configuration (Phase 8).

Shift definitions, NSGA-II parameters, post-optimization ranking weights, and the
prototype coverage template that expands Phase 7 daily role counts into
per-date / per-shift / per-department staffing requirements.

All coverage ratios are PROTOTYPE values and must be validated by hospital staff.
"""
from __future__ import annotations

# ---- Shift model -------------------------------------------------------------
# (start, end, credited_working_hours). Times are 24h; Night/On-call wrap midnight.
SHIFT_HOURS = {
    "Morning": ("08:00", "16:00", 8),
    "Evening": ("16:00", "24:00", 8),
    "Night":   ("00:00", "08:00", 8),
    "On-call": ("00:00", "24:00", 4),   # credited hours for a standby day
    "Off":     ("--:--", "--:--", 0),
}
WORKING_SHIFTS = ["Morning", "Evening", "Night", "On-call"]
# Start-hour on a 24h clock, used for rest-gap arithmetic.
SHIFT_START_HOUR = {"Morning": 8, "Evening": 16, "Night": 24, "On-call": 8}
SHIFT_END_HOUR = {"Morning": 16, "Evening": 24, "Night": 32, "On-call": 20}  # Night ends 08:00 next day

# ---- NSGA-II parameters ------------------------------------------------------
SEED = 42
POP_SIZE = 40
N_GEN = 40
CONFIRMED_DAYS = 7               # days 1..7 confirmed, later days provisional
DEFAULT_TARGET_WEEKLY_HOURS = 48

# ---- Post-optimization ranking (balanced recommendation) ---------------------
# Applied ONLY to feasible Pareto solutions; never trades a hard constraint.
RANKING_WEIGHTS = {
    "coverage": 0.35,       # service coverage  (min understaffing)
    "fairness": 0.25,       # workforce fairness (min inequality)
    "fatigue": 0.20,        # fatigue reduction
    "overtime": 0.10,       # overtime reduction
    "preference": 0.10,     # preference satisfaction
}
# Objective vector order used everywhere.
OBJECTIVES = ["understaffing", "unfairness", "fatigue", "overtime", "preference_violation"]

SUPPORTED_HORIZONS = [5, 7, 14, 21]

# ---- Fairness comparison groups ---------------------------------------------
# Fairness is measured WITHIN a group, never across groups (a doctor is not
# interchangeable with a nurse). Maps designation -> comparison group.
FAIRNESS_GROUPS = {
    "Medical Superintendent": "senior_doctors",
    "General Medical Officer": "medical_officers",
    "Emergency Medical Officer": "medical_officers",
    "Physician": "physicians",
    "Public Health Medical Officer": "medical_officers",
    "Anesthetist": "specialist_doctors",
    "Obstetrician and Gynecologist": "specialist_doctors",
    "Pediatrician": "specialist_doctors",
    "Nursing Superintendent": "senior_nurses",
    "Assistant Nursing Superintendent": "senior_nurses",
    "Senior Nursing Officer": "senior_nurses",
    "Nursing Officer": "nursing_officers",
    "Auxiliary Nurse Midwife": "anm",
    "Pharmacist": "allied_health",
    "Laboratory Technician": "allied_health",
    "Radiographer": "allied_health",
    "Operation Theatre Technician": "allied_health",
    "Counsellor": "allied_health",
    "Ward Attendant": "support",
    "Emergency Medical Technician and Driver": "emergency_transport",
}

# ---- Coverage template: Phase 7 role -> shift/department requirement ---------
# `around_clock` roles need coverage in Morning/Evening/Night; others in the
# listed shifts. `oncall_shift` adds a standby slot. `skill` (if set) is required.
COVERAGE_TEMPLATE = {
    "general_doctors": dict(designation="General Medical Officer", department="General OPD",
                            shifts=["Morning", "Evening"]),
    "physicians": dict(designation="Physician", department="Medicine",
                       shifts=["Morning", "Evening"], oncall_shift="On-call"),
    "emergency_doctors": dict(designation="Emergency Medical Officer", department="Emergency",
                              shifts=["Morning", "Evening", "Night"], around_clock=True,
                              skill="emergency"),
    "obgyn_doctors": dict(designation="Obstetrician and Gynecologist",
                          department="Maternal and Child Health",
                          shifts=["Morning"], oncall_shift="On-call",
                          specialist="obgyn"),
    "pediatricians": dict(designation="Pediatrician", department="Maternal and Child Health",
                          shifts=["Morning"], oncall_shift="On-call", specialist="pediatric"),
    "senior_nursing_officers": dict(designation="Senior Nursing Officer", department="Inpatient Ward",
                                    shifts=["Morning", "Evening", "Night"], around_clock=True,
                                    supervisory=True),
    "nursing_officers": dict(designation="Nursing Officer", department="Inpatient Ward",
                             shifts=["Morning", "Evening", "Night"], around_clock=True),
    "anm_staff": dict(designation="Auxiliary Nurse Midwife", department="Maternal and Child Health",
                      shifts=["Morning", "Evening"]),
    "lab_technicians": dict(designation="Laboratory Technician", department="Laboratory",
                            shifts=["Morning", "Evening"], oncall_shift="On-call"),
    "pharmacists": dict(designation="Pharmacist", department="Pharmacy",
                        shifts=["Morning", "Evening"]),
    "ambulance_crew": dict(designation="Emergency Medical Technician and Driver", department="Ambulance",
                           shifts=["Morning", "Evening", "Night"], around_clock=True),
}


# Which staff designations may fill each role. Specialists (OBGYN, Pediatrician)
# have NO substitute on purpose — an unmet specialist slot is a real shortage.
# General doctors and nurses cross-cover related roles (prototype policy).
ELIGIBLE_DESIGNATIONS = {
    "general_doctors": ["General Medical Officer", "Medical Superintendent", "Public Health Medical Officer"],
    "physicians": ["Physician", "General Medical Officer"],
    "emergency_doctors": ["Emergency Medical Officer", "General Medical Officer"],
    "obgyn_doctors": ["Obstetrician and Gynecologist"],
    "pediatricians": ["Pediatrician"],
    "senior_nursing_officers": ["Senior Nursing Officer", "Nursing Superintendent", "Assistant Nursing Superintendent"],
    "nursing_officers": ["Nursing Officer", "Senior Nursing Officer"],
    "anm_staff": ["Auxiliary Nurse Midwife", "Nursing Officer"],
    "lab_technicians": ["Laboratory Technician"],
    "pharmacists": ["Pharmacist"],
    "ambulance_crew": ["Emergency Medical Technician and Driver"],
}


def distribute_count(total: int, n_shifts: int, around_clock: bool) -> list[int]:
    """Split a daily role count across its shifts (>=1 each for 24/7 roles)."""
    total = max(total, n_shifts if around_clock else 1)
    base, rem = divmod(total, n_shifts)
    counts = [base + (1 if i < rem else 0) for i in range(n_shifts)]
    if around_clock:
        counts = [max(1, c) for c in counts]
    return counts
