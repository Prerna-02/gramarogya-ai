# GramArogya AI — Ethics, Fairness, Security & Audit (Phase 13)

This checklist records how the prototype stays safe, fair, transparent and
defensible, and where each control lives in the code.

> Prototype disclaimer: GramArogya AI is an academic decision-support prototype.
> It is not a certified medical device. All recommendations require review by
> authorized hospital staff before operational use.

## 1. Human oversight — AI recommends, humans decide
- Rosters are **recommendations**; the administrator approves. Overrides require a
  **reason**, recorded in the audit log (`POST /api/audit`, `override` requires a reason).
- Emergency alerts are **never auto-sent** — a human approves dispatch
  (`require_emergency_officer` + audit `alert_sent`).
- Patient-facing availability shows a *last-verified* time and "call before
  travelling" advice.

## 2. Fairness — within comparable roles only
- Night/weekend/on-call load is balanced **within a role group** (nurse vs nurse),
  never across groups. See `backend/services/scheduling_config.py::FAIRNESS_GROUPS`
  and `workforce_optimization::_fairness_report`.
- Reported metrics: **Shift Equity Index, Workload Variance, Rest Compliance**.
- **No protected attributes** (gender, caste, age, religion) are collected or used
  — `staff_master.csv` has none; the optimizer reads only qualification, skill,
  department, availability and hour limits. Enforced by test.

## 3. Privacy & data minimisation
- Only **aggregate, non-identifiable** counts are stored — no clinical patient
  records. Patients use **guest access** (no accounts, no personal data).
- Synthetic staff names only.

## 4. Patient safety
- **No diagnosis, no treatment.** The symptom triage (`/api/patient/triage`) never
  returns a remedy; red-flag symptoms escalate to **call 108** + a capable facility.
- No guaranteed bed; availability is shown with its freshness.

## 5. Security & access control
- Passwords hashed with **bcrypt**; sessions via **JWT** with expiry.
- **Role-based access:** `require_admin` for admin routes; `require_emergency_officer`
  (administrator/emergency officer only) to dispatch alerts — least privilege.
- **Secrets** (DB password, JWT secret, Groq key) live only in `.env`, which is
  gitignored and never committed.

## 6. Transparency — predictions are not guarantees
- Forecasts carry an **~80% uncertainty band** that widens with horizon, and a
  "beyond historical data" note for future dates.
- **Model info** endpoint (`/api/system/model-info`) exposes the selected model,
  R²/WAPE, feature/target counts, test window and trained date.
- Resource and roster outputs are **explainable** (each requirement shows how it
  was calculated); model choice is shown via the model-comparison chart.

## 7. Audit trail — accountability
- `audit_log` table + `backend/services/audit.py` record **who did what, when**:
  login, planning runs, roster approvals, overrides (+reason), alert dispatch.
- Viewable at `/api/audit` and on the **Fairness & Audit** page.

## 8. Fallbacks — graceful degradation
- LLM summaries fall back to **rule-based** text when the key is missing or the
  call fails.
- `/api/system/status` reports component health (model / database / LLM).
- Missing model artifacts return a clear **503** with instructions, not a crash.

## Completion check
No critical privacy, fairness, or unsafe-automation issue remains unresolved:
- ✅ Fairness measured within comparable groups; no protected attributes used.
- ✅ Human approval required for schedules and alerts; overrides logged.
- ✅ Secrets excluded from the repo; role-based access enforced.
- ✅ No diagnosis; emergencies escalated.
- ✅ Uncertainty, freshness and data-quality shown, not hidden.
