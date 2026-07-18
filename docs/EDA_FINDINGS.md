# GramArogya AI — EDA Findings

Summary of the analysis in [`notebooks/eda.ipynb`](../notebooks/eda.ipynb).
Dataset: `data/demand_resource_daily.csv` (2192 days, 2020-01-01 → 2025-12-31,
**140 columns** after the operational-layer rebuild).

**Bottom line:** the demand series is realistic and unchanged; the regenerated
operational layer now has genuine, explainable day-to-day variation. The
forecasting problem is well-posed for Phase 6.

---

## Part 1 — Demand (unchanged, re-verified after regeneration)

- **Total arrivals:** mean 138/day, range 85-221; a clear repeating annual peak.
- **Monsoon fever surge:** fever/infectious ~18 → ~60/day in months 7-9 (Monsoon
  season mean 46 vs Post-Monsoon 16) — the dominant seasonal signal.
- **Drivers map to the correct category:** humidity/rainfall → fever (0.66/0.49);
  outbreak severity → fever/total (0.88/0.83); events/festival → trauma
  (0.52/0.44); market day → OPD (0.46).
- **Outbreaks vs scenarios (now separated):** disease outbreaks load fever
  (Dengue ~68); `Mass_Casualty`/`Road_Accident_Surge` load trauma (~72).
- **Subcategories reconcile exactly** with their parent categories, and shift
  with context (Dengue → more `vector_borne_cases`, etc.).

*(Demand-preservation was asserted programmatically: 32 immutable demand columns
byte-identical; outbreak fields identical except the 8 Mass_Casualty relabels.)*

## Part 2 — Operational layer (regenerated)

### Beds & overflow
- Bed occupancy is **sequential** (length-of-stay carryover), drifting smoothly
  and brushing capacity on surges.
- **Overflow occurs on ~4% of days** (93 days, max 11), **~30× more often on
  outbreak/scenario days** (mean 0.32) than normal days (0.011). This fixes the
  old `overflow_patients = 0` problem.

### Specialists
- OBGYN required duty hours span **8-24**; on-call mobilised on high-maternal days.
- With only **1 OBGYN on staff**, the "minimum 2" policy flags a shortage on
  **~20% of days** — a realistic rural specialist gap. `required_obgyn_doctors`
  and `required_pediatricians` now vary (1-2) instead of being constant.

### Medicine inventory
- Stock **moves day-to-day** (`opening[t] == closing[t-1] + received[t]` holds
  for every item), sawtoothing between consumption and lead-time deliveries.
- Reorder flags toggle (61-134 reorders/item over 6 years); occasional shortages
  on the fastest-moving items (ORS, test kits, PPE).

### Oxygen
- Driven by **respiratory severity (r ≈ 0.98)**, not trauma (r ≈ 0.0) — the
  corrected clinical logic.

### Emergency risk
- Distribution ≈ **Normal 45% / Watch 36% / High 16% / Critical 3%**.
- **Critical days are almost entirely outbreak/scenario days**; `resource_shortage_count`
  and `overflow_patients` rise monotonically with the risk level. Rules are
  explainable (overflow, shortage count, outbreak/scenario severity).

## Part 3 — Data caveats resolved

The three Phase-5 caveats are now fixed:
- `overflow_patients` — was constant 0; now varies and concentrates on surges.
- `required_obgyn_doctors` / `required_pediatricians` — were constant; now vary.
- oxygen — now explicitly modelled from respiratory severity.

---

## Leakage-safe feature list (locked for Phase 6)

The demand model predicts the **6 targets** and may use **only** these **26
features**; all **106 operational columns are excluded** (asserted in the notebook).

**Features (26):** calendar/time (`day_of_week_num`, `week_of_year`, `month`,
`season`, `is_weekend`, `public_holiday`, `festival_flag`, `weekly_market_day`,
`vaccination_camp_flag`, `maternal_clinic_day`, `local_event_intensity`),
weather (`rainfall_mm`, `temperature_max_c`, `temperature_min_c`, `humidity_pct`),
outbreak/surveillance (`outbreak_type`, `outbreak_severity_0_5`,
`surveillance_alert`, `affected_villages`), lag/rolling (`patients_lag_1/2/7/14`,
`rolling_mean_7`, `rolling_std_7`, `rolling_mean_14`).

**Targets (6):** `general_opd_arrivals`, `fever_infectious_arrivals`,
`maternal_child_arrivals`, `trauma_emergency_arrivals`, `total_patient_arrivals`,
`expected_admissions`.

**Excluded (106):** all operational columns — scenarios, subcategories, beds,
inventory, specialists, oxygen, required staff/ambulance, shortages, and
`emergency_risk_level`. Computed *from* the forecast; using them would leak the
target.

> `emergency_scenario_type`/`_severity` could become forecast inputs later, but
> only using information genuinely known at forecast time.
> Modelling note: `outbreak_type` needs categorical encoding; the first
> 1/2/7/14 rows have null lag/rolling values by construction.
