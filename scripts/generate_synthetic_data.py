"""Regenerate the operational/resource layer of the daily dataset (post-Phase 5).

Approach: **preserve demand, rebuild ops layer.** The demand columns (targets,
dates, weather, calendar/event, outbreak, lag/rolling) are read unchanged from
the pristine demand file and are NEVER modified. Everything downstream of demand
(clinical subcategories, bed occupancy, medicine inventory, specialist coverage,
oxygen, shortages, emergency scenarios, risk levels) is regenerated with
explainable rules and a fixed random seed.

The one intentional correction to a demand-side field is mandated by the fix
spec: `Mass_Casualty` is a *scenario*, not a disease, so it is moved out of
`outbreak_type` into the new `emergency_scenario_type` field (on 8 days).

Usage:
    python scripts/generate_synthetic_data.py

Outputs:
    data/demand_resource_daily_before_phase6.csv   (backup of the old file)
    data/demand_resource_daily.csv                 (corrected file)
"""
from __future__ import annotations

import sys
from pathlib import Path

import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)

DATA = Path(__file__).resolve().parent.parent / "data"
DEMAND_CSV = DATA / "demand_forecasting_historical.csv"
DAILY_CSV = DATA / "demand_resource_daily.csv"
BACKUP_CSV = DATA / "demand_resource_daily_before_phase6.csv"

SEED = 42

# ---- Locked demand columns (must be byte-identical before/after) ------------
DEMAND_COLS = [
    "date", "day_of_week", "day_of_week_num", "week_of_year", "month", "season",
    "is_weekend", "public_holiday", "festival_flag", "weekly_market_day",
    "vaccination_camp_flag", "maternal_clinic_day", "local_event_intensity",
    "rainfall_mm", "temperature_max_c", "temperature_min_c", "humidity_pct",
    "outbreak_type", "outbreak_severity_0_5", "surveillance_alert",
    "affected_villages", "general_opd_arrivals", "fever_infectious_arrivals",
    "maternal_child_arrivals", "trauma_emergency_arrivals", "expected_admissions",
    "total_patient_arrivals", "patients_lag_1", "patients_lag_2", "patients_lag_7",
    "rolling_mean_7", "rolling_std_7", "patients_lag_14", "rolling_mean_14",
]
# outbreak_type/severity are demand-side but change ONLY on Mass_Casualty rows.
IMMUTABLE_DEMAND = [c for c in DEMAND_COLS if c not in ("outbreak_type", "outbreak_severity_0_5")]

# ---- Staffing available (from staff_master: 1 OBGYN, 1 Pediatrician) ---------
N_OBGYN_AVAILABLE = 1
N_PEDIATRICIAN_AVAILABLE = 1

# ---- Bed system: length of stay (days) and initial occupancy -----------------
LOS = {"general": 4.0, "emergency": 2.0, "isolation": 5.0}
BED_CAPACITY_PERCENTILE = 93  # total beds set near this pct of simulated occupancy

# ---- Medicine inventory params: (init, order_qty, safety_stock, lead_time, expiry_rate)
MED_PARAMS = {
    "iv_fluids":            dict(init=400, order_qty=300, safety=120, lead=5, expiry=0.002),
    "ors":                  dict(init=300, order_qty=250, safety=90,  lead=5, expiry=0.002),
    "diagnostic_test_kits": dict(init=350, order_qty=280, safety=100, lead=6, expiry=0.001),
    "antipyretics":         dict(init=900, order_qty=700, safety=250, lead=5, expiry=0.002),
    "ppe_kits":             dict(init=500, order_qty=400, safety=150, lead=7, expiry=0.001),
}


def load_demand() -> pd.DataFrame:
    """Read the pristine demand base; fall back to locked cols from the daily file."""
    if DEMAND_CSV.exists():
        df = pd.read_csv(DEMAND_CSV)
        src = DEMAND_CSV.name
    elif DAILY_CSV.exists():
        df = pd.read_csv(DAILY_CSV)[DEMAND_COLS].copy()
        src = DAILY_CSV.name
    else:
        raise FileNotFoundError("No demand source CSV found in data/.")
    df = df.sort_values("date").reset_index(drop=True)
    print(f"Loaded demand base from {src}: {df.shape}")
    return df


def multinomial_split(totals: np.ndarray, probs: np.ndarray, rng) -> np.ndarray:
    """Split each integer total into K parts by per-row probabilities (exact sum)."""
    out = np.zeros((len(totals), probs.shape[1]), dtype=int)
    for i, tot in enumerate(totals):
        if tot > 0:
            p = probs[i] / probs[i].sum()
            out[i] = rng.multinomial(int(tot), p)
    return out


def generate(df: pd.DataFrame, rng) -> pd.DataFrame:
    N = len(df)
    ot = df["outbreak_type"].fillna("None").to_numpy()
    season = df["season"].to_numpy()
    fever = df["fever_infectious_arrivals"].to_numpy()
    mch = df["maternal_child_arrivals"].to_numpy()
    trauma = df["trauma_emergency_arrivals"].to_numpy()
    opd = df["general_opd_arrivals"].to_numpy()
    adm = df["expected_admissions"].to_numpy()
    sev = df["outbreak_severity_0_5"].to_numpy()
    rain = df["rainfall_mm"].to_numpy()
    festival = df["festival_flag"].to_numpy()
    event = df["local_event_intensity"].to_numpy()
    vax = df["vaccination_camp_flag"].to_numpy()
    mclinic = df["maternal_clinic_day"].to_numpy()

    out = df.copy()

    # =====================================================================
    # 1. EMERGENCY SCENARIO CLASSIFICATION (separate from disease outbreak)
    # =====================================================================
    scenario = np.array(["None"] * N, dtype=object)
    scen_sev = np.zeros(N, dtype=int)

    mass = ot == "Mass_Casualty"
    scenario[mass] = "Mass_Casualty"
    scen_sev[mass] = sev[mass]                       # carry the original severity
    # Remove Mass_Casualty from the demand-side outbreak fields (the one relabel).
    new_ot = df["outbreak_type"].copy()
    new_ot[mass] = np.nan                            # -> "no outbreak"
    new_sev = sev.copy()
    new_sev[mass] = 0

    t95, t85 = np.quantile(trauma, 0.95), np.quantile(trauma, 0.85)
    rain97 = np.quantile(rain, 0.97)
    for i in range(N):
        if scenario[i] != "None":
            continue
        if rain[i] >= rain97 and season[i] == "Monsoon":
            scenario[i] = "Flood_Disruption"
            scen_sev[i] = int(np.clip(2 + (rain[i] - rain97) / 15, 1, 5))
        elif trauma[i] >= t95 and (festival[i] == 1 or event[i] >= 3):
            scenario[i] = "Road_Accident_Surge"
            scen_sev[i] = int(np.clip(2 + (trauma[i] - t95) / 4, 1, 5))
        elif season[i] == "Monsoon" and trauma[i] >= t85 and rng.random() < 0.25:
            scenario[i] = "Snakebite_Cluster"
            scen_sev[i] = int(np.clip(1 + (trauma[i] - t85) / 4, 1, 4))

    out["outbreak_type"] = new_ot
    out["outbreak_severity_0_5"] = new_sev
    # Write NaN (blank) for no-scenario days, matching the outbreak_type
    # convention (blank = none). The `scenario` string array is kept for the
    # internal logic below.
    out["emergency_scenario_type"] = pd.Series(scenario, index=out.index).replace("None", np.nan)
    out["emergency_scenario_severity_0_5"] = scen_sev

    # =====================================================================
    # 2. CLINICAL SUBCATEGORIES (each set sums exactly to its parent)
    # =====================================================================
    # Fever/infectious -> vector_borne, respiratory, gastrointestinal, other
    p = np.tile([0.35, 0.28, 0.22, 0.15], (N, 1)).astype(float)
    p[ot == "Dengue", :] = [0.62, 0.14, 0.12, 0.12]
    p[ot == "Malaria", :] = [0.60, 0.15, 0.13, 0.12]
    p[ot == "Respiratory", :] = [0.18, 0.55, 0.15, 0.12]
    p[ot == "Diarrheal", :] = [0.16, 0.16, 0.56, 0.12]
    p[season == "Monsoon"] *= np.array([1.25, 1.0, 1.15, 1.0])
    p[season == "Winter"] *= np.array([0.9, 1.3, 0.9, 1.0])
    fsplit = multinomial_split(fever, p, rng)
    out["vector_borne_cases"] = fsplit[:, 0]
    out["respiratory_cases"] = fsplit[:, 1]
    out["gastrointestinal_cases"] = fsplit[:, 2]
    out["other_fever_cases"] = fsplit[:, 3]
    # severe_respiratory is a subset of respiratory (not part of the sum)
    sev_frac = np.where(ot == "Respiratory", 0.40, 0.12)
    out["severe_respiratory_cases"] = rng.binomial(fsplit[:, 1], sev_frac)

    # Maternal-child -> pediatric, antenatal, obstetric_emergency, immunization
    pm = np.tile([0.45, 0.30, 0.08, 0.17], (N, 1)).astype(float)
    pm[vax == 1] *= np.array([1.0, 1.0, 1.0, 2.2])
    pm[mclinic == 1] *= np.array([1.0, 1.8, 1.0, 1.0])
    msplit = multinomial_split(mch, pm, rng)
    out["pediatric_cases"] = msplit[:, 0]
    out["antenatal_cases"] = msplit[:, 1]
    out["obstetric_emergency_cases"] = msplit[:, 2]
    out["immunization_visits"] = msplit[:, 3]

    resp = out["respiratory_cases"].to_numpy()
    sev_resp = out["severe_respiratory_cases"].to_numpy()
    gastro = out["gastrointestinal_cases"].to_numpy()
    vbc = out["vector_borne_cases"].to_numpy()
    ped_cases = out["pediatric_cases"].to_numpy()
    ante = out["antenatal_cases"].to_numpy()
    obst_emg = out["obstetric_emergency_cases"].to_numpy()

    # =====================================================================
    # 3. OXYGEN (driven mainly by respiratory severity)
    # =====================================================================
    oxy_cases = np.round(0.7 * sev_resp + 0.15 * resp + 0.03 * trauma).astype(int)
    out["oxygen_support_cases"] = oxy_cases
    req_oxy = np.ceil(oxy_cases * 0.8).astype(int) + 2
    cap_oxy = int(np.quantile(req_oxy, 0.90))
    avail_oxy = np.clip(cap_oxy + rng.integers(-2, 3, N), 4, None)
    out["required_oxygen_cylinders"] = req_oxy
    out["available_oxygen_cylinders"] = avail_oxy
    out["oxygen_shortage_units"] = np.maximum(0, req_oxy - avail_oxy)
    out["oxygen_shortage_flag"] = (req_oxy > avail_oxy).astype(int)

    # =====================================================================
    # 4. BED OCCUPANCY (sequential: today depends on yesterday)
    # =====================================================================
    # Split daily admissions across bed types by the day's case mix.
    w_iso = 0.18 + 0.6 * (fever / (fever + opd + mch + trauma + 1))
    w_emg = 0.12 + 0.7 * (trauma / (fever + opd + mch + trauma + 1))
    w_gen = np.clip(1.0 - w_iso - w_emg, 0.05, None)
    wsum = w_iso + w_emg + w_gen
    probs = np.stack([w_gen / wsum, w_emg / wsum, w_iso / wsum], axis=1)
    adm_split = multinomial_split(adm, probs, rng)
    adm_by = {"general": adm_split[:, 0], "emergency": adm_split[:, 1], "isolation": adm_split[:, 2]}

    for bt in ("general", "emergency", "isolation"):
        a = adm_by[bt]
        occ = np.zeros(N, int)
        disc = np.zeros(N, int)
        prev = int(round(a.mean() * LOS[bt]))       # steady-state initial occupancy
        for t in range(N):
            d = min(int(rng.poisson(prev / LOS[bt])), prev)
            o = max(0, prev + a[t] - d)
            disc[t], occ[t] = d, o
            prev = o
        total = int(round(np.quantile(occ, BED_CAPACITY_PERCENTILE / 100) / 2) * 2) + 4
        oos = rng.integers(0, 3, N) + (rng.random(N) < 0.05) * rng.integers(0, 3, N)
        usable = np.maximum(total - oos, 1)
        overflow = np.maximum(0, occ - usable)
        occupied = np.minimum(occ, usable)
        available = usable - occupied
        out[f"total_{bt}_beds"] = total
        out[f"occupied_{bt}_beds"] = occupied
        out[f"expected_{bt}_discharges"] = disc
        out[f"out_of_service_{bt}_beds"] = oos.astype(int)
        out[f"available_{bt}_beds"] = available
        out[f"projected_{bt}_occupancy"] = occ
        out[f"overflow_{bt}_patients"] = overflow
        out[f"required_{bt}_beds"] = occ            # beds needed = projected occupancy

    out["overflow_patients"] = (
        out["overflow_general_patients"] + out["overflow_emergency_patients"]
        + out["overflow_isolation_patients"]
    )

    # =====================================================================
    # 5. MEDICINE INVENTORY (sequential: closing[t] -> opening[t+1])
    # =====================================================================
    usage = {
        "iv_fluids": np.round(1.2 * adm + 0.15 * fever + 0.3 * gastro).astype(int),
        "ors": np.round(0.9 * gastro + 0.1 * fever).astype(int),
        "diagnostic_test_kits": np.round(0.35 * fever + 0.2 * vbc + 0.05 * opd).astype(int),
        "antipyretics": np.round(0.8 * fever + 0.08 * opd).astype(int),
        "ppe_kits": np.round(0.5 * resp + 0.8 * sev_resp + 2 * adm_by["isolation"] + sev).astype(int),
    }
    for item, need in usage.items():
        pr = MED_PARAMS[item]
        reorder_point = int(need.mean() * pr["lead"] + pr["safety"])
        opening = np.zeros(N, int); received = np.zeros(N, int)
        used = np.zeros(N, int); expired = np.zeros(N, int)
        closing = np.zeros(N, int); shortage = np.zeros(N, int); flag = np.zeros(N, int)
        stock = pr["init"]; pending = {}          # day_index -> qty arriving
        for t in range(N):
            rec = pending.pop(t, 0)
            stock += rec
            opening[t] = stock
            req = int(need[t])
            u = min(req, stock)
            short = req - u
            stock -= u
            exp = int(round(stock * pr["expiry"]))
            stock -= exp
            if stock <= reorder_point and not any(k >= t for k in pending):
                pending[t + pr["lead"]] = pr["order_qty"]
                flag[t] = 1
            received[t], used[t], expired[t] = rec, u, exp
            closing[t], shortage[t] = stock, short
        out[f"opening_stock_{item}"] = opening
        out[f"received_{item}"] = received
        out[f"used_{item}"] = used
        out[f"expired_{item}"] = expired
        out[f"closing_stock_{item}"] = closing
        out[f"required_{item}"] = need
        out[f"{item}_shortage_units"] = shortage
        out[f"{item}_reorder_flag"] = flag

    # =====================================================================
    # 6. SPECIALIST COVERAGE (OBGYN min 2 policy; Pediatric min 1)
    # =====================================================================
    # OBGYN active-duty requirement rises to 2 only on genuinely high-maternal or
    # multi-obstetric-emergency days (~12% of days); on-call backup is mobilised
    # more often. With only 1 OBGYN on staff, a 2-active day is a real shortage.
    mch_hi = np.quantile(mch, 0.75)
    mch_p90 = np.quantile(mch, 0.90)
    obgyn_active = np.where((obst_emg >= 2) | (mch >= mch_p90), 2, 1)
    out["minimum_obgyn_coverage"] = 2
    out["required_obgyn_duty_hours"] = obgyn_active * 8 + (obst_emg >= 1) * 4
    out["obgyn_on_call_required"] = ((obst_emg >= 1) | (mch >= mch_hi)).astype(int)
    out["obgyn_shortage_flag"] = (obgyn_active > N_OBGYN_AVAILABLE).astype(int)

    ped_hi = np.quantile(ped_cases, 0.75)
    ped_p90 = np.quantile(ped_cases, 0.90)
    ped_active = np.where(ped_cases >= ped_p90, 2, 1)
    out["minimum_pediatrician_coverage"] = 1
    out["required_pediatrician_duty_hours"] = ped_active * 8 + (ped_cases >= ped_p90) * 4
    out["pediatrician_on_call_required"] = (ped_cases >= ped_hi).astype(int)
    out["pediatrician_shortage_flag"] = (ped_active > N_PEDIATRICIAN_AVAILABLE).astype(int)

    # =====================================================================
    # 7. REQUIRED STAFF (recomputed, explainable) & AMBULANCE
    # =====================================================================
    out["required_general_doctors"] = 2 + (opd > np.quantile(opd, 0.66)).astype(int)
    out["required_physicians"] = 1 + (fever > np.quantile(fever, 0.75)).astype(int)
    out["required_emergency_doctors"] = 1 + (trauma > np.quantile(trauma, 0.75)).astype(int) \
        + (scenario != "None").astype(int)
    out["required_pediatricians"] = ped_active
    out["required_obgyn_doctors"] = obgyn_active
    load = out["total_patient_arrivals"].to_numpy()
    out["required_senior_nursing_officers"] = 2 + (load > np.quantile(load, 0.8)).astype(int)
    occ_total = out["occupied_general_beds"] + out["occupied_emergency_beds"] + out["occupied_isolation_beds"]
    out["required_nursing_officers"] = 4 + np.clip(occ_total // 12, 0, 4).astype(int)
    out["required_anm_staff"] = 1 + (mch > mch_hi).astype(int)
    out["required_lab_technicians"] = 1 + (usage["diagnostic_test_kits"] > np.quantile(usage["diagnostic_test_kits"], 0.75)).astype(int)
    out["required_pharmacists"] = 1 + (usage["antipyretics"] > np.quantile(usage["antipyretics"], 0.8)).astype(int)
    out["required_ambulance_crew"] = 1 + (trauma > t85).astype(int) + (scenario == "Mass_Casualty").astype(int) * 2

    req_amb = 1 + (trauma > t85).astype(int) + (scenario == "Mass_Casualty").astype(int) * 2 \
        + (scenario == "Road_Accident_Surge").astype(int)
    avail_amb = np.clip(3 + rng.integers(-1, 2, N), 1, None)
    out["required_ambulances"] = req_amb
    out["available_ambulances"] = avail_amb
    out["ambulance_shortage_units"] = np.maximum(0, req_amb - avail_amb)
    out["ambulance_shortage_flag"] = (req_amb > avail_amb).astype(int)

    # =====================================================================
    # 8. AGGREGATE SHORTAGES & EMERGENCY RISK (explainable rules)
    # =====================================================================
    shortage_flags = np.stack([
        (out["overflow_general_patients"] > 0).astype(int),
        (out["overflow_emergency_patients"] > 0).astype(int),
        (out["overflow_isolation_patients"] > 0).astype(int),
        out["oxygen_shortage_flag"].to_numpy(),
        out["obgyn_shortage_flag"].to_numpy(),
        out["pediatrician_shortage_flag"].to_numpy(),
        out["ambulance_shortage_flag"].to_numpy(),
    ] + [(out[f"{it}_shortage_units"] > 0).astype(int).to_numpy() for it in MED_PARAMS], axis=0)
    shortage_count = shortage_flags.sum(axis=0)
    out["resource_shortage_count"] = shortage_count

    max_sev = np.maximum(new_sev, scen_sev)
    overflow = out["overflow_patients"].to_numpy()
    emg_overflow = out["overflow_emergency_patients"].to_numpy()
    any_full = (out[["available_general_beds", "available_emergency_beds", "available_isolation_beds"]].min(axis=1) == 0).to_numpy()
    specialist_gap = (out["obgyn_shortage_flag"] | out["pediatrician_shortage_flag"]).to_numpy()

    # Explainable rules. A chronic single specialist gap maps to Watch, not High;
    # High needs real strain (3+ shortages, a severe event, or actual overflow).
    risk = np.array(["Normal"] * N, dtype=object)
    for t in range(N):
        if (emg_overflow[t] > 0) or (overflow[t] > 0 and (max_sev[t] >= 4 or shortage_count[t] >= 3)) \
                or shortage_count[t] >= 5:
            risk[t] = "Critical"
        elif (shortage_count[t] >= 3) or (max_sev[t] >= 4) or (overflow[t] > 0) \
                or (any_full[t] and shortage_count[t] >= 2):
            risk[t] = "High"
        elif (shortage_count[t] >= 1) or (max_sev[t] >= 2) or specialist_gap[t]:
            risk[t] = "Watch"
    out["emergency_risk_level"] = risk

    return out


def assert_demand_preserved(orig: pd.DataFrame, new: pd.DataFrame) -> None:
    """Point 10: confirm the locked demand columns are unchanged (with the one
    documented Mass_Casualty relabel to outbreak_type/severity)."""
    print("\n" + "=" * 60 + "\nDEMAND PRESERVATION REPORT\n" + "=" * 60)
    ok = True
    for c in IMMUTABLE_DEMAND:
        same = orig[c].fillna("<NA>").astype(str).equals(new[c].fillna("<NA>").astype(str))
        if not same:
            ok = False
            print(f"  CHANGED (unexpected): {c}")
    print(f"  {len(IMMUTABLE_DEMAND)} immutable demand columns identical: {ok}")

    mass = orig["outbreak_type"].fillna("None") == "Mass_Casualty"
    non_mass = ~mass
    ot_same = orig.loc[non_mass, "outbreak_type"].fillna("<NA>").astype(str).equals(
        new.loc[non_mass, "outbreak_type"].fillna("<NA>").astype(str))
    sev_same = orig.loc[non_mass, "outbreak_severity_0_5"].equals(new.loc[non_mass, "outbreak_severity_0_5"])
    print(f"  outbreak_type/severity identical on {int(non_mass.sum())} non-mass-casualty rows: {ot_same and sev_same}")
    relabel_ok = bool(
        new.loc[mass, "outbreak_type"].isna().all()
        and (new.loc[mass, "outbreak_severity_0_5"] == 0).all()
        and (new.loc[mass, "emergency_scenario_type"] == "Mass_Casualty").all()
    )
    print(f"  {int(mass.sum())} Mass_Casualty rows relabeled to emergency_scenario_type: {relabel_ok}")
    if not (ok and ot_same and sev_same and relabel_ok):
        raise AssertionError("Demand-preservation check FAILED.")
    print("  PASSED: demand preserved.")


def main() -> int:
    rng = np.random.default_rng(SEED)
    demand = load_demand()
    orig = demand.copy()

    result = generate(demand, rng)
    assert_demand_preserved(orig, result)

    if DAILY_CSV.exists():
        DAILY_CSV.replace(BACKUP_CSV)
        print(f"\nBacked up previous file -> {BACKUP_CSV.name}")
    result.to_csv(DAILY_CSV, index=False)
    print(f"Wrote {DAILY_CSV.name}: {result.shape[0]} rows, {result.shape[1]} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
