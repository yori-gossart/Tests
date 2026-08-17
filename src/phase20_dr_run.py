"""PHASE 20-DR -- Diagnostic Readiness on the ZeMA physical rig.

Executes PROTOCOLE_PHASE20_DR.md (frozen at 925fd37, amended at 62e5a24 and
ac563f4, all before any result).

fo_metrics is NOT imported and no FO or B* quantity is computed anywhere here.
The additive noise is a robustness stressor for the standard diagnostic system;
it is never an FO sigma.
"""

from __future__ import annotations

import json
import sys
import time
from itertools import groupby
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score,
                             log_loss, roc_auc_score)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase20_dr"
DATA = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/hyd/Hydraulic-systems/data")

SENSORS = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2",
           "TS1", "TS2", "TS3", "TS4", "VS1", "SE", "CE", "CP"]
GROUPS = {"PRESSURE": ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6"],
          "TEMPERATURE": ["TS1", "TS2", "TS3", "TS4"],
          "FLOW": ["FS1", "FS2"],
          "OTHER": ["EPS1", "VS1", "SE", "CE", "CP"]}
STAT_NAMES = ["mean", "std", "min", "max", "q25", "median", "q75", "slope"]
BIAS_DRIFT_SENSORS = ["PS1", "PS3", "TS1", "FS1", "EPS1"]
SEED = 20260817
BOOT = 2000
DELTA_MIN = 0.02
TARGETS = {"valve": 100, "pump": 0}
OTHERS = {"valve": ["cooler", "pump", "acc"], "pump": ["cooler", "valve", "acc"]}


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


# ------------------------------------------------------------------ loading

def load_raw() -> tuple[dict, pd.DataFrame, np.ndarray]:
    prof = pd.read_csv(DATA / "profile.txt", sep="\t", header=None,
                       names=["cooler", "valve", "pump", "acc", "stable"])
    prof["cfg"] = prof[["cooler", "valve", "pump", "acc"]].astype(str).agg("|".join, axis=1)
    keep = (prof.stable == 0).to_numpy()
    raw = {}
    for s in SENSORS:
        a = np.loadtxt(DATA / f"{s}.txt", delimiter="\t", dtype=np.float32)
        raw[s] = a[keep]
    return raw, prof[keep].reset_index(drop=True), keep


def stress_scale(raw: dict) -> dict:
    """Amendment 1: the scale at the level the perturbation is applied."""
    return {s: float(np.median(a.std(axis=1))) for s, a in raw.items()}


def make_split(prof: pd.DataFrame) -> pd.Series:
    cc = prof.groupby("cfg").agg(valve=("valve", "first"), pump=("pump", "first")).reset_index()
    cc["cell"] = cc.valve.astype(str) + "_" + cc.pump.astype(str)
    rng = np.random.default_rng(SEED)
    assign = {}
    for cell, g in cc.groupby("cell"):
        idx = rng.permutation(g.cfg.to_numpy())
        for c in idx[:7]:
            assign[c] = "train"
        for c in idx[7:9]:
            assign[c] = "valid"
        for c in idx[9:]:
            assign[c] = "test"
    return prof.cfg.map(assign)


# ------------------------------------------------------------ perturbations

def conditions() -> list[dict]:
    c = [{"name": "baseline", "family": "baseline", "drop": [], "kind": None}]
    for s in SENSORS:
        c.append({"name": f"drop_{s}", "family": "drop_one", "drop": [s], "kind": None})
    for g, ss in GROUPS.items():
        c.append({"name": f"dropgroup_{g}", "family": "drop_group", "drop": list(ss), "kind": None})
    for k in (2, 4, 8):
        c.append({"name": f"noise_x{k}", "family": "noise", "drop": [], "kind": ("noise", k)})
    for k in (2, 5, 10):
        c.append({"name": f"downsample_{k}", "family": "downsample", "drop": [],
                  "kind": ("downsample", k)})
    for s in BIAS_DRIFT_SENSORS:
        c.append({"name": f"bias_{s}", "family": "bias", "drop": [], "kind": ("bias", s)})
    for s in BIAS_DRIFT_SENSORS:
        c.append({"name": f"drift_{s}", "family": "drift", "drop": [], "kind": ("drift", s)})
    return c


def restore_conditions() -> list[dict]:
    """Group drop with exactly one sensor put back -- the action-test grid."""
    out = []
    for g, ss in GROUPS.items():
        for s in ss:
            out.append({"name": f"restore_{g}_{s}", "family": "restore",
                        "drop": [x for x in ss if x != s], "kind": None,
                        "group": g, "restored": s})
    return out


def cycle_stats(a: np.ndarray) -> np.ndarray:
    """(n_cycles, n_samples) -> (n_cycles, 8) frozen statistics."""
    n = a.shape[1]
    t = np.arange(n, dtype=np.float64)
    tc = t - t.mean()
    denom = float((tc ** 2).sum())
    slope = (a * tc[None, :]).sum(axis=1) / denom
    q = np.quantile(a, [0.25, 0.5, 0.75], axis=1)
    return np.column_stack([a.mean(1), a.std(1), a.min(1), a.max(1), q[0], q[1], q[2], slope])


def build_features(raw: dict, cond: dict, scale: dict, rng: np.random.Generator) -> tuple:
    cols, names, available = [], [], []
    for s in SENSORS:
        a = raw[s]
        if s in cond["drop"]:
            cols.append(np.full((a.shape[0], 8), np.nan))
            names += [f"{s}_{k}" for k in STAT_NAMES]
            available.append(0)
            continue
        k = cond["kind"]
        b = a
        if k is not None:
            if k[0] == "noise":
                b = a + rng.normal(0.0, k[1] * scale[s], size=a.shape).astype(np.float32)
            elif k[0] == "downsample":
                b = a[:, ::k[1]]
            elif k[0] == "bias" and k[1] == s:
                b = a + np.float32(2.0 * scale[s])
            elif k[0] == "drift" and k[1] == s:
                ramp = np.linspace(0, 4.0 * scale[s], a.shape[1], dtype=np.float32)
                b = a + ramp[None, :]
        cols.append(cycle_stats(b.astype(np.float64)))
        names += [f"{s}_{k2}" for k2 in STAT_NAMES]
        available.append(1)
    return np.hstack(cols), names, np.asarray(available)


# ------------------------------------------------------------ readiness axes

def healthy_reference(X: np.ndarray, prof: pd.DataFrame, split: pd.Series,
                      target: str) -> tuple[dict, np.ndarray, np.ndarray]:
    """TRAIN-only healthy reference, exact context first, marginal as fallback
    (amendment 2). Returns per-context (mu, sd), the marginal pair, and the
    per-cycle fallback flag."""
    opt = TARGETS[target]
    ctx = prof[OTHERS[target]].astype(str).agg("|".join, axis=1).to_numpy()
    tr_h = ((split == "train") & (prof[target] == opt)).to_numpy()
    per_ctx = {}
    for c in np.unique(ctx[tr_h]):
        m = tr_h & (ctx == c)
        if m.sum() >= 3:
            per_ctx[c] = (X[m].mean(0), np.maximum(X[m].std(0), 1e-12))
    marg = (X[tr_h].mean(0), np.maximum(X[tr_h].std(0), 1e-12))
    fallback = np.array([c not in per_ctx for c in ctx])
    return per_ctx, marg, fallback, ctx


def visibility(X: np.ndarray, ctx: np.ndarray, per_ctx: dict, marg: tuple,
               Sinv: np.ndarray, raw: dict, cond: dict) -> dict:
    mu = np.array([per_ctx.get(c, marg)[0] for c in ctx])
    sd = np.array([per_ctx.get(c, marg)[1] for c in ctx])
    d = X - mu
    maha = np.einsum("nc,cd,nd->n", d, Sinv, d)
    eff = np.abs(d / sd).max(axis=1)
    # Wasserstein-1 proxy on the feature marginals: mean |quantile difference|
    wass = np.abs(d / sd).mean(axis=1)
    return {"vis_mahalanobis": np.maximum(maha, 0.0),
            "vis_effect_size": eff, "vis_wasserstein": wass}


def isolability(X: np.ndarray, y: np.ndarray, cents: dict, Sinv: np.ndarray) -> dict:
    ks = sorted(cents)
    C = np.stack([cents[k] for k in ks])
    diff = X[:, None, :] - C[None, :, :]
    d2 = np.maximum(np.einsum("nkc,cd,nkd->nk", diff, Sinv, diff), 0.0)
    own = np.array([ks.index(v) for v in y])
    mask = np.ones_like(d2, dtype=bool)
    mask[np.arange(len(y)), own] = False
    d_own = np.sqrt(d2[np.arange(len(y)), own])
    d_near = np.sqrt(np.where(mask, d2, np.inf).min(axis=1))
    cd = np.array([[np.sqrt(max((C[i] - C[j]) @ Sinv @ (C[i] - C[j]), 0.0))
                    for j in range(len(ks))] for i in range(len(ks))])
    np.fill_diagonal(cd, np.inf)
    cmin = np.array([cd[own[i]].min() for i in range(len(y))])
    return {"iso_d_nearest": d_near, "iso_margin_ratio": d_near / (d_own + 1.0),
            "iso_centroid_min": cmin}


def robustness(X: np.ndarray, y: np.ndarray, cents: dict, Sfull: np.ndarray,
               avail: np.ndarray, iso_full: np.ndarray) -> dict:
    """Leave-one-channel-out retention, effective rank, cross-channel redundancy."""
    ks = sorted(cents)
    C = np.stack([cents[k] for k in ks])
    own = np.array([ks.index(v) for v in y])
    ratios = []
    for j, ok in enumerate(avail):
        if not ok:
            continue
        keep = np.ones(X.shape[1], dtype=bool)
        keep[j * 8:(j + 1) * 8] = False
        Sj = np.linalg.inv(Sfull[np.ix_(keep, keep)])
        diff = X[:, None, keep] - C[None, :, keep]
        d2 = np.maximum(np.einsum("nkc,cd,nkd->nk", diff, Sj, diff), 0.0)
        m = np.ones_like(d2, dtype=bool)
        m[np.arange(len(y)), own] = False
        ratios.append(np.sqrt(np.where(m, d2, np.inf).min(axis=1)) / np.maximum(iso_full, 1e-12))
    loco = np.min(np.stack(ratios), axis=0) if ratios else np.zeros(len(y))

    lam = np.maximum(np.linalg.eigvalsh(Sfull), 1e-15)
    p = lam / lam.sum()
    eff_rank = float(np.exp(-(p * np.log(p)).sum()))

    idx = np.flatnonzero(avail)
    if len(idx) >= 2:
        M = np.column_stack([X[:, j * 8] for j in idx])
        r2 = []
        for c in range(M.shape[1]):
            oth = np.delete(M, c, axis=1)
            r2.append(max(LinearRegression().fit(oth, M[:, c]).score(oth, M[:, c]), 0.0))
        red = float(np.mean(r2))
    else:
        red = 0.0
    return {"rob_loco_min": loco,
            "rob_effective_rank": np.full(len(y), eff_rank),
            "rob_redundancy": np.full(len(y), red)}


# --------------------------------------------------------------- classifier

def clf_metrics(y, pred, proba, classes) -> dict:
    Y = np.zeros((len(y), len(classes)))
    for i, c in enumerate(classes):
        Y[:, i] = (y == c).astype(float)
    try:
        auroc = roc_auc_score(Y, proba, average="macro", multi_class="ovr")
    except ValueError:
        auroc = float("nan")
    return {"balanced_accuracy": balanced_accuracy_score(y, pred),
            "macro_f1": f1_score(y, pred, average="macro"),
            "auroc_ovr_macro": auroc,
            "log_loss": log_loss(y, proba, labels=list(classes)),
            "brier": float(np.mean(np.sum((proba - Y) ** 2, axis=1)))}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)
    raw, prof, _ = load_raw()
    scale = stress_scale(raw)
    split = make_split(prof)
    prof = prof.assign(split=split)
    prof.to_csv(OUT / "SPLIT_ASSIGNMENT.csv", index=False)
    json.dump(scale, open(OUT / "STRESS_SCALE.json", "w"), indent=2)
    print(f"cycles={len(prof)} split={prof.split.value_counts().to_dict()} "
          f"({time.time()-t0:.0f}s)", flush=True)

    conds = conditions() + restore_conditions()
    rng = np.random.default_rng(SEED)
    rows, clf_rows, conf_rows = [], [], []

    for ci, cond in enumerate(conds):
        X, names, avail = build_features(raw, cond, scale, rng)
        Xf = np.nan_to_num(X, nan=0.0)
        tr = (prof.split == "train").to_numpy()
        # frozen imputation: dropped channels take the TRAIN mean of each feature
        if cond["drop"]:
            mu_tr = np.nanmean(np.where(np.isnan(X), np.nan, X)[tr], axis=0)
            mu_tr = np.nan_to_num(mu_tr, nan=0.0)
            Xf = np.where(np.isnan(X), mu_tr[None, :], X)

        for target in ("valve", "pump"):
            y = prof[target].to_numpy()
            rf = RandomForestClassifier(n_estimators=500, random_state=SEED, n_jobs=-1)
            rf.fit(Xf[tr], y[tr])
            proba = rf.predict_proba(Xf)
            pred = rf.classes_[proba.argmax(1)]

            lw = LedoitWolf(assume_centered=False).fit(Xf[tr])
            S = lw.covariance_
            Sinv = np.linalg.pinv(S)
            per_ctx, marg, fb, ctx = healthy_reference(Xf, prof, prof.split, target)
            cents = {k: Xf[tr & (y == k)].mean(0) for k in np.unique(y)}

            vis = visibility(Xf, ctx, per_ctx, marg, Sinv, raw, cond)
            iso = isolability(Xf, y, cents, Sinv)
            rob = robustness(Xf, y, cents, S, avail, iso["iso_d_nearest"])

            srt = np.sort(proba, axis=1)[:, ::-1]
            with np.errstate(divide="ignore"):
                ent = -(proba * np.log(np.maximum(proba, 1e-300))).sum(1)

            rec = {"condition": cond["name"], "family": cond["family"], "target": target,
                   "cfg": prof.cfg.to_numpy(), "split": prof.split.to_numpy(),
                   "y_true": y, "y_pred": pred,
                   "failure": (pred != y).astype(int),
                   "n_sensors": int(avail.sum()), "fallback_reference": fb.astype(int),
                   "rf_margin": srt[:, 0] - srt[:, 1], "rf_entropy": ent}
            rec.update(vis); rec.update(iso); rec.update(rob)
            rows.append(pd.DataFrame(rec))

            for sp in ("train", "valid", "test"):
                m = (prof.split == sp).to_numpy()
                cm = clf_metrics(y[m], pred[m], proba[m], rf.classes_)
                clf_rows.append({"condition": cond["name"], "family": cond["family"],
                                 "target": target, "split": sp, "n": int(m.sum()),
                                 "n_sensors": int(avail.sum()), **cm})
                if sp == "test":
                    C = confusion_matrix(y[m], pred[m], labels=list(rf.classes_))
                    for i, a in enumerate(rf.classes_):
                        for j, b in enumerate(rf.classes_):
                            conf_rows.append({"condition": cond["name"], "target": target,
                                              "true": int(a), "pred": int(b),
                                              "n": int(C[i, j])})
        if (ci + 1) % 5 == 0:
            print(f"  {ci+1}/{len(conds)} conditions ({time.time()-t0:.0f}s)", flush=True)

    ev = pd.concat(rows, ignore_index=True)
    ev.to_csv(OUT / "READINESS_EVENTS.csv.gz", index=False, compression="gzip")
    pd.DataFrame(clf_rows).to_csv(OUT / "CLASSIFIER_METRICS.csv", index=False)
    pd.DataFrame(conf_rows).to_csv(OUT / "CONFUSION_MATRICES.csv", index=False)
    print(f"events={len(ev)} ({time.time()-t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
