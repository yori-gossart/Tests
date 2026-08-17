"""PHASE 22-BR -- confirmatory execution (commit C).

Executes sections 3 to 9 of PROTOCOLE_PHASE22_BR.md
(SHA-256 3e48e6091655935e1aaf4cabeb7852540d7094d48d6e6ca1af02d3bfd86ce89b,
frozen at commit 8fe5233 before any data access; data gate at commit 7e8b17d).

Order of operations enforced by construction: for every cell, the hyperparameters,
the preprocessing, the probability calibration, PROB_BEST and the CONFIDENCE_WEAK
decision are all fixed from TRAIN/CALIB ONLY, and the TEST arrays are touched
only afterwards, inside `evaluate_on_test`.

fo_metrics is NOT imported. Visibility, Robustness, R7, FO and B* are absent.
ISO_FROZEN is computed for the descriptive annex only and can carry no verdict.
"""

from __future__ import annotations

import json
import time
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.calibration import CalibratedClassifierCV
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from phase21_ir_iso import ISO_KEYS, isolability, verify_verbatim
from phase22_br_data import LOADERS, gas_shift_split, stratified_split

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase22_br"

SEED = 22260822
BOOT = 2000
WEAK_THRESHOLD = 0.70
DELTA_MIN = 0.020
SVM_MAX_TRAIN = 10000
COVERAGES = [0.90, 0.80, 0.70]

GRIDS = {
    "M1_logreg": [{"C": c} for c in (0.01, 0.1, 1.0, 10.0)],
    "M2_rbf_svm": [{"C": c, "gamma": g} for c, g in product((1.0, 10.0), ("scale", 0.01))],
    "M3_random_forest": [{"max_features": f, "min_samples_leaf": m}
                         for f, m in product(("sqrt", 0.3), (1, 5))],
    "M4_hist_gradient_boosting": [{"learning_rate": lr, "max_leaf_nodes": n}
                                  for lr, n in product((0.05, 0.1), (31, 63))],
}
PROB_BASELINES = ["B1_max_prob", "B2_entropy", "B3_margin", "B4_platt", "B5_isotonic"]


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def fast_auc(y, s) -> float:
    y = np.asarray(y)
    n1 = float(y.sum())
    n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def aurc(err, score) -> float:
    o = np.argsort(score, kind="mergesort")
    e = np.asarray(err, dtype=float)[o]
    return float(np.mean(np.cumsum(e) / np.arange(1, len(e) + 1)))


def accuracy_at_coverage(err, score, cov) -> float:
    o = np.argsort(score, kind="mergesort")
    k = max(1, int(round(cov * len(o))))
    return float(1.0 - np.asarray(err, dtype=float)[o[:k]].mean())


def build_model(name, hp, seed=SEED, proba=False):
    if name == "M1_logreg":
        return LogisticRegression(max_iter=5000, random_state=seed, **hp)
    if name == "M2_rbf_svm":
        return SVC(kernel="rbf", probability=proba, random_state=seed, **hp)
    if name == "M3_random_forest":
        return RandomForestClassifier(n_estimators=500, random_state=seed,
                                      n_jobs=-1, **hp)
    return HistGradientBoostingClassifier(random_state=seed, **hp)


def preprocess(X, split):
    tr = split == "train"
    keep = np.nanstd(X[tr], axis=0) > 0
    keep &= ~np.all(np.isnan(X[tr]), axis=0)
    X = X[:, keep]
    ind_cols = np.flatnonzero(np.isnan(X[tr]).mean(axis=0) > 0.05)
    med = np.nan_to_num(np.nanmedian(X[tr], axis=0), nan=0.0)
    Xf = np.where(np.isnan(X), med[None, :], X)
    if len(ind_cols):
        Xf = np.hstack([Xf, np.isnan(X[:, ind_cols]).astype(float)])
    sc = StandardScaler().fit(Xf[tr])
    Z = np.nan_to_num(sc.transform(Xf), nan=0.0, posinf=0.0, neginf=0.0)
    return Z, {"n_features_kept": int(keep.sum()),
               "n_missing_indicators": int(len(ind_cols)),
               "n_features_final": int(Z.shape[1])}


def svm_subsample(Ztr, ytr, log, tag):
    if len(ytr) <= SVM_MAX_TRAIN:
        return Ztr, ytr
    rng = np.random.default_rng(SEED)
    sel = np.concatenate([rng.permutation(np.flatnonzero(ytr == c))[
        :max(1, int(round(SVM_MAX_TRAIN * (ytr == c).mean())))] for c in np.unique(ytr)])
    log.append(f"{tag}: SVM sous-echantillonne a {len(sel)} lignes de TRAIN (regle gelee)")
    return Ztr[sel], ytr[sel]


def confidence_scores(proba, cal_proba):
    srt = np.sort(proba, axis=1)[:, ::-1]
    out = {"B1_max_prob": -srt[:, 0]}
    with np.errstate(divide="ignore", invalid="ignore"):
        out["B2_entropy"] = -(proba * np.log(np.maximum(proba, 1e-300))).sum(1)
    out["B3_margin"] = -(srt[:, 0] - (srt[:, 1] if srt.shape[1] > 1 else 0.0))
    for k, p in cal_proba.items():
        out[k] = -np.sort(p, axis=1)[:, ::-1][:, 0] if p is not None else None
    return {k: v for k, v in out.items() if v is not None}


def run_cell(ds, mname, Z, y, split, log) -> dict:
    t0 = time.time()
    tag = f"{ds}/{mname}"
    tr, ca, te = (split == "train"), (split == "calib"), (split == "test")
    Ztr, ytr, Zca, yca = Z[tr], y[tr], Z[ca], y[ca]

    # ---- hyperparameters: grid selected on CALIB accuracy, TEST never touched
    Zf, yf = (svm_subsample(Ztr, ytr, log, tag) if mname == "M2_rbf_svm" else (Ztr, ytr))
    grid = []
    for hp in GRIDS[mname]:
        m = build_model(mname, hp, proba=False)
        m.fit(Zf, yf)
        grid.append({"hp": hp, "calib_accuracy": float((m.predict(Zca) == yca).mean())})
    best_hp = max(grid, key=lambda g: g["calib_accuracy"])["hp"]

    model = build_model(mname, best_hp, proba=True)
    model.fit(Zf, yf)
    classes = model.classes_
    proba_tr_ca = {"calib": model.predict_proba(Zca)}

    # ---- probability calibration, fitted on CALIB only
    cal = {}
    for key, meth in (("B4_platt", "sigmoid"), ("B5_isotonic", "isotonic")):
        try:
            c = CalibratedClassifierCV(model, cv="prefit", method=meth).fit(Zca, yca)
            cal[key] = c
        except Exception as e:
            cal[key] = None
            log.append(f"{tag}: {key} inapplicable ({e})")

    cal_ca = {k: (v.predict_proba(Zca) if v is not None else None) for k, v in cal.items()}
    conf_ca = confidence_scores(proba_tr_ca["calib"], cal_ca)
    pred_ca = classes[proba_tr_ca["calib"].argmax(1)]
    err_ca = (pred_ca != yca).astype(int)

    # ---- PROB_BEST chosen on CALIB only, then frozen
    auc_ca = {k: fast_auc(err_ca, v) for k, v in conf_ca.items()}
    order = [b for b in PROB_BASELINES if b in auc_ca and not np.isnan(auc_ca[b])]
    prob_best = max(order, key=lambda b: auc_ca[b]) if order else None
    weak = bool(prob_best is not None and auc_ca[prob_best] < WEAK_THRESHOLD)

    # ---- ISO on CALIB, and the two meta-models, fitted on CALIB only
    lw = LedoitWolf(assume_centered=False).fit(Ztr)
    Sinv = np.linalg.pinv(lw.covariance_)
    cents = {k: Ztr[ytr == k].mean(0) for k in np.unique(ytr)}
    iso_ca = isolability(Zca, pred_ca, cents, Sinv)

    Fb_ca = slog(conf_ca[prob_best]).reshape(-1, 1)
    Fi_ca = np.column_stack([slog(conf_ca[prob_best])] +
                            [slog(iso_ca[k]) for k in ISO_KEYS])
    scb = StandardScaler().fit(Fb_ca)
    sci = StandardScaler().fit(Fi_ca)
    meta_base = LogisticRegression(penalty="l2", C=1.0, max_iter=5000,
                                   random_state=SEED).fit(scb.transform(Fb_ca), err_ca)
    meta_iso = LogisticRegression(penalty="l2", C=1.0, max_iter=5000,
                                  random_state=SEED).fit(sci.transform(Fi_ca), err_ca)

    frozen = {"dataset": ds, "model": mname, "hp": best_hp, "grid": grid,
              "prob_best": prob_best, "auroc_calib_prob_best": auc_ca.get(prob_best),
              "auroc_calib_all": auc_ca, "confidence_weak": weak,
              "calib_accuracy": float((pred_ca == yca).mean()),
              "n_train": int(tr.sum()), "n_calib": int(ca.sum()), "n_test": int(te.sum()),
              "n_errors_calib": int(err_ca.sum()), "n_classes": int(len(classes)),
              "seconds_pre_test": round(time.time() - t0, 1)}
    log.append(f"{tag}: hp={best_hp} prob_best={prob_best} "
               f"AUROC_calib={auc_ca.get(prob_best):.3f} -> "
               f"{'CONFIDENCE_WEAK' if weak else 'confident'} "
               f"({time.time()-t0:.0f}s)")
    return {"frozen": frozen,
            "_objects": (model, classes, cal, cents, Sinv, prob_best,
                         scb, sci, meta_base, meta_iso)}


def evaluate_on_test(ds, mname, Z, y, split, cell, log) -> dict:
    """TEST is opened here, and only here."""
    (model, classes, cal, cents, Sinv, prob_best,
     scb, sci, meta_base, meta_iso) = cell["_objects"]
    te = split == "test"
    Zte, yte = Z[te], y[te]
    proba = model.predict_proba(Zte)
    pred = classes[proba.argmax(1)]
    err = (pred != yte).astype(int)
    cal_te = {k: (v.predict_proba(Zte) if v is not None else None) for k, v in cal.items()}
    conf = confidence_scores(proba, cal_te)

    iso_pred = isolability(Zte, pred, cents, Sinv)          # label-free
    iso_frozen = isolability(Zte, yte, cents, Sinv)         # ORACLE, annex only

    Fb = slog(conf[prob_best]).reshape(-1, 1)
    Fi = np.column_stack([slog(conf[prob_best])] + [slog(iso_pred[k]) for k in ISO_KEYS])
    s_base = meta_base.predict_proba(scb.transform(Fb))[:, 1]
    s_iso = meta_iso.predict_proba(sci.transform(Fi))[:, 1]

    scores = {"META_BASE": s_base, "META_ISO": s_iso,
              "PROB_BEST": conf[prob_best],
              "ISO_RAW": -iso_pred["iso_margin_ratio"]}
    for b, v in conf.items():
        scores[b] = v

    rows = []
    for k, v in scores.items():
        r = {"dataset": ds, "model": mname, "score": k,
             "auroc": fast_auc(err, v), "auprc": float(average_precision_score(err, v)),
             "aurc": aurc(err, v)}
        for c in COVERAGES:
            r[f"acc_at_cov_{int(c*100)}"] = accuracy_at_coverage(err, v, c)
        rows.append(r)

    d_auroc = fast_auc(err, s_iso) - fast_auc(err, s_base)
    d_aurc = aurc(err, s_base) - aurc(err, s_iso)
    rng = np.random.default_rng(SEED + 13)
    n = len(err)
    bA = np.empty(BOOT)
    bC = np.empty(BOOT)
    for b in range(BOOT):
        ii = rng.integers(0, n, n)
        ee = err[ii]
        if ee.sum() == 0 or ee.sum() == n:
            bA[b] = np.nan
            bC[b] = np.nan
            continue
        bA[b] = fast_auc(ee, s_iso[ii]) - fast_auc(ee, s_base[ii])
        bC[b] = aurc(ee, s_base[ii]) - aurc(ee, s_iso[ii])
    bAv = bA[~np.isnan(bA)]
    lo, hi = np.percentile(bAv, [2.5, 97.5])
    p = float(min(1.0, 2 * min((bAv <= 0).mean(), (bAv >= 0).mean())))
    bCv = bC[~np.isnan(bC)]
    clo, chi = np.percentile(bCv, [2.5, 97.5])

    # ORACLE annex: same meta form but with the true-label isolability
    Fo = np.column_stack([slog(conf[prob_best])] + [slog(iso_frozen[k]) for k in ISO_KEYS])
    oracle_auroc = fast_auc(err, meta_iso.predict_proba(sci.transform(Fo))[:, 1])

    log.append(f"{ds}/{mname}: TEST acc={1-err.mean():.4f} err={int(err.sum())} "
               f"dAUROC={d_auroc:+.4f} [{lo:+.4f};{hi:+.4f}] p={p:.4f} "
               f"dAURC={d_aurc:+.5f}")
    return {"rows": rows,
            "delta": {"dataset": ds, "model": mname,
                      "n_test": int(te.sum()), "n_errors_test": int(err.sum()),
                      "test_accuracy": float(1 - err.mean()),
                      "auroc_meta_base": fast_auc(err, s_base),
                      "auroc_meta_iso": fast_auc(err, s_iso),
                      "delta_auroc": d_auroc, "ci_low": float(lo), "ci_high": float(hi),
                      "p_raw": p, "aurc_meta_base": aurc(err, s_base),
                      "aurc_meta_iso": aurc(err, s_iso), "delta_aurc": d_aurc,
                      "aurc_ci_low": float(clo), "aurc_ci_high": float(chi),
                      "boot_delta_auroc": bAv},
            "oracle": {"dataset": ds, "model": mname,
                       "auroc_meta_oracle": oracle_auroc,
                       "delta_vs_meta_base": oracle_auroc - fast_auc(err, s_base)}}


def holm(pvals: list[float]) -> list[bool]:
    m = len(pvals)
    order = np.argsort(pvals)
    rej = [False] * m
    for i, k in enumerate(order):
        if pvals[k] <= 0.05 / (m - i):
            rej[k] = True
        else:
            break
    return rej


def strat_median(deltas: list[dict], key="delta_auroc") -> float:
    per = {}
    for d in deltas:
        per.setdefault(d["dataset"], []).append(d[key])
    return float(np.median([np.median(v) for v in per.values()]))


def strat_ci(deltas: list[dict]) -> tuple[float, float]:
    """Hierarchical bootstrap: per-cell paired draws already stored, recombined
    so that every dataset weighs the same."""
    per: dict[str, list[np.ndarray]] = {}
    for d in deltas:
        per.setdefault(d["dataset"], []).append(d["boot_delta_auroc"])
    nb = min(min(len(a) for a in v) for v in per.values())
    stat = np.empty(nb)
    for b in range(nb):
        stat[b] = np.median([np.median([a[b] for a in v]) for v in per.values()])
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def main() -> int:
    t0 = time.time()
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    vv = verify_verbatim()
    print(json.dumps(vv), flush=True)
    gate = json.load(open(OUT / "GATE_B.json"))
    log: list[str] = []
    frozen_rows, score_rows, deltas, oracles = [], [], [], []
    shift_frozen, shift_deltas, shift_scores = [], [], []

    for ds in ("GAS", "CREDIT", "DRYBEAN"):
        g = gate["datasets"][ds]
        if g["status"] != "EXECUTABLE":
            continue
        X, y, batch = LOADERS[ds](g["accepted"])
        analyses = [("main", stratified_split(y))]
        if ds == "GAS":
            analyses.append(("shift", gas_shift_split(batch)))
        for kind, split in analyses:
            Z, pinfo = preprocess(X, split)
            print(f"\n== {ds} [{kind}] == X{X.shape} -> Z{Z.shape} {pinfo}", flush=True)
            for mname in GRIDS:
                try:
                    cell = run_cell(ds, mname, Z, y, split, log)
                    print("  " + log[-1], flush=True)
                    ev = evaluate_on_test(ds, mname, Z, y, split, cell, log)
                    print("  " + log[-1], flush=True)
                except Exception as e:
                    log.append(f"{ds}/{mname} [{kind}]: NOT_EXECUTABLE {e}")
                    print("  " + log[-1], flush=True)
                    continue
                fr = {**cell["frozen"], "analysis": kind, "preprocess": pinfo}
                if kind == "main":
                    frozen_rows.append(fr)
                    score_rows += ev["rows"]
                    oracles.append(ev["oracle"])
                    if fr["confidence_weak"]:
                        deltas.append(ev["delta"])
                else:
                    shift_frozen.append(fr)
                    shift_scores += ev["rows"]
                    if fr["confidence_weak"]:
                        shift_deltas.append(ev["delta"])

    pd.DataFrame(frozen_rows).drop(columns=["grid", "auroc_calib_all"]).to_csv(
        OUT / "CELLS_MAIN.csv", index=False)
    pd.DataFrame(score_rows).to_csv(OUT / "SCORES_MAIN.csv", index=False)
    pd.DataFrame(oracles).to_csv(OUT / "ORACLE_ANNEX.csv", index=False)
    if shift_frozen:
        pd.DataFrame(shift_frozen).drop(columns=["grid", "auroc_calib_all"]).to_csv(
            OUT / "CELLS_SHIFT.csv", index=False)
        pd.DataFrame(shift_scores).to_csv(OUT / "SCORES_SHIFT.csv", index=False)

    # ---------------- verdicts, criteria frozen in section 9 --------------
    weak_ds = sorted({r["dataset"] for r in frozen_rows if r["confidence_weak"]})
    regime = "YES" if len(weak_ds) >= 3 else "NO"

    res: dict = {"verbatim_check": vv, "protocol_sha256": gate["protocol_sha256"],
                 "gate_b": {k: v["status"] for k, v in gate["datasets"].items()},
                 "confidence_weak_datasets": weak_ds,
                 "n_weak_cells": len(deltas)}

    if deltas:
        dd = pd.DataFrame([{k: v for k, v in d.items() if k != "boot_delta_auroc"}
                           for d in deltas])
        pv = [d["p_raw"] for d in deltas]
        rej = holm(pv)
        dd["holm_rejected"] = rej
        dd["holm_confirmed_gain"] = [bool(r and d > 0) for r, d in
                                     zip(rej, dd.delta_auroc)]
        dd.to_csv(OUT / "DELTAS_WEAK_CELLS.csv", index=False)

        per_ds = dd.groupby("dataset").delta_auroc.median()
        per_md = dd.groupby("model").delta_auroc.median()
        sm = strat_median(deltas)
        slo, shi = strat_ci(deltas)
        sm_aurc = strat_median(deltas, "delta_aurc")
        conf_cells = dd[dd.holm_confirmed_gain]
        no_rf = [d for d in deltas if d["model"] != "M3_random_forest"]
        nrf = pd.DataFrame([{k: v for k, v in d.items() if k != "boot_delta_auroc"}
                            for d in no_rf]) if no_rf else pd.DataFrame()
        if len(nrf):
            nrf_rej = holm([d["p_raw"] for d in no_rf])
            nrf["holm_confirmed_gain"] = [bool(r and d > 0) for r, d in
                                          zip(nrf_rej, nrf.delta_auroc)]

        c = {
            "1_datasets_positive_median": int((per_ds > 0).sum()),
            "1_pass": bool((per_ds > 0).sum() >= 3),
            "2_model_families_participating": int(dd.model.nunique()),
            "2_pass": bool(dd.model.nunique() >= 2),
            "3_global_median_delta_auroc": sm, "3_pass": bool(sm >= DELTA_MIN),
            "4_stratified_ci": [slo, shi], "4_pass": bool(slo > 0 or shi < 0),
            "5_holm_confirmed_cells": int(len(conf_cells)),
            "5_holm_confirmed_datasets": int(conf_cells.dataset.nunique()),
            "5_pass": bool(len(conf_cells) >= 3 and conf_cells.dataset.nunique() >= 3),
            "6_without_rf": ({
                "n_cells": int(len(nrf)),
                "datasets_positive_median": int(
                    (nrf.groupby("dataset").delta_auroc.median() > 0).sum()) if len(nrf) else 0,
                "families": int(nrf.model.nunique()) if len(nrf) else 0,
                "median_delta": strat_median(no_rf) if no_rf else float("nan"),
                "holm_confirmed_cells": int(nrf.holm_confirmed_gain.sum()) if len(nrf) else 0,
                "holm_confirmed_datasets": int(
                    nrf[nrf.holm_confirmed_gain].dataset.nunique()) if len(nrf) else 0}),
            "7_stratified_median_delta_aurc": sm_aurc, "7_pass": bool(sm_aurc > 0),
            "8_meta_iso_beats_meta_base": bool(sm > 0),
        }
        c["6_pass"] = bool(no_rf and c["6_without_rf"]["datasets_positive_median"] >= 3
                           and c["6_without_rf"]["families"] >= 2
                           and c["6_without_rf"]["median_delta"] >= DELTA_MIN
                           and c["6_without_rf"]["holm_confirmed_cells"] >= 3
                           and c["6_without_rf"]["holm_confirmed_datasets"] >= 3)
        c["8_pass"] = c["8_meta_iso_beats_meta_base"]
        incr = "YES" if all(c[f"{i}_pass"] for i in range(1, 9)) else "NO"
        rob_ds = "YES" if (c["1_pass"] and c["5_pass"]) else "NO"
        rob_md = "YES" if (c["2_pass"] and c["6_pass"]) else "NO"
        beaten = "YES" if (c["3_pass"] and c["4_pass"] and c["8_pass"]) else "NO"
        res["criteria"] = c
        res["per_dataset_median_delta"] = per_ds.round(5).to_dict()
        res["per_model_median_delta"] = per_md.round(5).to_dict()
    else:
        res["criteria"] = {"note": "aucune cellule CONFIDENCE_WEAK"}
        incr = rob_ds = rob_md = beaten = "NO"

    if not any(v == "EXECUTABLE" for v in res["gate_b"].values()):
        phase = "INCONCLUSIVE_ACCESS"
    elif regime == "YES" and incr == "YES" and rob_ds == "YES" and rob_md == "YES":
        phase = "CONFIRMED"
    elif regime == "NO" and not deltas:
        phase = "FALSIFIED"
    elif incr == "NO" and regime == "NO":
        phase = "FALSIFIED"
    elif incr == "NO":
        phase = "FALSIFIED" if len(deltas) >= 3 else "LIMITED"
    else:
        phase = "LIMITED"

    verdicts = {"REGIME_IDENTIFIABLE": regime, "INCREMENTAL_REGIME": incr,
                "ROBUST_ACROSS_DATASETS": rob_ds, "ROBUST_ACROSS_MODELS": rob_md,
                "PROBABILITY_BASELINE_BEATEN": beaten, "PHASE22_RESULT": phase}
    res["verdicts"] = verdicts
    res["branch_decision"] = ("CONTINUE_TO_VALIDATION" if phase == "CONFIRMED"
                              else "CLOSE_ISOLABILITY_TECH_BRANCH")

    if shift_deltas:
        sdd = pd.DataFrame([{k: v for k, v in d.items() if k != "boot_delta_auroc"}
                            for d in shift_deltas])
        srej = holm([d["p_raw"] for d in shift_deltas])
        sdd["holm_rejected"] = srej
        sdd.to_csv(OUT / "DELTAS_SHIFT.csv", index=False)
        res["natural_shift"] = {"weak_cells": len(shift_deltas),
                                "median_delta_auroc": float(sdd.delta_auroc.median()),
                                "holm_confirmed": int(sum(
                                    r and d > 0 for r, d in zip(srej, sdd.delta_auroc)))}
    elif shift_frozen:
        res["natural_shift"] = {"weak_cells": 0,
                                "note": "aucune cellule CONFIDENCE_WEAK sous shift"}

    (OUT / "logs" / "run.log").write_text("\n".join(log) + "\n")
    json.dump(res, open(OUT / "PHASE22_BR_RESULTS.json", "w"), indent=2, default=str)
    print("\n=== CRITERES ===")
    print(json.dumps(res["criteria"], indent=1, default=str))
    print("\n=== VERDICTS ===")
    for k, v in verdicts.items():
        print(f"{k:30s} {v}")
    print(f"BRANCH_DECISION: {res['branch_decision']}")
    print(f"({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
