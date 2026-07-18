"""Feature-engineering and forecasting tests (Phase 6 / Phase 14)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import train_forecast_model as tfm  # noqa: E402

# Columns the demand model must never see (they are computed from the forecast).
LEAKY_PREFIXES = ("required_", "available_", "total_", "occupied_", "projected_",
                  "overflow_", "out_of_service_", "opening_stock_", "closing_stock_",
                  "received_", "used_", "expired_")


def test_features_are_leakage_safe():
    # No feature is a target, and none is an operational/leaky column.
    assert not (set(tfm.FEATURES) & set(tfm.TARGETS))
    for f in tfm.FEATURES:
        assert not f.startswith(LEAKY_PREFIXES), f
        assert not f.endswith(("_shortage_units", "_shortage_flag", "_reorder_flag"))
    assert len(tfm.FEATURES) == 26 and len(tfm.TARGETS) == 6


def test_metrics_perfect_prediction():
    y = np.array([10.0, 20.0, 30.0, 40.0])
    m = tfm.metrics(y, y.copy())
    assert m["R2"] == 1.0
    assert m["MAE"] == 0.0
    assert m["RMSE"] == 0.0
    assert m["WAPE"] == 0.0


def test_metrics_known_values():
    y = np.array([100.0, 100.0])
    yhat = np.array([110.0, 90.0])
    m = tfm.metrics(y, yhat)
    assert abs(m["MAE"] - 10.0) < 1e-9
    assert abs(m["WAPE"] - 0.1) < 1e-9  # 20 abs error / 200 total
