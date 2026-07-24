"""Refresh only the staff-availability input table from its CSV source.

This avoids resetting demand, resources, rosters, or audit records when the
availability calendar changes.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from sqlalchemy import delete

from backend.db import SessionLocal
from backend.db_models import StaffAvailability


SOURCE = Path(__file__).resolve().parent.parent / "data" / "staff_availability.csv"


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    records = [
        StaffAvailability(
            staff_id=row["staff_id"],
            date=date.fromisoformat(row["date"]),
            availability_status=row["availability_status"].strip().lower(),
            shift=row["shift"].strip() or None,
            reason=row["reason"].strip() or None,
        )
        for row in rows
    ]
    with SessionLocal() as db:
        db.execute(delete(StaffAvailability))
        db.add_all(records)
        db.commit()
    print(f"Loaded {len(records)} staff availability records from {SOURCE.name}.")


if __name__ == "__main__":
    main()
