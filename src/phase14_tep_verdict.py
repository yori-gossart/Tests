"""
PHASE TEP -- endpoints, confidence intervals and the frozen success criterion.

Consumes only what phase14_tep_analyse.py produced. Applies the criterion exactly
as frozen; no threshold is recomputed from the results.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fo_metrics

REPO = Path(__file__).resolve().parents[1]
P14 = REPO / "phase14_tep"
RES = P14 / "results"
PROTO = json.loads((P14 / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
GEN = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")
TEPSRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
              "scratchpad/tep/tennessee-eastman-profBraatz")

KAPPA, ETA = PROTO["fo_inputs"]["kappa"], PROTO["fo_inputs"]["eta"]
FAULTS = PROTO["disturbances"]["ids"]
TRAIN_IDX = list(range(0, 25))
N_BOOT, BOOT_SEED = 2000, 20260816
DIRECTION = {"fo_d_S": -1, "snr_mean": -1, "count_above_3sigma": -1,
             "smallest_singular_value": -1, "design_size": -1,
             "entropy": +1, "top1_top2_margin": -1}
BASELINES = ["entropy", "top1_top2_margin", "snr_mean", "count_above_3sigma",
             "smallest_singular_value", "design_size"]
ALL_SCORES = ["fo_d_S"] + BASELINES


def auroc_rows(score: np.ndarray, fail: np.ndarray) -> np.ndarray:
    """Row-wise AUROC for (n_designs, n_scenarios) matrices, ties handled."""
    r = stats.rankdata(score, axis=1)
    npos = fail.sum(axis=1)
    nneg = fail.shape[1] - npos
    s = (r * fail).sum(axis=1)
    out = (s - npos * (npos + 1) / 2.0) / np.maximum(npos * nneg, 1)
    out[(npos == 0) | (nneg == 0)] = np.nan
    return out


def matrices(ev: pd.DataFrame, split: str, name: str):
    """(n_designs, n_scenarios) score and failure matrices, aligned on scenario."""
    d = ev[ev.split == split].copy()
    d["scen"] = d.fault.astype(str) + "_" + d.seed_idx.astype(str)
    sc = d.pivot(index="design_id", columns="scen", values=name).sort_index()
    fl = d.pivot(index="design_id", columns="scen", values="failure").sort_index()
    return (DIRECTION[name] * sc.to_numpy(float), fl.to_numpy(float),
            list(sc.columns), list(sc.index))


def mean_auroc_ci(ev: pd.DataFrame, split: str, name: str) -> dict:
    S, F, cols, _ = matrices(ev, split, name)
    point = float(np.nanmean(auroc_rows(S, F)))
    rng = np.random.default_rng(BOOT_SEED)
    n = S.shape[1]
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = rng.integers(0, n, n)                 # resample REALISATIONS
        boot[b] = np.nanmean(auroc_rows(S[:, idx], F[:, idx]))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"metric": name, "split": split, "mean_auroc": point,
            "ci_lo": float(lo), "ci_hi": float(hi),
            "ci_width": float(hi - lo), "n_scenarios": int(n),
            "n_designs": int(S.shape[0])}


def pooled(ev: pd.DataFrame, split: str) -> list[dict]:
    """Pooled over (design x scenario). Independence is violated -- flagged.
    It is reported because the design-size control is only testable here."""
    d = ev[ev.split == split]
    fail = d.failure.to_numpy(float)
    out = []
    for nm in ALL_SCORES:
        s = DIRECTION[nm] * d[nm].to_numpy(float)
        r = stats.rankdata(s)
        npos, nneg = fail.sum(), len(fail) - fail.sum()
        a = (float((r * fail).sum()) - npos * (npos + 1) / 2) / (npos * nneg)
        out.append({"metric": nm, "split": split, "pooled_auroc": a,
                    "n_pairs": int(len(fail)), "independence": "VIOLATED (design x scenario)"})
    return out


def spearman_table(ev: pd.DataFrame, split: str) -> list[dict]:
    d = ev[ev.split == split]
    out = []
    for nm in ALL_SCORES:
        for endpoint in ["log_loss", "rank_true", "reciprocal_rank", "posterior_true"]:
            rho, p = stats.spearmanr(d[nm], d[endpoint])
            out.append({"metric": nm, "endpoint": endpoint, "split": split,
                        "spearman_rho": float(rho), "p_value": float(p)})
    return out


def deciles(ev: pd.DataFrame, split: str, name: str = "fo_d_S") -> list[dict]:
    d = ev[ev.split == split]
    q = pd.qcut(d[name], 10, labels=False, duplicates="drop")
    out = []
    for k in sorted(pd.unique(q.dropna())):
        m = q == k
        out.append({"metric": name, "split": split, "decile": int(k) + 1,
                    "n": int(m.sum()), "failure_rate": float(d.failure[m].mean()),
                    "score_min": float(d[name][m].min()), "score_max": float(d[name][m].max())})
    return out


def per_fault(ev: pd.DataFrame, split: str) -> list[dict]:
    d = ev[ev.split == split]
    out = []
    for k in FAULTS:
        m = d[d.fault == k]
        fail = m.failure.to_numpy(float)
        row = {"fault": k, "split": split, "n": len(m),
               "failure_rate": float(fail.mean()),
               "accuracy": float(m.top1_correct.mean()),
               "median_fo_d_S": float(m.fo_d_S.median())}
        for nm in ["fo_d_S", "entropy", "top1_top2_margin"]:
            if 0 < fail.sum() < len(fail):
                s = DIRECTION[nm] * m[nm].to_numpy(float)
                r = stats.rankdata(s)
                npos, nneg = fail.sum(), len(fail) - fail.sum()
                row[f"auroc_{nm}"] = (float((r * fail).sum()) - npos * (npos + 1) / 2) / (npos * nneg)
            else:
                row[f"auroc_{nm}"] = float("nan")
        out.append(row)
    return out


def b_star_vs_dynamic(designs_channels: dict) -> list[dict]:
    """B* against B_dynamic across the pre-registered noise levels, on the TRAIN
    population where E* is frozen, with data REGENERATED at each level."""
    import re
    sigma = np.asarray([float(m.group(2)) for m in
                        re.finditer(r"XNS\((\d+)\)=([0-9.]+)D0", (TEPSRC / "teprob.f").read_text())])

    def load(path):
        z = np.load(path)
        b = {}
        for key in z.files:
            k, si = key.split("_")
            b[(int(k), int(si))] = z[key]
        return b

    banks = {1.0: load(GEN / "nominal.npz")}
    for lv in [2.0, 4.0, 8.0]:
        p = GEN / f"noise_{lv}.npz"
        if p.exists():
            banks[lv] = load(p)

    # One run of the 2750 generated is truncated: fault 5, seed index 3, at
    # noise x4, where the plant trips its own shutdown condition. That scenario
    # therefore does not exist at every level. A level-to-level comparison needs
    # one fixed population, so the comparison runs on the scenarios present at
    # ALL levels. This drops data that is absent, it does not move a threshold.
    def valid(bank) -> np.ndarray:
        return np.array([bank[(k, si)].shape == (41, 800)
                         for si in TRAIN_IDX for k in FAULTS])

    common = np.ones(len(TRAIN_IDX) * len(FAULTS), dtype=bool)
    for bank in banks.values():
        common &= valid(bank)

    def delta_train(bank):
        d, i = [], 0
        for si in TRAIN_IDX:
            base = bank[(0, si)].astype(np.float64)
            for k in FAULTS:
                if common[i]:
                    d.append(bank[(k, si)].astype(np.float64) - base)
                i += 1
        return np.stack(d)

    d_nom = delta_train(banks[1.0])
    support = fo_metrics.freeze_support(d_nom, sigma, KAPPA)

    out = []
    for lv, bank in sorted(banks.items()):
        d_lv = delta_train(bank)
        se = sigma * lv
        for did, ch in designs_channels.items():
            bs = fo_metrics.b_star(d_lv, se, ch, support, ETA)
            bd = fo_metrics.b_dynamic(d_lv, se, ch, KAPPA, ETA)
            out.append({"design_id": did, "n_channels": len(ch), "noise_scale": lv,
                        "n_scenarios_common": int(common.sum()),
                        "B_star": bs["B_star"], "B_star_support": bs["support_size"],
                        "B_dynamic": bd["B"], "B_dynamic_support": bd["support_size"],
                        "differ": bool(bs["B_star"] != bd["B"]
                                       or bs["support_size"] != bd["support_size"])})
    return out


def main() -> int:
    ev = pd.read_csv(RES / "EVENT_LEVEL_TEP.csv.gz")
    pdm = pd.read_csv(RES / "PER_DESIGN_METRICS.csv")
    print(f"events {len(ev)}  designs {pdm.design_id.nunique()}", flush=True)

    out = {}
    out["primary_auroc"] = [mean_auroc_ci(ev, sp, nm)
                            for sp in ["test", "val"] for nm in ALL_SCORES]
    print("primary AUROC done", flush=True)
    out["pooled_auroc"] = pooled(ev, "test") + pooled(ev, "val")
    out["spearman"] = spearman_table(ev, "test")
    out["deciles"] = deciles(ev, "test") + deciles(ev, "val")
    out["per_fault"] = per_fault(ev, "test") + per_fault(ev, "val")

    # AUPRC (per-design mean) from the already-computed table
    out["auprc"] = [{"metric": nm, "split": sp,
                     "mean_auprc": float(pdm[pdm.split == sp][f"auprc_{nm}"].mean()),
                     "prevalence": float(ev[ev.split == sp].failure.mean())}
                    for sp in ["test", "val"] for nm in ALL_SCORES]

    # per design SIZE
    size_rows = []
    for sp in ["test", "val"]:
        for sz in sorted(pdm["size"].unique()):
            m = pdm[(pdm.split == sp) & (pdm["size"] == sz)]
            r = {"split": sp, "design_size": int(sz), "n_designs": len(m),
                 "mean_accuracy": float(m.accuracy.mean())}
            for nm in ALL_SCORES:
                r[f"auroc_{nm}"] = float(m[f"auroc_{nm}"].mean())
            size_rows.append(r)
    out["by_design_size"] = size_rows

    designs_channels = {}
    rng = np.random.default_rng(20260816)
    for size in PROTO["sensor_designs"]["design_sizes"]:
        for rep in range(PROTO["sensor_designs"]["designs_per_size"]):
            designs_channels[len(designs_channels)] = sorted(
                rng.choice(41, size=size, replace=False).tolist())
    out["b_star_vs_dynamic"] = b_star_vs_dynamic(designs_channels)
    print("B* comparison done", flush=True)

    # calibration of B*(S) against the observed per-design failure rate on TEST
    bs_nom = {r["design_id"]: r["B_star"] for r in out["b_star_vs_dynamic"]
              if r["noise_scale"] == 1.0}
    cal = []
    for sp in ["test", "val"]:
        m = pdm[pdm.split == sp]
        pred = m.design_id.map(bs_nom).to_numpy(float)
        obs = (1.0 - m.accuracy.to_numpy(float))
        ok = ~np.isnan(pred)
        rho, p = stats.spearmanr(pred[ok], obs[ok])
        cal.append({"split": sp, "n_designs": int(ok.sum()),
                    "brier": float(np.mean((pred[ok] - obs[ok]) ** 2)),
                    "mean_B_star": float(pred[ok].mean()),
                    "mean_observed_failure_rate": float(obs[ok].mean()),
                    "spearman_B_star_vs_failure_rate": float(rho), "p_value": float(p)})
    out["b_star_calibration"] = cal

    # ---- the FROZEN success criterion, applied verbatim -------------------
    prim = {(r["metric"], r["split"]): r for r in out["primary_auroc"]}
    fo = prim[("fo_d_S", "test")]
    base = {b: prim[(b, "test")]["mean_auroc"] for b in BASELINES}
    best_base = max(base, key=base.get)
    n_fail = int(ev[ev.split == "test"].failure.sum())
    n_ok = int((ev[ev.split == "test"].failure == 0).sum())
    crit = {
        "fo_mean_auroc": fo["mean_auroc"], "fo_ci": [fo["ci_lo"], fo["ci_hi"]],
        "baselines": base, "best_baseline": best_base,
        "best_baseline_point": base[best_base],
        "c1_ci_lower_above_0.5": bool(fo["ci_lo"] > 0.5),
        "c2_point_above_every_baseline": bool(all(fo["mean_auroc"] > v for v in base.values())),
        "c3_ci_lower_above_best_baseline_point": bool(fo["ci_lo"] > base[best_base]),
        "inconclusive_gate": bool(n_fail < 30 or n_ok < 30),
        "n_test_failures": n_fail, "n_test_successes": n_ok,
    }
    crit["FO_SUPPORTED"] = bool(crit["c1_ci_lower_above_0.5"]
                                and crit["c2_point_above_every_baseline"]
                                and crit["c3_ci_lower_above_best_baseline_point"]
                                and not crit["inconclusive_gate"])
    out["frozen_success_criterion"] = crit

    (RES / "VERDICT_TABLES.json").write_text(json.dumps(out, indent=2, default=float))
    for k in ["primary_auroc", "pooled_auroc", "spearman", "deciles", "per_fault",
              "auprc", "by_design_size", "b_star_vs_dynamic", "b_star_calibration"]:
        pd.DataFrame(out[k]).to_csv(RES / f"{k}.csv", index=False)
    print(json.dumps(crit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
