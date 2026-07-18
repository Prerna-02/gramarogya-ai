# GramArogya AI — Data Dictionary

This document describes every column in the project's datasets. It is the
authoritative reference for feature engineering, resource-planning formulas,
and the NSGA-II workforce optimizer.

## Files

| File | Grain | Rows | Cols | Produced by |
|---|---|---|---|---|
| `data/demand_forecasting_historical.csv` | one row per day | 2192 | 34 | source (synthetic) |
| `data/resource_allocation_historical.csv` | one row per day | 2192 | 43 | source (synthetic) |
| **`data/demand_resource_daily.csv`** | one row per day | 2192 | **68** | `scripts/merge_datasets.py` |
| `data/staff_master.csv` | one row per staff member | 49 | 18 | source (synthetic) |

- **Period:** 2020-01-01 → 2025-12-31 (continuous daily, no gaps, no duplicates).
- **Facility:** single rural hospital (Gadchiroli case study). A `facility_id`
  key will be introduced when the dataset is extended to multiple hospitals.
- `demand_resource_daily.csv` is the **merge** of the two daily source files on
  `date`. Nine columns present in both files are identical and are kept once
  (sourced from the demand file): `date`, `outbreak_type`,
  `outbreak_severity_0_5`, `general_opd_arrivals`, `fever_infectious_arrivals`,
  `maternal_child_arrivals`, `trauma_emergency_arrivals`, `expected_admissions`,
  `total_patient_arrivals`.

---

## ⚠️ Target-leakage rule (read before modelling)

The demand-forecasting model may use **only the Forecast Predictor columns**
(Group A below) plus the lag/rolling features (Group A5). It must **never** use:

- **Group B — Patient Targets** (these are what the model *predicts*), or
- **Group C — Current Resource State**, or
- **Group D — Resource-Planning Outputs**.

Resource requirements are *derived from* the forecast (Phase 7), so feeding them
back as predictors would leak the answer. Resource planning consumes the
forecast output; the two are **sequential, not one model**.

---

## `demand_resource_daily.csv` — column reference

### Group A — Forecast Predictors (leakage-safe model inputs)

**A1. Calendar / time**

| Column | Type | Description |
|---|---|---|
| `date` | date (YYYY-MM-DD) | Calendar day. Primary key. |
| `day_of_week` | categorical | Monday … Sunday. |
| `day_of_week_num` | int | Day index (1–7). |
| `week_of_year` | int | ISO-style week number (1–53). |
| `month` | int | Month (1–12). |
| `season` | categorical | `Winter`, `Summer`, `Monsoon`, `Post_Monsoon`. |
| `is_weekend` | binary | 1 if Saturday/Sunday, else 0. |
| `public_holiday` | binary | 1 on a public holiday. |
| `festival_flag` | binary | 1 on a local/regional festival day. |
| `weekly_market_day` | binary | 1 on the weekly market day. |
| `vaccination_camp_flag` | binary | 1 when a vaccination camp is scheduled. |
| `maternal_clinic_day` | binary | 1 on a maternal-clinic day. |
| `local_event_intensity` | int (0–4) | Scale of local events/gatherings that day. |

**A2. Weather**

| Column | Type | Description |
|---|---|---|
| `rainfall_mm` | float | Daily rainfall in millimetres. |
| `temperature_max_c` | float | Daily maximum temperature (°C). |
| `temperature_min_c` | float | Daily minimum temperature (°C). |
| `humidity_pct` | float | Mean relative humidity (%). |

**A3. Outbreak / surveillance signals**

| Column | Type | Description |
|---|---|---|
| `outbreak_type` | categorical / null | Active outbreak: `Dengue`, `Malaria`, `Diarrheal`, `Respiratory`, `Mass_Casualty`. **Null/blank = no outbreak.** |
| `outbreak_severity_0_5` | int (0–5) | Outbreak severity; 0 when there is no outbreak. |
| `surveillance_alert` | binary | 1 when a public-health surveillance alert is active. |
| `affected_villages` | int | Number of villages affected by the current outbreak. |

*Modelling note:* in this prototype the outbreak signals are treated as
exogenous inputs available at prediction time. With real data, outbreak
foresight is limited — revisit this assumption before production use.

**A5. Lag & rolling features** (derived from **past** `total_patient_arrivals`; leakage-safe)

| Column | Type | Description |
|---|---|---|
| `patients_lag_1` | float | Total arrivals 1 day earlier. |
| `patients_lag_2` | float | Total arrivals 2 days earlier. |
| `patients_lag_7` | float | Total arrivals 7 days earlier. |
| `patients_lag_14` | float | Total arrivals 14 days earlier. |
| `rolling_mean_7` | float | Mean total arrivals over the previous 7 days. |
| `rolling_std_7` | float | Std dev of total arrivals over the previous 7 days. |
| `rolling_mean_14` | float | Mean total arrivals over the previous 14 days. |

*The first rows of the series have null lag/rolling values by definition
(1, 2, 7, and 14 nulls respectively). This is expected, not a data error.*

### Group B — Patient Targets (what the demand model predicts)

| Column | Type | Description |
|---|---|---|
| `general_opd_arrivals` | int | General OPD patient arrivals. |
| `fever_infectious_arrivals` | int | Fever / infectious-disease arrivals. |
| `maternal_child_arrivals` | int | Maternal & child-health arrivals. |
| `trauma_emergency_arrivals` | int | Trauma / emergency arrivals. |
| `total_patient_arrivals` | int | Total arrivals = **sum of the four categories** (holds on every row). |
| `expected_admissions` | int | Patients expected to be admitted (inpatient). |

### Group C — Current Resource State (capacity & stock on that day)

| Column | Type | Description |
|---|---|---|
| `available_general_beds` | int | General beds available. |
| `available_emergency_beds` | int | Emergency beds available. |
| `available_isolation_beds` | int | Isolation beds available. |
| `available_oxygen_cylinders` | int | Oxygen cylinders available. |
| `available_ambulances` | int | Ambulances available. |
| `stock_iv_fluid_units` | int | IV-fluid units in stock. |
| `stock_ors_units` | int | ORS units in stock. |
| `stock_diagnostic_test_kits` | int | Diagnostic test kits in stock. |
| `stock_antipyretic_units` | int | Antipyretic (fever-medicine) units in stock. |
| `stock_ppe_kits` | int | PPE kits in stock. |

### Group D — Resource-Planning Outputs (computed requirements & risk)

These are **outputs** of resource planning (Phase 7), not model inputs. In the
production system they are recomputed from the forecast and stored in
PostgreSQL; they appear in the historical CSV for reference/backtesting.

**D1. Required staff by designation**

`required_general_doctors`, `required_physicians`, `required_emergency_doctors`,
`required_pediatricians`, `required_obgyn_doctors`,
`required_senior_nursing_officers`, `required_nursing_officers`,
`required_anm_staff`, `required_lab_technicians`, `required_pharmacists`,
`required_ambulance_crew` — all `int`, count of staff required that day.

**D2. Required beds** — `required_general_beds`, `required_emergency_beds`,
`required_isolation_beds` (`int`).

**D3. Required medicines / consumables / equipment** —
`required_iv_fluid_units`, `required_ors_units`, `required_diagnostic_test_kits`,
`required_antipyretic_units`, `required_ppe_kits`, `required_oxygen_cylinders`,
`required_ambulances` (`int`).

**D4. Derived indicators**

| Column | Type | Description |
|---|---|---|
| `resource_shortage_count` | int | Number of resource types short that day (required > available). |
| `overflow_patients` | int | Patients beyond safe capacity. |
| `emergency_risk_level` | categorical | `Normal`, `Watch`, `High`, `Critical`. |

---

## `staff_master.csv` — column reference

Consumed by the NSGA-II workforce optimizer (Phase 8).

| Column | Type | Description |
|---|---|---|
| `staff_id` | str | Unique key (e.g. `DOC_001`). 49 unique. |
| `staff_name` | str | Synthetic name. |
| `staff_category` | categorical | `Doctor`, `Nurse`, `Allied Health`, `Support`, `Emergency Transport`. |
| `designation` | categorical | Role within the category (see list below). |
| `department` | categorical | Assigned department (see list below). |
| `qualification` | str | Qualifications (e.g. `MBBS, MD`, `B.Sc Nursing`). |
| `experience_years` | int | Years of experience (observed 3–18). |
| `skill_tags` | str (pipe-delimited) | Skills, `|`-separated (e.g. `Triage|Basic emergency care`). |
| `shift_eligibility` | str (pipe-delimited) | Eligible shifts from `{Morning, Evening, Night, On-call}`. |
| `max_weekly_hours` | int | Maximum weekly working hours (observed 42–48). |
| `max_consecutive_working_days` | int | Max consecutive working days. |
| `minimum_rest_hours` | int | Minimum rest between shifts (hours). |
| `max_night_shifts_per_month` | int | Cap on night shifts per month (observed 2–8). |
| `preferred_shift` | categorical | `Morning`, `Evening`, or `Night` (must be within `shift_eligibility`). |
| `emergency_on_call` | binary | 1 if eligible for emergency on-call. |
| `employment_type` | categorical | `Permanent` or `Contractual`. |
| `weekly_off_preference` | categorical | `Saturday`, `Sunday`, `Monday`, or `No preference`. |
| `active_status` | categorical | `Active` (inactive staff would be excluded from rostering). |

**Constraint columns for NSGA-II hard constraints:** `shift_eligibility`,
`max_weekly_hours`, `max_consecutive_working_days`, `minimum_rest_hours`,
`max_night_shifts_per_month`, `active_status`, and qualification/designation/
department capability. `preferred_shift` and `weekly_off_preference` feed the
soft (fairness/preference) objectives.

### Designations by category

- **Doctor:** Medical Superintendent, General Medical Officer, Emergency Medical
  Officer, Physician, Pediatrician, Obstetrician and Gynecologist, Anesthetist,
  Public Health Medical Officer.
- **Nurse:** Nursing Superintendent, Assistant Nursing Superintendent, Senior
  Nursing Officer, Nursing Officer, Auxiliary Nurse Midwife.
- **Allied Health:** Pharmacist, Laboratory Technician, Radiographer, Operation
  Theatre Technician, Counsellor.
- **Support:** Ward Attendant.
- **Emergency Transport:** Emergency Medical Technician and Driver.

### Departments

Administration, General OPD, Emergency, Medicine, Maternal and Child Health,
Operation Theatre, Public Health, Nursing Administration, Inpatient Ward,
Pharmacy, Laboratory, Radiology, Counselling, Ambulance.

---

## Missing-value conventions

| Situation | Representation | Treated as |
|---|---|---|
| No outbreak on a day | `outbreak_type` blank/null (severity 0) | valid "no outbreak" |
| Series warm-up | first N `*_lag_*` / `rolling_*` values null | expected; drop or impute at training |
| Anything else null | — | data error (flagged CRITICAL by `validate_data.py`) |

## Validation

Run `python scripts/validate_data.py` to check duplicates, date gaps, negative
values, category-total reconciliation, categorical domains, and staff-record
integrity. It exits non-zero on any CRITICAL issue. As of the last run: **0
critical, 0 warnings** across all files.
