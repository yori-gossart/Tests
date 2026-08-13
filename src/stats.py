"""
Paired statistics for FO against each baseline.

Comparisons are paired by event (Track A, Track B) or by scenario, because both
methods are run on the same leaks with the same detector -- the only difference
is which sensors they were allowed to use. Pairing removes the event-difficulty
variance that would otherwise swamp the effect.

For every comparison we report the FO minus baseline difference, a 95 percent
confidence interval from 10000 paired bootstrap resamples, and both the absolute
and the relative difference.

PRE-REGISTERED DECISION RULES (project-internal, not field standards)
---------------------------------------------------------------------
Primary : FO reduces the false-forgetting rate with a 95 percent CI entirely on
          the favourable side of zero.
Interest: at least 20 percent relative reduction of the false-forgetting rate.
Non-inferiority of recall: FO may lose at most 2 percentage points of recall.
"""

from __future__ import annotations

import numpy as np

N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20180101
REL_REDUCTION_TARGET = 0.20
RECALL_NONINFERIORITY_MARGIN = 0.02


def paired_bootstrap(
    fo: np.ndarray,
    base: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    lower_is_better: bool = True,
) -> dict:
    """Bootstrap the paired difference FO - baseline over the shared units.

    fo, base : per-unit values (one entry per leak event / scenario), aligned.
    """
    fo = np.asarray(fo, dtype=float)
    base = np.asarray(base, dtype=float)
    if fo.shape != base.shape:
        raise ValueError(f"unpaired inputs: {fo.shape} vs {base.shape}")
    n = len(fo)
    if n == 0:
        return {"n": 0, "error": "no paired units"}

    d = fo - base
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_d = d[idx].mean(axis=1)
    boot_fo = fo[idx].mean(axis=1)
    boot_base = base[idx].mean(axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        boot_rel = np.where(boot_base != 0, boot_d / boot_base, np.nan)

    lo, hi = np.percentile(boot_d, [2.5, 97.5])
    rel_lo, rel_hi = np.nanpercentile(boot_rel, [2.5, 97.5])
    mean_fo, mean_base = float(fo.mean()), float(base.mean())
    diff = mean_fo - mean_base
    rel = diff / mean_base if mean_base != 0 else float("nan")

    # "Favourable" means below zero when lower is better.
    ci_favourable = bool(hi < 0) if lower_is_better else bool(lo > 0)

    return {
        "n_units": int(n),
        "n_bootstrap": int(n_boot),
        "seed": int(seed),
        "mean_fo": mean_fo,
        "mean_baseline": mean_base,
        "absolute_difference": float(diff),
        "relative_difference": float(rel),
        "ci95_absolute": [float(lo), float(hi)],
        "ci95_relative": [float(rel_lo), float(rel_hi)],
        "ci_entirely_favourable": ci_favourable,
        "lower_is_better": bool(lower_is_better),
    }


def evaluate_decision_rules(ff_stat: dict, recall_stat: dict) -> dict:
    """Apply the pre-registered rules to one FO-vs-baseline comparison."""
    primary = bool(ff_stat.get("ci_entirely_favourable", False))
    rel = ff_stat.get("relative_difference", float("nan"))
    # false-forgetting is lower-is-better, so a reduction is a negative diff
    interest = bool(rel <= -REL_REDUCTION_TARGET) if np.isfinite(rel) else False
    recall_loss = -recall_stat.get("absolute_difference", float("nan"))
    non_inferior = bool(recall_loss <= RECALL_NONINFERIORITY_MARGIN) if np.isfinite(recall_loss) else False
    return {
        "primary_ci_favourable": primary,
        "relative_reduction": float(rel) if np.isfinite(rel) else None,
        "meets_20pct_relative_reduction": interest,
        "recall_loss_points": float(recall_loss) if np.isfinite(recall_loss) else None,
        "recall_non_inferior_2pt": non_inferior,
    }


def compare_against_random(
    fo_value: float, random_values: np.ndarray, lower_is_better: bool = True
) -> dict:
    """Where FO sits in the distribution of >=100 random placements."""
    r = np.asarray(random_values, dtype=float)
    if lower_is_better:
        beaten = float(np.mean(r > fo_value))
        pct = float(np.mean(r <= fo_value) * 100)
    else:
        beaten = float(np.mean(r < fo_value))
        pct = float(np.mean(r >= fo_value) * 100)
    return {
        "n_random": int(len(r)),
        "fo_value": float(fo_value),
        "random_mean": float(np.mean(r)),
        "random_std": float(np.std(r, ddof=1)) if len(r) > 1 else 0.0,
        "random_min": float(np.min(r)),
        "random_max": float(np.max(r)),
        "fraction_of_random_beaten_by_fo": beaten,
        "fo_percentile_in_random": pct,
    }
