"""PHASE 21-IR -- execution of the frozen protocol.

Executes sections 3 to 10 of PROTOCOLE_PHASE21_IR.md
(SHA-256 7d29354cc14ae5f26c4599d1213c70f7fea02f26fb4510ae741bf50a4513369f,
frozen at commit 71980a4, before any result).

fo_metrics is NOT imported. Visibility, Robustness, R7, FO and B* are absent.
The isolability function comes verbatim from src/phase21_ir_iso.py, which
self-checks against the Phase 20-DR frozen source.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from phase21_ir_iso import ISO_KEYS, isolability, verify_verbatim

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase21_ir"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p21")

SEED = 21260821
BOOT = 2000
ALPHA = 0.10
DELTA_MIN = 0.02
MIN_EVENTS = 20
SVM_MAX_TRAIN = 20000

BASELINES = ["B1_max_prob", "B2_entropy", "B3_margin", "B4_knn_dist",
             "B5_mahalanobis", "B6_conformal_aps"]


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def fast_auc(y, s) -> float:
    n1 = float(np.sum(y))
    n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def aurc(err, score) -> float:
    """Area under the risk-coverage curve; low score = confident."""
    o = np.argsort(score, kind="mergesort")
    e = np.asarray(err, dtype=float)[o]
    return float(np.mean(np.cumsum(e) / np.arange(1, len(e) + 1)))


# ------------------------------------------------------------------ loading

def load_secom(acc: dict):
    root = WORK / acc["data"]["repo"].split("/")[-1]
    X = pd.read_csv(root / acc["data"]["path"], sep=r"\s+", header=None,
                    engine="python", na_values=["NaN"]).to_numpy(dtype=float)
    lab = pd.read_csv(root / acc["labels"]["path"], sep=r"\s+", header=None,
                      engine="python")
    y = lab[0].to_numpy()
    rng = np.random.default_rng(SEED)
    split = np.empty(len(y), dtype=object)
    for c in np.unique(y):
        idx = np.flatnonzero(y == c)
        idx = rng.permutation(idx)
        n = len(idx)
        a, b = int(round(0.6 * n)), int(round(0.8 * n))
        split[idx[:a]] = "train"
        split[idx[a:b]] = "calib"
        split[idx[b:]] = "test"
    return X, y, split, np.arange(len(y))


def load_steel(acc: dict):
    root = WORK / acc["data"]["repo"].split("/")[-1]
    d = pd.read_csv(root / acc["data"]["path"], sep=r"\s+", header=None,
                    engine="python").to_numpy(dtype=float)
    X, Y = d[:, :27], d[:, 27:34]
    y = Y.argmax(axis=1)
    rng = np.random.default_rng(SEED)
    split = np.empty(len(y), dtype=object)
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        n = len(idx)
        a, b = int(round(0.6 * n)), int(round(0.8 * n))
        split[idx[:a]] = "train"
        split[idx[a:b]] = "calib"
        split[idx[b:]] = "test"
    return X, y, split, np.arange(len(y))


def load_har(acc: dict):
    root = WORK / acc["X_train"]["repo"].split("/")[-1]
    Xtr = np.loadtxt(root / acc["X_train"]["path"])
    Xte = np.loadtxt(root / acc["X_test"]["path"])
    ytr = np.loadtxt(root / acc["y_train"]["path"], dtype=int)
    yte = np.loadtxt(root / acc["y_test"]["path"], dtype=int)
    str_ = np.loadtxt(root / acc["s_train"]["path"], dtype=int)
    ste = np.loadtxt(root / acc["s_test"]["path"], dtype=int)
    subs = np.unique(str_)
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(subs)
    tr_subj, ca_subj = set(perm[:15].tolist()), set(perm[15:].tolist())
    split_tr = np.array(["train" if s in tr_subj else "calib" for s in str_], dtype=object)
    X = np.vstack([Xtr, Xte])
    y = np.r_[ytr, yte]
    split = np.r_[split_tr, np.array(["test"] * len(yte), dtype=object)]
    group = np.r_[str_, ste]
    return X, y, split, group


LOADERS = {"SECOM": load_secom, "STEEL": load_steel, "HAR": load_har}


# ------------------------------------------------------------ preprocessing

def preprocess(X, split):
    tr = split == "train"
    keep = np.nanstd(X[tr], axis=0) > 0
    keep &= ~np.all(np.isnan(X[tr]), axis=0)
    X = X[:, keep]
    miss_rate = np.isnan(X[tr]).mean(axis=0)
    ind_cols = np.flatnonzero(miss_rate > 0.05)
    med = np.nanmedian(X[tr], axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    ind = np.isnan(X[:, ind_cols]).astype(float) if len(ind_cols) else None
    Xf = np.where(np.isnan(X), med[None, :], X)
    if ind is not None:
        Xf = np.hstack([Xf, ind])
    sc = StandardScaler().fit(Xf[tr])
    Z = sc.transform(Xf)
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    return Z, {"n_features_kept": int(keep.sum()),
               "n_missing_indicators": int(len(ind_cols)),
               "n_features_final": int(Z.shape[1])}


def make_models():
    return {
        "M1_logreg": LogisticRegression(max_iter=5000, C=1.0, random_state=SEED),
        "M2_rbf_svm": SVC(C=1.0, gamma="scale", probability=True, random_state=SEED),
        "M3_random_forest": RandomForestClassifier(n_estimators=500, random_state=SEED,
                                                   n_jobs=-1),
        "M4_hist_gradient_boosting": HistGradientBoostingClassifier(random_state=SEED),
    }


# --------------------------------------------------------------- baselines

def conformal_aps(p_cal, y_cal, classes, p_eval) -> np.ndarray:
    """Adaptive Prediction Sets (Romano, Sesia & Candes 2020), non-randomised.
    Score returned = size of the prediction set at level ALPHA."""
    ci = {c: i for i, c in enumerate(classes)}
    order = np.argsort(-p_cal, axis=1)
    srt = np.take_along_axis(p_cal, order, axis=1)
    csum = np.cumsum(srt, axis=1)
    rank_true = np.array([np.flatnonzero(order[i] == ci[y_cal[i]])[0]
                          for i in range(len(y_cal))])
    scores = csum[np.arange(len(y_cal)), rank_true]
    n = len(scores)
    q = float(np.quantile(scores, min(1.0, np.ceil((n + 1) * (1 - ALPHA)) / n),
                          method="higher"))
    oe = np.argsort(-p_eval, axis=1)
    se = np.take_along_axis(p_eval, oe, axis=1)
    ce = np.cumsum(se, axis=1)
    return (ce < q).sum(axis=1) + 1.0


def baselines(Z, split, y, proba, classes, Sinv, cents):
    tr = split == "train"
    out = {}
    srt = np.sort(proba, axis=1)[:, ::-1]
    out["B1_max_prob"] = -srt[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        out["B2_entropy"] = -(proba * np.log(np.maximum(proba, 1e-300))).sum(1)
    out["B3_margin"] = -(srt[:, 0] - (srt[:, 1] if srt.shape[1] > 1 else 0.0))
    nn = NearestNeighbors(n_neighbors=10, algorithm="brute").fit(Z[tr])
    d, _ = nn.kneighbors(Z)
    out["B4_knn_dist"] = d.mean(axis=1)
    ks = sorted(cents)
    C = np.stack([cents[k] for k in ks])
    diff = Z[:, None, :] - C[None, :, :]
    d2 = np.maximum(np.einsum("nkc,cd,nkd->nk", diff, Sinv, diff), 0.0)
    out["B5_mahalanobis"] = d2.min(axis=1)
    ca = split == "calib"
    out["B6_conformal_aps"] = conformal_aps(proba[ca], y[ca], classes, proba)
    return out


# ------------------------------------------------------------------- cells

def run_cell(ds, mname, model, Z, y, split, group, log) -> dict | None:
    t0 = time.time()
    tr, ca, te = (split == "train"), (split == "calib"), (split == "test")
    Ztr, ytr = Z[tr], y[tr]
    if mname == "M2_rbf_svm" and tr.sum() > SVM_MAX_TRAIN:
        rng = np.random.default_rng(SEED)
        sel = np.concatenate([rng.permutation(np.flatnonzero(ytr == c))[
            :max(1, int(SVM_MAX_TRAIN * (ytr == c).mean()))] for c in np.unique(ytr)])
        Ztr, ytr = Ztr[sel], ytr[sel]
        log.append(f"{ds}/{mname}: SVM sous-echantillonne a {len(sel)} lignes (regle gelee)")
    model.fit(Ztr, ytr)
    classes = model.classes_
    proba = model.predict_proba(Z)
    pred = classes[proba.argmax(1)]
    err = (pred != y).astype(int)

    lw = LedoitWolf(assume_centered=False).fit(Z[tr])
    Sinv = np.linalg.pinv(lw.covariance_)
    cents = {k: Z[tr & (y == k)].mean(0) for k in np.unique(y)}

    iso_pred = isolability(Z, pred, cents, Sinv)       # ISO_PRED, no test label
    iso_frozen = isolability(Z, y, cents, Sinv)        # ISO_FROZEN, ORACLE
    base = baselines(Z, split, y, proba, classes, Sinv, cents)

    def fit_iso(d):
        F = slog(np.column_stack([d[k] for k in ISO_KEYS]))
        sc = StandardScaler().fit(F[ca])
        clf = LogisticRegression(max_iter=5000, random_state=SEED).fit(sc.transform(F[ca]),
                                                                      err[ca])
        return clf.predict_proba(sc.transform(F))[:, 1]

    n_err_te = int(err[te].sum())
    if n_err_te < MIN_EVENTS or len(np.unique(err[ca])) < 2:
        log.append(f"{ds}/{mname}: NOT_EVALUABLE_LOW_EVENTS "
                   f"({n_err_te} erreurs sur TEST, calib={int(err[ca].sum())})")
        return {"dataset": ds, "model": mname, "status": "NOT_EVALUABLE_LOW_EVENTS",
                "n_test": int(te.sum()), "n_errors_test": n_err_te,
                "test_accuracy": float(1 - err[te].mean())}

    scores = dict(base)
    scores["ISO_FIT"] = fit_iso(iso_pred)
    scores["ISO_RAW"] = -iso_pred["iso_margin_ratio"]
    scores["ISO_FROZEN_ORACLE"] = fit_iso(iso_frozen)

    auc_cal = {k: fast_auc(err[ca], v[ca]) for k, v in scores.items()}
    best_b = max(BASELINES, key=lambda b: auc_cal[b])
    cons_b = max(BASELINES, key=lambda b: fast_auc(err[te], scores[b][te]))

    F = np.column_stack([slog(scores[best_b]), scores["ISO_FIT"]])
    scc = StandardScaler().fit(F[ca])
    combo = LogisticRegression(max_iter=5000, random_state=SEED).fit(scc.transform(F[ca]),
                                                                    err[ca])
    scores["COMBO_best_plus_iso"] = combo.predict_proba(scc.transform(F))[:, 1]

    rows = []
    for k, v in scores.items():
        rows.append({"dataset": ds, "model": mname, "score": k,
                     "auroc": fast_auc(err[te], v[te]),
                     "auprc": float(average_precision_score(err[te], v[te])),
                     "aurc": aurc(err[te], v[te]),
                     "auroc_calib": auc_cal.get(k, float("nan"))})

    # paired bootstrap, unit = row, or subject for HAR
    gte = group[te]
    ug = np.unique(gte)
    byg = {g: np.flatnonzero(gte == g) for g in ug}
    rng = np.random.default_rng(SEED + 7)
    keys = list(scores)
    ete = err[te]
    Ste = {k: scores[k][te] for k in keys}
    B = np.empty((BOOT, len(keys)))
    for b in range(BOOT):
        pick = rng.choice(ug, size=len(ug), replace=True)
        ii = np.concatenate([byg[g] for g in pick])
        yy = ete[ii]
        for j, k in enumerate(keys):
            B[b, j] = fast_auc(yy, Ste[k][ii])
    ki = {k: j for j, k in enumerate(keys)}
    pt = {r["score"]: r["auroc"] for r in rows}

    def con(a, b):
        d = pt[a] - pt[b]
        dd = B[:, ki[a]] - B[:, ki[b]]
        dd = dd[~np.isnan(dd)]
        lo, hi = np.percentile(dd, [2.5, 97.5])
        return {"contrast": f"{a} - {b}", "delta_auroc": float(d),
                "ci_low": float(lo), "ci_high": float(hi),
                "excludes_zero": bool(lo > 0 or hi < 0)}

    contrasts = [con("ISO_FIT", best_b), con("ISO_FIT", cons_b),
                 con("COMBO_best_plus_iso", best_b),
                 con("ISO_FROZEN_ORACLE", best_b)]
    lo, hi = np.percentile(B[:, ki["ISO_FIT"]], [2.5, 97.5])

    log.append(f"{ds}/{mname}: acc={1-err[te].mean():.4f} err={n_err_te} "
               f"ISO_FIT={pt['ISO_FIT']:.3f} best={best_b}({pt[best_b]:.3f}) "
               f"({time.time()-t0:.0f}s)")
    return {"dataset": ds, "model": mname, "status": "OK",
            "n_train": int(tr.sum()), "n_calib": int(ca.sum()), "n_test": int(te.sum()),
            "n_errors_test": n_err_te, "test_accuracy": float(1 - err[te].mean()),
            "n_classes": int(len(classes)),
            "best_baseline_on_calib": best_b, "best_baseline_on_test": cons_b,
            "iso_fit_auroc": pt["ISO_FIT"],
            "iso_fit_ci_low": float(lo), "iso_fit_ci_high": float(hi),
            "rows": rows, "contrasts": contrasts,
            "bootstrap_unit": "sujet" if ds == "HAR" else "ligne"}


def main() -> int:
    t0 = time.time()
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    vv = verify_verbatim()
    print(json.dumps(vv), flush=True)
    gate = json.load(open(OUT / "GATE_A.json"))
    log: list[str] = []
    cells, allrows, allcon = [], [], []
    for ds in ("SECOM", "STEEL", "HAR"):
        if gate[ds]["status"] != "EXECUTABLE":
            continue
        X, y, split, group = LOADERS[ds](gate[ds]["accepted"])
        Z, pinfo = preprocess(X, split)
        print(f"\n== {ds} == X{X.shape} -> Z{Z.shape} {pinfo} "
              f"split={pd.Series(split).value_counts().to_dict()}", flush=True)
        for mname, model in make_models().items():
            try:
                c = run_cell(ds, mname, model, Z, y, split, group, log)
            except Exception as e:
                c = {"dataset": ds, "model": mname, "status": f"NOT_EXECUTABLE: {e}"}
                log.append(f"{ds}/{mname}: NOT_EXECUTABLE {e}")
            c["preprocess"] = pinfo
            cells.append(c)
            for r in c.pop("rows", []):
                allrows.append(r)
            for k in c.pop("contrasts", []):
                allcon.append({"dataset": ds, "model": mname, **k})
            print("  " + (log[-1] if log else ""), flush=True)

    pd.DataFrame(allrows).to_csv(OUT / "CELL_SCORES.csv", index=False)
    pd.DataFrame(allcon).to_csv(OUT / "CELL_CONTRASTS.csv", index=False)
    pd.DataFrame(cells).to_csv(OUT / "CELL_SUMMARY.csv", index=False)
    (OUT / "logs" / "run.log").write_text("\n".join(log) + "\n")

    # ---------------- verdicts, criteria frozen in section 9 --------------
    ok = [c for c in cells if c.get("status") == "OK"]
    a = np.array([c["iso_fit_auroc"] for c in ok])
    above = np.array([c["iso_fit_ci_low"] > 0.50 for c in ok])
    ds_ok = {c["dataset"] for c in ok if c["iso_fit_ci_low"] > 0.50}
    md_ok = {c["model"] for c in ok if c["iso_fit_ci_low"] > 0.50}
    no_rf = [c for c in ok if c["model"] != "M3_random_forest"]
    a_nrf = np.array([c["iso_fit_auroc"] for c in no_rf])
    ab_nrf = np.array([c["iso_fit_ci_low"] > 0.50 for c in no_rf])
    dsn = {c["dataset"] for c in no_rf if c["iso_fit_ci_low"] > 0.50}
    mdn = {c["model"] for c in no_rf if c["iso_fit_ci_low"] > 0.50}

    crit = {
        "n_cells_ok": len(ok),
        "c1_median_auroc": float(np.median(a)) if len(a) else float("nan"),
        "c1_pass": bool(len(a) and np.median(a) >= 0.70),
        "c2_frac_ci_above_half": float(above.mean()) if len(above) else 0.0,
        "c2_pass": bool(len(above) and above.mean() >= 2 / 3),
        "c3_n_datasets": len(ds_ok), "c3_n_models": len(md_ok),
        "c3_pass": bool(len(ds_ok) >= 2 and len(md_ok) >= 2),
        "c4_without_rf": {
            "median_auroc": float(np.median(a_nrf)) if len(a_nrf) else float("nan"),
            "frac_ci_above_half": float(ab_nrf.mean()) if len(ab_nrf) else 0.0,
            "n_datasets": len(dsn), "n_models": len(mdn)},
    }
    crit["c4_pass"] = bool(len(a_nrf) and np.median(a_nrf) >= 0.70
                           and ab_nrf.mean() >= 2 / 3
                           and len(dsn) >= 2 and len(mdn) >= 2)
    enough = (len(ok) >= 4 and len({c["dataset"] for c in ok}) >= 2
              and len({c["model"] for c in ok}) >= 2)
    allc = crit["c1_pass"] and crit["c2_pass"] and crit["c3_pass"] and crit["c4_pass"]
    if not enough:
        gen = "NO"
    elif allc:
        gen = "YES"
    elif crit["c1_pass"] or crit["c2_pass"]:
        gen = "PARTIAL"
    else:
        gen = "NO"

    cdf = pd.DataFrame(allcon)
    inc = {}
    for tag, key in (("iso_vs_best", "ISO_FIT - "), ("combo_vs_best", "COMBO_best_plus_iso - ")):
        s = cdf[cdf.contrast.str.startswith(key)]
        s = s[s.contrast.str.endswith(tuple(BASELINES))]
        win = s[(s.delta_auroc >= DELTA_MIN) & s.excludes_zero]
        inc[tag] = {"n_cells": int(len(s)), "n_confirmed_gain": int(len(win)),
                    "median_delta": float(s.delta_auroc.median()) if len(s) else float("nan"),
                    "cells": win[["dataset", "model", "delta_auroc"]].to_dict("records")}
    incr = "YES" if (inc["iso_vs_best"]["n_confirmed_gain"] > 0
                     or inc["combo_vs_best"]["n_confirmed_gain"] > 0) else "NO"
    nov = "SUPPORTED" if (gen == "YES" and incr == "YES") else "NOT_SUPPORTED"
    p22 = "YES" if (gen == "YES" and incr == "YES") else "NO"

    verdicts = {"GENERALIZATION": gen, "INCREMENTAL_VALUE": incr,
                "NOVELTY_SIGNAL": nov, "PHASE22_AUTHORIZED": p22}
    res = {"verbatim_check": vv, "gate_a": {k: gate[k]["status"] for k in gate},
           "criteria": crit, "incremental": inc, "verdicts": verdicts,
           "cells": cells}
    json.dump(res, open(OUT / "PHASE21_IR_RESULTS.json", "w"), indent=2, default=str)

    print("\n=== CRITERES ===")
    print(json.dumps(crit, indent=1))
    print("\n=== VERDICTS ===")
    for k, v in verdicts.items():
        print(f"{k:22s} {v}")
    print(f"({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
