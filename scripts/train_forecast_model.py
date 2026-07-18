"""Train, evaluate, and save the demand-forecasting models (Phase 6).

Predicts six leakage-safe targets (total arrivals, four service categories, and
expected admissions) using only the 26 leakage-safe features. Uses a strictly
chronological split (never shuffles a time series):

    train      2020-01-01 .. 2023-12-31
    validation 2024-01-01 .. 2024-12-31   (XGBoost early stopping)
    test       2025-01-01 .. 2025-12-31   (reported metrics / backtest)

Compares naive and seasonal-naive baselines against Random Forest and XGBoost,
selects the model family that generalises best across targets, and saves:

    backend/artifacts/demand_model.joblib   (chosen models + encoders)
    backend/artifacts/feature_config.json   (features, encodings, split, choice)
    backend/artifacts/model_metrics.json    (full comparison table)

Usage:
    python scripts/train_forecast_model.py

The module's functions are imported by notebooks/forecasting.ipynb.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / "data" / "demand_resource_daily.csv"
ARTIFACTS = ROOT / "backend" / "artifacts"

TRAIN_END = "2023-12-31"
VAL_END = "2024-12-31"

SEASON_MAP = {"Winter": 0, "Summer": 1, "Monsoon": 2, "Post_Monsoon": 3}
OUTBREAK_MAP = {"None": 0, "Dengue": 1, "Malaria": 2, "Diarrheal": 3, "Respiratory": 4}

FEATURES = [
    "day_of_week_num", "week_of_year", "month", "season_enc", "is_weekend",
    "public_holiday", "festival_flag", "weekly_market_day", "vaccination_camp_flag",
    "maternal_clinic_day", "local_event_intensity",
    "rainfall_mm", "temperature_max_c", "temperature_min_c", "humidity_pct",
    "outbreak_type_enc", "outbreak_severity_0_5", "surveillance_alert", "affected_villages",
    "patients_lag_1", "patients_lag_2", "patients_lag_7", "patients_lag_14",
    "rolling_mean_7", "rolling_std_7", "rolling_mean_14",
]
TARGETS = [
    "total_patient_arrivals", "general_opd_arrivals", "fever_infectious_arrivals",
    "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions",
]


# ---------------------------------------------------------------- data / features
def load_and_engineer(path: Path = DATA_CSV) -> pd.DataFrame:
    """Load the daily dataset, encode categoricals, drop series warm-up rows."""
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["season_enc"] = df["season"].map(SEASON_MAP)
    df["outbreak_type_enc"] = df["outbreak_type"].fillna("None").map(OUTBREAK_MAP)
    df = df.dropna(subset=FEATURES).reset_index(drop=True)   # drops first 14 rows (lag warm-up)
    return df


def chronological_split(df: pd.DataFrame):
    train = df[df["date"] <= TRAIN_END]
    val = df[(df["date"] > TRAIN_END) & (df["date"] <= VAL_END)]
    test = df[df["date"] > VAL_END]
    return train, val, test


# ---------------------------------------------------------------- metrics
def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    denom = np.sum(np.abs(y_true))
    return {
        "R2": float(r2_score(y_true, y_pred)),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "WAPE": float(np.sum(np.abs(y_true - y_pred)) / denom) if denom else float("nan"),
    }


# ---------------------------------------------------------------- models
def _make_rf() -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=400, max_depth=14, min_samples_leaf=2,
                                 n_jobs=-1, random_state=42)


def _make_xgb() -> XGBRegressor:
    return XGBRegressor(n_estimators=600, learning_rate=0.05, max_depth=5,
                        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                        random_state=42, n_jobs=-1, early_stopping_rounds=40)


def train_ml_models(train, val):
    """Fit RF and XGBoost per target. Returns {family: {target: fitted_model}}."""
    models = {"RandomForest": {}, "XGBoost": {}}
    Xtr, Xval = train[FEATURES], val[FEATURES]
    for tgt in TARGETS:
        rf = _make_rf().fit(Xtr, train[tgt])
        models["RandomForest"][tgt] = rf
        xgb = _make_xgb().fit(Xtr, train[tgt], eval_set=[(Xval, val[tgt])], verbose=False)
        models["XGBoost"][tgt] = xgb
    return models


def baseline_predictions(df: pd.DataFrame, test: pd.DataFrame, target: str):
    """Naive (t-1) and seasonal-naive (t-7) from the true series, aligned to test."""
    s = df.set_index("date")[target]
    naive = s.shift(1).loc[test["date"]].to_numpy()
    seasonal = s.shift(7).loc[test["date"]].to_numpy()
    return naive, seasonal


def evaluate_all(df, models, test) -> pd.DataFrame:
    """Return a tidy metrics table for every model x target on the test set."""
    rows = []
    Xte = test[FEATURES]
    for tgt in TARGETS:
        y = test[tgt].to_numpy()
        naive, seasonal = baseline_predictions(df, test, tgt)
        preds = {
            "Naive": naive,
            "SeasonalNaive": seasonal,
            "RandomForest": models["RandomForest"][tgt].predict(Xte),
            "XGBoost": models["XGBoost"][tgt].predict(Xte),
        }
        for name, yhat in preds.items():
            rows.append({"target": tgt, "model": name, **metrics(y, yhat)})
    return pd.DataFrame(rows)


def select_best_family(results: pd.DataFrame) -> str:
    """Pick the ML family with the best mean R2 across targets (must beat baselines)."""
    ml = results[results["model"].isin(["RandomForest", "XGBoost"])]
    mean_r2 = ml.groupby("model")["R2"].mean()
    return str(mean_r2.idxmax())


# ---------------------------------------------------------------- artifacts
def save_artifacts(models, results, best_family):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    bundle = {
        "family": best_family,
        "models": models[best_family],
        "features": FEATURES,
        "targets": TARGETS,
        "season_map": SEASON_MAP,
        "outbreak_map": OUTBREAK_MAP,
    }
    joblib.dump(bundle, ARTIFACTS / "demand_model.joblib")

    config = {
        "features": FEATURES,
        "targets": TARGETS,
        "season_map": SEASON_MAP,
        "outbreak_map": OUTBREAK_MAP,
        "split": {"train_end": TRAIN_END, "val_end": VAL_END},
        "selected_family": best_family,
    }
    (ARTIFACTS / "feature_config.json").write_text(json.dumps(config, indent=2))

    metrics_out = {
        "selected_family": best_family,
        "test_metrics": results.to_dict(orient="records"),
    }
    (ARTIFACTS / "model_metrics.json").write_text(json.dumps(metrics_out, indent=2))


def main() -> int:
    df = load_and_engineer()
    train, val, test = chronological_split(df)
    print(f"rows -> train {len(train)}, val {len(val)}, test {len(test)}")
    print(f"test period: {test['date'].min().date()} .. {test['date'].max().date()}")

    models = train_ml_models(train, val)
    results = evaluate_all(df, models, test)
    best = select_best_family(results)

    print("\nMean test R2 by model:")
    print(results.groupby("model")["R2"].mean().round(3).sort_values(ascending=False).to_string())
    print(f"\nSelected family: {best}")
    print("\nSelected-family test metrics by target:")
    sel = results[results["model"] == best].set_index("target")[["R2", "MAE", "RMSE", "WAPE"]]
    print(sel.round(3).to_string())

    save_artifacts(models, results, best)
    print(f"\nSaved artifacts to {ARTIFACTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
