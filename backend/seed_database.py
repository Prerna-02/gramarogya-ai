"""Seed the PostgreSQL database from the source CSV files.

Implemented in Phase 4. Reads data/demand_resource_daily.csv (produced by
scripts/merge_datasets.py) and data/staff_master.csv, then imports them into
the normalized tables.

Run:
    python -m backend.seed_database
"""


def main() -> None:
    raise NotImplementedError("Database seeding is implemented in Phase 4.")


if __name__ == "__main__":
    main()
