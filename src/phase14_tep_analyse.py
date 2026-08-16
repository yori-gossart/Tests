"""
PHASE TEP -- execution of the FROZEN protocol (PROTOCOLE_PREENREGISTRE_TEP.json,
commit cb307f9).

fo_metrics.py is imported, never edited. Every threshold, split, design list and
hyper-parameter comes from the frozen JSON and none is touched here.

TWO CONVENTIONS THE PROTOCOL DID NOT PIN DOWN, DECLARED BEFORE ANY RESULT
------------------------------------------------------------------------
1. Confidence intervals. The protocol asks for 95% CIs without naming a method.
   Used throughout: percentile bootstrap over the INDEPENDENCE UNIT, i.e. the
   (disturbance, seed) realisation, 2000 resamples, seeded 20260816. Bootstrapping
   scenarios rather than (scenario, design) pairs is what keeps rule 9 -- a time
   step, and equally a design, is not an extra experiment.

2. Direction of each score. FO asserts a priori that LOW visibility means the
   event is hard to reconstruct, so the discriminant for FAILURE is -d_S. Every
   baseline gets the direction its own a priori meaning implies, fixed here and
   never flipped afterwards:

       fo_d_S                 -x   low visibility  -> failure
       snr_mean               -x   low SNR         -> failure
       count_above_3sigma     -x   few loud channels -> failure
       smallest_singular_value -x  ill-conditioned -> failure
       design_size            -x   fewer sensors   -> failure
       entropy                +x   high entropy    -> failure
       top1_top2_margin       -x   small margin    -> failure

   An AUROC below 0.5 therefore means the score works OPPOSITE to its stated
   claim, and is reported as such rather than silently re-signed.

PRIMARY STATISTIC
-----------------
AUROC is computed per design over the 315 independent TEST realisations, then
averaged across the 120 frozen designs. The bootstrap resamples realisations and
recomputes the whole per-design set, so the CI reflects scenario sampling, not
design sampling. A pooled (design x scenario) analysis is also reported, flagged
as violating independence, because the design-size control is only testable there.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fo_metrics

REPO = Path(__file__).resolve().parents[1]
P14 = REPO / "phase14_tep"
PROTO = json.loads((P14 / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
GEN = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")
TEPSRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
              "scratchpad/tep/tennessee-eastman-profBraatz")

SEEDS = PROTO["seeds"]["list"]
FAULTS = PROTO["disturbances"]["ids"]
KAPPA = PROTO["fo_inputs"]["kappa"]
ETA = PROTO["fo_inputs"]["eta"]
SIZES = PROTO["sensor_designs"]["design_sizes"]
N_DESIGNS = PROTO["sensor_designs"]["designs_per_size"]
DESIGN_SEED = 20260816
NOISE_LEVELS = PROTO["noise_axis"]["levels"]
TRAIN_IDX = list(range(0, 25))
VAL_IDX = list(range(25, 35))
TEST_IDX = list(range(35, 50))
N_BOOT = 2000
BOOT_SEED = 20260816

DIRECTION = {                       # +1: high = failure, -1: low = failure
    "fo_d_S": -1, "snr_mean": -1, "count_above_3sigma": -1,
    "smallest_singular_value": -1, "design_size": -1,
    "entropy": +1, "top1_top2_margin": -1,
}
BASELINES = ["entropy", "top1_top2_margin", "snr_mean", "count_above_3sigma",
             "smallest_singular_value", "design_size"]


# ------------------------------------------------------------------ loading

def load_sigma() -> np.ndarray:
    import re
    src = (TEPSRC / "teprob.f").read_text()
    xns = [float(m.group(2)) for m in re.finditer(r"XNS\((\d+)\)=([0-9.]+)D0", src)]
    assert len(xns) == 41 and min(xns) > 0
    return np.asarray(xns, dtype=float)


def load_bank(path: Path) -> dict:
    z = np.load(path)
    out = {}
    for key in z.files:
        k, si = key.split("_")
        out[(int(k), int(si))] = z[key]
    return out


def build(bank: dict, seed_idx: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """delta (n,41,T), observed fault signal (n,41,T), fault id, seed idx."""
    d, obs, yf, ys = [], [], [], []
    for si in seed_idx:
        base = bank[(0, si)].astype(np.float64)
        for k in FAULTS:
            f = bank[(k, si)].astype(np.float64)
            d.append(f - base)
            obs.append(f)
            yf.append(k)
            ys.append(si)
    return np.stack(d), np.stack(obs), np.asarray(yf), np.asarray(ys)


# ------------------------------------------------------------------ designs

def frozen_designs() -> list[dict]:
    rng = np.random.default_rng(DESIGN_SEED)
    designs = []
    for size in SIZES:
        for rep in range(N_DESIGNS):
            ch = sorted(rng.choice(41, size=size, replace=False).tolist())
            designs.append({"design_id": len(designs), "size": size, "rep": rep,
                            "channels": ch})
    return designs


# ------------------------------------------------------------------ features

def features(obs: np.ndarray, ch: list[int]) -> np.ndarray:
    """Per-channel mean, std, min, max, last over the post-fault window, on S."""
    x = obs[:, ch, :]
    return np.concatenate([x.mean(2), x.std(2), x.min(2), x.max(2), x[:, :, -1]], axis=1)


# ------------------------------------------------------------------ scores

def scores_for_design(delta: np.ndarray, sigma: np.ndarray, ch: list[int],
                      proba: np.ndarray, classes: np.ndarray,
                      y_true: np.ndarray) -> dict:
    vis = fo_metrics.visibility(delta, sigma)          # (n, 41), fo_metrics unmodified
    d_S = vis[:, ch].max(axis=1)

    srt = np.sort(proba, axis=1)[:, ::-1]
    margin = srt[:, 0] - srt[:, 1]
    with np.errstate(divide="ignore"):
        entropy = -(proba * np.log(np.maximum(proba, 1e-300))).sum(axis=1)

    std = delta[:, ch, :] / sigma[None, ch, None]
    snr_mean = np.abs(std).mean(axis=(1, 2))
    count3 = (vis[:, ch] > 3.0).sum(axis=1).astype(float)
    ssv = np.array([np.linalg.svd(std[i], compute_uv=False)[-1] for i in range(std.shape[0])])

    pred = classes[proba.argmax(axis=1)]
    order = np.argsort(-proba, axis=1)
    rank = np.array([int(np.flatnonzero(classes[order[i]] == y_true[i])[0]) + 1
                     for i in range(len(y_true))])
    p_true = np.array([proba[i, np.flatnonzero(classes == y_true[i])[0]]
                       for i in range(len(y_true))])
    return {
        "fo_d_S": d_S, "entropy": entropy, "top1_top2_margin": margin,
        "snr_mean": snr_mean, "count_above_3sigma": count3,
        "smallest_singular_value": ssv,
        "design_size": np.full(len(d_S), float(len(ch))),
        "top1_correct": (pred == y_true).astype(int),
        "rank_true": rank, "reciprocal_rank": 1.0 / rank,
        "posterior_true": p_true,
        "log_loss": -np.log(np.maximum(p_true, 1e-300)),
        "top5_correct": np.array([int(y_true[i] in classes[order[i, :5]])
                                  for i in range(len(y_true))]),
    }


def auroc(score: np.ndarray, failure: np.ndarray, name: str) -> float:
    if failure.sum() == 0 or failure.sum() == len(failure):
        return float("nan")
    if np.ptp(score) == 0:
        return 0.5
    return float(roc_auc_score(failure, DIRECTION[name] * score))


def auprc(score: np.ndarray, failure: np.ndarray, name: str) -> float:
    if failure.sum() == 0:
        return float("nan")
    return float(average_precision_score(failure, DIRECTION[name] * score))


# ------------------------------------------------------------------- driver

def main() -> int:
    t0 = time.time()
    res = P14 / "results"
    res.mkdir(parents=True, exist_ok=True)
    sigma = load_sigma()
    bank = load_bank(GEN / "nominal.npz")
    designs = frozen_designs()
    print(f"loaded {len(bank)} runs, {len(designs)} frozen designs", flush=True)

    d_tr, o_tr, y_tr, s_tr = build(bank, TRAIN_IDX)
    d_va, o_va, y_va, s_va = build(bank, VAL_IDX)
    d_te, o_te, y_te, s_te = build(bank, TEST_IDX)
    print(f"scenarios: train {len(y_tr)}  val {len(y_va)}  test {len(y_te)}", flush=True)

    # --- stopping rule: E* must not be degenerate ---------------------------
    support = fo_metrics.freeze_support(d_tr, sigma, KAPPA)
    gate_support = 0 < support.size < len(y_tr)
    print(f"E* frozen on TRAIN: {support.size}/{len(y_tr)}  non-degenerate={gate_support}",
          flush=True)

    rows, per_design, stop = [], [], {}
    for di, dd in enumerate(designs):
        ch = dd["channels"]
        rf = RandomForestClassifier(n_estimators=500, random_state=DESIGN_SEED, n_jobs=-1)
        rf.fit(features(o_tr, ch), y_tr)

        if dd["size"] == 41 and dd["rep"] == 0:
            acc_tr = float(rf.score(features(o_tr, ch), y_tr))
            stop["inferrer_train_accuracy_full_design"] = acc_tr
            stop["inferrer_fit_gate_pass"] = bool(acc_tr >= 0.30)
            print(f"  stopping-rule check: RF train accuracy on 41-channel design = {acc_tr:.4f}",
                  flush=True)

        for split, (dl, ob, yy, ss) in [("val", (d_va, o_va, y_va, s_va)),
                                        ("test", (d_te, o_te, y_te, s_te))]:
            proba = rf.predict_proba(features(ob, ch))
            sc = scores_for_design(dl, sigma, ch, proba, rf.classes_, yy)
            df = pd.DataFrame({k: v for k, v in sc.items()})
            df["design_id"] = di
            df["design_size"] = dd["size"]
            df["design_rep"] = dd["rep"]
            df["split"] = split
            df["fault"] = yy
            df["seed_idx"] = ss
            df["failure"] = 1 - df["top1_correct"]
            rows.append(df)

            fail = df["failure"].to_numpy()
            entry = {"design_id": di, "size": dd["size"], "rep": dd["rep"], "split": split,
                     "n": len(fail), "n_fail": int(fail.sum()),
                     "accuracy": float(df["top1_correct"].mean())}
            for nm in ["fo_d_S"] + BASELINES:
                entry[f"auroc_{nm}"] = auroc(df[nm].to_numpy(), fail, nm)
                entry[f"auprc_{nm}"] = auprc(df[nm].to_numpy(), fail, nm)
            per_design.append(entry)
        if (di + 1) % 20 == 0:
            print(f"  {di+1}/{len(designs)} designs  ({time.time()-t0:.0f}s)", flush=True)

    events = pd.concat(rows, ignore_index=True)
    events.to_csv(res / "EVENT_LEVEL_TEP.csv.gz", index=False, compression="gzip")
    pd.DataFrame(per_design).to_csv(res / "PER_DESIGN_METRICS.csv", index=False)
    print(f"event rows: {len(events)}  ({time.time()-t0:.0f}s)", flush=True)

    json.dump({"support_size": support.size, "n_train": int(len(y_tr)),
               "support_non_degenerate": bool(gate_support), **stop},
              open(res / "STOPPING_RULES.json", "w"), indent=2)
    np.save(res / "support_mask.npy", support.mask)
    print("phase 1 complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
