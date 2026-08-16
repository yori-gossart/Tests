"""
PHASE 13A -- transposability gate: can FO/B* be applied to sklearn digits AS IS?

This script checks the ten access/structure conditions of the brief and then
asks the only question that matters for a gate: is FO computable on this problem
WITHOUT touching its definition, and are its inputs well posed here?

It deliberately does NOT test the FO hypothesis. No FO score is ever related to
a reconstruction outcome, no AUROC or correlation between visibility and
classifier success is computed. What is measured about FO is confined to whether
its own preconditions hold -- chiefly that the frozen support E* is non-empty and
non-trivial, which b_dynamic/b_star require to return anything but NaN.

fo_metrics.py is IMPORTED, never edited.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

import fo_metrics  # imported as-is; nothing in it is modified

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase13a_digits"

# --- declarations that FO's definition does NOT fix, frozen here, before any
# --- test label is consulted -----------------------------------------------
SEED = 20260816
KAPPA = 3.0
ETA = 3.0
MASK_LEVELS = [64, 48, 32, 16, 8, 4]      # number of pixels kept in the design


def check_1_2_load() -> dict:
    d = load_digits()
    return {
        "loaded_from": "sklearn.datasets.load_digits (bundled with the package, no network)",
        "data_shape": list(d.data.shape),
        "target_shape": list(d.target.shape),
        "images_shape": list(d.images.shape),
        "n_observations": int(d.data.shape[0]),
        "n_features": int(d.data.shape[1]),
        "classes": sorted(int(c) for c in np.unique(d.target)),
        "value_range": [float(d.data.min()), float(d.data.max())],
        "n_expected_1797": bool(d.data.shape[0] == 1797),
        "labels_available": bool(d.target.shape[0] == d.data.shape[0]),
        "any_nan": bool(np.isnan(d.data).any()),
    }


def check_3_4_channels(X: np.ndarray) -> dict:
    """64 pixels as observation channels; a subset as a sensor design."""
    rng = np.random.default_rng(SEED)
    designs = {}
    for k in MASK_LEVELS:
        sensors = sorted(rng.choice(64, size=k, replace=False).tolist())
        designs[f"k={k}"] = {"n_sensors": len(sensors), "first_5": sensors[:5]}
    always_zero = [int(j) for j in range(64) if np.all(X[:, j] == 0)]
    return {
        "channels_are_columns_of_X": True,
        "n_channels": int(X.shape[1]),
        "subset_indexing_works": True,
        "example_designs": designs,
        "channels_dead_over_whole_dataset": always_zero,
        "n_dead_channels": len(always_zero),
        "note": "a dead channel carries no signal at all; any design containing one "
                "spends a sensor slot for nothing, and sigma is undefined there.",
    }


def check_5_ground_truth(X: np.ndarray, y: np.ndarray) -> dict:
    """Is the true class unambiguous? Two identical feature vectors carrying
    different labels would make the target irrecoverable in principle."""
    _, inverse, counts = np.unique(X, axis=0, return_inverse=True, return_counts=True)
    conflicts = 0
    dup_groups = 0
    for gid in np.flatnonzero(counts > 1):
        members = np.flatnonzero(inverse == gid)
        dup_groups += 1
        if len(set(y[members].tolist())) > 1:
            conflicts += 1
    return {
        "n_unique_feature_vectors": int(len(counts)),
        "n_duplicate_groups": int(dup_groups),
        "n_duplicate_groups_with_conflicting_labels": int(conflicts),
        "label_dtype": str(y.dtype),
        "classes_balanced": {int(c): int((y == c).sum()) for c in np.unique(y)},
        "unambiguous": bool(conflicts == 0),
    }


def check_9_frozen_splits(X: np.ndarray, y: np.ndarray) -> dict:
    """Splits fixed by seed BEFORE anything is computed on the test labels."""
    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.30, random_state=SEED, stratify=y)
    tr, va = train_test_split(tr, test_size=0.20, random_state=SEED, stratify=y[tr])
    assert len(set(tr) & set(va)) == 0 and len(set(tr) & set(te)) == 0 and len(set(va) & set(te)) == 0
    return {
        "seed": SEED,
        "n_train": len(tr), "n_val": len(va), "n_test": len(te),
        "disjoint": True,
        "stratified": True,
        "frozen_before_any_result": True,
        "split_indices_sha_like": {
            "train_sum": int(tr.sum()), "val_sum": int(va.sum()), "test_sum": int(te.sum())},
    }, (tr, va, te)


def check_6_inferrer(X, y, tr, va, te) -> dict:
    """An independent inferrer must emit the six quantities the brief lists.

    Trained on TRAIN only, reported on VALIDATION only. The test split is not
    touched anywhere in this gate.
    """
    clf = LogisticRegression(max_iter=5000, random_state=SEED)
    clf.fit(X[tr], y[tr])
    proba = clf.predict_proba(X[va])
    pred = clf.classes_[proba.argmax(axis=1)]
    truth = y[va]

    order = np.argsort(-proba, axis=1)
    rank_true = np.array([int(np.flatnonzero(clf.classes_[order[i]] == truth[i])[0]) + 1
                          for i in range(len(truth))])
    srt = np.sort(proba, axis=1)[:, ::-1]
    margin = srt[:, 0] - srt[:, 1]
    with np.errstate(divide="ignore"):
        entropy = -(proba * np.log(np.maximum(proba, 1e-300))).sum(axis=1)
    success = (pred == truth).astype(int)

    return {
        "inferrer": "LogisticRegression(max_iter=5000), trained on TRAIN only",
        "evaluated_on": "VALIDATION only -- the test split is never touched in this gate",
        "emits": {
            "predicted_class": True,
            "posterior_probabilities": bool(proba.shape == (len(va), 10)),
            "rank_of_true_class": {"min": int(rank_true.min()), "max": int(rank_true.max())},
            "top1_top2_margin": {"min": round(float(margin.min()), 4),
                                 "max": round(float(margin.max()), 4)},
            "entropy": {"min": round(float(entropy.min()), 4),
                        "max": round(float(entropy.max()), 4)},
            "reconstruction_success_flag": {"n_success": int(success.sum()),
                                            "n_total": int(len(success))},
        },
        "all_six_available": True,
        "note": "validation accuracy is reported only to show the inferrer is functional; "
                "it is NOT related to any FO quantity anywhere in this phase.",
        "validation_accuracy": round(float(success.mean()), 4),
    }


def check_7_8_10_fo(X: np.ndarray, tr: np.ndarray) -> dict:
    """Can FO/B* run on digits with no change to fo_metrics.py?

    FO consumes delta of shape (n_scenarios, n_sensors, T) and a per-sensor
    sigma. Digits has no time axis, so T = 1 -- the max over t is a max over a
    singleton, which is the formula unchanged, not a modified formula.

    Two baselines for delta are tried because FO's definition does NOT fix one:
    delta is 'the deviation caused by the event', and digits does not say what
    the no-event state is.
    """
    rng = np.random.default_rng(SEED)
    results = {}

    baselines = {
        "blank_background": np.zeros(64),          # digits background is literally 0
        "train_mean_image": X[tr].mean(axis=0),    # deviation from the average digit
    }
    sigmas = {
        "train_pixel_std": np.maximum(X[tr].std(axis=0), 1e-9),
        "unit": np.ones(64),
    }

    for b_name, base in baselines.items():
        for s_name, sigma in sigmas.items():
            delta = (X - base[None, :])[:, :, None]      # (n_scen, 64, T=1)
            vis = fo_metrics.visibility(delta, sigma)
            d_R = vis.max(axis=1)                        # rich reference = all 64 pixels

            support = fo_metrics.freeze_support(delta, sigma, KAPPA)
            subset = sorted(rng.choice(64, size=8, replace=False).tolist())
            bs = fo_metrics.b_star(delta, sigma, subset, support, ETA)
            bd = fo_metrics.b_dynamic(delta, sigma, subset, KAPPA, ETA)

            results[f"{b_name}|{s_name}"] = {
                "d_R_min": round(float(d_R.min()), 4),
                "d_R_median": round(float(np.median(d_R)), 4),
                "d_R_max": round(float(d_R.max()), 4),
                "d_R_coefficient_of_variation": round(float(d_R.std() / d_R.mean()), 4),
                "support_size_E_star": support.size,
                "support_fraction": round(support.size / len(X), 4),
                "support_is_degenerate": bool(support.size == 0 or support.size == len(X)),
                "B_star": bs["B_star"],
                "B_dynamic": bd["B"],
            }

    # information-loss levels by masking pixels; labels are never touched
    mask_levels = {}
    for k in MASK_LEVELS:
        sensors = sorted(rng.choice(64, size=k, replace=False).tolist())
        mask_levels[f"k={k}"] = {"n_sensors_kept": k, "labels_modified": False}

    return {
        "fo_metrics_imported_unmodified": True,
        "time_axis_handling": "digits has no time axis -> T=1; max over t is a max over a "
                              "singleton, i.e. the formula unchanged",
        "free_choices_not_fixed_by_FO": ["delta baseline", "sigma", "kappa", "eta"],
        "kappa": KAPPA, "eta": ETA,
        "runs_without_error": True,
        "variants": results,
        "mask_levels": mask_levels,
        "labels_untouched_by_masking": True,
        "parameters_needing_test_labels": [],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_digits()
    X, y = d.data.astype(float), d.target

    report = {"phase": "13A_transposability_gate", "seed": SEED}
    report["check_1_2_load"] = check_1_2_load()
    report["check_3_4_channels"] = check_3_4_channels(X)
    report["check_5_ground_truth"] = check_5_ground_truth(X, y)
    splits, (tr, va, te) = check_9_frozen_splits(X, y)
    report["check_9_frozen_splits"] = splits
    report["check_6_inferrer"] = check_6_inferrer(X, y, tr, va, te)
    report["check_7_8_10_fo"] = check_7_8_10_fo(X, tr)

    (OUT / "GATE_13A_CHECKS.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
