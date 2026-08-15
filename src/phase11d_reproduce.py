"""
PHASE 11D -- Net3 Time Horizon reproduction against the OFFICIAL EPA workbook.

WHAT CHANGED SINCE 11B/11C
--------------------------
Two artefacts previously recorded as missing were supplied:

    phase11_epa/official/Data_A-pg4z_TestSourceInversion_Haxton_20160728.xlsx
    phase11_epa/official/REPRODUCTION_GATE_PROTOCOL.md

The workbook is now the reference truth: every target below is READ FROM IT at
run time, never transcribed. The pre-registered protocol supplies Gate R2.

WHAT DID NOT CHANGE, AND MUST NOT
---------------------------------
The reimplementation is byte-identical in behaviour to Phase 11B: same frozen
parameters, same likelihood, same sensor seed. The protocol forbids adjusting
parameters onto the targets, so nothing here is swept, fitted or re-selected.
11C already established, over 135 parameterisations, that the best ATTAINABLE
specificity RMSE is 8.72 points against a gate of <= 5; this run is the
single frozen-parameter reproduction the protocol asks for, not a search.

ENDPOINTS
---------
The workbook over-determines the specificity definition exactly (see
verify_specificity_definition): specificity = 1 - n_ge / n_nodes, where n_ge
counts candidates scoring >= the true source. Reproduced to 12 decimal places
on all three networks, with the denominator being total nodes for Net3 (97)
and Network2 (3358) but junctions only for BWSN2 (12523).

The ACCURACY definition remains under-determined. The workbook rules out
unique-top-1 (Network Size: accuracy 100% while 30 nodes are as-or-more
likely), so two set-membership hypotheses are reported side by side and
neither is used to tune anything.
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import wntr

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
P11 = REPO / "phase11_epa"
RAW = P11 / "raw"
OFFICIAL = P11 / "official"
OUT = P11 / "phase11d"
XLSX = OFFICIAL / "Data_A-pg4z_TestSourceInversion_Haxton_20160728.xlsx"

# --- resolved from the official WST configuration (unchanged from 11B) -----
POS_THRESHOLD = 100.0
NEG_THRESHOLD = 0.1
MEAS_FAILURE = 0.05
NUM_INJECTIONS = 1

# --- unresolved; FROZEN IN 11B AND DELIBERATELY NOT RE-CHOSEN HERE --------
INJECTION_STRENGTH = 1000.0     # mg/L SETPOINT
INJECTION_DURATION_H = 2
INJECTION_START_H = 2
N_SENSORS = 5
SIM_DURATION_H = 24
QUALITY_TIMESTEP_S = 300
REPORT_TIMESTEP_S = 900
SEED = 20260814

HORIZONS_H = [1, 2, 4, 8, 16, 24]

GATE_RMSE_ACCURACY = 5.0
GATE_RMSE_SPECIFICITY = 5.0
GATE_PLATEAU_FROM_H = 8


# ---------------------------------------------------------------- workbook

def read_official_time_horizon() -> pd.DataFrame:
    """The 'Time Horizon' sheet, all three methods, straight from the XLSX."""
    raw = pd.read_excel(XLSX, sheet_name="Time Horizon", header=None)
    blocks = {"probability_based": 0, "contaminant_status": 4, "optimization": 8}
    rows = []
    for method, c0 in blocks.items():
        for r in range(4, 10):          # r0 title, r2 method banner, r3 headers
            h, acc, spec = raw.iat[r, c0], raw.iat[r, c0 + 1], raw.iat[r, c0 + 2]
            rows.append({"method": method, "horizon_h": int(h),
                         "accuracy_pct": float(acc), "specificity_pct": float(spec)})
    return pd.DataFrame(rows)


def verify_specificity_definition() -> pd.DataFrame:
    """Re-derive specificity = 1 - n_ge/n on the Network Size sheet.

    Not decoration: this is the only reason the specificity endpoint is
    considered recovered rather than assumed, and it is re-checked here
    against the official workbook instead of the second-hand brief.
    """
    raw = pd.read_excel(XLSX, sheet_name="Network Size", header=None)
    blocks = {"probability_based": 0, "contaminant_status": 5, "optimization": 10}
    denominators = {"Net3(97)": 97, "Network2(3,358)": 3358, "BWSN2(12,523)": 12523}
    rows = []
    for method, c0 in blocks.items():
        for r in range(4, 7):           # r0 title, r2 method banner, r3 headers
            name = str(raw.iat[r, c0])
            spec = float(raw.iat[r, c0 + 1])
            n_ge = int(raw.iat[r, c0 + 2])
            n = denominators[name]
            derived = 100.0 * (1.0 - n_ge / n)
            rows.append({"method": method, "network": name, "n_nodes": n,
                         "n_ge_published": n_ge, "specificity_published": spec,
                         "specificity_derived": derived,
                         "abs_error": abs(derived - spec),
                         "exact": bool(abs(derived - spec) < 1e-9)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- hydraulics

def build_model(inp: Path) -> wntr.network.WaterNetworkModel:
    wn = wntr.network.WaterNetworkModel(str(inp))
    wn.options.quality.parameter = "CHEMICAL"
    wn.options.time.duration = SIM_DURATION_H * 3600
    wn.options.time.quality_timestep = QUALITY_TIMESTEP_S
    wn.options.time.report_timestep = REPORT_TIMESTEP_S
    return wn


def simulate_injection(inp: Path, source_node: str) -> pd.DataFrame:
    wn = build_model(inp)
    pat = wntr.network.elements.Pattern.binary_pattern(
        "inj",
        start_time=INJECTION_START_H * 3600,
        end_time=(INJECTION_START_H + INJECTION_DURATION_H) * 3600,
        duration=wn.options.time.duration,
        step_size=wn.options.time.pattern_timestep,
    )
    wn.add_pattern("inj", pat)
    wn.add_source("S1", source_node, "SETPOINT", INJECTION_STRENGTH, "inj")
    return wntr.sim.EpanetSimulator(wn).run_sim().node["quality"]


def build_signature_library(inp: Path, candidates: list[str]):
    """sig[c, node, t] discretised to {+1 positive, -1 negative, 0 ambiguous}."""
    t0 = time.time()
    sigs, times, cols = [], None, None
    for i, c in enumerate(candidates):
        q = simulate_injection(inp, c)
        if times is None:
            times = np.asarray(q.index, dtype=float)
            cols = list(q.columns)
        v = q.to_numpy(dtype=float)
        d = np.zeros_like(v, dtype=np.int8)
        d[v >= POS_THRESHOLD] = 1
        d[v <= NEG_THRESHOLD] = -1
        sigs.append(d.T)
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(candidates)} signatures ({time.time()-t0:.0f}s)", flush=True)
    return np.stack(sigs), times, cols


# ---------------------------------------------------------------- methods

def bayesian_posterior(obs, lib, sensor_idx, t_mask, p_fail=MEAS_FAILURE):
    """Probability Based: uniform prior, Bernoulli measurement-failure model."""
    o = obs[np.ix_(sensor_idx, t_mask)]
    p = lib[:, sensor_idx, :][:, :, t_mask]
    informative = p != 0
    agree = (p == o[None, :, :]) & informative
    n_agree = agree.sum(axis=(1, 2))
    n_inf = informative.sum(axis=(1, 2))
    loglik = n_agree * np.log(1 - p_fail) + (n_inf - n_agree) * np.log(p_fail)
    loglik -= loglik.max()
    post = np.exp(loglik)
    return post / post.sum()


def csa_scores(obs, lib, sensor_idx, t_mask):
    """Contaminant Status Algorithm: hard consistency, no MIP required.

    A candidate scores 1 if its discretised prediction contradicts no
    informative sensor reading, else 0. Ties at 1 are the feasible set.
    """
    o = obs[np.ix_(sensor_idx, t_mask)]
    p = lib[:, sensor_idx, :][:, :, t_mask]
    informative = (p != 0) & (o[None, :, :] != 0)
    contradiction = informative & (p != o[None, :, :])
    return (~contradiction.any(axis=(1, 2))).astype(float)


# ----------------------------------------------------------------- scoring

def score_scenario(scores: np.ndarray, true_idx: int, n_total_nodes: int) -> dict:
    """The two published endpoints, plus the diagnostics the protocol lists.

    n_ge  -- candidates scoring >= the true source (specificity numerator)
    n_gt  -- candidates scoring STRICTLY above it (accuracy hypothesis H1:
             the true source sits in the tied-argmax set iff n_gt == 0)
    """
    s_true = scores[true_idx]
    n_ge = int((scores >= s_true).sum())
    n_gt = int((scores > s_true).sum())
    order = np.argsort(-scores)
    srt = np.sort(scores)[::-1]
    total = scores.sum()
    post = scores / total if total > 0 else np.full_like(scores, 1.0 / len(scores))
    p_true = float(post[true_idx])
    with np.errstate(divide="ignore"):
        ent = float(-(post * np.log(np.maximum(post, 1e-300))).sum())
    return {
        "n_ge_true_source": n_ge,
        "n_gt_true_source": n_gt,
        "specificity_pct": 100.0 * (1.0 - n_ge / n_total_nodes),
        "in_tied_argmax": int(n_gt == 0),
        "top1_correct": int(order[0] == true_idx),
        "posterior_true_source": p_true,
        "nll_true_source": float(-np.log(max(p_true, 1e-300))),
        "posterior_entropy": ent,
        "top1_top2_margin": float(srt[0] - srt[1]) if len(srt) > 1 else np.nan,
        "candidate_set_size_q25": int((scores >= 0.25 * srt[0]).sum()),
    }


def run_net3(inp: Path) -> pd.DataFrame:
    wn = build_model(inp)
    candidates = list(wn.junction_name_list)
    n_total_nodes = wn.num_junctions + wn.num_tanks + wn.num_reservoirs

    print(f"  signature library: {len(candidates)} candidates, n_total_nodes={n_total_nodes}", flush=True)
    lib, times, cols = build_signature_library(inp, candidates)
    col_index = {c: i for i, c in enumerate(cols)}

    rng = np.random.default_rng(SEED)
    sensor_names = sorted(rng.choice(candidates, size=N_SENSORS, replace=False).tolist())
    sensor_idx = [col_index[s] for s in sensor_names]
    print(f"  sensors (UNRESOLVED design, 11B seed, NOT re-chosen): {sensor_names}", flush=True)

    rows = []
    for si, true_src in enumerate(candidates):
        true_idx = candidates.index(true_src)
        obs = lib[true_idx]
        for H in HORIZONS_H:
            t_mask = times <= H * 3600
            for method, scores in (
                ("probability_based", bayesian_posterior(obs, lib, sensor_idx, t_mask)),
                ("contaminant_status", csa_scores(obs, lib, sensor_idx, t_mask)),
            ):
                rec = {"network": "Net3", "scenario_id": si, "true_source": true_src,
                       "horizon_h": H, "method": method, "n_total_nodes": n_total_nodes,
                       "sensor_design": ";".join(sensor_names), "sensor_count": len(sensor_names)}
                rec.update(score_scenario(scores, true_idx, n_total_nodes))
                rows.append(rec)
        if (si + 1) % 25 == 0:
            print(f"    {si+1}/{len(candidates)} scenarios", flush=True)
    return pd.DataFrame(rows)


def scorecard(df: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Reproduced vs official, per method and horizon, with both accuracy
    hypotheses reported and neither privileged."""
    rows = []
    for method in df.method.unique():
        pub_m = official[official.method == method].set_index("horizon_h")
        for H in HORIZONS_H:
            s = df[(df.method == method) & (df.horizon_h == H)]
            rep_spec = float(s.specificity_pct.mean())
            pub_spec = float(pub_m.loc[H, "specificity_pct"])
            pub_acc = float(pub_m.loc[H, "accuracy_pct"])
            acc_h1 = 100.0 * float(s.in_tied_argmax.mean())
            acc_h2 = 100.0 * float((s.n_ge_true_source <= s.candidate_set_size_q25).mean())
            rows.append({
                "method": method, "horizon_h": H,
                "specificity_published": pub_spec,
                "specificity_reproduced": round(rep_spec, 2),
                "specificity_error": round(rep_spec - pub_spec, 2),
                "accuracy_published": pub_acc,
                "accuracy_H1_tied_argmax": round(acc_h1, 2),
                "accuracy_H1_error": round(acc_h1 - pub_acc, 2),
                "accuracy_H2_candidate_set": round(acc_h2, 2),
                "accuracy_H2_error": round(acc_h2 - pub_acc, 2),
                "mean_n_ge": round(float(s.n_ge_true_source.mean()), 2),
                "top1_pct": round(100.0 * float(s.top1_correct.mean()), 2),
            })
    return pd.DataFrame(rows)


def evaluate_gate_r2(sc: pd.DataFrame, official: pd.DataFrame) -> dict:
    """Gate R2 exactly as pre-registered, no softening."""
    def rmse(x):
        return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))

    per_method, methods_required = {}, ["probability_based", "contaminant_status", "optimization"]
    for method in methods_required:
        if method not in set(sc.method):
            per_method[method] = {"status": "NOT_IMPLEMENTED",
                                  "reason": "WST optimization method requires a compiled MIP "
                                            "solver (Merlion/Pyomo); unavailable in this environment"}
            continue
        m = sc[sc.method == method].sort_values("horizon_h")
        plateau = m[m.horizon_h >= GATE_PLATEAU_FROM_H]
        per_method[method] = {
            "status": "EVALUATED",
            "rmse_specificity": round(rmse(m.specificity_error), 2),
            "rmse_specificity_gate": GATE_RMSE_SPECIFICITY,
            "rmse_specificity_pass": bool(rmse(m.specificity_error) <= GATE_RMSE_SPECIFICITY),
            "rmse_accuracy_H1": round(rmse(m.accuracy_H1_error), 2),
            "rmse_accuracy_H2": round(rmse(m.accuracy_H2_error), 2),
            "rmse_accuracy_gate": GATE_RMSE_ACCURACY,
            "rmse_accuracy_pass_best_hypothesis": bool(
                min(rmse(m.accuracy_H1_error), rmse(m.accuracy_H2_error)) <= GATE_RMSE_ACCURACY),
            "accuracy_plateau_100_from_8h_H1": bool((plateau.accuracy_H1_tied_argmax == 100).all()),
            "accuracy_plateau_100_from_8h_H2": bool((plateau.accuracy_H2_candidate_set == 100).all()),
        }

    evaluated = [m for m, v in per_method.items() if v["status"] == "EVALUATED"]
    conditions = {
        "plateau_accuracy_100_from_8h_all_three_methods": False,
        "rmse_accuracy_le_5": all(per_method[m]["rmse_accuracy_pass_best_hypothesis"] for m in evaluated) and len(evaluated) == 3,
        "rmse_specificity_le_5": all(per_method[m]["rmse_specificity_pass"] for m in evaluated) and len(evaluated) == 3,
    }
    return {
        "gate": "R2_TIME_HORIZON",
        "protocol_sha256": None,
        "methods_required": methods_required,
        "methods_evaluated": evaluated,
        "per_method": per_method,
        "conditions": conditions,
        "verdict": "PASSED" if all(conditions.values()) else "FAILED",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Phase 11D -- Net3 Time Horizon vs OFFICIAL EPA workbook\n")

    print("Specificity definition re-derived on the official Network Size sheet:")
    vdef = verify_specificity_definition()
    vdef.to_csv(OUT / "SPECIFICITY_DEFINITION_CHECK.csv", index=False)
    print(vdef.to_string(index=False), "\n")

    official = read_official_time_horizon()
    official.to_csv(OUT / "OFFICIAL_TIME_HORIZON.csv", index=False)
    print("Official Time Horizon targets:")
    print(official.pivot(index="horizon_h", columns="method").to_string(), "\n")

    t0 = time.time()
    df = run_net3(RAW / "Net3.inp")
    df.to_csv(OUT / "EVENT_LEVEL_PHASE11D.csv", index=False)

    sc = scorecard(df, official)
    sc.to_csv(OUT / "REPRODUCTION_SCORECARD_11D.csv", index=False)
    print(f"\n{len(df)} rows, {df.scenario_id.nunique()} scenarios ({time.time()-t0:.0f}s)\n")
    print(sc.to_string(index=False))

    gate = evaluate_gate_r2(sc, official)
    (OUT / "GATE_R2_RESULT.json").write_text(json.dumps(gate, indent=2))
    print("\n" + "=" * 72)
    print(json.dumps(gate, indent=2))
    print("=" * 72)
    print(f"\nGATE R2 VERDICT: {gate['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
