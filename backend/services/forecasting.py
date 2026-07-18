"""Demand forecasting service.

Implemented in Phase 6. Loads the saved model artifact and produces 1-, 5-,
and 7-day patient forecasts by service category (general OPD, fever/infectious,
maternal-child, trauma/emergency) plus total arrivals and expected admissions.

IMPORTANT: only demand-safe predictors (calendar, season, weather, events,
outbreak signals, historical patient lags/rolling stats) are used as features.
Resource-requirement columns must never be used as predictors (target leakage).
"""
