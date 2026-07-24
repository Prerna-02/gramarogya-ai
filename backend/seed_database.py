"""Seed the database from the source CSV files (Phase 4).

Imports data/demand_resource_daily.csv into `daily_demand` + `resource_status`,
data/staff_master.csv into `staff`, date-specific staff availability records,
and a small prototype `nearby_facilities` set. Idempotent: truncates the seeded
tables first so it can be re-run.

Run:
    python -m backend.seed_database
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from backend.db import SessionLocal, engine
import backend.db_models  # noqa: F401  (ensure models are registered)

DATA = Path(__file__).resolve().parent.parent / "data"

DEMAND_COLS = [
    "date", "day_of_week", "day_of_week_num", "week_of_year", "month", "season",
    "is_weekend", "public_holiday", "festival_flag", "weekly_market_day",
    "vaccination_camp_flag", "maternal_clinic_day", "local_event_intensity",
    "rainfall_mm", "temperature_max_c", "temperature_min_c", "humidity_pct",
    "outbreak_type", "outbreak_severity_0_5", "surveillance_alert", "affected_villages",
    "general_opd_arrivals", "fever_infectious_arrivals", "maternal_child_arrivals",
    "trauma_emergency_arrivals", "expected_admissions", "total_patient_arrivals",
    "patients_lag_1", "patients_lag_2", "patients_lag_7", "patients_lag_14",
    "rolling_mean_7", "rolling_std_7", "rolling_mean_14",
]
RESOURCE_COLS = [
    "date", "emergency_scenario_type", "emergency_scenario_severity_0_5",
    "total_general_beds", "occupied_general_beds", "available_general_beds",
    "total_emergency_beds", "occupied_emergency_beds", "available_emergency_beds",
    "total_isolation_beds", "occupied_isolation_beds", "available_isolation_beds",
    "overflow_patients", "closing_stock_iv_fluids", "closing_stock_ors",
    "closing_stock_diagnostic_test_kits", "closing_stock_antipyretics", "closing_stock_ppe_kits",
    "available_oxygen_cylinders", "available_ambulances", "resource_shortage_count",
    "emergency_risk_level",
]

NEARBY_FACILITIES = [
    dict(name="CHC Aheri", facility_type="CHC", latitude=19.4187, longitude=79.9560,
         distance_km=24, travel_time_min=40,
         beds_available=18, capabilities="General|Maternity|Basic Emergency", status="Available"),
    dict(name="PHC Bhamragad", facility_type="PHC", latitude=19.4330, longitude=80.3520,
         distance_km=35, travel_time_min=70,
         beds_available=10, capabilities="General|Immunization", status="Available"),
    dict(name="District Hospital Gadchiroli", facility_type="District Hospital",
         latitude=20.1836, longitude=80.0028, distance_km=32,
         travel_time_min=55, beds_available=25, capabilities="Surgery|ICU|Trauma|Maternity|Lab|Radiology",
         status="Busy"),
    dict(name="Rural Hospital Etapalli", facility_type="Rural Hospital", latitude=19.6970, longitude=80.1030,
         distance_km=35, travel_time_min=65, beds_available=10,
         capabilities="General|Maternity|Ambulance", status="Limited"),
]


def _now():
    return datetime.now(timezone.utc)


def seed() -> None:
    df = pd.read_csv(DATA / "demand_resource_daily.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date   # real DATE, not text
    staff = pd.read_csv(DATA / "staff_master.csv")
    staff_availability = pd.read_csv(DATA / "staff_availability.csv")
    staff_availability["date"] = pd.to_datetime(staff_availability["date"]).dt.date

    demand = df[DEMAND_COLS].where(pd.notna(df[DEMAND_COLS]), None).copy()
    resource = df[RESOURCE_COLS].where(pd.notna(df[RESOURCE_COLS]), None).copy()
    demand["data_last_verified_at"] = _now()
    resource["data_last_verified_at"] = _now()
    staff = staff.copy()
    staff["created_at"] = _now()
    staff_availability = staff_availability.where(pd.notna(staff_availability), None).copy()
    staff_availability["created_at"] = _now()

    with engine.begin() as conn:
        # Clear seeded tables (respect FK order).
        for tbl in ["staff_availability", "resource_status", "daily_demand", "staff", "nearby_facilities"]:
            conn.execute(text(f'TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE'))

    demand.to_sql("daily_demand", engine, if_exists="append", index=False, chunksize=500, method="multi")
    resource.to_sql("resource_status", engine, if_exists="append", index=False, chunksize=500, method="multi")
    staff.to_sql("staff", engine, if_exists="append", index=False, chunksize=500, method="multi")
    staff_availability.to_sql("staff_availability", engine, if_exists="append", index=False,
                              chunksize=500, method="multi")

    with SessionLocal() as s:
        from backend.db_models import NearbyFacility
        s.add_all([NearbyFacility(data_last_verified_at=_now(), **f) for f in NEARBY_FACILITIES])
        s.commit()

    with engine.connect() as conn:
        for tbl in ["daily_demand", "resource_status", "staff", "staff_availability", "nearby_facilities"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            print(f"  {tbl:20s} {n} rows")
    print("Seed complete.")


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
