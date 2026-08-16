"""Freeze the Phase 16 confirmatory models.

Fits every model on Phase 14 TRAIN+VALID and writes FROZEN_MODELS.json with the
feature list, the standardisation constants and the logistic coefficients. Phase
16 refits NOTHING: it applies these numbers to realisations from seeds that do
not exist yet.

Run BEFORE any Phase 16 seed is generated. The generation script refuses to start
until the protocol file that accompanies this freeze is in place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
P15, P16 = REPO / "phase15_tep", REPO / "phase16_tep"

SCALE_FEATURES = ["fo_d_S", "mean_abs", "rms", "l2_channels", "mahalanobis",
                  "kl_gauss", "iso_d_nearest", "iso_d_mean_others",
                  "iso_kl_nearest", "iso_d_own", "design_size"]

STD = ["mean_abs", "rms", "l2_channels", "mahalanobis", "kl_gauss", "kl_undefined",
       "iso_d_nearest", "iso_d_mean_others", "iso_margin_ratio", "design_size"]
DET_STD = ["mean_abs", "mahalanobis", "kl_gauss", "kl_undefined"]

MODELS = {
    "M0_SNR": ["mean_abs"],
    "M1_FO": ["fo_d_S"],
    "M2_BSTAR": ["b_star"],
    "M3_FO_BSTAR": ["fo_d_S", "b_star"],
    "M4_SNR_FO": ["mean_abs", "fo_d_S"],
    "M5_SNR_FO_BSTAR": ["mean_abs", "fo_d_S", "b_star"],
    "M6_SNR_FO_BSTAR_INT": ["mean_abs", "fo_d_S", "b_star", "fo_x_bstar"],
    "M7_SNR_MAHA_ISO": ["mean_abs", "mahalanobis", "iso_d_nearest"],
    "M8_KL_ISO": ["kl_gauss", "kl_undefined", "iso_kl_nearest"],
    "M9_STANDARD_FULL": STD,
    "M10_STANDARD_PLUS_FO_BSTAR": STD + ["fo_d_S", "b_star", "fo_x_bstar"],
    # H3 pair: does FO add to standard DETECTABILITY (Mahalanobis + KL)?
    "MD_DET_STD": DET_STD,
    "MD_DET_STD_FO": DET_STD + ["fo_d_S"],
    # H7 pair: does standard isolability add to a visibility-only readiness model?
    "MI_VIS_ONLY": ["mean_abs", "fo_d_S"],
    "MI_VIS_ISO": ["mean_abs", "fo_d_S", "iso_d_nearest", "iso_margin_ratio"],
}

# (model_a, model_b) -- a is expected to beat b if the hypothesis holds
HYPOTHESES = {
    "H2_FO_BEYOND_SNR": ("M4_SNR_FO", "M0_SNR"),
    "H3_FO_BEYOND_STANDARD_DETECTABILITY": ("MD_DET_STD_FO", "MD_DET_STD"),
    "H6_FO_BSTAR_SYNERGY": ("M3_FO_BSTAR", "M1_FO"),
    "H7_ISOLABILITY_COMPLEMENT": ("MI_VIS_ISO", "MI_VIS_ONLY"),
    "H8_PROJECT_INCREMENT": ("M10_STANDARD_PLUS_FO_BSTAR", "M9_STANDARD_FULL"),
}


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def main() -> int:
    P16.mkdir(parents=True, exist_ok=True)
    ev = pd.read_csv(P15 / "FEATURES_PHASE15.csv.gz")
    bs = pd.read_csv(P15 / "BSTAR_COMPARISON.csv")
    ev = ev.merge(bs[["design_id", "b_star_equiv"]].rename(
        columns={"b_star_equiv": "b_star"}), on="design_id")

    fit = ev[ev.split.isin(["train", "val"])].copy()
    kl_impute = float(np.median(fit.kl_gauss[np.isfinite(fit.kl_gauss)]))
    kl = np.array(fit.kl_gauss, dtype=float, copy=True)
    undef = ~np.isfinite(kl)
    kl[undef] = kl_impute
    fit["kl_gauss"] = kl
    fit["kl_undefined"] = undef.astype(float)
    for c in SCALE_FEATURES:
        fit[c] = slog(fit[c].to_numpy(float))
    fit["fo_x_bstar"] = fit["fo_d_S"] * fit["b_star"]

    y = fit.failure.to_numpy(int)
    frozen = {}
    for name, feats in MODELS.items():
        X = fit[feats].to_numpy(float)
        mu, sd = X.mean(0), np.maximum(X.std(0), 1e-9)
        clf = LogisticRegression(max_iter=5000, C=1.0).fit((X - mu) / sd, y)
        frozen[name] = {"features": feats, "mu": mu.tolist(), "sd": sd.tolist(),
                        "coef": clf.coef_[0].tolist(),
                        "intercept": float(clf.intercept_[0])}
        print(f"{name:32s} {len(feats):2d} features", flush=True)

    spec = {
        "frozen_on": "2026-08-16",
        "fitted_on": "Phase 14 TRAIN + VALID (735 realisations x 120 designs)",
        "refit_on_phase16": False,
        "scale_features": SCALE_FEATURES,
        "kl_imputation_value": kl_impute,
        "kl_imputation_rule": "TRAIN+VALID median of the finite Gaussian KL; a binary "
                              "kl_undefined flag carries the information. IDV 21 has a "
                              "singular Sigma_f on every seed and is never dropped.",
        "models": frozen,
        "hypotheses": HYPOTHESES,
        "noise_levels": [2.0, 4.0, 8.0],
        "bootstrap": {"kind": "paired, resampling the SEED (the generation unit)",
                      "n_resamples": 2000, "seed": 20260816},
        "practical_threshold": {
            "min_auroc_difference": 0.02,
            "rule": "YES requires the paired CI to exclude 0 AND the point difference to "
                    "reach 0.02. A positive but smaller difference is WEAK, never YES.",
        },
    }
    (P16 / "FROZEN_MODELS.json").write_text(json.dumps(spec, indent=2))
    print(f"\nwrote FROZEN_MODELS.json with {len(frozen)} models", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
