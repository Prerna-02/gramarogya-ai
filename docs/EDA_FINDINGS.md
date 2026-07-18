# GramArogya AI — EDA Findings (Phase 5)

Summary of the exploratory analysis in [`notebooks/eda.ipynb`](../notebooks/eda.ipynb).
Dataset: `data/demand_resource_daily.csv` (2192 days, 2020-01-01 → 2025-12-31).

**Bottom line:** the synthetic data behaves like a plausible rural hospital. It
has strong, learnable structure; every driver moves the clinically correct
demand category; and resource requirements scale with demand. The forecasting
problem is realistic and well-posed for Phase 6.

---

## 1. Demand structure

- Total arrivals: mean **138/day**, range **85-221**, std 23.
- A clear, repeating **annual peak** every year (visible in the 30-day moving
  average) — seasonality is learnable, not noise.

## 2. Seasonality — the dominant signal

| Season | fever_infectious | total |
|---|---|---|
| Winter | 24.5 | 134.3 |
| Summer | 19.4 | 133.2 |
| **Monsoon** | **46.1** | **153.1** |
| Post-Monsoon | 16.3 | 119.6 |

- **Fever/infectious cases nearly triple in monsoon (months 7-9)**, ~18 → ~60/day.
  This mirrors real vector- and water-borne disease seasonality (dengue, malaria,
  diarrhoeal) and is the main driver of the annual peak.
- General OPD is steady (~85-95); maternal-child and trauma are roughly flat.

## 3. Weekly & event effects (each moves the right category)

- **Market day**: total load 153 vs 135 on other days; `weekly_market_day`
  correlates with **general_opd** at r = 0.46 (rural travel-day visits).
- **Festival**: trauma **doubles** (9.1 → 19.6); `festival_flag` ↔ trauma r = 0.44.
- **Vaccination camp**: maternal-child 8.2 → 11.1.
- Weekdays busier than weekends (Wed ~153, Sun ~124).

## 4. Correlations — causally plausible drivers

| Driver | Strongest with | r |
|---|---|---|
| humidity_pct / rainfall_mm | fever_infectious | 0.66 / 0.49 |
| outbreak_severity_0_5 | fever_infectious / total | 0.88 / 0.83 |
| local_event_intensity | trauma_emergency | 0.52 |
| festival_flag | trauma_emergency | 0.44 |
| weekly_market_day | general_opd | 0.46 |

Every major feature has a clear, clinically sensible reason to affect its demand
category — this satisfies the Phase 5 completion check.

## 5. Outbreak impact by type (mean cases)

| Outbreak | fever_infectious | trauma | total | days |
|---|---|---|---|---|
| Dengue | 67.6 | 9.2 | 176.2 | 220 |
| Malaria | 54.7 | 9.5 | 158.6 | 142 |
| Respiratory | 41.9 | 8.9 | 164.3 | 162 |
| Diarrheal | 34.8 | 8.9 | 156.9 | 125 |
| Mass_Casualty | 14.5 | **72.2** | 186.5 | 8 |
| None | 19.4 | 9.5 | 125.8 | 1535 |

Disease outbreaks stress the **fever** channel; **Mass_Casualty** stresses
**trauma** (~8× baseline). Different scenarios stress different resources —
central to the Phase 12 emergency engine.

## 6. Distributions

- General OPD ≈ symmetric; **fever_infectious is right-skewed** with a long tail
  (the monsoon/outbreak surges). No negative or impossible values.

## 7. Resource planning follows demand (validates Phase 7 logic)

| Demand | Resource | r |
|---|---|---|
| fever_infectious | required_antipyretic_units | 1.00 |
| fever_infectious | required_diagnostic_test_kits | 0.98 |
| fever_infectious | required_isolation_beds | 0.96 |
| expected_admissions | required_general_beds | 0.97 |
| trauma_emergency | required_emergency_beds | 0.85 |
| trauma_emergency | required_ambulances | 0.75 |

Emergency risk escalates monotonically with strain: mean `resource_shortage_count`
is 0.0 (Normal) → 1.4 (Watch) → 2.4 (High) → 5.0 (Critical).

## 8. Data caveats (carry into later phases)

- **`overflow_patients` is constant 0** across all 2192 days — no signal. The
  Phase 12 overload check must be computed from required-vs-available capacity +
  thresholds, **not** this column.
- **`required_obgyn_doctors` and `required_pediatricians` are constant = 1**
  (fixed minimum staffing) — exclude where feature variance is required.
- **`required_oxygen_cylinders` is driven by Respiratory outbreaks** (mean 10.4
  vs 1.2 baseline; r = 0.59 with severity), not trauma (r = 0.04). Model the
  oxygen requirement around respiratory load.

---

## Leakage-safe feature list (locked for Phase 6)

The demand model predicts the **targets** and may use **only** these inputs.

**Features (26) — Group A predictors + lag/rolling:**

- *Calendar/time:* `day_of_week_num`, `week_of_year`, `month`, `season`,
  `is_weekend`, `public_holiday`, `festival_flag`, `weekly_market_day`,
  `vaccination_camp_flag`, `maternal_clinic_day`, `local_event_intensity`
- *Weather:* `rainfall_mm`, `temperature_max_c`, `temperature_min_c`, `humidity_pct`
- *Outbreak/surveillance:* `outbreak_type`, `outbreak_severity_0_5`,
  `surveillance_alert`, `affected_villages`
- *Lag/rolling (past demand only):* `patients_lag_1`, `patients_lag_2`,
  `patients_lag_7`, `patients_lag_14`, `rolling_mean_7`, `rolling_std_7`,
  `rolling_mean_14`

**Targets (6):** `general_opd_arrivals`, `fever_infectious_arrivals`,
`maternal_child_arrivals`, `trauma_emergency_arrivals`, `total_patient_arrivals`,
`expected_admissions`

**Excluded — never use as model inputs (34):** all `required_*`, `available_*`,
`stock_*` columns, plus `resource_shortage_count`, `overflow_patients`,
`emergency_risk_level`. These are computed *from* the forecast (Group C/D) and
would leak the target.

> Modelling note: `outbreak_type` needs categorical encoding; the first
> 1/2/7/14 rows have null lag/rolling values by construction — drop or impute at
> training time.
