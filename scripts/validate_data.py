"""Validate the source CSV datasets (Phase 3).

Checks for duplicate dates, missing IDs, impossible negative counts, invalid
shift eligibility, and inconsistent category totals. Exits non-zero on any
critical error so it can gate the data-preparation step.

Usage:
    python scripts/validate_data.py
"""


def main() -> None:
    raise NotImplementedError("Data validation is implemented in Phase 3.")


if __name__ == "__main__":
    main()
