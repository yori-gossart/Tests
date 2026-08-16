"""PHASE 15 -- exploratory autopsy A-E on the Phase 14 data.

EXPLORATORY. Nothing here confirms anything. Models are fit on TRAIN and
compared on VALID only; the Phase 14 TEST split is reported once for context and
is not used to choose anything.

Feature transforms, declared once and applied identically everywhere: every
scale-like statistic enters as signed log1p, because the visibility family spans
four orders of magnitude (d_S runs 0 to ~1450) and a linear logistic term would
be dominated by the upper tail. B* is a proportion and enters untransformed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fo_metrics
import tep_metrics as TM

REPO = Path(__file__).resolve().parents[1]
P15 = REPO / "phase15_tep"
P14 = REPO / "phase14_tep"
PROTO = json.loads((P14 / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
GEN = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")
TEPSRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
              "scratchpad/tep/tennessee-eastman-profBraatz")
FAULTS = PROTO["disturbances"]["ids"]
KAPPA, ETA = PROTO["fo_inputs"]["kappa"], PROTO["fo_inputs"]["eta"]
BOOT, SEED = 2000, 20260816

SCALE_FEATURES = ["fo_d_S", "mean_abs", "rms", "l2_channels", "mahalanobis",
                  "kl_gauss", "iso_d_nearest", "iso_d_mean_others",
                  "iso_kl_nearest", "iso_d_own", "design_size"]

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
    "M9_STANDARD_FULL": ["mean_abs", "rms", "l2_channels", "mahalanobis", "kl_gauss",
                         "kl_undefined", "iso_d_nearest", "iso_d_mean_others",
                         "iso_margin_ratio", "design_size"],
    "M10_STANDARD_PLUS_FO_BSTAR": ["mean_abs", "rms", "l2_channels", "mahalanobis",
                                   "kl_gauss", "kl_undefined", "iso_d_nearest",
                                   "iso_d_mean_others", "iso_margin_ratio", "design_size",
                                   "fo_d_S", "b_star", "fo_x_bstar"],
}


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def prep(ev: pd.DataFrame, kl_impute: float | None = None) -> tuple[pd.DataFrame, float]:
    """Transform features and handle the one metric that is genuinely undefined.

    The Gaussian KL needs a non-degenerate Sigma_f. IDV 21 produces a deviation
    of zero to machine precision on every seed, so its covariance is singular and
    the divergence is +inf -- not a large value, an undefined one. The mission
    anticipates this ("lorsque mathematiquement definissable").

    Treatment is the standard missing-indicator one: a binary kl_undefined flag
    carries the information, and kl_gauss itself is imputed at the TRAIN median
    of its finite values. The median is deliberately neutral. Mapping +inf to a
    large KL would assert that these realisations are highly detectable, which is
    backwards -- the infinity comes from -ln det Sigma_f blowing up on a point
    mass, not from any signal. IDV 21 is never dropped.
    """
    d = ev.copy()
    kl = np.array(d["kl_gauss"], dtype=float, copy=True)
    undef = ~np.isfinite(kl)
    if kl_impute is None:
        kl_impute = float(np.median(kl[np.isfinite(kl)]))
    kl[undef] = kl_impute
    d["kl_gauss"] = kl
    d["kl_undefined"] = undef.astype(float)
    for c in SCALE_FEATURES:
        d[c] = slog(d[c].to_numpy(float))
    d["fo_x_bstar"] = d["fo_d_S"] * d["b_star"]
    return d, kl_impute


def design_level_bstar(ev: pd.DataFrame, support: np.ndarray) -> pd.DataFrame:
    """B* and the rival tail statistics, per design, on the SAME frozen support."""
    tr = ev[ev.split == "train"]
    out = []
    for did, g in tr.groupby("design_id"):
        g = g.sort_values(["seed_idx", "fault"])
        d_S = g.fo_d_S.to_numpy(float)
        row = {"design_id": did, "design_size": int(g.design_size.iloc[0])}
        row.update(TM.tail_statistics(d_S, support, ETA))
        out.append(row)
    return pd.DataFrame(out)


def fit_eval(train: pd.DataFrame, evalset: pd.DataFrame, feats: list[str]) -> dict:
    Xtr, ytr = train[feats].to_numpy(float), train.failure.to_numpy(int)
    Xev, yev = evalset[feats].to_numpy(float), evalset.failure.to_numpy(int)
    mu, sd = Xtr.mean(0), np.maximum(Xtr.std(0), 1e-9)
    clf = LogisticRegression(max_iter=5000, C=1.0)
    clf.fit((Xtr - mu) / sd, ytr)
    p = clf.predict_proba((Xev - mu) / sd)[:, 1]
    return {"p": p, "y": yev, "coef": dict(zip(feats, clf.coef_[0].round(4))),
            "auroc": roc_auc_score(yev, p), "auprc": average_precision_score(yev, p),
            "brier": brier_score_loss(yev, p), "log_loss": log_loss(yev, p),
            "calib_slope": float(np.polyfit(p, yev, 1)[0])}


def paired_boot(pA, pB, y, groups, n=BOOT, seed=SEED) -> dict:
    """Paired bootstrap of the AUROC difference, resampling the GROUP (seed)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx_by = {g: np.flatnonzero(groups == g) for g in uniq}
    diffs = np.empty(n)
    for b in range(n):
        pick = rng.choice(uniq, len(uniq), replace=True)
        idx = np.concatenate([idx_by[g] for g in pick])
        yy = y[idx]
        if yy.min() == yy.max():
            diffs[b] = np.nan
            continue
        diffs[b] = roc_auc_score(yy, pA[idx]) - roc_auc_score(yy, pB[idx])
    lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
    return {"delta_auroc": float(roc_auc_score(y, pA) - roc_auc_score(y, pB)),
            "ci_lo": float(lo), "ci_hi": float(hi), "ci_excludes_zero": bool(lo > 0)}


def main() -> int:
    (P15 / "figures").mkdir(parents=True, exist_ok=True)
    ev = pd.read_csv(P15 / "FEATURES_PHASE15.csv.gz")
    support = np.load(P15 / "support_mask_train.npy")
    print(f"features: {len(ev)} rows, {ev.design_id.nunique()} designs", flush=True)

    out = {}

    # ---------- A1: is FO the same object as max|delta|/sigma? --------------
    out["A_identity_check"] = {
        "max_abs_diff_fo_vs_max_abs": float(np.abs(ev.fo_d_S - ev.max_abs).max()),
        "note": "FO's per-scenario score d_S IS max_{j in S, t} |delta|/sigma_j. "
                "Not an approximation -- the same statistic under another name.",
    }

    # ---------- A2: FO against the standard visibility family ---------------
    bs = design_level_bstar(ev, support)
    ev = ev.merge(bs[["design_id", "b_star_equiv"]].rename(
        columns={"b_star_equiv": "b_star"}), on="design_id", how="left")
    d_tr_raw = ev[ev.split == "train"]
    kl_impute = float(np.median(d_tr_raw.kl_gauss[np.isfinite(d_tr_raw.kl_gauss)]))
    d, _ = prep(ev, kl_impute)
    tr, va, te = (d[d.split == s].copy() for s in ("train", "val", "test"))
    out["A_kl_domain"] = {
        "rows_undefined": int((~np.isfinite(ev.kl_gauss)).sum()),
        "realisations_undefined": int(ev[~np.isfinite(ev.kl_gauss)][["fault", "seed_idx"]]
                                      .drop_duplicates().shape[0]),
        "faults_affected": sorted(ev[~np.isfinite(ev.kl_gauss)].fault.unique().tolist()),
        "train_median_imputation": kl_impute,
        "note": "IDV 21 has zero deviation to machine precision on every seed, so "
                "Sigma_f is singular and the Gaussian KL is undefined, not large. "
                "Missing-indicator treatment; the fault is never dropped.",
    }

    vis_family = ["fo_d_S", "mean_abs", "rms", "l2_channels", "mahalanobis", "kl_gauss"]
    rows = []
    for split, dd in [("train", tr), ("val", va), ("test", te)]:
        y = dd.failure.to_numpy(int)
        for m in vis_family + ["iso_d_nearest", "iso_margin_ratio", "rf_entropy", "rf_margin"]:
            x = dd[m].to_numpy(float)
            sign = +1 if m == "rf_entropy" else -1
            # kl_gauss is scored only where it is defined; the coverage is reported
            keep = (dd.kl_undefined.to_numpy() == 0) if m == "kl_gauss" else np.ones(len(dd), bool)
            yy = y[keep]
            rows.append({"split": split, "metric": m, "n_scored": int(keep.sum()),
                         "coverage": float(keep.mean()),
                         "auroc": roc_auc_score(yy, sign * x[keep]),
                         "auprc": average_precision_score(yy, sign * x[keep]),
                         "spearman_logloss": float(stats.spearmanr(x[keep], dd.log_loss[keep])[0])})
    out["A_visibility_family"] = rows

    corr = {}
    for m in vis_family:
        corr[m] = {"spearman_vs_fo": float(stats.spearmanr(tr.fo_d_S, tr[m])[0]),
                   "pearson_vs_fo": float(np.corrcoef(tr.fo_d_S, tr[m])[0, 1])}
    mi = mutual_info_classif(
        tr[["fo_d_S", "mean_abs"]].to_numpy(float), tr.failure.to_numpy(int),
        random_state=SEED)
    corr["mutual_information_bits"] = {"fo_d_S": float(mi[0] / np.log(2)),
                                       "mean_abs": float(mi[1] / np.log(2))}
    out["A_fo_vs_snr_association"] = corr

    # ---------- A3 + D: the model ladder ------------------------------------
    fitted, model_rows = {}, []
    for name, feats in MODELS.items():
        r = fit_eval(tr, va, feats)
        fitted[name] = r
        model_rows.append({"model": name, "n_features": len(feats), "split": "val",
                           **{k: r[k] for k in ("auroc", "auprc", "brier", "log_loss",
                                                "calib_slope")},
                           "features": "|".join(feats)})
    out["D_model_ladder"] = model_rows

    groups = va.seed_idx.to_numpy()
    y = va.failure.to_numpy(int)
    comps = [("M4_SNR_FO", "M0_SNR", "H2 FO beyond SNR"),
             ("M10_STANDARD_PLUS_FO_BSTAR", "M9_STANDARD_FULL", "H8 project increment"),
             ("M1_FO", "M0_SNR", "FO alone vs SNR alone"),
             ("M5_SNR_FO_BSTAR", "M4_SNR_FO", "B* on top of SNR+FO"),
             ("M3_FO_BSTAR", "M1_FO", "H6 synergy: B* adds to FO"),
             ("M3_FO_BSTAR", "M2_BSTAR", "H6 synergy: FO adds to B*"),
             ("M6_SNR_FO_BSTAR_INT", "M5_SNR_FO_BSTAR", "interaction term"),
             ("M10_STANDARD_PLUS_FO_BSTAR", "M7_SNR_MAHA_ISO", "vs compact standard"),
             ("M9_STANDARD_FULL", "M0_SNR", "standard ensemble vs SNR")]
    out["D_paired_comparisons"] = [
        {"model_a": a, "model_b": b, "question": q,
         **paired_boot(fitted[a]["p"], fitted[b]["p"], y, groups)}
        for a, b, q in comps]

    # ---------- B: isolability and the faults where FO failed ---------------
    per_fault = []
    for split, dd in [("val", va), ("test", te)]:
        for k in FAULTS:
            g = dd[dd.fault == k]
            fail = g.failure.to_numpy(int)
            row = {"split": split, "fault": k, "n": len(g),
                   "failure_rate": float(fail.mean()),
                   "median_fo_d_S": float(np.expm1(g.fo_d_S).median()),
                   "median_iso_d_nearest": float(np.expm1(g.iso_d_nearest).median()),
                   "median_iso_margin_ratio": float(g.iso_margin_ratio.median()),
                   "median_mahalanobis": float(np.expm1(g.mahalanobis).median())}
            for m, sgn in [("fo_d_S", -1), ("iso_d_nearest", -1),
                           ("iso_margin_ratio", -1), ("mahalanobis", -1)]:
                row[f"auroc_{m}"] = (roc_auc_score(fail, sgn * g[m]) if 0 < fail.sum() < len(fail)
                                     else float("nan"))
            per_fault.append(row)
    out["B_per_fault"] = per_fault

    # ---------- C: B* structural and operational ----------------------------
    tail_cols = ["b_star_equiv", "q05", "q10", "minimum", "mean", "cvar05", "cvar10"]
    rate = (ev[ev.split == "val"].groupby("design_id").failure.mean()
            .rename("val_failure_rate").reset_index())
    rate_te = (ev[ev.split == "test"].groupby("design_id").failure.mean()
               .rename("test_failure_rate").reset_index())
    bs = bs.merge(rate, on="design_id").merge(rate_te, on="design_id")
    bs.to_csv(P15 / "BSTAR_COMPARISON.csv", index=False)

    oper = []
    for c in tail_cols + ["design_size"]:
        for tgt in ("val_failure_rate", "test_failure_rate"):
            rho, p = stats.spearmanr(bs[c], bs[tgt])
            oper.append({"statistic": c, "target": tgt, "spearman": float(rho),
                         "p_value": float(p), "abs_spearman": abs(float(rho))})
    out["C_bstar_operational"] = oper
    out["C_bstar_calibration"] = {
        "mean_b_star": float(bs.b_star_equiv.mean()),
        "mean_val_failure_rate": float(bs.val_failure_rate.mean()),
        "brier_design_level": float(np.mean((bs.b_star_equiv - bs.val_failure_rate) ** 2)),
        "underestimation_factor": float(bs.val_failure_rate.mean() / max(bs.b_star_equiv.mean(), 1e-9)),
    }

    # ---------- E: readiness regimes ---------------------------------------
    va2 = va.copy()
    vis_med = tr.fo_d_S.median()
    iso_med = tr.iso_margin_ratio.median()
    va2["regime"] = np.where(va2.fo_d_S < vis_med,
                             np.where(va2.iso_margin_ratio < iso_med, "1_lowvis_lowiso",
                                      "2_lowvis_highiso"),
                             np.where(va2.iso_margin_ratio < iso_med, "3_highvis_lowiso",
                                      "4_highvis_highiso"))
    reg = (va2.groupby("regime")
           .agg(n=("failure", "size"), failure_rate=("failure", "mean"),
                median_rank_true=("rank_true", "median"),
                median_log_loss=("log_loss", "median"))
           .reset_index())
    reg["thresholds"] = f"vis<{vis_med:.3f} (TRAIN median), iso<{iso_med:.3f} (TRAIN median)"
    out["E_regimes"] = reg.to_dict("records")

    (P15 / "PHASE15_TABLES.json").write_text(json.dumps(out, indent=2, default=float))
    pd.DataFrame(out["A_visibility_family"]).to_csv(P15 / "STANDARD_METRICS_AUDIT.csv", index=False)
    pd.DataFrame(model_rows).to_csv(P15 / "INCREMENTAL_VALUE.csv", index=False)
    pd.DataFrame(out["D_paired_comparisons"]).to_csv(P15 / "ABLATIONS.csv", index=False)
    pd.DataFrame(per_fault).to_csv(P15 / "FAULT_CONFUSABILITY.csv", index=False)
    json.dump({k: fitted[k]["coef"] for k in fitted},
              open(P15 / "MODEL_COEFFICIENTS.json", "w"), indent=2)

    print(json.dumps({k: out[k] for k in ("A_identity_check", "A_fo_vs_snr_association",
                                          "C_bstar_calibration")}, indent=2, default=float))
    print("\n--- model ladder (VALID) ---")
    print(pd.DataFrame(model_rows)[["model", "auroc", "auprc", "brier", "log_loss"]]
          .round(4).to_string(index=False))
    print("\n--- paired comparisons (VALID, seed-level bootstrap) ---")
    print(pd.DataFrame(out["D_paired_comparisons"]).round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
