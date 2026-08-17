"""PHASE 20-DR -- confirmatory analysis of the Diagnostic Readiness architecture.

Executes sections 6, 7, 8 and 9 of PROTOCOLE_PHASE20_DR.md (frozen at 925fd37,
amended at 62e5a24 and ac563f4).

fo_metrics is NOT imported. No FO or B* quantity appears anywhere.

Operationalisations required by the protocol but not spelled out in it are fixed
HERE, in code, and this file is committed before any TEST endpoint is read.
They are listed in OPERATIONALISATIONS below and repeated in the report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.feature_selection import f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, normalized_mutual_info_score
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase20_dr"

SEED = 20260817
BOOT = 2000
DELTA_MIN = 0.02

VIS = ["vis_mahalanobis", "vis_effect_size", "vis_wasserstein"]
ISO = ["iso_d_nearest", "iso_margin_ratio", "iso_centroid_min"]
ROB = ["rob_loco_min", "rob_effective_rank", "rob_redundancy"]
CTRL = ["n_sensors"]

LADDER = {"R0": CTRL, "R1": VIS, "R2": ISO, "R3": ROB,
          "R4": VIS + ISO, "R5": VIS + ROB, "R6": ISO + ROB,
          "R7": VIS + ROB + ISO}

SENSORS = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2",
           "TS1", "TS2", "TS3", "TS4", "VS1", "SE", "CE", "CP"]
GROUPS = {"PRESSURE": ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6"],
          "TEMPERATURE": ["TS1", "TS2", "TS3", "TS4"],
          "FLOW": ["FS1", "FS2"],
          "OTHER": ["EPS1", "VS1", "SE", "CE", "CP"]}
STAT_NAMES = ["mean", "std", "min", "max", "q25", "median", "q75", "slope"]
TARGETS = {"valve": 100, "pump": 0}

CAUSES = ["LOW_VISIBILITY", "LOW_ISOLABILITY", "LOW_ROBUSTNESS",
          "CLASSIFIER_LIMITED", "MIXED_UNKNOWN"]

OPERATIONALISATIONS = {
    "axis_score": "mean of the TRAIN-standardised signed-log of the three metrics of "
                  "the axis, oriented so that HIGHER = better readiness",
    "low_tertile": "axis score below the 33.33th percentile of the TRAIN distribution "
                   "of that axis score",
    "readiness_fit_set": "TRAIN + VALID rows of the 38 pre-registered conditions, "
                         "both targets pooled; TEST opened only for the endpoints",
    "best_single_and_best_pair": "selected on VALID, never on TEST",
    "univariate_sensor_ranking": "ANOVA F of the 8 baseline features of the sensor "
                                 "against the target on TRAIN, averaged as a rank over "
                                 "the two targets; one global ranking, identical for "
                                 "every case (protocol 8, ACTION_GENERIC)",
    "most_discriminant_sensor": "top of that global ranking; only that drop_one "
                                "condition carries a declared expected cause",
    "case_cause": "modal attributed cause over the TRAIN+VALID failing cycles of the "
                  "degraded case; CLASSIFIER_LIMITED if that case has no failure",
    "mixed_action_rule": "protocol 8 declares no action for MIXED; extension fixed "
                         "here: apply the rule of the lowest-scoring low axis",
    "action_endpoint": "balanced accuracy on TEST of the frozen classifier of the "
                       "restore condition selected by the strategy, minus the "
                       "balanced accuracy of the degraded condition, averaged over "
                       "the 8 cases; bootstrap resamples TEST configurations",
}


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def fast_auc(y: np.ndarray, s: np.ndarray) -> float:
    n1 = float(y.sum())
    n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def calib_slope(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    lg = np.log(p / (1 - p)).reshape(-1, 1)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(LogisticRegression(max_iter=5000).fit(lg, y).coef_[0, 0])


def bal_acc(y: np.ndarray, p: np.ndarray, classes) -> float:
    rec = []
    for c in classes:
        m = y == c
        if m.sum():
            rec.append(float((p[m] == c).mean()))
    return float(np.mean(rec)) if rec else float("nan")


# ----------------------------------------------------------------- ladder

def fit_ladder(ev: pd.DataFrame) -> tuple[dict, dict]:
    fitm = ev.split.isin(["train", "valid"]).to_numpy()
    y = ev.failure.to_numpy()
    scores = {}
    models = {}
    for name, cols in LADDER.items():
        X = slog(ev[cols].to_numpy(dtype=float))
        sc = StandardScaler().fit(X[fitm])
        clf = LogisticRegression(max_iter=5000).fit(sc.transform(X[fitm]), y[fitm])
        scores[name] = clf.predict_proba(sc.transform(X))[:, 1]
        models[name] = (sc, clf, cols)
    return scores, models


def ladder_endpoints(y, scores, mask) -> pd.DataFrame:
    rows = []
    for name, s in scores.items():
        yy, ss = y[mask], s[mask]
        rows.append({"model": name, "n_features": len(LADDER[name]),
                     "auroc": fast_auc(yy, ss),
                     "auprc": float(average_precision_score(yy, ss)),
                     "brier": float(np.mean((ss - yy) ** 2)),
                     "log_loss": float(-np.mean(yy * np.log(np.clip(ss, 1e-12, 1)) +
                                                (1 - yy) * np.log(np.clip(1 - ss, 1e-12, 1)))),
                     "calibration_slope": calib_slope(yy, ss),
                     "base_rate": float(yy.mean()), "n": int(mask.sum())})
    return pd.DataFrame(rows)


def boot_indices(cfgs: np.ndarray, rng) -> list[np.ndarray]:
    uc = np.unique(cfgs)
    byc = {c: np.flatnonzero(cfgs == c) for c in uc}
    out = []
    for _ in range(BOOT):
        pick = rng.choice(uc, size=len(uc), replace=True)
        out.append(np.concatenate([byc[c] for c in pick]))
    return out


def verdict_delta(lo: float, hi: float, d: float) -> str:
    if lo > 0 or hi < 0:
        return "YES" if abs(d) >= DELTA_MIN else "WEAK"
    return "NO"


def main() -> int:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ev = pd.read_csv(OUT / "READINESS_EVENTS.csv.gz")
    clfm = pd.read_csv(OUT / "CLASSIFIER_METRICS.csv")
    ev["cycle"] = ev.groupby(["condition", "target"]).cumcount()
    main_ev = ev[ev.family != "restore"].reset_index(drop=True)
    print(f"events={len(ev)} main={len(main_ev)} "
          f"failure_rate={main_ev.failure.mean():.4f} ({time.time()-t0:.0f}s)", flush=True)

    report: dict = {"operationalisations": OPERATIONALISATIONS}

    # ---------------- 1. readiness ladder ---------------------------------
    scores, _ = fit_ladder(main_ev)
    y = main_ev.failure.to_numpy()
    te = (main_ev.split == "test").to_numpy()
    va = (main_ev.split == "valid").to_numpy()
    ep_test = ladder_endpoints(y, scores, te)
    ep_valid = ladder_endpoints(y, scores, va)
    ep_test.to_csv(OUT / "LADDER_TEST.csv", index=False)
    ep_valid.to_csv(OUT / "LADDER_VALID.csv", index=False)
    print(ep_test.to_string(index=False), flush=True)

    te_idx = np.flatnonzero(te)
    bidx = boot_indices(main_ev.cfg.to_numpy()[te_idx], rng)
    B = np.empty((BOOT, len(LADDER)))
    Bb = np.empty((BOOT, len(LADDER)))
    names = list(LADDER)
    for b, ii in enumerate(bidx):
        jj = te_idx[ii]
        yy = y[jj]
        for k, nm in enumerate(names):
            ss = scores[nm][jj]
            B[b, k] = fast_auc(yy, ss)
            Bb[b, k] = np.mean((ss - yy) ** 2)
    print(f"bootstrap done ({time.time()-t0:.0f}s)", flush=True)

    def contrast(a: str, b: str) -> dict:
        d = float(ep_test.set_index("model").auroc[a] - ep_test.set_index("model").auroc[b])
        dd = B[:, names.index(a)] - B[:, names.index(b)]
        lo, hi = np.percentile(dd, [2.5, 97.5])
        db = Bb[:, names.index(a)] - Bb[:, names.index(b)]
        blo, bhi = np.percentile(db, [2.5, 97.5])
        return {"contrast": f"{a}-{b}", "delta_auroc": d,
                "ci_low": float(lo), "ci_high": float(hi),
                "delta_brier": float(ep_test.set_index("model").brier[a] -
                                     ep_test.set_index("model").brier[b]),
                "brier_ci_low": float(blo), "brier_ci_high": float(bhi),
                "verdict": verdict_delta(float(lo), float(hi), d)}

    va_auc = ep_valid.set_index("model").auroc
    best_single = max(["R1", "R2", "R3"], key=lambda m: va_auc[m])
    best_pair = max(["R4", "R5", "R6"], key=lambda m: va_auc[m])
    cons_single = max(["R1", "R2", "R3"], key=lambda m: ep_test.set_index("model").auroc[m])

    contrasts = [contrast("R1", "R0"), contrast("R2", "R0"), contrast("R3", "R0"),
                 contrast("R7", "R0"), contrast("R7", best_single),
                 contrast("R7", best_pair), contrast("R7", cons_single),
                 contrast("R7", "R1"), contrast("R7", "R2"), contrast("R7", "R3")]
    cdf = pd.DataFrame(contrasts)
    cdf.to_csv(OUT / "LADDER_CONTRASTS.csv", index=False)
    print(cdf.to_string(index=False), flush=True)

    report["ladder"] = {
        "test": ep_test.to_dict("records"), "valid": ep_valid.to_dict("records"),
        "contrasts": contrasts, "best_single_on_valid": best_single,
        "best_pair_on_valid": best_pair, "best_single_on_test_conservative": cons_single,
    }

    # per component (target), secondary -- models refitted within the component
    per_target = []
    for tgt in ("valve", "pump"):
        sub = main_ev[main_ev.target == tgt].reset_index(drop=True)
        sc2, _ = fit_ladder(sub)
        e2 = ladder_endpoints(sub.failure.to_numpy(), sc2,
                              (sub.split == "test").to_numpy())
        e2["target"] = tgt
        per_target.append(e2)
    ptdf = pd.concat(per_target, ignore_index=True)
    ptdf.to_csv(OUT / "LADDER_PER_TARGET.csv", index=False)
    report["ladder_per_target"] = ptdf.to_dict("records")

    # per block (perturbation family), pooled model, TEST rows of that family only
    per_block = []
    for fam, g in main_ev[te].groupby("family"):
        gi = g.index.to_numpy()
        for nm in names:
            per_block.append({"family": fam, "model": nm, "n": len(gi),
                              "base_rate": float(y[gi].mean()),
                              "auroc": fast_auc(y[gi], scores[nm][gi])})
    pbdf = pd.DataFrame(per_block)
    pbdf.to_csv(OUT / "LADDER_PER_FAMILY.csv", index=False)
    report["ladder_per_family"] = pbdf.to_dict("records")

    # sensitivity to amendment 2: exact-context reference only
    exact = te & (main_ev.fallback_reference == 0).to_numpy()
    ep_exact = ladder_endpoints(y, scores, exact)
    ep_exact.to_csv(OUT / "LADDER_TEST_EXACT_MATCH_ONLY.csv", index=False)
    report["fallback_sensitivity"] = {
        "n_test_exact": int(exact.sum()), "n_test_all": int(te.sum()),
        "endpoints_exact": ep_exact.to_dict("records")}
    print(f"amendment-2 sensitivity: exact-context TEST rows {int(exact.sum())}/"
          f"{int(te.sum())}", flush=True)

    # ---------------- 2. axis scores and tertiles -------------------------
    tr = (main_ev.split == "train").to_numpy()
    axis_cols = {"visibility": VIS, "isolability": ISO, "robustness": ROB}
    ax = {}
    thr = {}
    for a, cols in axis_cols.items():
        Z = slog(main_ev[cols].to_numpy(dtype=float))
        mu, sd = Z[tr].mean(0), np.maximum(Z[tr].std(0), 1e-12)
        s = ((Z - mu) / sd).mean(1)
        ax[a] = s
        thr[a] = float(np.percentile(s[tr], 100 / 3))
    main_ev = main_ev.assign(**{f"ax_{a}": v for a, v in ax.items()})
    report["tertile_thresholds_train"] = thr

    low = {a: (ax[a] < thr[a]) for a in axis_cols}
    nlow = low["visibility"].astype(int) + low["isolability"].astype(int) + \
        low["robustness"].astype(int)
    cause = np.full(len(main_ev), "CLASSIFIER_LIMITED", dtype=object)
    cause[nlow >= 2] = "MIXED_UNKNOWN"
    cause[(nlow == 1) & low["visibility"]] = "LOW_VISIBILITY"
    cause[(nlow == 1) & low["isolability"]] = "LOW_ISOLABILITY"
    cause[(nlow == 1) & low["robustness"]] = "LOW_ROBUSTNESS"
    main_ev = main_ev.assign(cause=cause)
    main_ev[["condition", "family", "target", "cfg", "split", "y_true", "y_pred",
             "failure", "n_sensors", "fallback_reference", "ax_visibility",
             "ax_isolability", "ax_robustness", "cause"]].to_csv(
        OUT / "ATTRIBUTION_ROWS.csv.gz", index=False, compression="gzip")

    # ---------------- 3. global univariate sensor ranking (TRAIN) ---------
    base = ev[(ev.condition == "baseline")]
    prof = pd.read_csv(OUT / "SPLIT_ASSIGNMENT.csv")
    feat = np.load(OUT / "BASELINE_FEATURES.npy") if (OUT / "BASELINE_FEATURES.npy").exists() \
        else None
    if feat is None:
        raise SystemExit("BASELINE_FEATURES.npy missing -- run phase20_dr_run.py first")
    trm = (prof.split == "train").to_numpy()
    ranks = []
    for tgt in ("valve", "pump"):
        F, _ = f_classif(feat[trm], prof[tgt].to_numpy()[trm])
        F = np.nan_to_num(F, nan=0.0)
        per_sensor = np.array([F[i * 8:(i + 1) * 8].mean() for i in range(len(SENSORS))])
        ranks.append(rankdata(-per_sensor))
    mean_rank = np.mean(ranks, axis=0)
    order = [SENSORS[i] for i in np.argsort(mean_rank)]
    sensor_rank = {s: float(mean_rank[SENSORS.index(s)]) for s in SENSORS}
    top_sensor = order[0]
    report["univariate_sensor_ranking"] = {"order": order, "mean_rank": sensor_rank,
                                           "most_discriminant": top_sensor}
    pd.DataFrame({"sensor": SENSORS, "mean_rank": mean_rank}).sort_values(
        "mean_rank").to_csv(OUT / "SENSOR_RANKING.csv", index=False)
    print(f"global sensor ranking: {order}", flush=True)

    # ---------------- 4. attribution validity -----------------------------
    exp = {}
    for c in main_ev.condition.unique():
        f = main_ev.family[main_ev.condition == c].iloc[0]
        if f == "noise":
            exp[c] = ["LOW_VISIBILITY", "LOW_ROBUSTNESS"]
        elif f == "drop_group":
            exp[c] = ["LOW_ROBUSTNESS", "LOW_ISOLABILITY"]
        elif f == "downsample":
            exp[c] = ["LOW_VISIBILITY"]
        elif f in ("bias", "drift"):
            exp[c] = ["LOW_ROBUSTNESS"]
        elif f == "baseline":
            exp[c] = ["CLASSIFIER_LIMITED"]
        elif f == "drop_one":
            exp[c] = ["LOW_ISOLABILITY"] if c == f"drop_{top_sensor}" else None
    fail = main_ev[(main_ev.split == "test") & (main_ev.failure == 1)].copy()
    fail["expected"] = fail.condition.map(lambda c: exp[c])
    scored = fail[fail.expected.notna()].copy()
    scored["expected_key"] = scored.expected.map(lambda e: "|".join(e))
    strict = scored.apply(lambda r: r.cause in r.expected, axis=1)
    lenient = scored.apply(
        lambda r: r.cause in r.expected or
        (r.cause == "MIXED_UNKNOWN" and len(r.expected) >= 2), axis=1)
    nmi = float(normalized_mutual_info_score(scored.expected_key, scored.cause))
    cont = pd.crosstab(scored.expected_key, scored.cause)
    cont.to_csv(OUT / "ATTRIBUTION_CONTINGENCY.csv")
    scored = scored.assign(strict=strict.to_numpy(), lenient=lenient.to_numpy())
    per_fam = scored.groupby("family").agg(
        n=("cause", "size"), strict=("strict", "mean"),
        lenient=("lenient", "mean")).reset_index()
    per_fam.to_csv(OUT / "ATTRIBUTION_BY_FAMILY.csv", index=False)

    # chance level: the marginal distribution of attributed causes
    marg = scored.cause.value_counts(normalize=True)
    chance = float(np.mean([sum(marg.get(c, 0.0) for c in e)
                            for e in scored.expected]))
    report["attribution"] = {
        "n_test_failures": int((main_ev.split == "test").pipe(
            lambda m: main_ev.failure[m.to_numpy()]).sum()),
        "n_scored": int(len(scored)), "strict_accuracy": float(strict.mean()),
        "lenient_accuracy": float(lenient.mean()), "chance_accuracy": chance,
        "nmi": nmi, "cause_distribution": marg.to_dict(),
        "by_family": per_fam.to_dict("records"),
        "contingency": cont.to_dict(),
    }
    print(f"attribution strict={strict.mean():.3f} lenient={lenient.mean():.3f} "
          f"chance={chance:.3f} nmi={nmi:.3f} n={len(scored)}", flush=True)

    # ---------------- 5. action test --------------------------------------
    piv = {(c, t): g.sort_values("cycle")
           for (c, t), g in ev.groupby(["condition", "target"])}
    tr_va = prof.split.isin(["train", "valid"]).to_numpy()
    te_m = (prof.split == "test").to_numpy()
    cfg_te = prof.cfg.to_numpy()[te_m]

    # separation helpers, TRAIN only
    def sep_two_classes(tgt, ca, cb, sensors):
        yv = prof[tgt].to_numpy()
        m1 = trm & (yv == ca)
        m2 = trm & (yv == cb)
        out = {}
        for s in sensors:
            i = SENSORS.index(s)
            F = feat[:, i * 8:(i + 1) * 8]
            sd = np.sqrt((F[m1].var(0) + F[m2].var(0)) / 2) + 1e-12
            out[s] = float(np.max(np.abs(F[m1].mean(0) - F[m2].mean(0)) / sd))
        return out

    def sep_healthy(tgt, sensors):
        yv = prof[tgt].to_numpy()
        m1 = trm & (yv == TARGETS[tgt])
        m2 = trm & (yv != TARGETS[tgt])
        out = {}
        for s in sensors:
            i = SENSORS.index(s)
            F = feat[:, i * 8:(i + 1) * 8]
            sd = np.sqrt((F[m1].var(0) + F[m2].var(0)) / 2) + 1e-12
            out[s] = float(np.max(np.abs(F[m1].mean(0) - F[m2].mean(0)) / sd))
        return out

    fitm_clf = clfm[clfm.split.isin(["train", "valid"])]
    drop_cost = {}
    for tgt in ("valve", "pump"):
        base_ba = fitm_clf[(fitm_clf.condition == "baseline") &
                           (fitm_clf.target == tgt)].balanced_accuracy.mean()
        for s in SENSORS:
            v = fitm_clf[(fitm_clf.condition == f"drop_{s}") &
                         (fitm_clf.target == tgt)].balanced_accuracy.mean()
            drop_cost[(tgt, s)] = float(base_ba - v)

    arng = np.random.default_rng(SEED)
    cases = []
    for g, ss in GROUPS.items():
        for tgt in ("valve", "pump"):
            cond = f"dropgroup_{g}"
            d = piv[(cond, tgt)]
            fv = d[tr_va]
            f_fail = fv[fv.failure == 1]
            if len(f_fail) == 0:
                cs = "CLASSIFIER_LIMITED"
            else:
                key = main_ev[(main_ev.condition == cond) & (main_ev.target == tgt) &
                              main_ev.split.isin(["train", "valid"]) &
                              (main_ev.failure == 1)]
                cs = key.cause.mode().iloc[0] if len(key) else "CLASSIFIER_LIMITED"
            if cs == "MIXED_UNKNOWN":
                zs = {a: main_ev.loc[(main_ev.condition == cond) &
                                     (main_ev.target == tgt) &
                                     main_ev.split.isin(["train", "valid"]),
                                     f"ax_{a}"].mean() for a in axis_cols}
                cs = {"visibility": "LOW_VISIBILITY", "isolability": "LOW_ISOLABILITY",
                      "robustness": "LOW_ROBUSTNESS"}[min(zs, key=zs.get)]
                mixed_resolved = True
            else:
                mixed_resolved = False

            s_random = str(arng.choice(sorted(ss)))
            s_generic = min(ss, key=lambda x: sensor_rank[x])
            if cs == "LOW_VISIBILITY":
                s_guided = max(sep_healthy(tgt, ss).items(), key=lambda kv: kv[1])[0]
            elif cs == "LOW_ISOLABILITY":
                cm = fv[fv.failure == 1]
                if len(cm):
                    pair = cm.groupby(["y_true", "y_pred"]).size().idxmax()
                    s_guided = max(sep_two_classes(tgt, pair[0], pair[1], ss).items(),
                                   key=lambda kv: kv[1])[0]
                else:
                    s_guided = s_generic
            elif cs == "LOW_ROBUSTNESS":
                s_guided = max(ss, key=lambda x: drop_cost[(tgt, x)])
            else:
                s_guided = None
            cases.append({"group": g, "target": tgt, "condition": cond, "cause": cs,
                          "mixed_resolved": mixed_resolved, "random": s_random,
                          "generic": s_generic, "guided": s_guided})
    cdf2 = pd.DataFrame(cases)
    cdf2.to_csv(OUT / "ACTION_CASES.csv", index=False)
    print(cdf2.to_string(index=False), flush=True)

    def preds_for(cond, tgt, sensor, group):
        c = cond if sensor is None else f"restore_{group}_{sensor}"
        d = piv[(c, tgt)]
        return (d.y_true.to_numpy()[te_m], d.y_pred.to_numpy()[te_m])

    strat = ["degraded", "random", "generic", "guided"]
    arr = {}
    for r in cases:
        k = (r["group"], r["target"])
        arr[(k, "degraded")] = preds_for(r["condition"], r["target"], None, r["group"])
        for s in ("random", "generic", "guided"):
            arr[(k, s)] = preds_for(r["condition"], r["target"], r[s], r["group"])
    classes = {t: sorted(prof[t].unique()) for t in ("valve", "pump")}

    def eval_all(sel: np.ndarray) -> dict:
        out = {}
        for s in strat:
            v = []
            for r in cases:
                yt, yp = arr[((r["group"], r["target"]), s)]
                v.append(bal_acc(yt[sel], yp[sel], classes[r["target"]]))
            out[s] = float(np.nanmean(v))
        return out

    allsel = np.arange(int(te_m.sum()))
    point = eval_all(allsel)
    per_case = []
    for r in cases:
        row = {"group": r["group"], "target": r["target"], "cause": r["cause"]}
        for s in strat:
            yt, yp = arr[((r["group"], r["target"]), s)]
            row[f"balacc_{s}"] = bal_acc(yt, yp, classes[r["target"]])
            row[f"sensor_{s}"] = r.get(s)
        per_case.append(row)
    pcdf = pd.DataFrame(per_case)
    pcdf.to_csv(OUT / "ACTION_PER_CASE.csv", index=False)
    print(pcdf.to_string(index=False), flush=True)

    ucfg = np.unique(cfg_te)
    bycfg = {c: np.flatnonzero(cfg_te == c) for c in ucfg}
    brng = np.random.default_rng(SEED + 1)
    Ba = np.empty((BOOT, len(strat)))
    for b in range(BOOT):
        pick = brng.choice(ucfg, size=len(ucfg), replace=True)
        sel = np.concatenate([bycfg[c] for c in pick])
        e = eval_all(sel)
        Ba[b] = [e[s] for s in strat]
    ai = {s: i for i, s in enumerate(strat)}

    def acontrast(a, b):
        d = point[a] - point[b]
        dd = Ba[:, ai[a]] - Ba[:, ai[b]]
        lo, hi = np.percentile(dd, [2.5, 97.5])
        return {"contrast": f"{a}-{b}", "delta_balanced_accuracy": float(d),
                "ci_low": float(lo), "ci_high": float(hi),
                "significant": bool(lo > 0 or hi < 0)}

    acs = [acontrast("guided", "generic"), acontrast("guided", "random"),
           acontrast("guided", "degraded"), acontrast("generic", "degraded"),
           acontrast("random", "degraded"), acontrast("generic", "random")]
    adf = pd.DataFrame(acs)
    adf.to_csv(OUT / "ACTION_CONTRASTS.csv", index=False)
    print(adf.to_string(index=False), flush=True)
    report["action_test"] = {"point": point, "contrasts": acs,
                             "per_case": pcdf.to_dict("records"),
                             "cases": cdf2.to_dict("records")}

    # ---------------- 6. verdicts -----------------------------------------
    cmap = {c["contrast"]: c for c in contrasts}
    v_vis = cmap["R1-R0"]["verdict"]
    v_iso = cmap["R2-R0"]["verdict"]
    v_rob = cmap["R3-R0"]["verdict"]
    r7_best = cmap[f"R7-{best_single}"]
    r7_cons = cmap[f"R7-{cons_single}"]
    if r7_best["verdict"] == "YES" and r7_cons["verdict"] in ("YES", "WEAK"):
        v_pred = "SUPPORTED"
    elif r7_best["verdict"] == "WEAK" or r7_cons["verdict"] in ("YES", "WEAK"):
        v_pred = "PARTIAL"
    else:
        v_pred = "NOT_SUPPORTED"

    st, ch = float(strict.mean()), chance
    if st >= 0.60 and st > ch + 0.10:
        v_attr = "SUPPORTED"
    elif st > ch + 0.05:
        v_attr = "PARTIAL"
    else:
        v_attr = "NOT_SUPPORTED"

    gg = acs[0]
    if gg["significant"] and gg["delta_balanced_accuracy"] > 0:
        v_act = "BETTER"
    elif gg["significant"] and gg["delta_balanced_accuracy"] < 0:
        v_act = "WORSE"
    else:
        v_act = "EQUIVALENT"

    r7_beats_single = r7_best["verdict"] in ("YES", "WEAK") and \
        r7_best["delta_auroc"] > 0
    if v_pred == "SUPPORTED" and v_attr == "SUPPORTED" and v_act == "BETTER":
        v_arch, v_prod = "PASS", "YES"
    elif not r7_beats_single and v_act != "BETTER":
        v_arch, v_prod = "FAIL", "NO"
    else:
        v_arch, v_prod = "PARTIAL", "NOT_YET"

    verdicts = {"VISIBILITY_PHYSICAL_VALUE": v_vis,
                "ISOLABILITY_PHYSICAL_VALUE": v_iso,
                "ROBUSTNESS_PHYSICAL_VALUE": v_rob,
                "READINESS_FAILURE_PREDICTION": v_pred,
                "FAILURE_CAUSE_ATTRIBUTION": v_attr,
                "READINESS_GUIDED_ACTION": v_act,
                "PHYSICAL_ARCHITECTURE_VALIDATION": v_arch,
                "PRODUCT_PROTOTYPE_JUSTIFIED": v_prod}
    report["verdicts"] = verdicts
    fr = ev[ev.condition == "baseline"].groupby(
        ["target", "split"]).fallback_reference.mean().round(4)
    report["fallback_rate"] = {f"{a}/{b}": float(v) for (a, b), v in fr.items()}

    # classifier degradation summary, per family and per component
    deg = clfm[clfm.split == "test"].copy()
    b0 = deg[deg.condition == "baseline"].set_index("target").balanced_accuracy
    deg["delta_vs_baseline"] = deg.balanced_accuracy - deg.target.map(b0)
    deg.to_csv(OUT / "CLASSIFIER_DEGRADATION_TEST.csv", index=False)
    report["classifier_baseline_test"] = b0.to_dict()
    report["classifier_degradation_by_family"] = deg[deg.family != "restore"].groupby(
        ["family", "target"]).delta_vs_baseline.mean().round(4).reset_index().to_dict(
        "records")

    json.dump(report, open(OUT / "PHASE20_DR_RESULTS.json", "w"), indent=2, default=str)
    print("\n=== VERDICTS ===")
    for k, v in verdicts.items():
        print(f"{k:36s} {v}")
    print(f"({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
