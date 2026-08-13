"""
The three evidence tracks.

TRACK A -- EVENT_HELDOUT_2018
    Leave-One-Leak-Event-Out over the 14 events of 2018. For every fold the
    held-out event is removed from everything that is learned: the nominal
    model is refitted without it, the residual scale sigma is re-estimated
    without it, the alarm threshold is re-calibrated on the leak-free control
    with that fold's model, and every method re-selects its sensors from that
    fold's sigma. Only then is the held-out event scored. FO and all baselines
    go through the identical detector.

TRACK B -- OFFICIAL_ARTEFACT_RECONSTRUCTED_BENCHMARK
    The frozen protocol, unchanged, applied to the regenerated 2019 year. This
    is NOT a validation on the published BattLeDIM SCADA: the published CSVs
    could not be downloaded, the published model artefact repeats its 365-day
    demand patterns in the second year, the released generator adds no
    measurement noise, and the 2019 ground truth was visible during the data
    inventory. Those four caveats travel with every number this track produces.

TRACK C -- SYNTHETIC_ROBUSTNESS_STUDY
    Perturbed demand and sensor noise, with every distribution and parameter
    frozen from 2018 alone. Explicitly synthetic.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector  # noqa: E402
import evaluate  # noqa: E402
import selection  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# Outputs may be redirected to a scratch root for a fixture dry run; the raw
# official artefacts are always read from the repository itself.
WORK = Path(os.environ.get("FO_WORK_ROOT", REPO))
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = WORK / "data" / "processed"
RESULTS = WORK / "results"

METHOD_NAMES = [
    "FO",
    "D_optimal_bayesian",
    "A_optimal_bayesian",
    "E_optimal_observable_subspace",
    "bayesian_information_gain",
    "D_optimal_rank_reduced",
    "A_optimal_rank_reduced",
    "E_optimal_rank_reduced",
    "goal_oriented_oed",
    "topological_dispersion",
    "centrality",
]


# ---------------------------------------------------------------------------
# Shared context
# ---------------------------------------------------------------------------


class Context:
    def __init__(self, library_path: Path, inp_path: Path):
        self.lib = selection.Library.load(library_path)
        self.sensor_ids = [str(s) for s in self.lib.sensors]
        self.topo = evaluate.Topology.build(inp_path)
        sig, pipe_names = evaluate.pipe_level_signatures(
            self.lib.delta, self.lib.scenarios, self.topo
        )
        self.localiser = detector.Localiser(signatures=sig, names=np.array(pipe_names))
        self.topology_cache = (
            selection.build_graph_distances(inp_path, self.sensor_ids),
            selection.betweenness_centrality(inp_path, self.sensor_ids),
        )


def bisect_threshold(Z_noleak: np.ndarray, all_sensors: list[int], k: float,
                     budget: int, min_gap: int, n_iter: int = 8) -> tuple[float, int]:
    """Smallest h (to within the bisection tolerance) giving at most `budget`
    alarms on the leak-free control. Bisection, so ~8 CUSUM sweeps instead of
    a 60-point grid."""
    stat = detector.cusum_statistic(Z_noleak, all_sensors, k)
    lo, hi = 0.0, float(np.nanmax(stat)) * 1.05

    def n_alarms(h: float) -> int:
        ps = detector.per_sensor_alarms(Z_noleak, k, h, min_gap)
        return len(detector.subset_alarms(ps, all_sensors, min_gap))

    if n_alarms(hi) > budget:
        return hi, n_alarms(hi)
    for _ in range(n_iter):
        mid = 0.5 * (lo + hi)
        if n_alarms(mid) <= budget:
            hi = mid
        else:
            lo = mid
    return hi, n_alarms(hi)


def subsets_from_selection(sel: dict, budget: int) -> dict[str, list[int]]:
    b = sel["budgets"][str(budget)]
    out = {name: b[name]["subset"] for name in METHOD_NAMES if name in b}
    return out


# ---------------------------------------------------------------------------
# Running one year for a set of subsets
# ---------------------------------------------------------------------------


def run_year(
    ctx: Context,
    Z: np.ndarray,
    timestamps: pd.DatetimeIndex,
    per_sensor: list[list[int]],
    subsets: dict[str, list[int]],
    random_subsets: list[list[int]],
    leaks: list[evaluate.LeakEvent],
    min_gap: int,
    window: int,
) -> dict:
    out: dict = {"methods": {}, "random": []}
    for name, subset in subsets.items():
        t0 = time.time()
        dets = detector.run_subset(Z, subset, per_sensor, min_gap, ctx.localiser,
                                   window, timestamps)
        score = evaluate.scoring_battledim(dets, leaks, ctx.topo)
        metrics = evaluate.standard_metrics(score, leaks, ctx.topo)
        metrics["compute_time_s"] = round(time.time() - t0, 3)
        metrics["n_detections"] = score["n_detections"]
        out["methods"][name] = {
            "subset": subset,
            "sensor_ids": [ctx.sensor_ids[i] for i in subset],
            "metrics": metrics,
            "score": score,
            "detections": dets,
        }
    for rs in random_subsets:
        dets = detector.run_subset(Z, rs, per_sensor, min_gap, ctx.localiser,
                                   window, timestamps)
        score = evaluate.scoring_battledim(dets, leaks, ctx.topo)
        out["random"].append(
            {
                "subset": rs,
                "score": score,
                "metrics": evaluate.standard_metrics(score, leaks, ctx.topo),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Track A
# ---------------------------------------------------------------------------


def track_a(
    ctx: Context,
    frozen: dict,
    dir_2018: Path,
    dir_noleak: Path,
    budgets=selection.BUDGETS,
) -> dict:
    c = frozen["constants"]
    ts, X, P = detector.load_year(dir_2018, 2018, ctx.sensor_ids)
    tsN, XN, PN = detector.load_year(dir_noleak, 2018, ctx.sensor_ids)
    leaks = evaluate.load_ground_truth(
        RAW / "dataset_configuration_historical.yalm", ts,
        dir_2018 / "2018_SCADA_Leaks.csv",
    )
    all_sensors = list(range(len(ctx.sensor_ids)))
    print(f"Track A: {len(leaks)} events, {len(ts)} samples", flush=True)

    folds = []
    for e, leak in enumerate(leaks):
        t0 = time.time()
        train = np.ones(len(ts), dtype=bool)
        train[leak.start_idx : leak.end_idx + 1] = False   # hold the event out

        nominal = detector.fit_nominal(X, P, train, ctx.sensor_ids)
        Z = nominal.standardised(X, P)
        ZN = nominal.standardised(XN, PN)
        h, n_fa = bisect_threshold(ZN, all_sensors, c["k_cusum"],
                                   c["false_alarm_budget_per_year"], c["min_gap_steps"])
        per_sensor = detector.per_sensor_alarms(Z, c["k_cusum"], h, c["min_gap_steps"])

        sel = selection.select_all(
            lib=ctx.lib, sigma=nominal.sigma, kappa=c["kappa"], eta=c["eta"],
            tau=c["tau"], n_random=c["n_random_replications"], seed=c["seed"] + e,
            inp_path=RAW / "L-TOWN_v2_Model.inp", budgets=budgets,
            allow_exhaustive=False, topology=ctx.topology_cache, verbose=False,
        )

        fold = {
            "held_out_event_index": e,
            "held_out_link": leak.link_id,
            "held_out_type": leak.leak_type,
            "held_out_diameter_m": leak.diameter_m,
            "h_alarm": h,
            "false_alarms_on_noleak": n_fa,
            "budgets": {},
        }
        for k in budgets:
            subs = subsets_from_selection(sel, k)
            rnd = sel["budgets"][str(k)]["random"]["replications"]
            res = run_year(ctx, Z, ts, per_sensor, subs, rnd, leaks,
                           c["min_gap_steps"], c["window_steps"])
            entry = {"methods": {}, "random": []}
            for name, r in res["methods"].items():
                detected, delay, dist = _held_out_detail(r["score"], e)
                entry["methods"][name] = {
                    "subset": r["subset"],
                    "held_out_detected": detected,
                    "held_out_delay_h": delay,
                    "held_out_localisation_m": dist,
                    "false_positives_full_year": r["metrics"]["false_positives"],
                    "battledim_score_eur_full_year": r["metrics"]["battledim_score_eur"],
                    "compute_time_s": r["metrics"]["compute_time_s"],
                }
            for r in res["random"]:
                det_r, _, _ = _held_out_detail(r["score"], e)
                entry["random"].append({"subset": r["subset"], "held_out_detected": det_r})
            fold["budgets"][str(k)] = entry
        fold["wall_clock_s"] = round(time.time() - t0, 1)
        folds.append(fold)
        print(f"  fold {e+1}/{len(leaks)} ({leak.link_id}, {leak.leak_type}) "
              f"h={h:.2f} {fold['wall_clock_s']}s", flush=True)

    return {"track": "EVENT_HELDOUT_2018", "n_events": len(leaks), "folds": folds}


def _held_out_detail(score: dict, e: int):
    """(detected, delay_h, localisation_m) for leak index e, read off the
    official scoring's own matching so Track A and the BattLeDIM score can
    never disagree about what counts as a detection."""
    detected_idx = score["detected_leak_indices"]
    if e not in detected_idx:
        return 0, None, None
    pos = detected_idx.index(e)
    delay_h = score["delays_steps"][pos] * 5.0 / 60.0
    dist_m = score["matched"][pos][2]
    return 1, float(delay_h), float(dist_m)


# ---------------------------------------------------------------------------
# Track B
# ---------------------------------------------------------------------------


def track_b(
    ctx: Context,
    frozen: dict,
    dir_2018: Path,
    dir_2019: Path,
    budgets=selection.BUDGETS,
) -> dict:
    c = frozen["constants"]
    ts18, X18, P18 = detector.load_year(dir_2018, 2018, ctx.sensor_ids)
    nominal = detector.fit_nominal(X18, P18, np.ones(len(ts18), dtype=bool), ctx.sensor_ids)

    ts19, X19, P19 = detector.load_year(dir_2019, 2019, ctx.sensor_ids)
    Z19 = nominal.standardised(X19, P19)
    leaks = evaluate.load_ground_truth(
        RAW / "dataset_configuration_evaluation.yalm", ts19,
        dir_2019 / "2019_SCADA_Leaks.csv",
    )
    per_sensor = detector.per_sensor_alarms(Z19, c["k_cusum"], c["h_alarm"],
                                            c["min_gap_steps"])
    print(f"Track B: {len(leaks)} events, {len(ts19)} samples", flush=True)

    out = {
        "track": "OFFICIAL_ARTEFACT_RECONSTRUCTED_BENCHMARK",
        "not_a_validation_on": "published BattLeDIM SCADA (unreachable, see PROVENANCE.json)",
        "caveats": [
            "F2: the published L-TOWN_v2_Real.inp carries only 365 days of demand "
            "patterns, so regenerated 2019 demands repeat 2018 verbatim",
            "F3: the released dataset_generator.py applies no measurement noise",
            "F4: the 2019 ground truth ships inside the 2018 configuration file and "
            "was visible during the mandatory data inventory",
            "F1: the published 2019 SCADA CSVs could not be downloaded at all",
        ],
        "n_events": len(leaks),
        "budgets": {},
    }
    for k in budgets:
        subs = subsets_from_selection(frozen["selection"], k)
        rnd = frozen["selection"]["budgets"][str(k)]["random"]["replications"]
        res = run_year(ctx, Z19, ts19, per_sensor, subs, rnd, leaks,
                       c["min_gap_steps"], c["window_steps"])
        for r in res["methods"].values():
            r.pop("detections", None)
            r.pop("score", None)
        for r in res["random"]:
            r.pop("score", None)
        out["budgets"][str(k)] = res
        print(f"  budget k={k} done", flush=True)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--track", choices=["a", "b"], required=True)
    ap.add_argument("--library", default=str(PROC / "sensitivity_library.npz"))
    ap.add_argument("--inp", default=str(RAW / "L-TOWN_v2_Model.inp"))
    ap.add_argument("--frozen", default=str(WORK / "FROZEN_PROTOCOL.json"))
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(Path(args.frozen).read_text())
    ctx = Context(Path(args.library), Path(args.inp))

    if args.track == "a":
        res = track_a(ctx, frozen, PROC / "regenerated_2018", PROC / "regenerated_2018_noleak")
        path = RESULTS / "track_a_event_heldout_2018.json"
    else:
        res = track_b(ctx, frozen, PROC / "regenerated_2018", PROC / "regenerated_2019")
        path = RESULTS / "track_b_reconstructed_2019.json"
    path.write_text(json.dumps(res, indent=2) + "\n")
    print(f"wrote {path}")
