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

    monthly = _monthly_weather(hist)
    market_dow = int(hist.loc[hist["weekly_market_day"] == 1, "day_of_week_num"].mode().iloc[0])
    totals = hist["total_patient_arrivals"].astype(float).tolist()   # extended recursively

    out = []
    for i in range(horizon):
        d = start_date + timedelta(days=i)
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
            "vaccination_camp_flag": 0, "maternal_clinic_day": 0, "local_event_intensity": 0,
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
        totals.append(float(preds["total_patient_arrivals"]))
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


def total_series(start, horizon: int) -> dict:
    """Total-patient series from `start` for `horizon` days.

    For dates within the historical data: returns actual + model prediction
    (the model was trained/tested, so we can show both). For future dates:
    returns the forecast (predicted only, actual = null).
    """
    bundle, config = _load()
    hist = _history().copy()
    hist["season_enc"] = hist["season"].map(config["season_map"])
    hist["outbreak_type_enc"] = hist["outbreak_type"].fillna("None").map(config["outbreak_map"])
    heng = hist.dropna(subset=config["features"]).copy()
    heng.index = heng["date"].dt.date
    model = bundle["models"]["total_patient_arrivals"]
    last = hist["date"].max().date()

    if isinstance(start, str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
    dates = [start + timedelta(days=i) for i in range(horizon)]
    out = []
    fut = [d for d in dates if d > last]
    for d in dates:
        if d <= last:
            if d in heng.index:
                X = heng.loc[[d], config["features"]].astype(float)
                out.append({"date": d.isoformat(), "actual": int(heng.loc[d, "total_patient_arrivals"]),
                            "predicted": round(float(model.predict(X)[0]), 1)})
            else:  # before the series warm-up window
                out.append({"date": d.isoformat(), "actual": None, "predicted": None})
    if fut:
        for f in future_forecast(fut[0], len(fut)):
            out.append({"date": f["date"], "actual": None, "predicted": f["total_patient_arrivals"]})
    out.sort(key=lambda r: r["date"])
    return {"start": start.isoformat(), "horizon": horizon,
            "is_future": start > last, "last_data_date": last.isoformat(), "series": out}


def model_metrics() -> dict:
    path = ARTIFACTS / "model_metrics.json"
    if not path.exists():
        raise ModelNotTrained("Model metrics not found. Run scripts/train_forecast_model.py.")
    return json.loads(path.read_text())
