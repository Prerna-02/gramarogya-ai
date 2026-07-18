"""Validate the source CSV datasets (Phase 3).

Runs a battery of data-quality checks over the daily demand/resource data and
the staff master, then prints a report grouped by severity:

    CRITICAL  data is unsafe to build on; the script exits non-zero
    WARNING   worth a human look, but not blocking
    INFO      expected / accepted observations (e.g. lag columns empty at the
              start of the series, no outbreak on most days)

Usage:
    python scripts/validate_data.py

Exit code is 0 only when there are zero CRITICAL issues, so this doubles as a
gate before merging or training.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DEMAND_CSV = DATA_DIR / "demand_forecasting_historical.csv"
RESOURCE_CSV = DATA_DIR / "resource_allocation_historical.csv"
STAFF_CSV = DATA_DIR / "staff_master.csv"
MERGED_CSV = DATA_DIR / "demand_resource_daily.csv"

# Columns allowed to contain nulls, with the reason:
#  - outbreak_type is null on days with no outbreak
#  - lag/rolling features are undefined for the first N rows of the series
EXPECTED_NULLABLE = {
    "outbreak_type",
    "patients_lag_1",
    "patients_lag_2",
    "patients_lag_7",
    "patients_lag_14",
    "rolling_mean_7",
    "rolling_std_7",
    "rolling_mean_14",
}

CATEGORY_COLS = [
    "general_opd_arrivals",
    "fever_infectious_arrivals",
    "maternal_child_arrivals",
    "trauma_emergency_arrivals",
]

BINARY_COLS = [
    "is_weekend",
    "public_holiday",
    "festival_flag",
    "weekly_market_day",
    "vaccination_camp_flag",
    "maternal_clinic_day",
    "surveillance_alert",
]

SEASONS = {"Winter", "Summer", "Monsoon", "Post_Monsoon"}
RISK_LEVELS = {"Normal", "Watch", "High", "Critical"}
SHIFT_TOKENS = {"Morning", "Evening", "Night", "On-call"}
PREFERRED_SHIFTS = {"Morning", "Evening", "Night"}


class Report:
    """Collects issues by severity and controls the process exit code."""

    def __init__(self) -> None:
        self.critical: list[str] = []
        self.warning: list[str] = []
        self.info: list[str] = []

    def critical_(self, msg: str) -> None:
        self.critical.append(msg)

    def warn(self, msg: str) -> None:
        self.warning.append(msg)

    def info_(self, msg: str) -> None:
        self.info.append(msg)

    def section(self, title: str) -> None:
        print(f"\n--- {title} ---")

    def summarize(self) -> int:
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        for label, items in (
            ("INFO", self.info),
            ("WARNING", self.warning),
            ("CRITICAL", self.critical),
        ):
            print(f"\n{label} ({len(items)}):")
            for m in items:
                print(f"  - {m}")
        ok = not self.critical
        print("\n" + ("PASSED: 0 critical issues." if ok else "FAILED: critical issues present."))
        return 0 if ok else 1


def validate_daily(df: pd.DataFrame, name: str, rep: Report) -> None:
    """Checks that apply to any daily demand/resource table."""
    rep.section(f"{name}: {df.shape[0]} rows x {df.shape[1]} cols")

    # Date column: present, parseable, unique, contiguous.
    if "date" not in df.columns:
        rep.critical_(f"{name}: missing 'date' column")
        return
    dates = pd.to_datetime(df["date"], errors="coerce")
    if dates.isna().any():
        rep.critical_(f"{name}: {int(dates.isna().sum())} unparseable date(s)")
    dup = int(dates.duplicated().sum())
    if dup:
        rep.critical_(f"{name}: {dup} duplicate date(s)")
    else:
        rep.info_(f"{name}: no duplicate dates")
    valid = dates.dropna()
    if not valid.empty:
        full = pd.date_range(valid.min(), valid.max(), freq="D")
        missing = len(set(full) - set(valid))
        if missing:
            rep.warn(f"{name}: {missing} missing day(s) between {valid.min().date()} and {valid.max().date()}")
        else:
            rep.info_(f"{name}: continuous daily coverage {valid.min().date()} -> {valid.max().date()}")

    # Unexpected nulls (expected-nullable columns are only reported as INFO).
    for col in df.columns:
        n = int(df[col].isna().sum())
        if not n:
            continue
        if col in EXPECTED_NULLABLE:
            rep.info_(f"{name}: {col} has {n} null(s) (expected)")
        else:
            rep.critical_(f"{name}: {col} has {n} unexpected null(s)")

    # Negative values in numeric columns are impossible for counts/stock.
    num = df.select_dtypes(include="number")
    negs = (num < 0).sum()
    negs = negs[negs > 0]
    if len(negs):
        for col, n in negs.items():
            rep.critical_(f"{name}: {col} has {int(n)} negative value(s)")
    else:
        rep.info_(f"{name}: no negative numeric values")

    # Category totals must reconcile with the reported total.
    if set(CATEGORY_COLS + ["total_patient_arrivals"]).issubset(df.columns):
        mismatch = int((df[CATEGORY_COLS].sum(axis=1) != df["total_patient_arrivals"]).sum())
        if mismatch:
            rep.critical_(f"{name}: {mismatch} row(s) where category sum != total_patient_arrivals")
        else:
            rep.info_(f"{name}: category counts reconcile with total on all rows")

    # Binary flags in {0, 1}.
    for col in BINARY_COLS:
        if col in df.columns:
            bad = set(df[col].dropna().unique()) - {0, 1}
            if bad:
                rep.critical_(f"{name}: {col} has non-binary value(s) {sorted(bad)}")

    # Domain checks.
    if "season" in df.columns:
        bad = set(df["season"].dropna().unique()) - SEASONS
        if bad:
            rep.warn(f"{name}: unexpected season value(s) {sorted(bad)}")
    if "outbreak_severity_0_5" in df.columns:
        bad = [v for v in df["outbreak_severity_0_5"].dropna().unique() if not 0 <= v <= 5]
        if bad:
            rep.critical_(f"{name}: outbreak_severity_0_5 out of range: {sorted(bad)}")
    if "emergency_risk_level" in df.columns:
        bad = set(df["emergency_risk_level"].dropna().unique()) - RISK_LEVELS
        if bad:
            rep.warn(f"{name}: unexpected emergency_risk_level value(s) {sorted(bad)}")

    # Consistency: no outbreak type <-> zero severity.
    if {"outbreak_type", "outbreak_severity_0_5"}.issubset(df.columns):
        no_type = df["outbreak_type"].isna()
        bad_pos = int(((no_type) & (df["outbreak_severity_0_5"] > 0)).sum())
        bad_neg = int(((~no_type) & (df["outbreak_severity_0_5"] == 0)).sum())
        if bad_pos or bad_neg:
            rep.warn(
                f"{name}: outbreak_type/severity inconsistency "
                f"(no-type-but-severity>0: {bad_pos}, has-type-but-severity=0: {bad_neg})"
            )
        else:
            rep.info_(f"{name}: outbreak_type and severity are consistent")


def validate_staff(df: pd.DataFrame, rep: Report) -> None:
    rep.section(f"staff_master: {df.shape[0]} rows x {df.shape[1]} cols")

    if "staff_id" not in df.columns:
        rep.critical_("staff: missing 'staff_id' column")
        return
    if df["staff_id"].isna().any():
        rep.critical_(f"staff: {int(df['staff_id'].isna().sum())} missing staff_id(s)")
    if not df["staff_id"].is_unique:
        dupes = df.loc[df["staff_id"].duplicated(), "staff_id"].tolist()
        rep.critical_(f"staff: duplicate staff_id(s) {dupes}")
    else:
        rep.info_(f"staff: {df['staff_id'].nunique()} unique staff_ids")

    # Any unexpected nulls in the staff master are critical.
    nulls = df.isna().sum()
    nulls = nulls[nulls > 0]
    if len(nulls):
        for col, n in nulls.items():
            rep.critical_(f"staff: {col} has {int(n)} null(s)")
    else:
        rep.info_("staff: no null values")

    # shift_eligibility tokens must come from the known set.
    if "shift_eligibility" in df.columns:
        bad_rows = []
        for sid, val in zip(df["staff_id"], df["shift_eligibility"]):
            tokens = {t.strip() for t in str(val).split("|")}
            if tokens - SHIFT_TOKENS:
                bad_rows.append(sid)
        if bad_rows:
            rep.critical_(f"staff: invalid shift_eligibility token(s) for {bad_rows}")
        else:
            rep.info_("staff: all shift_eligibility tokens valid")

    # preferred_shift must be a real shift and eligible for that worker.
    if {"preferred_shift", "shift_eligibility"}.issubset(df.columns):
        bad_domain, not_eligible = [], []
        for sid, pref, elig in zip(df["staff_id"], df["preferred_shift"], df["shift_eligibility"]):
            if pref not in PREFERRED_SHIFTS:
                bad_domain.append(sid)
            elif pref not in {t.strip() for t in str(elig).split("|")}:
                not_eligible.append(sid)
        if bad_domain:
            rep.critical_(f"staff: preferred_shift outside {PREFERRED_SHIFTS} for {bad_domain}")
        if not_eligible:
            rep.warn(f"staff: preferred_shift not in shift_eligibility for {not_eligible}")

    # emergency_on_call in {0, 1}.
    if "emergency_on_call" in df.columns:
        bad = set(df["emergency_on_call"].dropna().unique()) - {0, 1}
        if bad:
            rep.critical_(f"staff: emergency_on_call has non-binary value(s) {sorted(bad)}")

    # Numeric sanity ranges.
    ranges = {
        "experience_years": (0, 60),
        "max_weekly_hours": (1, 168),
        "max_consecutive_working_days": (1, 31),
        "minimum_rest_hours": (0, 48),
        "max_night_shifts_per_month": (0, 31),
    }
    for col, (lo, hi) in ranges.items():
        if col in df.columns:
            bad = df[(df[col] < lo) | (df[col] > hi)]
            if len(bad):
                rep.critical_(f"staff: {col} out of [{lo}, {hi}] for {bad['staff_id'].tolist()}")


def main() -> int:
    rep = Report()
    print("=" * 60)
    print("GramArogya AI — data validation")
    print("=" * 60)

    if MERGED_CSV.exists():
        validate_daily(pd.read_csv(MERGED_CSV), "demand_resource_daily", rep)
    else:
        rep.info_("demand_resource_daily.csv not found yet (run merge_datasets.py)")
        if DEMAND_CSV.exists():
            validate_daily(pd.read_csv(DEMAND_CSV), "demand_forecasting_historical", rep)
        else:
            rep.critical_(f"missing {DEMAND_CSV.name}")
        if RESOURCE_CSV.exists():
            validate_daily(pd.read_csv(RESOURCE_CSV), "resource_allocation_historical", rep)
        else:
            rep.critical_(f"missing {RESOURCE_CSV.name}")

    if STAFF_CSV.exists():
        validate_staff(pd.read_csv(STAFF_CSV), rep)
    else:
        rep.critical_(f"missing {STAFF_CSV.name}")

    return rep.summarize()


if __name__ == "__main__":
    sys.exit(main())
