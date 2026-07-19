# GramArogya AI — Workforce Optimization (Phase 8)

`backend/services/workforce_optimization.py` converts Phase 7 staffing
requirements + `staff_master.csv` into a roster of **named staff assignments**
(date · shift · department · role), optimised with **NSGA-II** (`pymoo`) and
auto-selecting one **balanced** recommended roster.

> ⚠️ Coverage ratios, shift times, and ranking weights are prototype values in
> `backend/services/scheduling_config.py` (the single config source) and must be
> validated by hospital staff.

## Inputs

1. **Forecast per date** (`forecast_by_date`) → Phase 7 `plan_resources` → daily
   role counts, expanded into per-shift/department requirements via the
   `COVERAGE_TEMPLATE`.
2. **`staff_master.csv`** — designation, department, skills, shift eligibility,
   hour/rest/consecutive/night limits, preferred shift, emergency on-call, active
   status.
3. **`availability`** (optional) — leave, unavailable shifts, locked & completed
   assignments, and work history (recent nights/weekends/hours, fatigue,
   overtime). **These fields are not in the repo**, so they default to
   "all available, no history" (documented fallback) and can be injected.

## Shift model (single source: `scheduling_config.py`)

Morning 08–16 · Evening 16–24 · Night 00–08 · On-call (standby) · Off.

## Configurable horizon

`scheduling_horizon_days` ∈ {5, 7, 14, 21}. Days 1–7 are **confirmed**; days
after Day 7 are **provisional** (regenerable). Locked/completed assignments are
immutable and never changed.

## Decision representation

One real gene in `[0, 1]` per **slot** (a slot = one unit of a requirement's
preferred count). A gene selects the GA-preferred eligible staff member; decode
fills each slot with the **first feasible** candidate (GA pick first, then the
rest of the eligible pool), else leaves it **unfilled**. This makes every decoded
roster **feasible by construction** — no hard-constraint violations — and pushes
genuine gaps into the understaffing objective and the shortage report.

## Hard constraints (enforced in decode)

Active status, shift eligibility, approved leave / unavailable shifts, one shift
per staff per day (no overlap), max weekly hours, minimum rest between shifts,
max consecutive working days, night-shift eligibility + monthly cap, and
designation/skill eligibility (specialists have **no substitute**). Locked and
completed assignments are pre-placed and occupy the staff. **Staff are never
fabricated.**

**Specialists:** OBGYN requires an active-duty slot **plus** an on-call backup
(escalates with maternal/obstetric demand); with only 1 OBGYN on staff the backup
appears as a reported shortage. Pediatric coverage scales with maternal demand.

## NSGA-II objectives (all minimised)

`understaffing` (service coverage) · `unfairness` (night+weekend+on-call spread
**within comparable designation groups**) · `fatigue` · `overtime` ·
`preference_violation` (non-preferred shifts + unnecessary department changes).

## Balanced selection (no 3-option choice for the admin)

After optimisation, feasible Pareto solutions are normalised and ranked by
configurable weights — **coverage 35% · fairness 25% · fatigue 20% · overtime
10% · preference 10%** — and the best becomes the **AI Recommended Roster —
Balanced Plan**. Weights apply only *after* hard constraints; they never trade a
hard constraint. Up to two distinct alternatives are returned when they exist:
**Minimum Overtime Plan** and **Emergency Readiness Plan**.

## Shortage handling

If minimum coverage cannot be met, the service returns the best safe partial
roster and an explicit `unmet_staffing_requirements` list (date, shift,
department, designation, required, assigned, shortfall) with a recommended action
(activate on-call, locum, referral, or administrator intervention).

## Output schema

`roster_run_id`, `planning_run_id`, `start_date`, `scheduling_horizon_days`,
`recommended_roster`, `recommended_roster_scores`, `recommendation_reason`,
`alternative_rosters`, `unmet_staffing_requirements`, `hard_constraint_violations`,
`soft_constraint_warnings`, `fairness_metrics`, `fatigue_metrics`,
`overtime_metrics`, `preference_satisfaction`, `optimization_metadata`
(seed, population, generations, execution time, feasible solutions, objectives).

Each assignment: `staff_id`, `staff_name`, `date`, `shift`, `department`,
`assigned_role`, `assignment_status`, `confirmed_or_provisional`,
`manually_overridden`, `override_reason`.

## Manual overrides

`validate_override(roster, change, staff_records, availability)` rechecks
eligibility, designation/skill, hours, rest, night cap, and double-booking;
returns warnings, requires an `override_reason` when warnings exist, and produces
an audit-log entry. The override UI is a later phase.

## Run

```python
import pandas as pd
from backend.services.workforce_optimization import generate_roster
staff = pd.read_csv("data/staff_master.csv")
forecast_by_date = {"2026-01-05": {... six targets ...}, ...}
result = generate_roster(forecast_by_date, staff, "2026-01-05", 7)
```

Tests: `pytest tests/test_workforce_optimization.py` (24 tests).
