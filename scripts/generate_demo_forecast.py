"""Demo: forecast a 7-day window and produce explainable resource plans (Phase 7).

Loads the trained demand model, forecasts the six targets for each day in a
window, runs the resource-planning engine, and prints a readable 7-day plan plus
a fully explained breakdown for one day (the Phase 7 completion check).

Usage:
    python scripts/generate_demo_forecast.py [START_DATE] [DAYS]
    # e.g. python scripts/generate_demo_forecast.py 2025-09-01 7

Requires the artifacts from train_forecast_model.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import train_forecast_model as tfm  # noqa: E402
from backend.services.resource_planning import plan_resources  # noqa: E402

MODEL_PATH = ROOT / "backend" / "artifacts" / "demand_model.joblib"

AVAIL_FROM_ROW = {  # engine availability key -> dataset column
    # Beds compare needed concurrent occupancy against TOTAL capacity
    # (shortage == overflow), not against currently-free beds.
    "general_beds": "total_general_beds",
    "emergency_beds": "total_emergency_beds",
    "isolation_beds": "total_isolation_beds",
    "diagnostic_test_kits": "closing_stock_diagnostic_test_kits",
    "antipyretics": "closing_stock_antipyretics",
    "iv_fluids": "closing_stock_iv_fluids",
    "ors": "closing_stock_ors",
    "ppe_kits": "closing_stock_ppe_kits",
    "oxygen_cylinders": "available_oxygen_cylinders",
    "ambulances": "available_ambulances",
}


def staff_availability() -> dict:
    s = pd.read_csv(ROOT / "data" / "staff_master.csv")
    c = lambda d: int((s["designation"] == d).sum())
    return {
        "general_doctors": c("General Medical Officer") + c("Medical Superintendent"),
        "physicians": c("Physician"),
        "emergency_doctors": c("Emergency Medical Officer"),
        "obgyn_doctors": c("Obstetrician and Gynecologist"),
        "pediatricians": c("Pediatrician"),
        "lab_technicians": c("Laboratory Technician"),
        "pharmacists": c("Pharmacist"),
        "anm_staff": c("Auxiliary Nurse Midwife"),
        "senior_nursing_officers": c("Senior Nursing Officer"),
        "nursing_officers": c("Nursing Officer"),
    }


def forecast_row(models, row) -> dict:
    # Transposing a single row Series yields object dtype; features are all
    # numeric, so cast back to float for the model.
    X = row[tfm.FEATURES].to_frame().T.astype(float)
    return {t: float(models[t].predict(X)[0]) for t in tfm.TARGETS}


def print_line_items(title, items):
    print(f"\n  {title}")
    for it in items:
        flag = "" if it["status"] == "OK" else f"  <-- {it['status']}"
        print(f"    {it['resource']:24s} req {it['required']:>4}  avail {it['available']:>4}"
              f"  short {it['shortage']:>3}{flag}")
        print(f"        why: {it['explanation']}")


def main() -> int:
    if not MODEL_PATH.exists():
        print("Model artifact not found. Run: python scripts/train_forecast_model.py")
        return 1
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-09-01"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    bundle = joblib.load(MODEL_PATH)
    models = bundle["models"]
    df = tfm.load_and_engineer()
    staff_avail = staff_availability()

    window = df[df["date"] >= start].head(days)
    if window.empty:
        print(f"No data on/after {start}.")
        return 1

    print("=" * 74)
    print(f"7-DAY FORECAST + RESOURCE PLAN  ({bundle['family']} model)   from {start}")
    print("=" * 74)
    print(f"{'date':12s} {'total':>6} {'opd':>5} {'fever':>6} {'mat':>4} {'trauma':>7} "
          f"{'adm':>4} {'status':>9} shortages")

    plans = []
    for _, row in window.iterrows():
        fc = forecast_row(models, row)
        avail = {**staff_avail, **{k: int(row[col]) for k, col in AVAIL_FROM_ROW.items()}}
        plan = plan_resources(fc, avail)
        plans.append((row["date"], fc, plan))
        f = plan["forecast"]; su = plan["summary"]
        print(f"{row['date'].date()!s:12s} {f['total_patient_arrivals']:>6} "
              f"{f['general_opd_arrivals']:>5} {f['fever_infectious_arrivals']:>6} "
              f"{f['maternal_child_arrivals']:>4} {f['trauma_emergency_arrivals']:>7} "
              f"{f['expected_admissions']:>4} {su['status']:>9} "
              f"{','.join(su['shortages']) or '-'}")

    # Full explainable breakdown for the highest-shortage day.
    date, fc, plan = max(plans, key=lambda p: p[2]["summary"]["shortage_count"])
    print("\n" + "=" * 74)
    print(f"EXPLAINED PLAN FOR {date.date()}  (status: {plan['summary']['status']}, "
          f"{plan['summary']['shortage_count']} shortages)")
    print("=" * 74)
    print(f"  forecast: {plan['forecast']}")
    print(f"  bed admission split: {plan['bed_admission_split']}")
    print_line_items("STAFF", plan["staff"].values())
    print_line_items("BEDS", plan["beds"].values())
    print_line_items("MEDICINES", plan["medicines"].values())
    print_line_items("OXYGEN / AMBULANCE", [plan["oxygen"], plan["ambulances"]])
    if plan["summary"]["reorders"]:
        print(f"\n  reorder recommended: {', '.join(plan['summary']['reorders'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
