# GramArogya AI — Resource-Planning Engine (Phase 7)

`backend/services/resource_planning.py` turns a category-level demand **forecast**
into **explainable operational requirements** and compares them to current
availability to flag shortages.

> ⚠️ **Prototype ratios.** All coefficients below are illustrative defaults for
> the prototype and **must be validated by healthcare staff** before real use.
> They live in `RESOURCE_CONFIG` and are fully configurable.

## Contract

```python
plan_resources(forecast, availability=None, config=RESOURCE_CONFIG) -> dict
```

- **Input `forecast`** — the six Group-B targets only (`general_opd_arrivals`,
  `fever_infectious_arrivals`, `maternal_child_arrivals`,
  `trauma_emergency_arrivals`, `total_patient_arrivals`, `expected_admissions`).
- **Input `availability`** — current capacity/stock (defaults provided).
- **Leakage-safe:** never reads the historical `required_*` columns; it *derives*
  requirements from the forecast, so it can run on any future forecast.
- **Every output line carries an `explanation`** string (the Phase 7 completion
  check: "for any date, show how each requirement was calculated").

## Rules

### Staff — caseload ratios (1 staff per N cases)

| Role | Driver | 1 per |
|---|---|---|
| general_doctors | general_opd_arrivals | 45 |
| physicians | fever_infectious_arrivals | 40 |
| emergency_doctors | trauma_emergency_arrivals | 12 |
| lab_technicians | fever_infectious_arrivals | 30 |
| pharmacists | total_patient_arrivals | 120 |
| anm_staff | maternal_child_arrivals | 8 |

`required = ceil(driver / caseload)`.

**Specialists (minimum-coverage policy):** `obgyn_doctors` = 2 (1 duty + 1
on-call), `pediatricians` = 1, each **+1** when `maternal_child_arrivals ≥ 13`.
With only 1 OBGYN on staff, the minimum-2 policy flags a shortage on high-maternal
days — a realistic rural gap.

**Nursing:** `senior_nursing_officers` = 2 (+1 when total load > 160);
`nursing_officers` = 4 + (planned beds // 12).

### Beds — admissions split by case mix, held for length of stay

Admissions are apportioned to bed types by the day's mix (fever → isolation,
trauma → emergency, remainder → general), then multiplied by the average length
of stay:

`required_{type}_beds = ceil(expected_admissions × share_{type} × LOS_{type})`,
with LOS = general 4d, emergency 2d, isolation 5d.

Beds compare **needed concurrent occupancy against total capacity** (shortage =
overflow).

### Medicines / consumables — usage + reorder point

`required = rate × driver (+ optional extra term)`.

| Item | Driver (rate) | Extra | Safety | Lead |
|---|---|---|---|---|
| diagnostic_test_kits | fever (0.35) | — | 100 | 6 |
| antipyretics | fever (0.80) | — | 250 | 5 |
| iv_fluids | admissions (1.20) | fever (0.15) | 120 | 5 |
| ors | fever (0.20) | — | 90 | 5 |
| ppe_kits | fever (0.35) | — | 150 | 7 |

`reorder_point = required × lead_time + safety_stock`; a **reorder** is flagged
when stock ≤ reorder point (even if not yet short).

### Oxygen — respiratory-driven (not trauma)

`severe_resp ≈ fever × 0.30 (respiratory share) × 0.15 (severe share)`;
`required_oxygen_cylinders = ceil(severe_resp × 0.8) + 2 baseline`.

### Ambulances

`required = 1 standby + ceil(trauma / 15)`.

## Output & status

Each line reports `required`, `available`, `shortage`, `surplus`, `status`
(`OK` / `REORDER` / `SHORTAGE`) and its `explanation`. The summary aggregates
`shortage_count` and maps it to a status: **Normal** (0) / **Watch** (1–2) /
**High** (3–4) / **Critical** (≥5).

## Demo

```bash
python scripts/generate_demo_forecast.py 2025-09-01 7
```

Loads the Phase 6 model, forecasts a 7-day window, and prints the plan for each
day plus a fully explained breakdown for the highest-shortage day.
