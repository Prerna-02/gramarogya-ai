# GramArogya AI — Data Dictionary

Authoritative reference for every column in the project's datasets. Used by
feature engineering, resource-planning formulas, and the NSGA-II optimizer.

## Files

| File | Grain | Rows | Cols | Produced by |
|---|---|---|---|---|
| `data/demand_forecasting_historical.csv` | one row per day | 2192 | 34 | source (synthetic) — **pristine demand base** |
| `data/resource_allocation_historical.csv` | one row per day | 2192 | 43 | source (synthetic, superseded) |
| **`data/demand_resource_daily.csv`** | one row per day | 2192 | **140** | `scripts/generate_synthetic_data.py` |
| `data/demand_resource_daily_before_phase6.csv` | one row per day | 2192 | 68 | backup of the pre-regeneration file |
| `data/staff_master.csv` | one row per staff member | 49 | 18 | source (synthetic) |

- **Period:** 2020-01-01 → 2025-12-31 (continuous daily, no gaps/duplicates).
- **Facility:** single rural hospital (Gadchiroli). A `facility_id` key will be
  added when scaling to multiple hospitals.

## How the current dataset was built (preserve demand, rebuild ops)

`demand_resource_daily.csv` is produced by `scripts/generate_synthetic_data.py`
(fixed seed = 42, reproducible). It reads the **pristine demand columns** from
`demand_forecasting_historical.csv` **unchanged**, and regenerates only the
**operational/resource layer** with explainable rules and sequential (day-to-day)
simulation.

**The one intentional change to a demand-side field:** `Mass_Casualty` is a
*scenario*, not a disease, so it is moved out of `outbreak_type` (8 days →
blank, severity 0) into the new `emergency_scenario_type` field. All other
demand columns are byte-identical before/after (asserted by the generator).

---

## ⚠️ Target-leakage rule (read before modelling)

The demand model uses **only the 26 leakage-safe features** (Group A). It must
**never** use any operational column — those are computed *from* the forecast.

**Excluded from demand-model inputs (all operational columns):**
`emergency_scenario_type`, `emergency_scenario_severity_0_5`, all `required_*`,
`available_*`, `total_*`, `occupied_*`, `projected_*`, `overflow_*`,
`out_of_service_*`, `expected_*_discharges`, all `opening_stock_*`,
`closing_stock_*`, `received_*`, `used_*`, `expired_*`, `*_shortage_units`,
`*_shortage_flag`, `*_reorder_flag`, the clinical subcategory columns,
`resource_shortage_count`, and `emergency_risk_level`.

> Emergency-scenario fields *could* become forecast inputs later, but only using
> information genuinely known at forecast time (see `docs/EDA_FINDINGS.md`).

---

## Group A — Forecast Predictors (26 leakage-safe model inputs)

**Calendar/time:** `date`, `day_of_week`, `day_of_week_num`, `week_of_year`,
`month`, `season` (`Winter`/`Summer`/`Monsoon`/`Post_Monsoon`), `is_weekend`,
`public_holiday`, `festival_flag`, `weekly_market_day`, `vaccination_camp_flag`,
`maternal_clinic_day`, `local_event_intensity` (0–4). Binary flags are 0/1.

**Weather:** `rainfall_mm`, `temperature_max_c`, `temperature_min_c`, `humidity_pct` (float).

**Outbreak/surveillance:**
| Column | Type | Description |
|---|---|---|
| `outbreak_type` | categorical / null | `Dengue`, `Malaria`, `Diarrheal`, `Respiratory`. **Blank/null = no outbreak.** (No longer contains `Mass_Casualty`.) |
| `outbreak_severity_0_5` | int (0–5) | Outbreak severity; 0 when no outbreak. |
| `surveillance_alert` | binary | Public-health alert active. |
| `affected_villages` | int | Villages affected by the outbreak. |

**Lag/rolling** (past `total_patient_arrivals` only): `patients_lag_1`,
`patients_lag_2`, `patients_lag_7`, `patients_lag_14`, `rolling_mean_7`,
`rolling_std_7`, `rolling_mean_14` (float; first 1/2/7/14 rows null by design).

## Group B — Patient Targets (what the demand model predicts)

`general_opd_arrivals`, `fever_infectious_arrivals`, `maternal_child_arrivals`,
`trauma_emergency_arrivals`, `total_patient_arrivals` (= sum of the four
categories), `expected_admissions` (all int).

### Clinical subcategories (derived from targets — planning only, not new demand)

Generated to **sum exactly to their parent** so total demand is unchanged.

| Parent | Subcategories (sum to parent) | Extra |
|---|---|---|
| `fever_infectious_arrivals` | `vector_borne_cases`, `respiratory_cases`, `gastrointestinal_cases`, `other_fever_cases` | `severe_respiratory_cases` (⊆ respiratory) |
| `maternal_child_arrivals` | `pediatric_cases`, `antenatal_cases`, `obstetric_emergency_cases`, `immunization_visits` | — |

Split weights follow the day's outbreak/season/event context (e.g. Dengue →
more `vector_borne_cases`; `vaccination_camp_flag` → more `immunization_visits`).

---

## Operational layer (regenerated; **excluded** from demand-model inputs)

### Emergency scenarios (distinct from disease outbreaks)

| Column | Type | Description |
|---|---|---|
| `emergency_scenario_type` | categorical / null | `Mass_Casualty`, `Road_Accident_Surge`, `Flood_Disruption`, `Snakebite_Cluster`. **Blank/null = no scenario.** Labelled from existing demand (high trauma / extreme rainfall); does not create new demand. |
| `emergency_scenario_severity_0_5` | int (0–5) | Scenario severity; 0 when no scenario. |

### Beds (sequential occupancy: today depends on yesterday)

Three bed types — **general, emergency, isolation** — each with this 8-column
block (`{t}` = bed type):

| Column pattern | Description |
|---|---|
| `total_{t}_beds` | Physical capacity (fixed per type). |
| `occupied_{t}_beds` | Beds actually occupied (≤ usable). |
| `expected_{t}_discharges` | Discharges that day (drives carryover). |
| `out_of_service_{t}_beds` | Beds down for maintenance. |
| `available_{t}_beds` | usable − occupied (usable = total − out_of_service). |
| `projected_{t}_occupancy` | Bed *demand* = prev occupancy + admissions − discharges. |
| `overflow_{t}_patients` | max(0, projected − usable). |
| `required_{t}_beds` | Beds needed (= projected occupancy). |

Plus `overflow_patients` = sum of the three overflow columns. Overflow is rare
(~4% of days) and concentrated on outbreak/scenario surges.

### Medicine inventory (sequential: `closing[t]` → `opening[t+1]`)

Five items — **iv_fluids, ors, diagnostic_test_kits, antipyretics, ppe_kits** —
each with this 8-column block (`{item}`):

| Column pattern | Description |
|---|---|
| `opening_stock_{item}` | Stock at start of day (= previous closing + received). |
| `received_{item}` | Units delivered (arrive `lead_time` days after a reorder). |
| `used_{item}` | Units consumed (demand-driven; capped by stock on hand). |
| `expired_{item}` | Units lost to expiry/wastage. |
| `closing_stock_{item}` | opening + received − used − expired. |
| `required_{item}` | Demand-driven requirement for the day. |
| `{item}_shortage_units` | max(0, required − stock available). |
| `{item}_reorder_flag` | 1 when closing ≤ reorder point (avg usage × lead time + safety stock). |

### Specialist coverage

| Column | Type | Description |
|---|---|---|
| `minimum_obgyn_coverage` | int | Policy minimum (= 2: 1 duty + 1 on-call). |
| `required_obgyn_duty_hours` | int | 8–24; rises with maternal/obstetric-emergency load. |
| `obgyn_on_call_required` | binary | On-call OBGYN mobilised. |
| `obgyn_shortage_flag` | binary | 1 when active OBGYN needed (2) exceeds the 1 on staff. |
| `minimum_pediatrician_coverage` | int | Policy minimum (= 1). |
| `required_pediatrician_duty_hours` | int | Rises with pediatric load. |
| `pediatrician_on_call_required` | binary | On-call pediatrician mobilised. |
| `pediatrician_shortage_flag` | binary | 1 when 2 pediatricians needed vs 1 on staff. |

### Oxygen (driven mainly by respiratory severity)

`oxygen_support_cases` (from severe/total respiratory + a little trauma),
`required_oxygen_cylinders`, `available_oxygen_cylinders`,
`oxygen_shortage_units`, `oxygen_shortage_flag`. Corr with respiratory severity
≈ 0.98; with trauma ≈ 0.0.

### Required staff & ambulance

`required_general_doctors`, `required_physicians`, `required_emergency_doctors`,
`required_pediatricians`, `required_obgyn_doctors`,
`required_senior_nursing_officers`, `required_nursing_officers`,
`required_anm_staff`, `required_lab_technicians`, `required_pharmacists`,
`required_ambulance_crew` — all int, recomputed from demand/occupancy via
explainable thresholds. `required_obgyn_doctors` and `required_pediatricians`
now **vary** (1–2) instead of being constant.

Ambulance: `required_ambulances`, `available_ambulances`,
`ambulance_shortage_units`, `ambulance_shortage_flag`.

### Aggregate indicators

| Column | Type | Description |
|---|---|---|
| `resource_shortage_count` | int | Count of active shortages (bed overflow per type, each medicine shortage, oxygen, OBGYN, pediatric, ambulance). |
| `emergency_risk_level` | categorical | `Normal` / `Watch` / `High` / `Critical`, from explainable rules combining overflow, shortage count, and outbreak/scenario severity. Distribution ≈ 45/36/16/3%. |

---

## `staff_master.csv` — column reference

Consumed by the NSGA-II workforce optimizer (Phase 8).

| Column | Type | Description |
|---|---|---|
| `staff_id` | str | Unique key (e.g. `DOC_001`). 49 unique. |
| `staff_name` | str | Synthetic name. |
| `staff_category` | categorical | `Doctor`, `Nurse`, `Allied Health`, `Support`, `Emergency Transport`. |
| `designation` | categorical | Role within category (see list below). |
| `department` | categorical | Assigned department. |
| `qualification` | str | e.g. `MBBS, MD`, `B.Sc Nursing`. |
| `experience_years` | int | 3–18. |
| `skill_tags` | str (pipe-delimited) | e.g. `Triage|Basic emergency care`. |
| `shift_eligibility` | str (pipe-delimited) | Subset of `{Morning, Evening, Night, On-call}`. |
| `max_weekly_hours` | int | 42–48. |
| `max_consecutive_working_days` | int | Max consecutive working days. |
| `minimum_rest_hours` | int | Minimum rest between shifts. |
| `max_night_shifts_per_month` | int | Night-shift cap (2–8). |
| `preferred_shift` | categorical | `Morning`/`Evening`/`Night` (within eligibility). |
| `emergency_on_call` | binary | Eligible for emergency on-call. |
| `employment_type` | categorical | `Permanent` or `Contractual`. |
| `weekly_off_preference` | categorical | `Saturday`/`Sunday`/`Monday`/`No preference`. |
| `active_status` | categorical | `Active`. |

**Specialist availability (from this file):** 1 OBGYN, 1 Pediatrician, 2
Emergency Medical Officers — which is why the OBGYN "minimum 2" policy flags a
shortage on high-maternal days.

### Designations by category

- **Doctor:** Medical Superintendent, General Medical Officer, Emergency Medical
  Officer, Physician, Pediatrician, Obstetrician and Gynecologist, Anesthetist,
  Public Health Medical Officer.
- **Nurse:** Nursing Superintendent, Assistant Nursing Superintendent, Senior
  Nursing Officer, Nursing Officer, Auxiliary Nurse Midwife.
- **Allied Health:** Pharmacist, Laboratory Technician, Radiographer, Operation
  Theatre Technician, Counsellor.
- **Support:** Ward Attendant. **Emergency Transport:** Emergency Medical
  Technician and Driver.

### Departments

Administration, General OPD, Emergency, Medicine, Maternal and Child Health,
Operation Theatre, Public Health, Nursing Administration, Inpatient Ward,
Pharmacy, Laboratory, Radiology, Counselling, Ambulance.

---

## Missing-value conventions

| Situation | Representation | Treated as |
|---|---|---|
| No outbreak on a day | `outbreak_type` blank/null (severity 0) | valid "no outbreak" |
| No emergency scenario | `emergency_scenario_type` blank/null (severity 0) | valid "no scenario" |
| Series warm-up | first N `*_lag_*` / `rolling_*` values null | expected; drop/impute at training |
| Anything else null | — | data error (flagged CRITICAL by `validate_data.py`) |

## Reproduce / validate

```bash
python scripts/generate_synthetic_data.py   # rebuild ops layer (seed=42)
python scripts/validate_data.py             # structural/classification/variation/sequential/logical checks
```

`validate_data.py` exits non-zero on any CRITICAL issue. Last run: **0 critical,
0 warnings**.
