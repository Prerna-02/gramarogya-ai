"""Generate the 1-7 January 2026 demonstration forecast (Phase 6).

Loads the saved model artifact and produces the operational 7-day forecast with
uncertainty ranges for the demo. The backtest (actual-vs-predicted) view uses a
chronological holdout from 2025, since January 2026 actuals do not yet exist.

Usage:
    python scripts/generate_demo_forecast.py
"""


def main() -> None:
    raise NotImplementedError("Demo forecast generation is implemented in Phase 6.")


if __name__ == "__main__":
    main()
