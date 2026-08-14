"""
PHASE 11B -- reproduction of the EPA / Seth et al. 2016 Net3 source-inversion
experiments, Bayesian ("Probability Based") method.

WHY THIS IS A REIMPLEMENTATION AND NOT WST
------------------------------------------
The official Water Security Toolkit was obtained (USEPA/Water-Security-Toolkit
@ 07f997cc) but cannot be run here: pywst is Python 2 and only marshals files,
while the three algorithms live in compiled C/C++ (inversionsim, csarun,
Merlion) and the optimization method additionally needs a MIP solver through
Pyomo/AMPL. The brief's rule 3 therefore applies: fall back to WNTR/EPANET and
document every algorithmic divergence.

WHAT IS RESOLVED, AND FROM WHERE
--------------------------------
From the official WST inversion configuration (raw/inversion_config.yml,
raw/inversion_ex1.yml), i.e. not invented:

    positive threshold   100.0    concentration above which a reading is positive
    negative threshold     0.1    below which it is negative
    measurement failure   0.05    probability a sensor reading is wrong
    num injections        1
    feasible nodes        null    -> every node is a candidate source

The SPECIFICITY definition was recovered, not guessed. The brief reports, for
Probability Based, both a specificity and the count of nodes as-or-more likely
than the true source, on three networks of known size:

    Net3    97 nodes, 30 better -> 1 - 30/97    = 69.07 %   published 69.07
    Net6  3358 nodes, 32 better -> 1 - 32/3358  = 99.05 %   published 99.05
    BWSN2 12527 nodes,45 better -> 1 - 45/12527 = 99.64 %   published 99.64

Three independent points, zero disagreement. So

    specificity = 1 - rank_true_source / n_total_nodes

where rank counts candidates whose posterior is >= the true source's.

WHAT REMAINS UNRESOLVED
-----------------------
Recorded in UNRESOLVED_PARAMETERS.csv and never tuned to help FO:
injection strength and duration, the sensor design, the scenario count, and
above all the definition of the published "accuracy" -- which the brief
explicitly warns is NOT top-1 source accuracy. A hypothesis is tested and
reported, not assumed.
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

# --- resolved from the official WST configuration --------------------------
POS_THRESHOLD = 100.0
NEG_THRESHOLD = 0.1
MEAS_FAILURE = 0.05
NUM_INJECTIONS = 1

# --- unresolved; frozen before any result was inspected --------------------
INJECTION_STRENGTH = 1000.0     # mg/L SETPOINT
INJECTION_DURATION_H = 2
INJECTION_START_H = 2
N_SENSORS = 5
SIM_DURATION_H = 24
QUALITY_TIMESTEP_S = 300
REPORT_TIMESTEP_S = 900
SEED = 20260814

HORIZONS_H = [1, 2, 4, 8, 16, 24]

# Published Probability Based values, TRANSCRIBED FROM THE MISSION BRIEF
# (the official XLSX was never received).
PUBLISHED_PB = {
    "accuracy":    {1: 1, 2: 1, 4: 44, 8: 100, 16: 100, 24: 100},
    "specificity": {1: 35, 2: 52, 4: 72, 8: 90, 16: 90, 24: 90},
}


def build_model(inp: Path) -> wntr.network.WaterNetworkModel:
    wn = wntr.network.WaterNetworkModel(str(inp))
    wn.options.quality.parameter = "CHEMICAL"
    wn.options.time.duration = SIM_DURATION_H * 3600
    wn.options.time.quality_timestep = QUALITY_TIMESTEP_S
    wn.options.time.report_timestep = REPORT_TIMESTEP_S
    return wn


def simulate_injection(inp: Path, source_node: str) -> pd.DataFrame:
    """Concentration at every node over time for an injection at source_node."""
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


def build_signature_library(inp: Path, candidates: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """sig[c, node, t] discretised to {+1 positive, -1 negative, 0 ambiguous}."""
    t0 = time.time()
    sigs, times = [], None
    for i, c in enumerate(candidates):
        q = simulate_injection(inp, c)
        if times is None:
            times = np.asarray(q.index, dtype=float)
            cols = list(q.columns)
        v = q.to_numpy(dtype=float)
        d = np.zeros_like(v, dtype=np.int8)
        d[v >= POS_THRESHOLD] = 1
        d[v <= NEG_THRESHOLD] = -1
        sigs.append(d.T)  # (nodes, time)
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(candidates)} signatures ({time.time()-t0:.0f}s)", flush=True)
    return np.stack(sigs), times, cols


def bayesian_posterior(obs: np.ndarray, lib: np.ndarray, sensor_idx: list[int],
                       t_mask: np.ndarray, p_fail: float = MEAS_FAILURE) -> np.ndarray:
    """Posterior over candidate sources, uniform prior.

    Each (sensor, time) reading is an independent Bernoulli: the candidate's
    predicted state matches the observation with probability 1 - p_fail. This
    is the WST measurement-failure model applied to the discretised readings.
    Ambiguous predictions (0) carry no information and are skipped.
    """
    o = obs[np.ix_(sensor_idx, t_mask)]
    p = lib[:, sensor_idx, :][:, :, t_mask]
    informative = p != 0
    agree = (p == o[None, :, :]) & informative
    n_agree = agree.sum(axis=(1, 2))
    n_inf = informative.sum(axis=(1, 2))
    n_dis = n_inf - n_agree
    loglik = n_agree * np.log(1 - p_fail) + n_dis * np.log(p_fail)
    loglik -= loglik.max()
    post = np.exp(loglik)
    return post / post.sum()


def run_net3(inp: Path, n_scenarios: int | None = None) -> pd.DataFrame:
    wn = build_model(inp)
    candidates = list(wn.junction_name_list)
    n_total_nodes = wn.num_junctions + wn.num_tanks + wn.num_reservoirs

    print(f"  building signature library: {len(candidates)} candidates", flush=True)
    lib, times, cols = build_signature_library(inp, candidates)
    col_index = {c: i for i, c in enumerate(cols)}

    rng = np.random.default_rng(SEED)
    sensor_names = sorted(rng.choice(candidates, size=N_SENSORS, replace=False).tolist())
    sensor_idx = [col_index[s] for s in sensor_names]
    print(f"  sensors (UNRESOLVED design, seeded): {sensor_names}", flush=True)

    scenarios = candidates if n_scenarios is None else candidates[:n_scenarios]
    rows = []
    for si, true_src in enumerate(scenarios):
        obs = lib[candidates.index(true_src)]        # noise-free observation
        for H in HORIZONS_H:
            t_mask = times <= H * 3600
            post = bayesian_posterior(obs, lib, sensor_idx, t_mask)
            p_true = post[candidates.index(true_src)]
            # rank counts candidates as-or-more likely than the true source
            n_better = int((post >= p_true).sum())
            rank = n_better
            order = np.argsort(-post)
            top1 = candidates[order[0]]
            top5 = [candidates[i] for i in order[:5]]
            with np.errstate(divide="ignore"):
                ent = float(-(post * np.log(np.maximum(post, 1e-300))).sum())
            srt = np.sort(post)[::-1]
            rows.append({
                "network": "Net3", "scenario_id": si, "true_source": true_src,
                "horizon_h": H, "n_total_nodes": n_total_nodes,
                "rank_true_source": rank,
                "reciprocal_rank": 1.0 / rank if rank > 0 else np.nan,
                "specificity_pct": 100.0 * (1.0 - rank / n_total_nodes),
                "top1_source": top1,
                "top1_correct": int(top1 == true_src),
                "top5_contains_true": int(true_src in top5),
                "posterior_true_source": float(p_true),
                "nll_true_source": float(-np.log(max(p_true, 1e-300))),
                "posterior_entropy": ent,
                "top1_top2_margin": float(srt[0] - srt[1]) if len(srt) > 1 else np.nan,
                "candidate_set_size": int((post >= 0.25 * srt[0]).sum()),
                "sensor_design": ";".join(sensor_names),
                "sensor_count": len(sensor_names),
            })
        if (si + 1) % 25 == 0:
            print(f"    {si+1}/{len(scenarios)} scenarios", flush=True)
    return pd.DataFrame(rows)


def scorecard(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for H in HORIZONS_H:
        s = df[df.horizon_h == H]
        rep_spec = float(s.specificity_pct.mean())
        pub_spec = PUBLISHED_PB["specificity"][H]
        rows.append({
            "experiment": "time_horizon", "condition": f"{H}h",
            "method": "probability_based(bayesian)", "metric": "specificity_pct",
            "published_value": pub_spec, "reproduced_value": round(rep_spec, 2),
            "absolute_error": round(rep_spec - pub_spec, 2),
            "relative_error": round((rep_spec - pub_spec) / pub_spec, 4),
            "passed_gate": abs(rep_spec - pub_spec) <= 5.0,
            "notes": "specificity definition recovered and verified on 3 networks",
        })
        # the accuracy hypothesis under test: true source retained in the
        # candidate set. Reported, never used to tune anything.
        rep_acc = 100.0 * float((s.rank_true_source <= s.candidate_set_size).mean())
        pub_acc = PUBLISHED_PB["accuracy"][H]
        rows.append({
            "experiment": "time_horizon", "condition": f"{H}h",
            "method": "probability_based(bayesian)", "metric": "accuracy_pct_HYPOTHESISED",
            "published_value": pub_acc, "reproduced_value": round(rep_acc, 2),
            "absolute_error": round(rep_acc - pub_acc, 2),
            "relative_error": round((rep_acc - pub_acc) / pub_acc, 4) if pub_acc else np.nan,
            "passed_gate": abs(rep_acc - pub_acc) <= 5.0,
            "notes": "UNRESOLVED definition; hypothesis = true source inside candidate set",
        })
    return pd.DataFrame(rows)


def main() -> int:
    P11.mkdir(parents=True, exist_ok=True)
    inp = RAW / "Net3.inp"
    print("Phase 11B -- Net3 Time Horizon, Bayesian (Probability Based)")
    t0 = time.time()
    df = run_net3(inp)
    (P11 / "event_level").mkdir(exist_ok=True)
    df.to_csv(P11 / "event_level" / "EVENT_LEVEL_SOURCE_INVERSION.csv", index=False)

    sc = scorecard(df)
    sc.to_csv(P11 / "REPRODUCTION_SCORECARD.csv", index=False)

    print(f"\n{len(df)} rows over {df.scenario_id.nunique()} scenarios "
          f"x {len(HORIZONS_H)} horizons  ({time.time()-t0:.0f}s)\n")
    print(sc[["condition", "metric", "published_value", "reproduced_value",
              "absolute_error", "passed_gate"]].to_string(index=False))

    spec = sc[sc.metric == "specificity_pct"]
    rmse = float(np.sqrt((spec.absolute_error ** 2).mean()))
    print(f"\nspecificity RMSE vs published: {rmse:.2f} points (gate: <= 5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
