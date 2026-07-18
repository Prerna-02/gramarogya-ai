"""Consolidate the two historical CSVs into one daily dataset (Phase 3).

Run once during Data Preparation. It merges the demand and resource history by
`date` into a single file the forecasting and resource-planning code consumes:

    data/demand_forecasting_historical.csv   (demand predictors + patient targets)
    data/resource_allocation_historical.csv  (resource requirements + stock state)
        -> data/demand_resource_daily.csv

Steps:
    1. Load both daily files.
    2. Verify the columns present in BOTH files are identical row-for-row
       (aligned on date). If they diverge, abort rather than silently pick one.
    3. Drop those duplicates from the resource file (kept once from demand).
    4. Merge on `date` (one row per day) and sort chronologically.
    5. Write data/demand_resource_daily.csv.
    6. Re-validate the merged output.

The merge key is `date` (single-facility prototype). A `facility_id` key can be
added when the dataset is extended to multiple hospitals.

Usage:
    python scripts/merge_datasets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from validate_data import Report, validate_daily, validate_staff, STAFF_CSV

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEMAND_CSV = DATA_DIR / "demand_forecasting_historical.csv"
RESOURCE_CSV = DATA_DIR / "resource_allocation_historical.csv"
OUT_CSV = DATA_DIR / "demand_resource_daily.csv"


def _columns_identical(demand: pd.DataFrame, resource: pd.DataFrame, cols: list[str]) -> list[str]:
    """Return the list of overlapping columns that DIFFER between the files."""
    d = demand.set_index("date")
    r = resource.set_index("date").loc[d.index]
    differing = []
    for col in cols:
        if col == "date":
            continue
        a, b = d[col], r[col]
        if a.dtype.kind in "biufc" and b.dtype.kind in "biufc":
            same = np.allclose(a.fillna(-999_999), b.fillna(-999_999))
        else:
            same = a.fillna("<NA>").astype(str).equals(b.fillna("<NA>").astype(str))
        if not same:
            differing.append(col)
    return differing


def merge() -> pd.DataFrame:
    if not DEMAND_CSV.exists() or not RESOURCE_CSV.exists():
        raise FileNotFoundError("Both source CSVs must exist in data/ before merging.")

    demand = pd.read_csv(DEMAND_CSV)
    resource = pd.read_csv(RESOURCE_CSV)
    print(f"Loaded demand {demand.shape} and resource {resource.shape}")

    if len(demand) != len(resource) or set(demand["date"]) != set(resource["date"]):
        raise ValueError("Date coverage differs between the two files; cannot merge safely.")

    overlap = [c for c in demand.columns if c in resource.columns]
    print(f"Overlapping columns ({len(overlap)}): {overlap}")

    differing = _columns_identical(demand, resource, overlap)
    if differing:
        raise ValueError(
            "Overlapping columns are NOT identical across files; refusing to drop "
            f"duplicates: {differing}"
        )
    print("Verified: all overlapping columns are identical across both files.")

    # Keep overlaps once (from demand); append only the resource-specific columns.
    resource_only = [c for c in resource.columns if c not in demand.columns]
    merged = demand.merge(
        resource[["date"] + resource_only],
        on="date",
        how="inner",
        validate="one_to_one",
    )
    merged = merged.sort_values("date").reset_index(drop=True)

    print(
        f"Merged shape {merged.shape} "
        f"(= {demand.shape[1]} + {resource.shape[1]} - {len(overlap)} columns)"
    )
    return merged


def main() -> int:
    merged = merge()
    merged.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} ({merged.shape[0]} rows, {merged.shape[1]} columns)")

    # Re-validate the freshly written file plus the staff master.
    print("\nRe-validating merged output...")
    rep = Report()
    validate_daily(merged, "demand_resource_daily", rep)
    if STAFF_CSV.exists():
        validate_staff(pd.read_csv(STAFF_CSV), rep)
    return rep.summarize()


if __name__ == "__main__":
    sys.exit(main())
