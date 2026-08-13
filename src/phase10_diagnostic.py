"""
PHASE E (BattLeDIM substitute) -- is the FO score a useful FAILURE PREDICTOR?

Phase E as specified belongs on the EPA source-identification dataset, which
could not be acquired (see EPA_DATA_MANIFEST.json). Its central question can
still be asked on BattLeDIM, and is asked here:

    given a sensor set S and a leak scenario z, does the FO visibility score
    d_S(z) predict that the pipeline will FAIL on that scenario?

This is a different question from the one FO-v1 answered. FO-v1 asked whether
minimising B produces better designs (it does not). This asks whether the score
carries information about per-scenario failure -- a diagnostic use, not a
design use.

LABEL. A scenario counts as a failure when the event is not detected inside its
own window by the sensor set under test. Localisation error is analysed as a
continuous secondary outcome.

DIAGNOSTIC BASELINES, so FO is not graded against nothing:
    per-scenario reference signal strength  ||dp_S(z)||_2 / sqrt(k)   (SNR)
    top1-top2 margin of the localisation cosine scores
    nearest-signature Mahalanobis-style margin
    smallest singular value of H_S restricted to the scenario neighbourhood
FO earns a diagnostic claim only if it is not dominated by these.

EVERYTHING IS OUT-OF-SAMPLE with respect to FO-v1's freeze: the scores come
from the frozen library and the frozen sigma, and no threshold is tuned here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector  # noqa: E402
import evaluate  # noqa: E402
import selection  # noqa: E402
import tracks  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = REPO / "data" / "processed"
OUT = REPO / "phase10_reset"

N_BOOT = 10_000
SEED = 20260813


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def auroc(score: np.ndarray, label: np.ndarray) -> float:
    """P(score(failure) > score(success)); ties counted as half."""
    m = np.isfinite(score)
    s, y = score[m], label[m]
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def auprc(score: np.ndarray, label: np.ndarray) -> float:
    m = np.isfinite(score)
    s, y = score[m], label[m]
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s)
    y = y[order]
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    rec = tp / y.sum()
    return float(np.sum(np.diff(np.concatenate([[0.0], rec])) * prec))


def brier(prob: np.ndarray, label: np.ndarray) -> float:
    m = np.isfinite(prob)
    return float(np.mean((prob[m] - label[m]) ** 2))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 8 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return float("nan")
    return float(np.corrcoef(pd.Series(a[m]).rank(), pd.Series(b[m]).rank())[0, 1])


def boot_ci(fn, score, label, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(score)
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        v = fn(score[i], label[i])
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))


# ---------------------------------------------------------------------------
# Per-scenario score assembly
# ---------------------------------------------------------------------------


def build_rows(ctx, frozen, year_dir, year, cfg_name) -> pd.DataFrame:
    c = frozen["constants"]
    sigma = np.array([frozen["sigma_per_sensor_m"][s] for s in ctx.sensor_ids])
    bias = np.array([frozen["model_bias_per_sensor_sigma_units"][s]
                     for s in ctx.sensor_ids])

    ts18, X18, P18 = detector.load_year(PROC / "regenerated_2018", 2018, ctx.sensor_ids)
    nominal = detector.fit_nominal(X18, P18, np.ones(len(ts18), bool), ctx.sensor_ids)
    nominal.bias = bias
    ctx.localiser.sigma = nominal.sigma

    ts, X, P = detector.load_year(year_dir, year, ctx.sensor_ids)
    Z = nominal.standardised(X, P)
    leaks = evaluate.load_ground_truth(RAW / cfg_name, ts,
                                       year_dir / f"{year}_SCADA_Leaks.csv")
    per_sensor = detector.per_sensor_alarms(Z, c["k_cusum"], c["h_alarm"],
                                            c["min_gap_steps"])

    lib = ctx.lib
    vis = lib.visibility(sigma)                       # (n_scen, n_sensors)
    scen = {str(s): i for i, s in enumerate(lib.scenarios)}
    H = lib.design_matrix()
    Hn = H / np.maximum(np.linalg.norm(H, axis=0, keepdims=True), 1e-12)
    topo = ctx.topo

    def scenario_index(link_id: str):
        """Map a leak PIPE to its scenario row: use the endpoint junction with
        the stronger reference signature."""
        ends = topo.link_nodes.get(link_id)
        if not ends:
            return None
        cand = [scen[e] for e in ends if e in scen]
        if not cand:
            return None
        return max(cand, key=lambda i: vis[i].max())

    rows = []
    for k in selection.BUDGETS:
        subsets = tracks.subsets_from_selection(frozen["selection"], k)
        for mname, S in subsets.items():
            dets = detector.run_subset(Z, S, per_sensor, c["min_gap_steps"],
                                       ctx.localiser, c["window_steps"], ts)
            timed = evaluate.match_in_time(dets, leaks, topo)
            for leak in leaks:
                zi = scenario_index(leak.link_id)
                if zi is None:
                    continue
                ev = timed["per_event"][leak.link_id]
                dS = float(vis[zi, S].max())              # FO visibility score
                sig_vec = H[S, zi]
                snr = float(np.linalg.norm(sig_vec) / np.sqrt(len(S)))
                # isolability margin: how distinct is this scenario's signature
                # from its nearest neighbour, as seen by S
                u = Hn[S, zi]
                un = u / max(np.linalg.norm(u), 1e-12)
                A = Hn[S, :]
                An = A / np.maximum(np.linalg.norm(A, axis=0, keepdims=True), 1e-12)
                cos = An.T @ un
                cos[zi] = -np.inf
                margin = float(1.0 - np.max(cos))
                # smallest singular value of the local design block
                nb = np.argsort(-cos)[:10]
                svals = np.linalg.svd(Hn[np.ix_(S, nb)], compute_uv=False)
                rows.append({
                    "year": year, "budget": k, "method": mname,
                    "event": leak.link_id, "leak_type": leak.leak_type,
                    "diameter_m": leak.diameter_m,
                    "failure": int(1 - ev["detected"]),
                    "localisation_m": ev["distance_m"],
                    "delay_h": (ev["delay_steps"] * 5 / 60
                                if ev["delay_steps"] is not None else np.nan),
                    "fo_visibility_dS": dS,
                    "fo_neg_visibility": -dS,      # higher = more failure-prone
                    "snr": snr,
                    "neg_snr": -snr,
                    "isolability_margin": margin,
                    "neg_isolability_margin": -margin,
                    "smallest_sv": float(svals[-1]),
                    "neg_smallest_sv": -float(svals[-1]),
                })
    return pd.DataFrame(rows)


def evaluate_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """AUROC / AUPRC / Brier / Spearman for each candidate failure predictor."""
    predictors = ["fo_neg_visibility", "neg_snr", "neg_isolability_margin",
                  "neg_smallest_sv"]
    out = []
    for (year,), g0 in df.groupby(["year"]):
        prevalence = float(g0["failure"].mean())
        for p in predictors:
            s = g0[p].to_numpy(dtype=float)
            y = g0["failure"].to_numpy(dtype=float)
            a = auroc(s, y)
            ap = auprc(s, y)
            lo, hi = boot_ci(auroc, s, y)
            plo, phi = boot_ci(auprc, s, y)
            rank = pd.Series(s).rank(pct=True).to_numpy()
            out.append({
                "year": year, "predictor": p, "n": int(len(g0)),
                "failure_prevalence": prevalence,
                "auroc": a, "auroc_ci_lo": lo, "auroc_ci_hi": hi,
                "auprc": ap, "auprc_ci_lo": plo, "auprc_ci_hi": phi,
                "auprc_above_prevalence": bool(plo > prevalence),
                "brier_rank_as_prob": brier(rank, y),
                "spearman_vs_localisation": spearman(
                    s, g0["localisation_m"].to_numpy(dtype=float)),
                "spearman_vs_delay": spearman(s, g0["delay_h"].to_numpy(dtype=float)),
            })
    return pd.DataFrame(out)


def decile_table(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (year,), g in df.groupby(["year"]):
        g = g.copy()
        g["decile"] = pd.qcut(g["fo_neg_visibility"].rank(method="first"), 10,
                              labels=False, duplicates="drop")
        for d, gg in g.groupby("decile"):
            out.append({"year": year, "decile": int(d), "n": int(len(gg)),
                        "failure_rate": float(gg["failure"].mean()),
                        "mean_fo_visibility": float(gg["fo_visibility_dS"].mean())})
    return pd.DataFrame(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((REPO / "FROZEN_PROTOCOL.json").read_text())
    ctx = tracks.Context(PROC / "sensitivity_library.npz", RAW / "L-TOWN_v2_Model.inp")

    parts = [
        build_rows(ctx, frozen, PROC / "regenerated_2018", 2018,
                   "dataset_configuration_historical.yalm"),
        build_rows(ctx, frozen, PROC / "regenerated_2019", 2019,
                   "dataset_configuration_evaluation.yalm"),
    ]
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(OUT / "FO_DIAGNOSTIC_RESULTS.csv", index=False)

    diag = evaluate_diagnostics(df)
    diag.to_csv(OUT / "FO_DIAGNOSTIC_METRICS.csv", index=False)
    decile_table(df).to_csv(OUT / "FO_DIAGNOSTIC_DECILES.csv", index=False)

    print(diag[["year", "predictor", "n", "failure_prevalence", "auroc",
                "auroc_ci_lo", "auroc_ci_hi", "auprc",
                "spearman_vs_localisation"]].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
