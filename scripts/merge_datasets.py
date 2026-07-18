"""Consolidate the two historical CSVs into one daily dataset (Phase 3).

Runs once during Data Preparation. It validates, removes duplicated columns,
and merges the demand and resource history by date into a single file:

    data/demand_forecasting_historical.csv   (demand predictors + patient targets)
    data/resource_allocation_historical.csv  (resource requirements + stock state)
        -> data/demand_resource_daily.csv

So the merge never has to be done manually in Excel.

Usage:
    python scripts/merge_datasets.py

NOTE: Full implementation lands in the Data Preparation phase. The merge key is
`date` (the prototype models a single facility; a `facility_id` key can be added
when the dataset is extended to multiple hospitals). Overlapping columns present
in both files (e.g. outbreak_type, total_patient_arrivals, category arrivals)
are kept once, sourced from the demand file, and verified to be identical across
the two files before dropping the duplicates.
"""


def main() -> None:
    raise NotImplementedError(
        "Dataset consolidation is implemented in the Data Preparation phase."
    )


if __name__ == "__main__":
    main()
