"""PHASE 16 -- blind confirmatory analysis.

Applies FROZEN_MODELS.json exactly as committed: feature list, transform,
standardisation constants and logistic coefficients are all read from the file
and NOTHING is refitted on Phase 16 data. The only thing computed here is what
the frozen models predict on realisations they have never seen.

Structures reused unchanged from Phase 15: sigma (declared XNS), the null
covariance and the fault centroids (both estimated on Phase 14 TRAIN), the 120
frozen designs, and the FO support E*. Re-estimating any of them on Phase 16
data would leak the confirmatory set into the predictor.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fo_metrics
import tep_metrics as TM

REPO = Path(__file__).resolve().parents[1]
P14, P15, P16 = REPO / "phase14_tep", REPO / "phase15_tep", REPO / "phase16_tep"
PROTO = json.loads((P14 / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
FROZEN = json.loads((P16 / "FROZEN_MODELS.json").read_text())
GEN16 = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen16")
GEN14 = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")
TEPSRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
              "scratchpad/tep/tennessee-eastman-profBraatz")

FAULTS = PROTO["disturbances"]["ids"]
KAPPA, ETA = PROTO["fo_inputs"]["kappa"], PROTO["fo_inputs"]["eta"]
SIZES, N_DESIGNS = PROTO["sensor_designs"]["design_sizes"], PROTO["sensor_designs"]["designs_per_size"]
DESIGN_SEED = 20260816
BOOT = FROZEN["bootstrap"]["n_resamples"]
BSEED = FROZEN["bootstrap"]["seed"]
DELTA_MIN = FROZEN["practical_threshold"]["min_auroc_difference"]
SCALE_FEATURES = FROZEN["scale_features"]
MODELS = FROZEN["models"]


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def load_sigma():
    import re
    return np.asarray([float(m.group(2)) for m in re.finditer(
        r"XNS\((\d+)\)=([0-9.]+)D0", (TEPSRC / "teprob.f").read_text())])


def load_bank(p):
    z = np.load(p)
    return {tuple(int(x) for x in k.split("_")): z[k] for k in z.files}


def designs():
    rng = np.random.default_rng(DESIGN_SEED)
    return [{"design_id": i, "size": s, "channels": sorted(rng.choice(41, size=s, replace=False).tolist())}
            for i, s in enumerate([s for s in SIZES for _ in range(N_DESIGNS)])]


def build(bank, seed_idx):
    d, obs, yf, ys = [], [], [], []
    ok = []
    for si in seed_idx:
        if (0, si) not in bank or bank[(0, si)].shape != (41, 800):
            continue
        base = bank[(0, si)].astype(np.float64)
        for k in FAULTS:
            f = bank.get((k, si))
            if f is None or f.shape != (41, 800):
                continue
            d.append(f - base); obs.append(f); yf.append(k); ys.append(si); ok.append((k, si))
    return np.stack(d), np.stack(obs), np.asarray(yf), np.asarray(ys)


def rf_features(obs, ch):
    x = obs[:, ch, :]
    return np.concatenate([x.mean(2), x.std(2), x.min(2), x.max(2), x[:, :, -1]], axis=1)


def rf_outputs(proba, classes, y):
    pred = classes[proba.argmax(axis=1)]
    order = np.argsort(-proba, axis=1)
    rank = np.array([int(np.flatnonzero(classes[order[i]] == y[i])[0]) + 1 for i in range(len(y))])
    p_true = np.array([proba[i, np.flatnonzero(classes == y[i])[0]] for i in range(len(y))])
    srt = np.sort(proba, axis=1)[:, ::-1]
    with np.errstate(divide="ignore"):
        ent = -(proba * np.log(np.maximum(proba, 1e-300))).sum(axis=1)
    return {"failure": (pred != y).astype(int), "rank_true": rank,
            "log_loss": -np.log(np.maximum(p_true, 1e-300)),
            "rf_entropy": ent, "rf_margin": srt[:, 0] - srt[:, 1]}


def featurise(bank, seed_idx, sigma, Sn, centroids, dsg, rf_by_design, b_star_by_design,
              tag) -> pd.DataFrame:
    d, obs, y, s = build(bank, seed_idx)
    W = TM.whiten(d, sigma)
    v, m, Sf = TM.per_channel_visibility(W), TM.mean_profile(W), TM.scenario_covariance(W)
    rows = []
    for dd in dsg:
        ch = dd["channels"]
        vis = TM.visibility_metrics(W, v, m, Sf, Sn, ch)
        iso = TM.isolability_metrics(m, y, centroids, Sn, ch)
        fo_d_S = fo_metrics.visibility(d, sigma)[:, ch].max(axis=1)
        rf = rf_by_design[dd["design_id"]]
        out = rf_outputs(rf.predict_proba(rf_features(obs, ch)), rf.classes_, y)
        rec = {"design_id": dd["design_id"], "design_size": dd["size"], "cohort": tag,
               "fault": y, "seed_idx": s, "fo_d_S": fo_d_S,
               "b_star": b_star_by_design[dd["design_id"]]}
        rec.update(vis); rec.update(iso); rec.update(out)
        rows.append(pd.DataFrame(rec))
    return pd.concat(rows, ignore_index=True)


def prep(ev):
    """Apply the transforms and the KL rule EXACTLY as frozen.

    FROZEN_MODELS.json carries kl_imputation_value, computed on Phase 14
    TRAIN+VALID before Phase 16 existed. It is applied here verbatim: nothing is
    re-derived from the confirmatory data.
    """
    d = ev.copy()
    kl = np.array(d["kl_gauss"], dtype=float, copy=True)
    undef = ~np.isfinite(kl)
    kl[undef] = FROZEN["kl_imputation_value"]
    d["kl_gauss"] = kl
    d["kl_undefined"] = undef.astype(float)
    for c in SCALE_FEATURES:
        d[c] = slog(d[c].to_numpy(float))
    d["fo_x_bstar"] = d["fo_d_S"] * d["b_star"]
    return d


def apply_frozen(d: pd.DataFrame, name: str) -> np.ndarray:
    spec = MODELS[name]
    X = d[spec["features"]].to_numpy(float)
    z = (X - np.asarray(spec["mu"])) / np.asarray(spec["sd"])
    lin = z @ np.asarray(spec["coef"]) + spec["intercept"]
    return 1.0 / (1.0 + np.exp(-lin))


def paired_boot(pA, pB, y, groups):
    rng = np.random.default_rng(BSEED)
    uniq = np.unique(groups)
    idx_by = {g: np.flatnonzero(groups == g) for g in uniq}
    out = np.empty(BOOT)
    for b in range(BOOT):
        pick = rng.choice(uniq, len(uniq), replace=True)
        idx = np.concatenate([idx_by[g] for g in pick])
        yy = y[idx]
        out[b] = (np.nan if yy.min() == yy.max()
                  else roc_auc_score(yy, pA[idx]) - roc_auc_score(yy, pB[idx]))
    lo, hi = np.nanpercentile(out, [2.5, 97.5])
    delta = roc_auc_score(y, pA) - roc_auc_score(y, pB)
    verdict = ("YES" if (lo > 0 and delta >= DELTA_MIN)
               else "WEAK" if lo > 0 else "NO")
    return {"delta_auroc": float(delta), "ci_lo": float(lo), "ci_hi": float(hi),
            "ci_excludes_zero": bool(lo > 0), "meets_practical_threshold": bool(delta >= DELTA_MIN),
            "verdict": verdict}


def main() -> int:
    t0 = time.time()
    (P16 / "logs").mkdir(parents=True, exist_ok=True)
    (P16 / "figures").mkdir(parents=True, exist_ok=True)
    sigma = load_sigma()
    Sn = np.load(P15 / "null_covariance.npy")
    dsg = designs()

    # centroids and the RF: rebuilt from PHASE 14 TRAIN, exactly as frozen
    bank14 = load_bank(GEN14 / "nominal.npz")
    d14, o14, y14, s14 = build(bank14, list(range(0, 25)))
    centroids = TM.fault_centroids(TM.mean_profile(TM.whiten(d14, sigma)), y14, FAULTS)
    support = fo_metrics.freeze_support(d14, sigma, KAPPA)

    cohorts = {"nominal": load_bank(GEN16 / "nominal.npz")}
    for lv in FROZEN["noise_levels"]:
        p = GEN16 / f"noise_{lv}.npz"
        if p.exists():
            cohorts[f"noise_x{lv:g}"] = load_bank(p)

    cache = P16 / "CONFIRMATORY_FEATURES.csv.gz"
    if cache.exists():
        # The featurisation is deterministic given the frozen structures, so a
        # completed run is reused rather than recomputed. Nothing about it
        # depends on results.
        ev = pd.read_csv(cache)
        print(f"reusing cached features: {len(ev)} rows ({time.time()-t0:.0f}s)", flush=True)
    else:
        rf_by_design, b_star_by_design = {}, {}
        for dd in dsg:
            ch = dd["channels"]
            rf = RandomForestClassifier(n_estimators=500, random_state=DESIGN_SEED, n_jobs=-1)
            rf.fit(rf_features(o14, ch), y14)
            rf_by_design[dd["design_id"]] = rf
            d_S14 = fo_metrics.visibility(d14, sigma)[:, ch].max(axis=1)
            b_star_by_design[dd["design_id"]] = float(np.mean(d_S14[support.mask] <= ETA))
        print(f"frozen structures rebuilt from Phase 14 TRAIN ({time.time()-t0:.0f}s)", flush=True)
        frames = []
        for tag, bank in cohorts.items():
            seeds = sorted({si for (_, si) in bank})
            frames.append(featurise(bank, seeds, sigma, Sn, centroids, dsg,
                                    rf_by_design, b_star_by_design, tag))
            print(f"cohort {tag}: {len(frames[-1])} rows ({time.time()-t0:.0f}s)", flush=True)
        ev = pd.concat(frames, ignore_index=True)
        ev.to_csv(cache, index=False, compression="gzip")

    d = prep(ev)
    nom = d[d.cohort == "nominal"].copy()
    y, groups = nom.failure.to_numpy(int), nom.seed_idx.to_numpy()
    preds = {name: apply_frozen(nom, name) for name in MODELS}

    model_rows = [{"model": n, "cohort": "nominal", "n": len(y),
                   "auroc": roc_auc_score(y, p), "auprc": average_precision_score(y, p),
                   "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p),
                   "calib_slope": float(np.polyfit(p, y, 1)[0])}
                  for n, p in preds.items()]
    pd.DataFrame(model_rows).to_csv(P16 / "MODEL_COMPARISON.csv", index=False)

    hyp = {}
    for h, (a, b) in FROZEN["hypotheses"].items():
        hyp[h] = {"model_a": a, "model_b": b, **paired_boot(preds[a], preds[b], y, groups)}

    # H1: FO alone must retain an out-of-sample association with failure
    fo_auc = roc_auc_score(y, -nom.fo_d_S.to_numpy(float))
    rng = np.random.default_rng(BSEED)
    uniq = np.unique(groups); idx_by = {g: np.flatnonzero(groups == g) for g in uniq}
    bs = np.empty(BOOT)
    for b in range(BOOT):
        idx = np.concatenate([idx_by[g] for g in rng.choice(uniq, len(uniq), replace=True)])
        bs[b] = roc_auc_score(y[idx], -nom.fo_d_S.to_numpy(float)[idx])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    hyp["H1_FO_SIGNAL"] = {"auroc": float(fo_auc), "ci_lo": float(lo), "ci_hi": float(hi),
                           "verdict": "YES" if lo > 0.5 else "NO"}

    # H4: B* structural behaviour on the confirmatory noise cohorts
    struct = []
    for tag, bank in cohorts.items():
        if tag == "nominal":
            continue
        lv = float(tag.split("x")[1])
        seeds = sorted({si for (_, si) in bank})
        dd_, _, yy, _ = build(bank, seeds)
        for design in dsg[:20]:
            ch = design["channels"]
            sup = fo_metrics.freeze_support(dd_, sigma, KAPPA)
            bstar = fo_metrics.b_star(dd_, sigma * lv, ch, sup, ETA)
            bdyn = fo_metrics.b_dynamic(dd_, sigma * lv, ch, KAPPA, ETA)
            struct.append({"cohort": tag, "noise_scale": lv, "design_id": design["design_id"],
                           "B_star": bstar["B_star"], "B_star_support": bstar["support_size"],
                           "B_dynamic": bdyn["B"], "B_dynamic_support": bdyn["support_size"]})
    pd.DataFrame(struct).to_csv(P16 / "NOISE_ROBUSTNESS.csv", index=False)

    # per-fault and leave-one-fault-out on the decisive comparison
    a, b = FROZEN["hypotheses"]["H8_PROJECT_INCREMENT"]
    per_fault, loo = [], []
    for k in FAULTS:
        mk = nom.fault.to_numpy() == k
        yy = y[mk]
        row = {"fault": k, "n": int(mk.sum()), "failure_rate": float(yy.mean())}
        if 0 < yy.sum() < len(yy):
            row["auroc_fo"] = roc_auc_score(yy, -nom.fo_d_S.to_numpy(float)[mk])
            row["auroc_iso"] = roc_auc_score(yy, -nom.iso_margin_ratio.to_numpy(float)[mk])
            row[f"auroc_{a}"] = roc_auc_score(yy, preds[a][mk])
            row[f"auroc_{b}"] = roc_auc_score(yy, preds[b][mk])
        per_fault.append(row)
        keep = ~mk
        if 0 < y[keep].sum() < keep.sum():
            loo.append({"excluded_fault": k,
                        "delta_auroc": float(roc_auc_score(y[keep], preds[a][keep])
                                             - roc_auc_score(y[keep], preds[b][keep]))})
    pd.DataFrame(per_fault).to_csv(P16 / "PER_FAULT_RESULTS.csv", index=False)

    by_size = (nom.assign(pa=preds[a], pb=preds[b]).groupby("design_size")
               .apply(lambda g: pd.Series({
                   "n": len(g), "failure_rate": g.failure.mean(),
                   "auroc_a": roc_auc_score(g.failure, g.pa) if g.failure.nunique() > 1 else np.nan,
                   "auroc_b": roc_auc_score(g.failure, g.pb) if g.failure.nunique() > 1 else np.nan}),
                   include_groups=False).reset_index())

    res = {"hypotheses": hyp, "model_comparison": model_rows,
           "leave_one_fault_out": loo,
           "loo_delta_min": float(min(r["delta_auroc"] for r in loo)) if loo else None,
           "loo_delta_max": float(max(r["delta_auroc"] for r in loo)) if loo else None,
           "by_design_size": by_size.to_dict("records"),
           "n_realisations_nominal": int(nom.groupby(["fault", "seed_idx"]).ngroups),
           "n_seeds": int(nom.seed_idx.nunique())}
    (P16 / "CONFIRMATORY_RESULTS.json").write_text(json.dumps(res, indent=2, default=float))
    pd.DataFrame([{"hypothesis": k, **v} for k, v in hyp.items()]).to_csv(
        P16 / "CONFIRMATORY_RESULTS.csv", index=False)
    print(json.dumps(hyp, indent=2, default=float))
    print(pd.DataFrame(model_rows).round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
