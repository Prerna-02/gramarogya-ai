"""Resource-planning engine (Phase 7).

Translates a category-level demand forecast into explainable operational
requirements — staff, beds, medicines, oxygen, ambulances — and compares each
against current availability to flag shortages.

Design principles:
- **Explainable, not learned.** Every requirement is a documented prototype
  formula (see `docs/RESOURCE_PLANNING.md`); each output carries an `explanation`.
- **Leakage-safe.** Consumes only the forecast (Group B targets) + current
  availability. It never reads the historical `required_*` columns.
- **Prototype ratios** are clearly labelled and must be validated by healthcare
  staff before real use.

Public entry point:
    plan_resources(forecast, availability=None, config=RESOURCE_CONFIG) -> dict
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ------------------------------------------------------------------ config
# All ratios are PROTOTYPE values for demonstration. See docs/RESOURCE_PLANNING.md.

RESOURCE_CONFIG = {
    # 1 staff member per N cases of the given driver (caseload ratios).
    "staff_caseload": {
        "general_doctors":   ("general_opd_arrivals", 45),
        "physicians":        ("fever_infectious_arrivals", 40),
        "emergency_doctors": ("trauma_emergency_arrivals", 12),
        "lab_technicians":   ("fever_infectious_arrivals", 30),
        "pharmacists":       ("total_patient_arrivals", 120),
        "anm_staff":         ("maternal_child_arrivals", 8),
    },
    # Specialists: minimum coverage policy + demand escalation.
    "specialists": {
        "obgyn_doctors": {"minimum": 2, "driver": "maternal_child_arrivals", "escalate_at": 13},
        "pediatricians": {"minimum": 1, "driver": "maternal_child_arrivals", "escalate_at": 13},
    },
    # Nurses scale with beds in use.
    "nursing": {"base_senior": 2, "per_occupied_beds": 12, "base_officers": 4},
    # Beds: split admissions by case mix, then hold for the average length of stay.
    "beds": {
        "length_of_stay": {"general": 4, "emergency": 2, "isolation": 5},
        "iso_weight_per_fever": 0.6, "emergency_weight_per_trauma": 0.7, "general_base": 0.18,
    },
    # Medicines/consumables: required = rate x driver (+ optional extra term).
    "medicines": {
        "diagnostic_test_kits": {"driver": "fever_infectious_arrivals", "rate": 0.35, "safety": 100, "lead": 6},
        "antipyretics":         {"driver": "fever_infectious_arrivals", "rate": 0.80, "safety": 250, "lead": 5},
        "iv_fluids":            {"driver": "expected_admissions", "rate": 1.20,
                                 "extra": ("fever_infectious_arrivals", 0.15), "safety": 120, "lead": 5},
        "ors":                  {"driver": "fever_infectious_arrivals", "rate": 0.20, "safety": 90, "lead": 5},
        "ppe_kits":             {"driver": "fever_infectious_arrivals", "rate": 0.35, "safety": 150, "lead": 7},
    },
    # Oxygen: respiratory-driven. severe_resp ~= fever x resp_fraction x severe_fraction.
    "oxygen": {"resp_fraction_of_fever": 0.30, "severe_fraction_of_resp": 0.15,
               "cylinders_per_case": 0.8, "baseline": 2},
    # Ambulances: 1 standby + 1 per N trauma cases.
    "ambulance": {"standby": 1, "per_trauma": 15},
}

# Reasonable prototype defaults when availability is not supplied.
DEFAULT_AVAILABILITY = {
    "general_doctors": 5, "physicians": 1, "emergency_doctors": 2, "obgyn_doctors": 1,
    "pediatricians": 1, "lab_technicians": 3, "pharmacists": 2, "anm_staff": 4,
    "senior_nursing_officers": 5, "nursing_officers": 12,
    "general_beds": 28, "emergency_beds": 8, "isolation_beds": 12,
    "diagnostic_test_kits": 200, "antipyretics": 600, "iv_fluids": 300, "ors": 250, "ppe_kits": 400,
    "oxygen_cylinders": 12, "ambulances": 3,
}


@dataclass
class Requirement:
    """One planned resource line with its shortage and a plain-language reason."""
    resource: str
    required: int
    available: int
    explanation: str
    reorder_needed: bool = False

    @property
    def shortage(self) -> int:
        return max(0, self.required - self.available)

    @property
    def surplus(self) -> int:
        return max(0, self.available - self.required)

    @property
    def status(self) -> str:
        if self.shortage > 0:
            return "SHORTAGE"
        if self.reorder_needed:
            return "REORDER"
        return "OK"

    def to_dict(self) -> dict:
        return {
            "resource": self.resource, "required": self.required, "available": self.available,
            "shortage": self.shortage, "surplus": self.surplus, "status": self.status,
            "reorder_needed": self.reorder_needed, "explanation": self.explanation,
        }


def _ceil(x: float) -> int:
    return int(math.ceil(x - 1e-9))


def _plan_staff(f, avail, cfg):
    out = {}
    for role, (driver, caseload) in cfg["staff_caseload"].items():
        req = _ceil(f[driver] / caseload)
        out[role] = Requirement(
            role, max(req, 0), avail.get(role, 0),
            f"ceil({f[driver]} {driver} / {caseload} per staff) = {req}")
    for role, spec in cfg["specialists"].items():
        req = spec["minimum"] + (1 if f[spec["driver"]] >= spec["escalate_at"] else 0)
        out[role] = Requirement(
            role, req, avail.get(role, 0),
            f"min coverage {spec['minimum']}" +
            (f" +1 (escalation: {spec['driver']} >= {spec['escalate_at']})" if req > spec["minimum"] else ""))
    return out


def _plan_beds(f, avail, cfg):
    b = cfg["beds"]
    fever, trauma, adm = f["fever_infectious_arrivals"], f["trauma_emergency_arrivals"], f["expected_admissions"]
    denom = f["fever_infectious_arrivals"] + f["general_opd_arrivals"] + f["maternal_child_arrivals"] + trauma + 1
    w_iso = b["iso_weight_per_fever"] * fever / denom
    w_emg = b["emergency_weight_per_trauma"] * trauma / denom
    w_gen = max(b["general_base"], 1 - w_iso - w_emg)
    total_w = w_iso + w_emg + w_gen
    weights = {"isolation": w_iso / total_w, "emergency": w_emg / total_w, "general": w_gen / total_w}
    out = {}
    for bt, w in weights.items():
        los = b["length_of_stay"][bt]
        req = _ceil(adm * w * los)
        out[bt] = Requirement(
            f"{bt}_beds", req, avail.get(f"{bt}_beds", 0),
            f"ceil({adm} admissions x {w:.2f} {bt}-share x {los}d stay) = {req}")
    return out, weights


def _plan_nursing(f, beds, avail, cfg):
    n = cfg["nursing"]
    occ = sum(r.required for r in beds.values())
    senior = n["base_senior"] + (1 if f["total_patient_arrivals"] > 160 else 0)
    officers = n["base_officers"] + occ // n["per_occupied_beds"]
    return {
        "senior_nursing_officers": Requirement(
            "senior_nursing_officers", senior, avail.get("senior_nursing_officers", 0),
            f"base {n['base_senior']}" + (" +1 (load>160)" if senior > n["base_senior"] else "")),
        "nursing_officers": Requirement(
            "nursing_officers", officers, avail.get("nursing_officers", 0),
            f"base {n['base_officers']} + {occ} planned beds // {n['per_occupied_beds']} = {officers}"),
    }


def _plan_medicines(f, avail, cfg):
    out = {}
    for item, r in cfg["medicines"].items():
        req = r["rate"] * f[r["driver"]]
        expl = f"{r['rate']} x {f[r['driver']]} {r['driver']}"
        if "extra" in r:
            ecol, erate = r["extra"]
            req += erate * f[ecol]
            expl += f" + {erate} x {f[ecol]} {ecol}"
        req = _ceil(req)
        stock = avail.get(item, 0)
        reorder_point = _ceil(req * r["lead"] + r["safety"])
        out[item] = Requirement(
            item, req, stock, f"{expl} = {req}; reorder point {reorder_point}",
            reorder_needed=stock <= reorder_point)
    return out


def _plan_oxygen(f, avail, cfg):
    o = cfg["oxygen"]
    severe_resp = f["fever_infectious_arrivals"] * o["resp_fraction_of_fever"] * o["severe_fraction_of_resp"]
    req = _ceil(severe_resp * o["cylinders_per_case"]) + o["baseline"]
    return Requirement(
        "oxygen_cylinders", req, avail.get("oxygen_cylinders", 0),
        f"~{severe_resp:.1f} severe-resp cases x {o['cylinders_per_case']} + {o['baseline']} baseline = {req}")


def _plan_ambulance(f, avail, cfg):
    a = cfg["ambulance"]
    req = a["standby"] + _ceil(f["trauma_emergency_arrivals"] / a["per_trauma"])
    return Requirement(
        "ambulances", req, avail.get("ambulances", 0),
        f"{a['standby']} standby + ceil({f['trauma_emergency_arrivals']} trauma / {a['per_trauma']}) = {req}")


def plan_resources(forecast: dict, availability: dict | None = None,
                   config: dict = RESOURCE_CONFIG) -> dict:
    """Compute an explainable resource plan for one forecast day.

    `forecast` must contain the six Group-B targets. `availability` overrides the
    prototype defaults. Returns a nested dict of requirements plus a summary.
    """
    required_keys = ["general_opd_arrivals", "fever_infectious_arrivals",
                     "maternal_child_arrivals", "trauma_emergency_arrivals",
                     "total_patient_arrivals", "expected_admissions"]
    missing = [k for k in required_keys if k not in forecast]
    if missing:
        raise ValueError(f"forecast missing keys: {missing}")
    f = {k: max(0, round(float(forecast[k]))) for k in required_keys}
    avail = {**DEFAULT_AVAILABILITY, **(availability or {})}

    staff = _plan_staff(f, avail, config)
    beds, bed_weights = _plan_beds(f, avail, config)
    nursing = _plan_nursing(f, beds, avail, config)
    medicines = _plan_medicines(f, avail, config)
    oxygen = _plan_oxygen(f, avail, config)
    ambulance = _plan_ambulance(f, avail, config)

    all_reqs = list(staff.values()) + list(beds.values()) + list(nursing.values()) \
        + list(medicines.values()) + [oxygen, ambulance]
    shortages = [r.to_dict() for r in all_reqs if r.shortage > 0]
    reorders = [r.resource for r in all_reqs if r.reorder_needed and r.shortage == 0]

    n = len(shortages)
    status = "Critical" if n >= 5 else "High" if n >= 3 else "Watch" if n >= 1 else "Normal"

    return {
        "forecast": f,
        "staff": {k: v.to_dict() for k, v in {**staff, **nursing}.items()},
        "beds": {k: v.to_dict() for k, v in beds.items()},
        "bed_admission_split": {k: round(v, 2) for k, v in bed_weights.items()},
        "medicines": {k: v.to_dict() for k, v in medicines.items()},
        "oxygen": oxygen.to_dict(),
        "ambulances": ambulance.to_dict(),
        "summary": {
            "shortage_count": n,
            "status": status,
            "shortages": [s["resource"] for s in shortages],
            "reorders": reorders,
        },
    }
