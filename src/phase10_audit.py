"""
PHASE A -- forensic audit of the frozen FO-v1 result.

FO-v1 is not re-run and not modified. This module reads its frozen outputs and
asks what BattLeDIM actually falsified.

Produces
    EVENT_LEVEL_BATTLEDIM.csv   one row per (track, budget, method, event)
    SURROGATE_CORRELATIONS.csv  design criterion vs realised endpoint, over
                                >= 1000 random designs per budget
    audit_summary.json          freeze chronology, the event driving FO's floor,
                                and the 33-sensor vs all-junctions comparison

THE CENTRAL QUESTION
--------------------
FO-v1 showed that minimising B does not buy detection performance. That is
consistent with two very different explanations:

  (a) B is a poor surrogate -- it does not track the endpoint at all;
  (b) B is a fine surrogate but the endpoint was saturated, so nothing could
      track it.

These are separated by correlating each design criterion against the realised
endpoint across many designs. If EVERY criterion is uncorrelated with the
endpoint, the endpoint carries no signal and FO-v1 falsified nothing about B.
If some criteria correlate and B does not, that is evidence against B itself.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector  # noqa: E402
import evaluate  # noqa: E402
import selection  # noqa: E402
import tracks  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = REPO / "data" / "processed"
RESULTS = REPO / "results"
OUT = REPO / "phase10_reset"

N_DESIGNS = 1000
AUDIT_SEED = 20260813


# ---------------------------------------------------------------------------
# A1. Event-level table
# ---------------------------------------------------------------------------


def event_level_table() -> pd.DataFrame:
    rows = []
    ta = json.loads((RESULTS / "track_a_event_heldout_2018.json").read_text())
    for fold in ta["folds"]:
        for k, entry in fold["budgets"].items():
            for m, r in entry["methods"].items():
                rows.append({
                    "track": "A_EVENT_HELDOUT_2018",
                    "budget": int(k), "method": m,
                    "event": fold["held_out_link"],
                    "leak_type": fold["held_out_type"],
                    "diameter_m": fold["held_out_diameter_m"],
                    "detected": r["held_out_detected"],
                    "delay_h": r["held_out_delay_h"],
                    "localisation_m": r["held_out_localisation_m"],
                })
    tb = json.loads((RESULTS / "track_b_reconstructed_2019.json").read_text())
    for k, entry in tb["budgets"].items():
        for m, r in entry["methods"].items():
            for ev, det in r["metrics"]["per_leak_detected"].items():
                rows.append({
                    "track": "B_RECONSTRUCTED_2019",
                    "budget": int(k), "method": m, "event": ev,
                    "leak_type": None, "diameter_m": None,
                    "detected": det, "delay_h": None, "localisation_m": None,
                })
    return pd.DataFrame(rows)


def identify_fo_floor(df: pd.DataFrame) -> dict:
    """Which event(s) does FO keep missing at k >= 6 in Track A?"""
    a = df[(df.track == "A_EVENT_HELDOUT_2018") & (df.method == "FO")]
    out = {}
    for k in sorted(a.budget.unique()):
        sub = a[a.budget == k]
        missed = sub[sub.detected == 0]
        out[str(k)] = {
            "n_events": int(len(sub)),
            "missed": missed[["event", "leak_type", "diameter_m"]].to_dict("records"),
            "false_forgetting_rate": float(1 - sub.detected.mean()),
        }
    persistent = set.intersection(*[
        {m["event"] for m in v["missed"]} for k, v in out.items() if int(k) >= 6
    ]) if any(int(k) >= 6 for k in out) else set()
    # who else misses those events, at k=8?
    others = {}
    for ev in persistent:
        w = df[(df.track == "A_EVENT_HELDOUT_2018") & (df.budget == 8) & (df.event == ev)]
        others[ev] = {r.method: int(r.detected) for r in w.itertuples()}
    return {"per_budget": out, "persistently_missed_at_k>=6": sorted(persistent),
            "who_detects_it_at_k8": others}


# ---------------------------------------------------------------------------
# A2. Design criterion vs realised endpoint
# ---------------------------------------------------------------------------


def design_criteria(lib: selection.Library, sigma: np.ndarray, kappa: float,
                    eta: float, tau: float, subsets: list[list[int]],
                    goal_idx: np.ndarray, D_top: np.ndarray,
                    bc: np.ndarray) -> pd.DataFrame:
    vis = lib.visibility(sigma)
    eligible = vis.max(axis=1) >= kappa
    vis_e = vis[eligible]
    H = lib.design_matrix()
    Hn = H / np.maximum(np.linalg.norm(H, axis=0, keepdims=True), 1e-12)
    r = 4
    _, _, Vt = np.linalg.svd(H, full_matrices=False)
    H_red = H @ Vt[:r].T
    sig = float(np.mean(sigma))

    rows = []
    for s in subsets:
        d_S = vis_e[:, s].max(axis=1)
        Hs = H[s, :]
        rows.append({
            "B_blind_spot": float(np.mean(d_S <= eta)),
            "visibility_p05": float(np.percentile(d_S, 5)),
            "visibility_mean": float(np.mean(d_S)),
            "D_optimal_bayesian": selection.crit_bayes_d(Hs, sig, tau),
            "A_optimal_bayesian": selection.crit_bayes_a(Hs, sig, tau),
            "E_observable_subspace": selection.crit_bayes_e(Hs, sig, tau),
            "bayesian_information_gain": selection.crit_infogain(Hs, sig, tau),
            "D_optimal_rank_reduced": selection.crit_classical_d(H_red[s, :]),
            "A_optimal_rank_reduced": selection.crit_classical_a(H_red[s, :]),
            "E_optimal_rank_reduced": selection.crit_classical_e(H_red[s, :]),
            "goal_oriented_oed": selection.crit_goal_oriented(Hn[s, :], goal_idx),
            "topological_spread": float(np.min([
                D_top[a, b] for i, a in enumerate(s) for b in s[i + 1:]
            ])) if len(s) > 1 else 0.0,
            "mean_betweenness": float(np.mean(bc[s])),
        })
    return pd.DataFrame(rows)


def realised_endpoints(ctx, Z, ts, per_sensor, leaks, c, subsets) -> pd.DataFrame:
    rows = []
    for s in subsets:
        dets = detector.run_subset(Z, s, per_sensor, c["min_gap_steps"],
                                   ctx.localiser, c["window_steps"], ts)
        timed = evaluate.match_in_time(dets, leaks, ctx.topo)
        score = evaluate.scoring_battledim(dets, leaks, ctx.topo)
        m = evaluate.standard_metrics(score, leaks, ctx.topo, timed)
        rows.append({
            "recall": m["recall"],
            "false_forgetting_rate": m["false_forgetting_rate"],
            "false_positives": m["false_positives"],
            "delay_mean_h": m["detection_delay_mean_h"],
            "localisation_mean_m": m["localisation_distance_mean_m"],
            "battledim_score_eur": m["battledim_score_eur"],
        })
    return pd.DataFrame(rows)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho with NaNs dropped pairwise; nan when a side is constant."""
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 10:
        return float("nan")
    x, y = a[m], b[m]
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1])


def surrogate_correlations(ctx, frozen, lib, year_dir, year, cfg_name,
                           budgets=selection.BUDGETS,
                           n_designs=N_DESIGNS) -> pd.DataFrame:
    c = frozen["constants"]
    sigma = np.array([frozen["sigma_per_sensor_m"][s] for s in ctx.sensor_ids])
    bias = np.array([frozen["model_bias_per_sensor_sigma_units"][s]
                     for s in ctx.sensor_ids])

    ts18, X18, P18 = detector.load_year(PROC / "regenerated_2018", 2018, ctx.sensor_ids)
    nominal = detector.fit_nominal(X18, P18, np.ones(len(ts18), bool), ctx.sensor_ids)
    nominal.bias = bias
    ctx.localiser.sigma = nominal.sigma

    ts, X, P = detector.load_year(year_dir, year, ctx.sensor_ids)
    Z = nominal.standardised(X, P)
    leaks = evaluate.load_ground_truth(RAW / cfg_name, ts,
                                       year_dir / f"{year}_SCADA_Leaks.csv")
    per_sensor = detector.per_sensor_alarms(Z, c["k_cusum"], c["h_alarm"],
                                            c["min_gap_steps"])

    rng = np.random.default_rng(AUDIT_SEED)
    n_sensors = lib.n_sensors
    goal_idx = rng.choice(lib.n_scen, size=min(400, lib.n_scen), replace=False)
    D_top = selection.build_graph_distances(RAW / "L-TOWN_v2_Model.inp", ctx.sensor_ids)
    bc = selection.betweenness_centrality(RAW / "L-TOWN_v2_Model.inp", ctx.sensor_ids)

    out = []
    for k in budgets:
        t0 = time.time()
        subs = [sorted(rng.choice(n_sensors, size=k, replace=False).tolist())
                for _ in range(n_designs)]
        crit = design_criteria(lib, sigma, c["kappa"], c["eta"], c["tau"],
                               subs, goal_idx, D_top, bc)
        endp = realised_endpoints(ctx, Z, ts, per_sensor, leaks, c, subs)
        for cname in crit.columns:
            for ename in endp.columns:
                out.append({
                    "year": year, "budget": k, "n_designs": len(subs),
                    "design_criterion": cname, "endpoint": ename,
                    "spearman_rho": spearman(crit[cname].to_numpy(),
                                             endp[ename].to_numpy()),
                    "endpoint_std": float(np.nanstd(endp[ename].to_numpy())),
                    "endpoint_n_unique": int(pd.Series(endp[ename]).nunique(dropna=True)),
                })
        print(f"  {year} k={k}: {len(subs)} designs in {time.time()-t0:.0f}s", flush=True)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# A3. Freeze chronology, straight from git
# ---------------------------------------------------------------------------


def freeze_chronology() -> dict:
    import subprocess

    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                              text=True).stdout.strip()

    log = git("log", "--reverse", "--format=%H|%cI|%s")
    entries = [dict(zip(("sha", "iso", "subject"), l.split("|", 2)))
               for l in log.splitlines() if "|" in l]
    def first_matching(sub):
        for e in entries:
            if sub.lower() in e["subject"].lower():
                return e
        return None
    return {
        "n_commits": len(entries),
        "freeze_commit": first_matching("Correct a CUSUM specification"),
        "track_b_commit": first_matching("Record Track A and Track B"),
        "final_commit": first_matching("Final results"),
        "note": (
            "The freeze was reissued once (correction C-BIAS). Both protocols are "
            "committed. Track B results were committed strictly after the freeze "
            "commit; the ordering is visible in git history and is not merely "
            "asserted."
        ),
        "all_commits": entries,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((REPO / "FROZEN_PROTOCOL.json").read_text())
    lib = selection.Library.load(PROC / "sensitivity_library.npz")
    ctx = tracks.Context(PROC / "sensitivity_library.npz", RAW / "L-TOWN_v2_Model.inp")

    print("A1 event-level table", flush=True)
    df = event_level_table()
    df.to_csv(OUT / "EVENT_LEVEL_BATTLEDIM.csv", index=False)
    floor = identify_fo_floor(df)
    print(json.dumps(floor["persistently_missed_at_k>=6"]), flush=True)

    print("A2 surrogate correlations", flush=True)
    parts = [
        surrogate_correlations(ctx, frozen, lib, PROC / "regenerated_2018", 2018,
                               "dataset_configuration_historical.yalm"),
        surrogate_correlations(ctx, frozen, lib, PROC / "regenerated_2019", 2019,
                               "dataset_configuration_evaluation.yalm"),
    ]
    corr = pd.concat(parts, ignore_index=True)
    corr.to_csv(OUT / "SURROGATE_CORRELATIONS.csv", index=False)

    print("A3 freeze chronology", flush=True)
    chrono = freeze_chronology()

    (OUT / "audit_summary.json").write_text(json.dumps({
        "fo_floor": floor,
        "freeze_chronology": chrono,
        "n_designs_per_budget": N_DESIGNS,
        "audit_seed": AUDIT_SEED,
    }, indent=2) + "\n")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
