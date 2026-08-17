"""PHASE 23-RT -- confirmatory pipeline.

Executes PROTOCOLE_PHASE23_RT.md
(SHA-256 19c17f5265926ec6a89a888f5c400078d600ad1155aa1e2f1b50ac238c33829e,
frozen at e531cd7, amended at b870d5e, data gate at 91837b1 -- all before TEST).

Two stages with a hard boundary:

  --stage calib   fits everything on TRAIN, selects hyperparameters and PROB
                  thresholds on CALIBRATION, fits the two meta-models on
                  CALIBRATION, decides NOT_EXECUTABLE cells. NEVER touches TEST.
  --stage test    opens TEST once and computes every endpoint.

fo_metrics is NOT imported. ISO_FROZEN (oracle variant) is never used.
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from phase21_ir_iso import ISO_KEYS, isolability, verify_verbatim
from phase23_rt_metrics import (all_metrics, ci_and_p, fixed_threshold_operating_point,
                                holm, paired_bootstrap)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase23_rt"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p23")
STATE = WORK / "calib_state.pkl"

SEED = 23260823
N_BOOT = 10_000
MIN_ERRORS = 20
SVM_MAX_TRAIN = 10_000
TARGET_REJECTION = 0.10
OP_GAIN_THRESHOLD = 0.05

GRIDS = {
    "M1_logreg": [{"C": c} for c in (0.1, 1.0, 10.0)],
    "M2_random_forest": [{"min_samples_leaf": m} for m in (1, 5)],
    "M3_gradient_boosting": [{"learning_rate": lr} for lr in (0.05, 0.1)],
    "M4_rbf_svm": [{"C": c} for c in (1.0, 10.0)],
}
STD_FEATURES = ["MCP_RISK", "ENTROPY_RISK", "MARGIN_RISK"]


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def build(name, hp, proba=False):
    if name == "M1_logreg":
        return LogisticRegression(max_iter=5000, random_state=SEED, **hp)
    if name == "M2_random_forest":
        return RandomForestClassifier(n_estimators=300, random_state=SEED,
                                      n_jobs=-1, **hp)
    if name == "M3_gradient_boosting":
        return HistGradientBoostingClassifier(random_state=SEED, **hp)
    return SVC(kernel="rbf", gamma="scale", probability=proba, random_state=SEED, **hp)


def preprocess(X, split):
    tr = split == "train"
    keep = np.nanstd(X[tr], axis=0) > 0
    keep &= ~np.all(np.isnan(X[tr]), axis=0)
    X = X[:, keep]
    ind = np.flatnonzero(np.isnan(X[tr]).mean(axis=0) > 0.05)
    med = np.nan_to_num(np.nanmedian(X[tr], axis=0), nan=0.0)
    Xf = np.where(np.isnan(X), med[None, :], X)
    if len(ind):
        Xf = np.hstack([Xf, np.isnan(X[:, ind]).astype(float)])
    sc = StandardScaler().fit(Xf[tr])
    Z = np.nan_to_num(sc.transform(Xf), nan=0.0, posinf=0.0, neginf=0.0)
    return Z, {"n_features_kept": int(keep.sum()),
               "n_missing_indicators": int(len(ind)),
               "n_features_final": int(Z.shape[1])}


def risk_scores(proba: np.ndarray) -> dict:
    K = proba.shape[1]
    srt = np.sort(proba, axis=1)[:, ::-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = -(proba * np.log(np.maximum(proba, 1e-300))).sum(1) / np.log(K)
    return {"MCP_RISK": 1.0 - srt[:, 0],
            "ENTROPY_RISK": ent,
            "MARGIN_RISK": 1.0 - (srt[:, 0] - (srt[:, 1] if K > 1 else 0.0))}


def load_dataset(name: str):
    X = np.load(WORK / f"X_{name}.npy")
    y = np.load(WORK / f"y_{name}.npy", allow_pickle=True)
    sp = pd.read_csv(OUT / f"SPLIT_{name}.csv").split.to_numpy()
    return X, y, sp


# ------------------------------------------------------------- stage: calib

def stage_calib() -> int:
    t0 = time.time()
    vv = verify_verbatim()
    print(json.dumps(vv), flush=True)
    gate = json.load(open(OUT / "DATA_GATE.json"))
    names = list(gate["retained"])
    state, rows, log = {}, [], []

    for ds in names:
        X, y, sp = load_dataset(ds)
        Z, pinfo = preprocess(X, sp)
        tr, ca = sp == "train", sp == "calib"
        print(f"\n== {ds} == X{X.shape} -> Z{Z.shape} {pinfo}", flush=True)
        lw = LedoitWolf(assume_centered=False).fit(Z[tr])
        Sinv = np.linalg.pinv(lw.covariance_)
        cents = {k: Z[tr & (y == k)].mean(0) for k in np.unique(y[tr])}

        for mname in GRIDS:
            t1 = time.time()
            Ztr, ytr = Z[tr], y[tr]
            sub = None
            if mname == "M4_rbf_svm" and len(ytr) > SVM_MAX_TRAIN:
                rng = np.random.default_rng(SEED)
                sub = np.concatenate([rng.permutation(np.flatnonzero(ytr == c))[
                    :max(1, int(round(SVM_MAX_TRAIN * (ytr == c).mean())))]
                    for c in np.unique(ytr)])
                Ztr, ytr = Ztr[sub], ytr[sub]
                log.append(f"{ds}/{mname}: SVM sur {len(sub)} lignes TRAIN (regle gelee)")
            grid = []
            for hp in GRIDS[mname]:
                m = build(mname, hp, proba=False)
                m.fit(Ztr, ytr)
                grid.append({"hp": hp,
                             "calib_accuracy": float((m.predict(Z[ca]) == y[ca]).mean())})
            best_hp = max(grid, key=lambda g: g["calib_accuracy"])["hp"]
            model = build(mname, best_hp, proba=True)
            model.fit(Ztr, ytr)
            classes = model.classes_

            p_ca = model.predict_proba(Z[ca])
            pred_ca = classes[p_ca.argmax(1)]
            err_ca = (pred_ca != y[ca]).astype(int)
            n_err = int(err_ca.sum())
            std_ca = risk_scores(p_ca)
            iso_ca = isolability(Z[ca], pred_ca, cents, Sinv)

            if n_err < MIN_ERRORS or len(np.unique(err_ca)) < 2:
                rows.append({"dataset": ds, "model": mname, "status": "NOT_EXECUTABLE",
                             "reason": f"{n_err} erreurs sur CALIBRATION < {MIN_ERRORS}",
                             "hp": best_hp, "n_errors_calib": n_err,
                             "calib_accuracy": float(1 - err_ca.mean())})
                log.append(f"{ds}/{mname}: NOT_EXECUTABLE, {n_err} erreurs CALIB "
                           f"< {MIN_ERRORS}")
                print("  " + log[-1], flush=True)
                continue

            Fb = np.column_stack([std_ca[k] for k in STD_FEATURES])
            Fi = np.column_stack([std_ca[k] for k in STD_FEATURES]
                                 + [slog(iso_ca[k]) for k in ISO_KEYS])
            scb, sci = StandardScaler().fit(Fb), StandardScaler().fit(Fi)
            meta_base = LogisticRegression(penalty="l2", C=1.0, max_iter=5000,
                                           random_state=SEED).fit(scb.transform(Fb), err_ca)
            meta_iso = LogisticRegression(penalty="l2", C=1.0, max_iter=5000,
                                          random_state=SEED).fit(sci.transform(Fi), err_ca)
            s_base_ca = meta_base.predict_proba(scb.transform(Fb))[:, 1]
            s_iso_ca = meta_iso.predict_proba(sci.transform(Fi))[:, 1]
            iso_pred_ca = -iso_ca["iso_margin_ratio"]

            # operational thresholds frozen on CALIBRATION only
            thr = {k: float(np.quantile(v, 1 - TARGET_REJECTION))
                   for k, v in {**std_ca, "ISO_PRED": iso_pred_ca,
                                "STANDARD_META": s_base_ca,
                                "ISO_META": s_iso_ca}.items()}

            state[(ds, mname)] = {"model": model, "classes": classes, "cents": cents,
                                  "Sinv": Sinv, "scb": scb, "sci": sci,
                                  "meta_base": meta_base, "meta_iso": meta_iso,
                                  "thresholds": thr, "Z": Z, "y": y, "sp": sp}
            rows.append({"dataset": ds, "model": mname, "status": "OK", "hp": best_hp,
                         "grid": grid, "n_errors_calib": n_err,
                         "calib_accuracy": float(1 - err_ca.mean()),
                         "n_train": int(tr.sum()), "n_calib": int(ca.sum()),
                         "n_test": int((sp == "test").sum()),
                         "n_classes": int(len(classes)),
                         "svm_subsample": None if sub is None else int(len(sub)),
                         "thresholds_calib": thr, "preprocess": pinfo})
            log.append(f"{ds}/{mname}: hp={best_hp} acc_calib="
                       f"{1-err_ca.mean():.4f} err_calib={n_err} ({time.time()-t1:.0f}s)")
            print("  " + log[-1], flush=True)

    pd.DataFrame([{k: v for k, v in r.items() if k not in ("grid", "thresholds_calib",
                                                           "preprocess")}
                  for r in rows]).to_csv(OUT / "CALIB_STAGE.csv", index=False)
    json.dump({"verbatim_check": vv, "cells": rows,
               "TEST_OPENED": "NO"}, open(OUT / "CALIB_STAGE.json", "w"),
              indent=2, default=str)
    (OUT / "logs" / "calib_stage.log").write_text("\n".join(log) + "\n")
    with open(STATE, "wb") as f:
        pickle.dump(state, f)

    ok = [r for r in rows if r["status"] == "OK"]
    ds_ok = sorted({r["dataset"] for r in ok})
    print(f"\n=== CALIB STAGE: {len(ok)}/{len(rows)} cellules executables, "
          f"{len(ds_ok)} jeux: {ds_ok} ({time.time()-t0:.0f}s) ===")
    print("TEST_OPENED: NO")
    return 0


# -------------------------------------------------------------- stage: test

def stage_test() -> int:
    t0 = time.time()
    print("=== OUVERTURE DU TEST ===", flush=True)
    with open(STATE, "rb") as f:
        state = pickle.load(f)
    calib = json.load(open(OUT / "CALIB_STAGE.json"))
    log, score_rows, deltas, oper_rows = [], [], [], []

    for (ds, mname), st in state.items():
        Z, y, sp = st["Z"], st["y"], st["sp"]
        te = sp == "test"
        model, classes = st["model"], st["classes"]
        p_te = model.predict_proba(Z[te])
        pred = classes[p_te.argmax(1)]
        yte = y[te]
        err = (pred != yte).astype(int)
        n_err = int(err.sum())

        std = risk_scores(p_te)
        iso = isolability(Z[te], pred, st["cents"], st["Sinv"])     # label-free
        iso_pred = -iso["iso_margin_ratio"]
        Fb = np.column_stack([std[k] for k in STD_FEATURES])
        Fi = np.column_stack([std[k] for k in STD_FEATURES]
                             + [slog(iso[k]) for k in ISO_KEYS])
        s_base = st["meta_base"].predict_proba(st["scb"].transform(Fb))[:, 1]
        s_iso = st["meta_iso"].predict_proba(st["sci"].transform(Fi))[:, 1]

        scores = {**std, "ISO_PRED": iso_pred,
                  "STANDARD_META": s_base, "ISO_META": s_iso}

        if n_err < MIN_ERRORS:
            log.append(f"{ds}/{mname}: NOT_EVALUABLE_LOW_EVENTS ({n_err} erreurs TEST)")
            print("  " + log[-1], flush=True)
            score_rows.append({"dataset": ds, "model": mname, "score": "-",
                               "status": "NOT_EVALUABLE_LOW_EVENTS",
                               "n_test": int(te.sum()), "n_errors_test": n_err,
                               "test_accuracy": float(1 - err.mean())})
            continue

        for k, v in scores.items():
            score_rows.append({"dataset": ds, "model": mname, "score": k, "status": "OK",
                               "n_test": int(te.sum()), "n_errors_test": n_err,
                               "test_accuracy": float(1 - err.mean()),
                               **all_metrics(err, v)})
            op = fixed_threshold_operating_point(err, v, st["thresholds"][k])
            oper_rows.append({"dataset": ds, "model": mname, "score": k, **op})

        mb = all_metrics(err, s_base)
        mi = all_metrics(err, s_iso)
        bs = paired_bootstrap(err, s_iso, s_base, N_BOOT, SEED + 101)
        d = {"dataset": ds, "model": mname, "n_test": int(te.sum()),
             "n_errors_test": n_err, "test_accuracy": float(1 - err.mean()),
             "augrc_standard": mb["augrc"], "augrc_iso": mi["augrc"],
             "delta_augrc": mb["augrc"] - mi["augrc"],
             "aurc_standard": mb["aurc"], "aurc_iso": mi["aurc"],
             "delta_aurc": mb["aurc"] - mi["aurc"],
             "ec10_standard": mb["error_capture_10"], "ec10_iso": mi["error_capture_10"],
             "delta_error_capture_10": mi["error_capture_10"] - mb["error_capture_10"],
             "re10_standard": mb["residual_error_10"], "re10_iso": mi["residual_error_10"],
             "delta_residual_error_10": mb["residual_error_10"] - mi["residual_error_10"],
             "auroc_iso_pred_for_error": _auroc(err, iso_pred)}
        for key, arr in bs.items():
            c = ci_and_p(arr)
            d[f"{key}_ci_low"] = c["ci_low"]
            d[f"{key}_ci_high"] = c["ci_high"]
            d[f"{key}_p_raw"] = c["p_raw"]
        b_iso = _auroc_boot(err, iso_pred, SEED + 202)
        d["auroc_iso_ci_low"], d["auroc_iso_ci_high"] = b_iso
        deltas.append(d)
        log.append(f"{ds}/{mname}: acc={1-err.mean():.4f} err={n_err} "
                   f"dAUGRC={d['delta_augrc']:+.5f} "
                   f"dEC10={d['delta_error_capture_10']:+.4f} "
                   f"AUROC(ISO)={d['auroc_iso_pred_for_error']:.3f} "
                   f"({time.time()-t0:.0f}s)")
        print("  " + log[-1], flush=True)

    dd = pd.DataFrame(deltas)
    if len(dd):
        rej = holm(dd.delta_augrc_p_raw.tolist())
        dd["holm_rejected"] = rej
        dd["holm_confirmed_gain"] = [bool(r and v > 0)
                                     for r, v in zip(rej, dd.delta_augrc)]
    pd.DataFrame(score_rows).to_csv(OUT / "CELL_SCORES.csv", index=False)
    pd.DataFrame(oper_rows).to_csv(OUT / "OPERATING_POINT.csv", index=False)
    dd.to_csv(OUT / "DELTAS.csv", index=False)
    (OUT / "logs" / "test_stage.log").write_text("\n".join(log) + "\n")

    res = _verdicts(dd, calib)
    json.dump(res, open(OUT / "PHASE23_RT_RESULTS.json", "w"), indent=2, default=str)
    print("\n=== AGREGATIONS ===")
    print(json.dumps(res["aggregation"], indent=1, default=str))
    print("\n=== GATES ===")
    print(json.dumps(res["gates"], indent=1, default=str))
    print("\n=== VERDICTS ===")
    for k, v in res["verdicts"].items():
        print(f"{k:30s} {v}")
    print(f"({time.time()-t0:.0f}s)")
    return 0


def _auroc(y, s) -> float:
    from scipy.stats import rankdata
    y = np.asarray(y)
    n1 = float(y.sum())
    n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _auroc_boot(y, s, seed) -> tuple:
    rng = np.random.default_rng(seed)
    n = len(y)
    v = np.empty(2000)
    for b in range(2000):
        ii = rng.integers(0, n, n)
        v[b] = _auroc(y[ii], s[ii])
    v = v[~np.isnan(v)]
    lo, hi = np.percentile(v, [2.5, 97.5])
    return float(lo), float(hi)


def _verdicts(dd: pd.DataFrame, calib: dict) -> dict:
    if len(dd) == 0:
        return {"aggregation": {}, "gates": {},
                "verdicts": {"ERROR_RISK_REPLICATED": "NO", "INCREMENTAL_TRIAGE": "NO",
                             "ROBUST_ACROSS_DATASETS": "NO", "ROBUST_ACROSS_MODELS": "NO",
                             "OPERATIONAL_GAIN": "NO", "PHASE23_RESULT": "FALSIFIED",
                             "BRANCH_DECISION": "CLOSE_APPLICATIVE_ISO_BRANCH"}}
    no_rf = dd[dd.model != "M2_random_forest"]
    med = lambda f, c: float(f[c].median()) if len(f) else float("nan")
    agg = {
        "n_cells": int(len(dd)), "n_datasets": int(dd.dataset.nunique()),
        "n_models": int(dd.model.nunique()),
        "MEDIAN_DELTA_AUGRC_ALL": med(dd, "delta_augrc"),
        "MEAN_DELTA_AUGRC_ALL": float(dd.delta_augrc.mean()),
        "MEDIAN_DELTA_ERROR_CAPTURE_10_ALL": med(dd, "delta_error_capture_10"),
        "MEDIAN_DELTA_RESIDUAL_ERROR_10_ALL": med(dd, "delta_residual_error_10"),
        "MEDIAN_DELTA_AUGRC_NO_RF": med(no_rf, "delta_augrc"),
        "MEDIAN_DELTA_ERROR_CAPTURE_10_NO_RF": med(no_rf, "delta_error_capture_10"),
        "MEDIAN_DELTA_RESIDUAL_ERROR_10_NO_RF": med(no_rf, "delta_residual_error_10"),
        "n_positive_augrc": int((dd.delta_augrc > 0).sum()),
        "n_negative_augrc": int((dd.delta_augrc < 0).sum()),
        "n_ci_contains_zero": int(((dd.delta_augrc_ci_low <= 0)
                                   & (dd.delta_augrc_ci_high >= 0)).sum()),
        "per_dataset_median_delta_augrc":
            dd.groupby("dataset").delta_augrc.median().round(6).to_dict(),
        "per_dataset_median_delta_ec10":
            dd.groupby("dataset").delta_error_capture_10.median().round(6).to_dict(),
        "per_model_median_delta_augrc":
            dd.groupby("model").delta_augrc.median().round(6).to_dict(),
        "per_model_median_delta_ec10":
            dd.groupby("model").delta_error_capture_10.median().round(6).to_dict(),
        "median_auroc_iso_pred": float(dd.auroc_iso_pred_for_error.median()),
    }
    # stratified aggregate CI: median over datasets of per-dataset medians
    agg["STRATIFIED_MEDIAN_DELTA_AUGRC"] = float(np.median(
        [v for v in agg["per_dataset_median_delta_augrc"].values()]))

    # --- GATE 1
    iso_above = ((dd.auroc_iso_ci_low > 0.50)).to_numpy()
    g1_ds = dd[dd.auroc_iso_ci_low > 0.50].dataset.nunique()
    g1_md = dd[dd.auroc_iso_ci_low > 0.50].model.nunique()
    nrf_above = (no_rf.auroc_iso_ci_low > 0.50).to_numpy() if len(no_rf) else np.array([])
    g1 = {"median_auroc_iso": agg["median_auroc_iso_pred"],
          "frac_ci_above_half": float(iso_above.mean()),
          "n_datasets": int(g1_ds), "n_models": int(g1_md),
          "no_rf_median_auroc": med(no_rf, "auroc_iso_pred_for_error"),
          "no_rf_frac_ci_above_half": float(nrf_above.mean()) if len(nrf_above) else 0.0,
          "no_rf_n_datasets": int(no_rf[no_rf.auroc_iso_ci_low > 0.50].dataset.nunique())
          if len(no_rf) else 0,
          "no_rf_n_models": int(no_rf[no_rf.auroc_iso_ci_low > 0.50].model.nunique())
          if len(no_rf) else 0}
    g1["pass"] = bool(g1["median_auroc_iso"] >= 0.55 and g1["frac_ci_above_half"] >= 2 / 3
                      and g1["n_datasets"] >= 2 and g1["n_models"] >= 2
                      and g1["no_rf_median_auroc"] >= 0.55
                      and g1["no_rf_frac_ci_above_half"] >= 2 / 3
                      and g1["no_rf_n_datasets"] >= 2 and g1["no_rf_n_models"] >= 2)

    # --- GATE 2
    sig_pos = dd[(dd.delta_augrc > 0) & (dd.delta_augrc_ci_low > 0)]
    g2 = {"median_delta_augrc": agg["MEDIAN_DELTA_AUGRC_ALL"],
          "median_delta_ec10": agg["MEDIAN_DELTA_ERROR_CAPTURE_10_ALL"],
          "n_significant_positive_cells": int(len(sig_pos)),
          "n_datasets_with_significant_positive": int(sig_pos.dataset.nunique()),
          "stratified_median": agg["STRATIFIED_MEDIAN_DELTA_AUGRC"]}
    g2["pass"] = bool(g2["median_delta_augrc"] > 0 and g2["median_delta_ec10"] > 0
                      and len(sig_pos) >= 3 and sig_pos.dataset.nunique() >= 2
                      and g2["stratified_median"] > 0)

    # --- GATE 3
    pos_ds = [d for d in agg["per_dataset_median_delta_augrc"]
              if agg["per_dataset_median_delta_augrc"][d] > 0
              and agg["per_dataset_median_delta_ec10"][d] > 0]
    need = 3 if agg["n_datasets"] >= 4 else 2
    g3 = {"positive_datasets": pos_ds, "n_positive": len(pos_ds),
          "n_datasets": agg["n_datasets"], "required": need}
    g3["pass"] = bool(len(pos_ds) >= need)

    # --- GATE 4
    pos_md = [m for m, v in agg["per_model_median_delta_augrc"].items() if v > 0]
    g4 = {"positive_families": pos_md, "n_positive": len(pos_md),
          "median_delta_augrc_no_rf": agg["MEDIAN_DELTA_AUGRC_NO_RF"],
          "median_delta_ec10_no_rf": agg["MEDIAN_DELTA_ERROR_CAPTURE_10_NO_RF"]}
    g4["pass"] = bool(len(pos_md) >= 3 and agg["MEDIAN_DELTA_AUGRC_NO_RF"] > 0
                      and agg["MEDIAN_DELTA_ERROR_CAPTURE_10_NO_RF"] > 0)

    # --- GATE 5
    g5 = {"median_delta_ec10": agg["MEDIAN_DELTA_ERROR_CAPTURE_10_ALL"],
          "threshold": OP_GAIN_THRESHOLD,
          "median_delta_residual_error_10": agg["MEDIAN_DELTA_RESIDUAL_ERROR_10_ALL"]}
    g5["pass"] = bool(g5["median_delta_ec10"] >= OP_GAIN_THRESHOLD
                      and g5["median_delta_residual_error_10"] > 0)

    v = {"ERROR_RISK_REPLICATED": "YES" if g1["pass"] else "NO",
         "INCREMENTAL_TRIAGE": "YES" if g2["pass"] else "NO",
         "ROBUST_ACROSS_DATASETS": "YES" if g3["pass"] else "NO",
         "ROBUST_ACROSS_MODELS": "YES" if g4["pass"] else "NO",
         "OPERATIONAL_GAIN": "YES" if g5["pass"] else "NO"}
    if all(x == "YES" for x in v.values()):
        v["PHASE23_RESULT"] = "SUPPORTED"
        v["BRANCH_DECISION"] = "ADVANCE_TO_PRODUCT_VALIDATION"
    else:
        v["PHASE23_RESULT"] = "FALSIFIED"
        v["BRANCH_DECISION"] = "CLOSE_APPLICATIVE_ISO_BRANCH"
    return {"aggregation": agg,
            "gates": {"GATE1_ERROR_RISK_REPLICATED": g1,
                      "GATE2_INCREMENTAL_TRIAGE": g2,
                      "GATE3_ROBUST_ACROSS_DATASETS": g3,
                      "GATE4_ROBUST_ACROSS_MODELS": g4,
                      "GATE5_OPERATIONAL_GAIN": g5},
            "verdicts": v, "TEST_OPENED": "YES"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["calib", "test"], required=True)
    a = ap.parse_args()
    raise SystemExit(stage_calib() if a.stage == "calib" else stage_test())
