"""
TRACK C -- SYNTHETIC_ROBUSTNESS_STUDY, plus the anti-bias controls.

Everything here is explicitly synthetic. The reconstructed benchmark has no
measurement noise and repeats its demands between years (findings F3 and F2),
so this track puts both back in and asks whether the Track A / Track B ordering
of the methods survives. Every distribution and parameter is frozen from 2018
alone; none of them was chosen after seeing any Track B number.

Perturbations
    sensor noise      i.i.d. Gaussian at multiples {0, 1, 2, 4} of the frozen
                      per-sensor sigma
    demand variation  circular block bootstrap of the 2018 residual field,
                      preserving its spatial correlation across sensors and its
                      temporal autocorrelation within 24 h blocks, at scales
                      {0, 0.5, 1.0}
    seeds             5 per cell

Anti-bias controls (protocol section 10)
    C1 label permutation      leak pipe labels permuted among the events; a
                              genuine spatial advantage must collapse
    C2 multiple seeds         the grid above
    C3 no-leak control        the leak-free 2018 year: any alarm is a false one
    C4 threshold sensitivity  h scaled by {0.5, 0.75, 1, 1.5, 2}; the best h is
                              never selected using 2019
    C5 single sensor failure  each sensor of S removed in turn
    C6 successive removal     sensors removed one at a time down to k=2
    C7 bootstrap by leak      paired resampling over events (src/stats.py)
    C8 bootstrap by period    resampling over calendar blocks of the year

Adverse results are kept. Nothing in this module drops a cell because it is
unfavourable to FO.
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
import tracks  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("FO_WORK_ROOT", REPO))
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = WORK / "data" / "processed"
RESULTS = WORK / "results"

NOISE_MULTIPLIERS = (0.0, 1.0, 2.0, 4.0)
DEMAND_SCALES = (0.0, 0.5, 1.0)
SEEDS = (0, 1, 2, 3, 4)
THRESHOLD_SCALES = (0.5, 0.75, 1.0, 1.5, 2.0)
BLOCK_STEPS = 288  # 24 h blocks for the demand bootstrap
N_PERIOD_BLOCKS = 12


# ---------------------------------------------------------------------------
# Perturbations
# ---------------------------------------------------------------------------


def block_bootstrap_field(residuals: np.ndarray, n_out: int, block: int,
                          rng: np.random.Generator) -> np.ndarray:
    """Circular block bootstrap of a (T, J) residual field.

    Whole time blocks are resampled across ALL sensors at once, so the spatial
    correlation between sensors and the within-block temporal autocorrelation
    are both preserved. This is what makes the injected variation behave like
    demand variation rather than like white noise.
    """
    T = residuals.shape[0]
    n_blocks = int(np.ceil(n_out / block))
    starts = rng.integers(0, T, size=n_blocks)
    idx = (starts[:, None] + np.arange(block)[None, :]) % T
    return residuals[idx.reshape(-1)][:n_out]


def perturb(P: np.ndarray, sigma: np.ndarray, noise_mult: float,
            demand_field: np.ndarray | None, demand_scale: float,
            rng: np.random.Generator) -> np.ndarray:
    out = P.copy()
    if noise_mult > 0:
        out = out + rng.normal(0.0, 1.0, size=P.shape) * (sigma[None, :] * noise_mult)
    if demand_field is not None and demand_scale > 0:
        out = out + demand_scale * demand_field
    return out


# ---------------------------------------------------------------------------
# Core evaluation helper
# ---------------------------------------------------------------------------


def evaluate_subsets(ctx: tracks.Context, Z: np.ndarray, ts: pd.DatetimeIndex,
                     subsets: dict[str, list[int]], leaks, c: dict,
                     h: float) -> dict[str, dict]:
    per_sensor = detector.per_sensor_alarms(Z, c["k_cusum"], h, c["min_gap_steps"])
    out = {}
    for name, subset in subsets.items():
        dets = detector.run_subset(Z, subset, per_sensor, c["min_gap_steps"],
                                   ctx.localiser, c["window_steps"], ts)
        score = evaluate.scoring_battledim(dets, leaks, ctx.topo)
        out[name] = evaluate.standard_metrics(score, leaks, ctx.topo)
    return out


# ---------------------------------------------------------------------------
# Track C
# ---------------------------------------------------------------------------


def main() -> int:
    t_start = time.time()
    frozen = json.loads((WORK / "FROZEN_PROTOCOL.json").read_text())
    c = frozen["constants"]
    ctx = tracks.Context(PROC / "sensitivity_library.npz", RAW / "L-TOWN_v2_Model.inp")
    sigma = np.array([frozen["sigma_per_sensor_m"][s] for s in ctx.sensor_ids])

    dir18, dir19 = PROC / "regenerated_2018", PROC / "regenerated_2019"
    dirNL = PROC / "regenerated_2018_noleak"

    ts18, X18, P18 = detector.load_year(dir18, 2018, ctx.sensor_ids)
    nominal = detector.fit_nominal(X18, P18, np.ones(len(ts18), bool), ctx.sensor_ids)
    resid18 = nominal.residuals(X18, P18)

    ts19, X19, P19 = detector.load_year(dir19, 2019, ctx.sensor_ids)
    leaks19 = evaluate.load_ground_truth(
        RAW / "dataset_configuration_evaluation.yalm", ts19,
        dir19 / "2019_SCADA_Leaks.csv",
    )

    out: dict = {
        "track": "SYNTHETIC_ROBUSTNESS_STUDY",
        "label": "SYNTHETIC -- not a benchmark result",
        "frozen_from": "2018 only; no parameter here was chosen after seeing Track B",
        "grid": {
            "noise_multipliers": list(NOISE_MULTIPLIERS),
            "demand_scales": list(DEMAND_SCALES),
            "seeds": list(SEEDS),
        },
        "cells": [],
        "controls": {},
    }

    # ---- main perturbation grid, on the reconstructed 2019 year ------------
    for k in selection.BUDGETS:
        subsets = tracks.subsets_from_selection(frozen["selection"], k)
        for nm in NOISE_MULTIPLIERS:
            for dsc in DEMAND_SCALES:
                for seed in SEEDS:
                    if nm == 0.0 and dsc == 0.0 and seed != SEEDS[0]:
                        continue  # unperturbed cell is deterministic
                    rng = np.random.default_rng(10_000 * k + 100 * int(nm * 10) + seed)
                    field = (
                        block_bootstrap_field(resid18, len(ts19), BLOCK_STEPS, rng)
                        if dsc > 0 else None
                    )
                    Pp = perturb(P19, sigma, nm, field, dsc, rng)
                    Z = nominal.standardised(X19, Pp)
                    metrics = evaluate_subsets(ctx, Z, ts19, subsets, leaks19, c,
                                               c["h_alarm"])
                    out["cells"].append(
                        {
                            "budget": k, "noise_multiplier": nm,
                            "demand_scale": dsc, "seed": seed,
                            "methods": {
                                n: {
                                    "false_forgetting_rate": m["false_forgetting_rate"],
                                    "recall": m["recall"],
                                    "precision": m["precision"],
                                    "f1": m["f1"],
                                    "false_positives": m["false_positives"],
                                    "battledim_score_eur": m["battledim_score_eur"],
                                }
                                for n, m in metrics.items()
                            },
                        }
                    )
        print(f"  grid budget k={k} done ({time.time()-t_start:.0f}s)", flush=True)

    # ---- C1 label permutation ---------------------------------------------
    perm_rng = np.random.default_rng(c["seed"])
    perm_results = []
    for rep in range(10):
        labels = [lk.link_id for lk in leaks19]
        shuffled = list(perm_rng.permutation(labels))
        permuted = [
            evaluate.LeakEvent(
                link_id=shuffled[i], start_idx=lk.start_idx, end_idx=lk.end_idx,
                leak_type=lk.leak_type, diameter_m=lk.diameter_m, flow_cmh=lk.flow_cmh,
            )
            for i, lk in enumerate(leaks19)
        ]
        Z = nominal.standardised(X19, P19)
        subsets = tracks.subsets_from_selection(frozen["selection"], 8)
        m = evaluate_subsets(ctx, Z, ts19, subsets, permuted, c, c["h_alarm"])
        perm_results.append({n: v["false_forgetting_rate"] for n, v in m.items()})
    out["controls"]["C1_label_permutation"] = {
        "budget": 8, "n_replications": len(perm_results),
        "expectation": "a genuine spatial advantage for FO must collapse here",
        "false_forgetting_rate_per_replication": perm_results,
    }

    # ---- C3 no-leak control ------------------------------------------------
    tsN, XN, PN = detector.load_year(dirNL, 2018, ctx.sensor_ids)
    ZN = nominal.standardised(XN, PN)
    psN = detector.per_sensor_alarms(ZN, c["k_cusum"], c["h_alarm"], c["min_gap_steps"])
    noleak = {}
    for k in selection.BUDGETS:
        subsets = tracks.subsets_from_selection(frozen["selection"], k)
        noleak[str(k)] = {
            n: len(detector.subset_alarms(psN, s, c["min_gap_steps"]))
            for n, s in subsets.items()
        }
    out["controls"]["C3_no_leak_false_alarms"] = {
        "description": "alarms on the leak-free 2018 year; every one is a false alarm",
        "counts_per_budget": noleak,
    }

    # ---- C4 threshold sensitivity -----------------------------------------
    Z19 = nominal.standardised(X19, P19)
    thr = {}
    for scale in THRESHOLD_SCALES:
        h = c["h_alarm"] * scale
        subsets = tracks.subsets_from_selection(frozen["selection"], 8)
        m = evaluate_subsets(ctx, Z19, ts19, subsets, leaks19, c, h)
        thr[str(scale)] = {
            n: {"false_forgetting_rate": v["false_forgetting_rate"],
                "recall": v["recall"], "false_positives": v["false_positives"]}
            for n, v in m.items()
        }
    out["controls"]["C4_threshold_sensitivity"] = {
        "budget": 8, "h_frozen": c["h_alarm"],
        "note": "reported across the whole range; the best h is never selected using 2019",
        "by_scale": thr,
    }

    # ---- C5 / C6 sensor failure and successive removal --------------------
    ps19 = detector.per_sensor_alarms(Z19, c["k_cusum"], c["h_alarm"], c["min_gap_steps"])
    fail, succ = {}, {}
    for k in (8, 12):
        subsets = tracks.subsets_from_selection(frozen["selection"], k)
        fail[str(k)], succ[str(k)] = {}, {}
        for n, s in subsets.items():
            drops = []
            for j in s:
                red = [x for x in s if x != j]
                dets = detector.run_subset(Z19, red, ps19, c["min_gap_steps"],
                                           ctx.localiser, c["window_steps"], ts19)
                sc = evaluate.scoring_battledim(dets, leaks19, ctx.topo)
                drops.append(evaluate.standard_metrics(sc, leaks19, ctx.topo)["false_forgetting_rate"])
            fail[str(k)][n] = {
                "per_sensor_false_forgetting": drops,
                "worst": float(np.max(drops)), "mean": float(np.mean(drops)),
            }
            cur, curve = list(s), []
            while len(cur) > 2:
                cur = cur[:-1]
                dets = detector.run_subset(Z19, cur, ps19, c["min_gap_steps"],
                                           ctx.localiser, c["window_steps"], ts19)
                sc = evaluate.scoring_battledim(dets, leaks19, ctx.topo)
                curve.append(
                    {"size": len(cur),
                     "false_forgetting_rate":
                         evaluate.standard_metrics(sc, leaks19, ctx.topo)["false_forgetting_rate"]}
                )
            succ[str(k)][n] = curve
    out["controls"]["C5_single_sensor_failure"] = fail
    out["controls"]["C6_successive_removal"] = succ

    # ---- C8 bootstrap by calendar period -----------------------------------
    edges = np.linspace(0, len(ts19), N_PERIOD_BLOCKS + 1).astype(int)
    per_block = {}
    subsets = tracks.subsets_from_selection(frozen["selection"], 8)
    for n, s in subsets.items():
        vals = []
        for b in range(N_PERIOD_BLOCKS):
            lo, hi = edges[b], edges[b + 1]
            in_block = [lk for lk in leaks19 if lo <= lk.start_idx < hi]
            if not in_block:
                continue
            dets = detector.run_subset(Z19, s, ps19, c["min_gap_steps"],
                                       ctx.localiser, c["window_steps"], ts19)
            sc = evaluate.scoring_battledim(dets, in_block, ctx.topo)
            vals.append(evaluate.standard_metrics(sc, in_block, ctx.topo)["false_forgetting_rate"])
        per_block[n] = vals
    out["controls"]["C8_bootstrap_by_period"] = {
        "n_blocks": N_PERIOD_BLOCKS, "budget": 8,
        "false_forgetting_rate_per_block": per_block,
    }

    out["wall_clock_s"] = round(time.time() - t_start, 1)
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / "track_c_robustness.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
