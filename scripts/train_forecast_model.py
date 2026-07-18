"""Train, evaluate, and save the demand-forecasting model (Phase 6).

Builds calendar/seasonal/weather/outbreak/lag features using only information
available at prediction time, uses a chronological train-validation-test split
(never a random shuffle), trains naive/seasonal-naive baselines plus Random
Forest and XGBoost, evaluates R2/MAE/RMSE/WAPE on unseen dates, and saves:

    backend/artifacts/demand_model.joblib
    backend/artifacts/feature_config.json
    backend/artifacts/model_metrics.json

Usage:
    python scripts/train_forecast_model.py
"""


def main() -> None:
    raise NotImplementedError("Model training is implemented in Phase 6.")


if __name__ == "__main__":
    main()
