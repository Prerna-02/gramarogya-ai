"""Demand forecasting service (Phase 6 model, served in Phase 9).

Loads the saved model artifact and produces:
- `future_forecast(start_date, horizon)` — an operational 1..N day forecast for
  dates beyond the historical data, using seasonal covariates (monthly weather
  means, weekly market-day pattern) and recursive lag/rolling features.
- `backtest_latest(n)` — recent actual-vs-predicted pairs from the historical
  test window (for the dashboard's actual-vs-predicted chart).

Uses only leakage-safe features. Resource-requirement columns are never inputs.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "backend" / "artifacts"
DATA_CSV = ROOT / "data" / "demand_resource_daily.csv"

MONTH_SEASON = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Summer", 4: "Summer",
                5: "Summer", 6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
                10: "Post_Monsoon", 11: "Post_Monsoon"}
WEATHER_COLS = ["rainfall_mm", "temperature_max_c", "temperature_min_c", "humidity_pct"]


class ModelNotTrained(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load():
    model_path = ARTIFACTS / "demand_model.joblib"
    config_path = ARTIFACTS / "feature_config.json"
    if not model_path.exists() or not config_path.exists():
        raise ModelNotTrained("Run scripts/train_forecast_model.py first.")
    bundle = joblib.load(model_path)
    config = json.loads(config_path.read_text())
    return bundle, config


@lru_cache(maxsize=1)
def _history():
    df = pd.read_csv(DATA_CSV, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return df


def is_ready() -> bool:
    try:
        _load()
        return True
    except ModelNotTrained:
        return False


def _monthly_weather(hist):
    return hist.groupby(hist["date"].dt.month)[WEATHER_COLS].mean()


def future_forecast(start_date, horizon: int) -> list[dict]:
    """Predict the six targets for each day in [start_date, start_date+horizon)."""
    bundle, config = _load()
    models = bundle["models"]
    features = config["features"]
    season_map = config["season_map"]
    hist = _history()

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    last_observed = hist["date"].max().date()
    # When a user selects a date beyond the day after history, recursively bridge
    # every missing day before returning the requested window. Lag features then
    # describe the correct preceding dates rather than jumping across the gap.
    origin = last_observed + timedelta(days=1) if start_date > last_observed + timedelta(days=1) else start_date
    bridge_days = max(0, (start_date - origin).days)

    monthly = _monthly_weather(hist)
    market_dow = int(hist.loc[hist["weekly_market_day"] == 1, "day_of_week_num"].mode().iloc[0])
    maternal_days = hist.loc[hist["maternal_clinic_day"] == 1, "day_of_week_num"]
    maternal_dow = int(maternal_days.mode().iloc[0]) if not maternal_days.empty else None
    admission_rate_by_dow = (hist["expected_admissions"] / hist["total_patient_arrivals"].clip(lower=1)) \
        .groupby(hist["day_of_week_num"]).mean().to_dict()
    totals = hist["total_patient_arrivals"].astype(float).tolist()   # extended recursively

    out = []
    for i in range(bridge_days + horizon):
        d = origin + timedelta(days=i)
        wk = monthly.loc[d.month]
        dow = d.isoweekday()
        row = {
            "day_of_week_num": dow,
            "week_of_year": d.isocalendar()[1],
            "month": d.month,
            "season_enc": season_map[MONTH_SEASON[d.month]],
            "is_weekend": 1 if dow >= 6 else 0,
            "public_holiday": 0, "festival_flag": 0,
            "weekly_market_day": 1 if dow == market_dow else 0,
            "vaccination_camp_flag": 0,
            "maternal_clinic_day": 1 if maternal_dow is not None and dow == maternal_dow else 0,
            "local_event_intensity": 0,
            "rainfall_mm": float(wk["rainfall_mm"]), "temperature_max_c": float(wk["temperature_max_c"]),
            "temperature_min_c": float(wk["temperature_min_c"]), "humidity_pct": float(wk["humidity_pct"]),
            "outbreak_type_enc": 0, "outbreak_severity_0_5": 0, "surveillance_alert": 0, "affected_villages": 0,
            "patients_lag_1": totals[-1], "patients_lag_2": totals[-2],
            "patients_lag_7": totals[-7], "patients_lag_14": totals[-14],
            "rolling_mean_7": float(np.mean(totals[-7:])), "rolling_std_7": float(np.std(totals[-7:])),
            "rolling_mean_14": float(np.mean(totals[-14:])),
        }
        X = pd.DataFrame([row])[features].astype(float)
        preds = {t: max(0, round(float(models[t].predict(X)[0]))) for t in config["targets"]}
        # The admissions target is low-volume and its direct model prediction
        # can flatten after integer rounding. Calibrate its lower bound with the
        # historical admission rate for the same weekday. This remains derived
        # from the hospital dataset and lets distinct demand peaks propagate to
        # bed planning instead of disappearing at the conversion step.
        rate_based_admissions = round(preds["total_patient_arrivals"] * admission_rate_by_dow.get(dow, 0.06))
        preds["expected_admissions"] = max(preds["expected_admissions"], rate_based_admissions)
        totals.append(float(preds["total_patient_arrivals"]))
        if d >= start_date:
            out.append({"date": d.isoformat(), **preds})
    return out


def backtest_latest(n: int = 30) -> list[dict]:
    """Recent actual-vs-predicted totals from the historical test window."""
    bundle, config = _load()
    hist = _history().copy()
    hist["season_enc"] = hist["season"].map(config["season_map"])
    hist["outbreak_type_enc"] = hist["outbreak_type"].fillna("None").map(config["outbreak_map"])
    hist = hist.dropna(subset=config["features"]).tail(n)
    X = hist[config["features"]].astype(float)
    pred = bundle["models"]["total_patient_arrivals"].predict(X)
    return [{"date": d.date().isoformat(), "actual": int(a), "predicted": round(float(p), 1)}
            for d, a, p in zip(hist["date"], hist["total_patient_arrivals"], pred)]


def last_data_date() -> date:
    return _history()["date"].max().date()


CATEGORY_TARGETS = ["general_opd_arrivals", "fever_infectious_arrivals",
                    "maternal_child_arrivals", "trauma_emergency_arrivals"]
BAND_Z = 1.2816  # ~80% interval


@lru_cache(maxsize=1)
def _residual_std() -> float:
    """Std of the model's total-arrivals residuals on the 2025 test window."""
    bundle, config = _load()
    hist = _history().copy()
    hist["season_enc"] = hist["season"].map(config["season_map"])
    hist["outbreak_type_enc"] = hist["outbreak_type"].fillna("None").map(config["outbreak_map"])
    heng = hist.dropna(subset=config["features"])
    test = heng[heng["date"] > "2024-12-31"]
    if test.empty:
        test = heng.tail(200)
    pred = bundle["models"]["total_patient_arrivals"].predict(test[config["features"]].astype(float))
    return float(np.std(test["total_patient_arrivals"].to_numpy() - pred))


def total_series(start, horizon: int, context_days: int = 0) -> dict:
    """Total-patient series with per-category forecasts and an uncertainty band.

    Past dates: actual + model prediction. Future dates: forecast with an
    empirical +/- band (from backtest residuals) that widens with horizon.
    `context_days` prepends that many recent actual days before `start`.
    """
    bundle, config = _load()
    hist = _history().copy()
    hist["season_enc"] = hist["season"].map(config["season_map"])
    hist["outbreak_type_enc"] = hist["outbreak_type"].fillna("None").map(config["outbreak_map"])
    heng = hist.dropna(subset=config["features"]).copy()
    heng.index = heng["date"].dt.date
    models = bundle["models"]
    feats = config["features"]
    last = hist["date"].max().date()
    sigma = _residual_std()

    if isinstance(start, str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
    ctx = [start - timedelta(days=i) for i in range(context_days, 0, -1)]
    window = [start + timedelta(days=i) for i in range(horizon)]
    all_dates = ctx + window
    fut = [d for d in all_dates if d > last]

    rows = []
    for d in all_dates:
        if d > last:
            continue
        e = {"date": d.isoformat(), "kind": "context" if d in ctx else "window",
             "actual": None, "predicted": None, "lower": None, "upper": None, "band": None, "cat": None}
        if d in heng.index:
            X = heng.loc[[d], feats].astype(float)
            e["actual"] = int(heng.loc[d, "total_patient_arrivals"])
            e["predicted"] = round(float(models["total_patient_arrivals"].predict(X)[0]), 1)
            e["cat"] = {c: max(0, round(float(models[c].predict(X)[0]))) for c in CATEGORY_TARGETS}
        rows.append(e)

    if fut:
        for h, f in enumerate(future_forecast(fut[0], len(fut)), start=1):
            hw = round(BAND_Z * sigma * (1 + 0.10 * (h - 1)), 1)
            p = f["total_patient_arrivals"]
            lo, hi = max(0, round(p - hw)), round(p + hw)
            in_window = datetime.strptime(f["date"], "%Y-%m-%d").date() in window
            rows.append({"date": f["date"], "kind": "window" if in_window else "context",
                         "actual": None, "predicted": p, "lower": lo, "upper": hi, "band": [lo, hi],
                         "cat": {c: f[c] for c in CATEGORY_TARGETS}})

    rows.sort(key=lambda r: r["date"])
    win = [r for r in rows if r["kind"] == "window" and (r["actual"] is not None or r["predicted"] is not None)]
    vals = [(r["actual"] if r["actual"] is not None else r["predicted"]) for r in win]
    peak = max(win, key=lambda r: (r["actual"] if r["actual"] is not None else r["predicted"])) if win else None
    # Expose separated local maxima in long windows without altering any model
    # prediction. This prevents a tied weekly pattern being reduced to one date.
    peak_indices = []
    for index, value in enumerate(vals):
        before = vals[index - 1] if index else float("-inf")
        after = vals[index + 1] if index + 1 < len(vals) else float("-inf")
        if value > before and value >= after:
            peak_indices.append(index)
    separated = []
    for index in sorted(peak_indices, key=lambda idx: (-vals[idx], idx)):
        if all(abs(index - existing) >= 4 for existing in separated):
            separated.append(index)
        if len(separated) == 3:
            break
    separated.sort()
    peak_days = [{"date": win[index]["date"], "value": vals[index]} for index in separated]
    peak_dates = {item["date"] for item in peak_days}
    for row in rows:
        row["is_peak"] = row["date"] in peak_dates
    return {
        "start": start.isoformat(), "horizon": horizon, "is_future": start > last,
        "last_data_date": last.isoformat(), "band_pct": 80, "series": rows,
        "avg": round(sum(vals) / len(vals)) if vals else None,
        "peak": {"date": peak["date"], "value": peak["actual"] if peak["actual"] is not None else peak["predicted"]} if peak else None,
        "peak_days": peak_days,
        "total": round(sum(vals)) if vals else None,
    }


def patterns() -> dict:
    """Average total arrivals by day-of-week and by month (from history)."""
    import calendar
    hist = _history()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly = hist.groupby("day_of_week")["total_patient_arrivals"].mean().reindex(order)
    monthly = hist.groupby(hist["date"].dt.month)["total_patient_arrivals"].mean()
    return {
        "weekly": [{"day": d[:3], "avg": round(float(v), 1)} for d, v in weekly.items()],
        "monthly": [{"month": calendar.month_abbr[int(m)], "avg": round(float(v), 1)} for m, v in monthly.items()],
    }


def model_metrics() -> dict:
    path = ARTIFACTS / "model_metrics.json"
    if not path.exists():
        raise ModelNotTrained("Model metrics not found. Run scripts/train_forecast_model.py.")
    return json.loads(path.read_text())


def model_info() -> dict:
    """Traceability: which model, its headline metrics, and when it was trained."""
    from datetime import datetime as _dt
    _, config = _load()
    hist = _history()
    total = {x["model"]: x for x in model_metrics()["test_metrics"] if x["target"] == "total_patient_arrivals"}
    sel = total.get(config["selected_family"])
    mp = ARTIFACTS / "demand_model.joblib"
    feature_columns = config["features"]
    encoded_sources = {
        "season_enc": "season",
        "outbreak_type_enc": "outbreak_type",
    }
    return {
        "selected_model": config["selected_family"],
        "n_features": len(config["features"]),
        "n_targets": len(config["targets"]),
        "split": config["split"],
        "trained_at": _dt.fromtimestamp(mp.stat().st_mtime).isoformat() if mp.exists() else None,
        "total_r2": round(sel["R2"], 3) if sel else None,
        "total_wape_pct": round(sel["WAPE"] * 100, 1) if sel else None,
        "dataset": {
            "name": DATA_CSV.name,
            "records": int(len(hist)),
            "date_start": hist["date"].min().date().isoformat(),
            "date_end": hist["date"].max().date().isoformat(),
            "columns": hist.columns.tolist(),
            "source_feature_columns": [encoded_sources.get(column, column) for column in feature_columns],
            "feature_columns": feature_columns,
            "engineered_feature_columns": [
                {"column": column, "derived_from": source}
                for column, source in encoded_sources.items()
                if column in feature_columns
            ],
            "target_columns": config["targets"],
        },
    }
