"""
Turn the three tracks into tables, figures, verdicts and the final report.

Outputs
    results/*.csv                    per-budget tables, one row per method
    results/bootstrap_*.json         10000-resample paired comparisons
    results/verdicts.json            the three track verdicts and the global one
    figures/*.png
    FO_BATTLEDIM_EXTERNAL_VALIDATION_FINAL.md

VERDICT VOCABULARY
    Track verdicts   SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED
    Global verdict   STRONG_INTERNAL_BENCHMARK_SUPPORT / PROMISING /
                     INCONCLUSIVE / NOT_SUPPORTED

VALIDATED_EXTERNALLY is not reachable from this repository and is never
emitted. It requires FO to have been run on the published BattLeDIM SCADA or on
another comparable real external dataset, and the published SCADA could not be
downloaded (finding F1). The guard is mechanical: GLOBAL_VERDICTS does not
contain the string.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stats  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
FIGURES = REPO / "figures"

BASELINES = [
    "D_optimal_bayesian",
    "A_optimal_bayesian",
    "E_optimal_observable_subspace",
    "bayesian_information_gain",
    "D_optimal_rank_reduced",
    "A_optimal_rank_reduced",
    "E_optimal_rank_reduced",
    "goal_oriented_oed",
    "topological_dispersion",
    "centrality",
]

GLOBAL_VERDICTS = (
    "STRONG_INTERNAL_BENCHMARK_SUPPORT",
    "PROMISING",
    "INCONCLUSIVE",
    "NOT_SUPPORTED",
)
TRACK_VERDICTS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED")

MIN_BUDGETS_FOR_SUPPORT = 2


# ---------------------------------------------------------------------------
# Track A -> paired vectors over the 14 events
# ---------------------------------------------------------------------------


def track_a_vectors(track_a: dict) -> dict[str, dict[str, np.ndarray]]:
    """{budget: {method: per-event 0/1 miss vector}} -- paired by event."""
    out: dict[str, dict[str, np.ndarray]] = {}
    folds = track_a["folds"]
    budgets = sorted(folds[0]["budgets"].keys(), key=int)
    for k in budgets:
        methods = folds[0]["budgets"][k]["methods"].keys()
        per_method = {}
        for m in methods:
            miss = [1 - f["budgets"][k]["methods"][m]["held_out_detected"] for f in folds]
            per_method[m] = np.array(miss, dtype=float)
        rnd = np.array(
            [
                [1 - r["held_out_detected"] for r in f["budgets"][k]["random"]]
                for f in folds
            ],
            dtype=float,
        )  # (n_events, n_random)
        per_method["_random_matrix"] = rnd
        out[k] = per_method
    return out


def track_b_vectors(track_b: dict) -> dict[str, dict[str, np.ndarray]]:
    """{budget: {method: per-event 0/1 miss vector}} for the 2019 reconstruction."""
    out: dict[str, dict[str, np.ndarray]] = {}
    for k, entry in track_b["budgets"].items():
        per_method = {}
        link_order = None
        for m, r in entry["methods"].items():
            det = r["metrics"]["per_leak_detected"]
            if link_order is None:
                link_order = list(det.keys())
            per_method[m] = np.array([1 - det[l] for l in link_order], dtype=float)
        rnd = np.array(
            [[1 - r["metrics"]["per_leak_detected"][l] for l in link_order]
             for r in entry["random"]],
            dtype=float,
        ).T  # (n_events, n_random)
        per_method["_random_matrix"] = rnd
        out[k] = per_method
    return out


def recall_vectors(miss: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {m: 1.0 - v for m, v in miss.items() if not m.startswith("_")}


# ---------------------------------------------------------------------------
# Bootstrap comparisons
# ---------------------------------------------------------------------------


def compare_track(vectors: dict[str, dict[str, np.ndarray]], label: str) -> dict:
    out = {"track": label, "budgets": {}}
    for k, per_method in vectors.items():
        if "FO" not in per_method:
            continue
        fo_miss = per_method["FO"]
        fo_rec = 1.0 - fo_miss
        entry = {"baselines": {}}
        for b in BASELINES:
            if b not in per_method:
                continue
            ff = stats.paired_bootstrap(fo_miss, per_method[b], lower_is_better=True)
            rc = stats.paired_bootstrap(fo_rec, 1.0 - per_method[b], lower_is_better=False)
            entry["baselines"][b] = {
                "false_forgetting": ff,
                "recall": rc,
                "decision": stats.evaluate_decision_rules(ff, rc),
            }
        rnd = per_method.get("_random_matrix")
        if rnd is not None and rnd.size:
            entry["random"] = stats.compare_against_random(
                float(fo_miss.mean()), rnd.mean(axis=0), lower_is_better=True
            )
        out["budgets"][k] = entry
    return out


def verdict_for(comparison: dict) -> tuple[str, dict]:
    """A track is SUPPORTED when FO's CI is entirely favourable on false
    forgetting against every baseline at at least MIN_BUDGETS_FOR_SUPPORT
    budgets, with recall non-inferiority holding there."""
    per_budget = {}
    for k, entry in comparison["budgets"].items():
        decisions = [v["decision"] for v in entry["baselines"].values()]
        if not decisions:
            continue
        all_fav = all(d["primary_ci_favourable"] for d in decisions)
        any_fav = any(d["primary_ci_favourable"] for d in decisions)
        non_inf = all(d["recall_non_inferior_2pt"] for d in decisions)
        per_budget[k] = {
            "beats_all_baselines_ci": bool(all_fav),
            "beats_some_baseline_ci": bool(any_fav),
            "recall_non_inferior_vs_all": bool(non_inf),
            "n_baselines_beaten": int(sum(d["primary_ci_favourable"] for d in decisions)),
            "n_baselines": len(decisions),
        }
    strong = [k for k, v in per_budget.items()
              if v["beats_all_baselines_ci"] and v["recall_non_inferior_vs_all"]]
    partial = [k for k, v in per_budget.items() if v["beats_some_baseline_ci"]]

    if len(strong) >= MIN_BUDGETS_FOR_SUPPORT:
        verdict = "SUPPORTED"
    elif partial:
        verdict = "PARTIALLY_SUPPORTED"
    else:
        verdict = "NOT_SUPPORTED"
    return verdict, {
        "per_budget": per_budget,
        "budgets_with_full_advantage": sorted(strong, key=int),
        "budgets_with_partial_advantage": sorted(partial, key=int),
    }


def robustness_verdict(track_c: dict, ref_ordering_holds: bool) -> tuple[str, dict]:
    cells = pd.DataFrame(
        [
            {
                "budget": c["budget"], "noise": c["noise_multiplier"],
                "demand": c["demand_scale"], "seed": c["seed"], "method": m,
                "ff": v["false_forgetting_rate"], "recall": v["recall"],
            }
            for c in track_c["cells"] for m, v in c["methods"].items()
        ]
    )
    if cells.empty:
        return "NOT_SUPPORTED", {"reason": "no robustness cells"}

    agg = cells.groupby(["budget", "noise", "demand", "method"])["ff"].mean().reset_index()
    wins, total = 0, 0
    detail = []
    for (b, n, d), grp in agg.groupby(["budget", "noise", "demand"]):
        g = grp.set_index("method")["ff"]
        if "FO" not in g.index:
            continue
        base = g.drop(index=[i for i in ["FO"] if i in g.index])
        total += 1
        won = bool((g["FO"] <= base).all())
        wins += int(won)
        detail.append({"budget": int(b), "noise": float(n), "demand": float(d),
                       "fo_ff": float(g["FO"]), "best_baseline_ff": float(base.min()),
                       "fo_at_least_as_good_as_all": won})
    frac = wins / total if total else 0.0
    if frac >= 0.75 and ref_ordering_holds:
        v = "SUPPORTED"
    elif frac >= 0.4:
        v = "PARTIALLY_SUPPORTED"
    else:
        v = "NOT_SUPPORTED"
    return v, {"n_cells": total, "cells_where_fo_dominates": wins,
               "fraction": frac, "per_cell": detail}


def global_verdict(va: str, vb: str, vc: str) -> tuple[str, str]:
    order = {"SUPPORTED": 2, "PARTIALLY_SUPPORTED": 1, "NOT_SUPPORTED": 0}
    a, b, cc = order[va], order[vb], order[vc]
    if a == 2 and b == 2 and cc >= 1:
        g = "STRONG_INTERNAL_BENCHMARK_SUPPORT"
    elif a >= 1 and b >= 1:
        g = "PROMISING"
    elif a + b + cc == 0:
        g = "NOT_SUPPORTED"
    else:
        g = "INCONCLUSIVE"
    reason = (
        f"Track A {va}, Track B {vb}, Track C {vc}. VALIDATED_EXTERNALLY is not "
        "available from this repository: it requires the published BattLeDIM SCADA "
        "or another comparable real external dataset, and the published SCADA could "
        "not be downloaded (finding F1)."
    )
    assert g in GLOBAL_VERDICTS
    return g, reason


# ---------------------------------------------------------------------------
# Figures
#
# Palette: the validated reference instance (references/palette.md). FO takes
# categorical slot 1 and the three closest baselines slots 2-3 plus violet;
# every remaining method is drawn in muted ink rather than a generated hue,
# because eleven methods exceed the eight-slot categorical palette and a ninth
# generated hue is never allowed. Identity is therefore carried by direct
# labels, not by colour alone -- which also discharges the validator's contrast
# WARN on the aqua slot.
# ---------------------------------------------------------------------------

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
FO_COLOR = "#2a78d6"
HL = ["#eb6834", "#1baf7a", "#4a3aa7"]
GOOD = "#0ca30c"
CRIT = "#d03b3b"
SEQ = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#256abf", "#184f95", "#0d366b"]


def _style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=12)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.8, axis="y")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(1.0)


def _rank_baselines(vectors: dict) -> list[str]:
    """Baselines ordered by mean miss rate over budgets -- the closest three get
    their own hue, the rest stay muted."""
    scores = {}
    for b in BASELINES:
        vals = [v[b].mean() for v in vectors.values() if b in v]
        if vals:
            scores[b] = float(np.mean(vals))
    return sorted(scores, key=scores.get)


def fig_rate_vs_budget(vectors: dict, title: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    budgets = sorted(vectors.keys(), key=int)
    x = [int(k) for k in budgets]
    ranked = _rank_baselines(vectors)
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    _style(ax, title, "sensor budget k", "false-forgetting rate  (1 - recall)")

    for b in ranked[3:]:
        y = [vectors[k][b].mean() for k in budgets]
        ax.plot(x, y, color=MUTED, linewidth=1.2, alpha=0.55, zorder=1)
    for i, b in enumerate(ranked[:3]):
        y = [vectors[k][b].mean() for k in budgets]
        ax.plot(x, y, color=HL[i], linewidth=2.0, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=2)
        ax.annotate(b.replace("_", " "), (x[-1], y[-1]), xytext=(6, 0),
                    textcoords="offset points", color=HL[i], fontsize=8,
                    va="center")
    y = [vectors[k]["FO"].mean() for k in budgets]
    ax.plot(x, y, color=FO_COLOR, linewidth=2.6, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.annotate("FO", (x[-1], y[-1]), xytext=(6, 0), textcoords="offset points",
                color=FO_COLOR, fontsize=9, fontweight="bold", va="center")

    ax.set_xticks(x)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.16)
    fig.text(0.01, 0.01, f"{len(ranked)} baselines; the three closest to FO are "
             "labelled, the rest drawn in grey", color=MUTED, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def fig_forest(comparison: dict, budget: str, title: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    entry = comparison["budgets"].get(budget)
    if not entry:
        return
    rows = []
    for b, v in entry["baselines"].items():
        ff = v["false_forgetting"]
        rows.append((b, ff["absolute_difference"], ff["ci95_absolute"],
                     ff["ci_entirely_favourable"]))
    rows.sort(key=lambda r: r[1])

    fig, ax = plt.subplots(figsize=(7.6, 0.42 * len(rows) + 2.0), dpi=160)
    _style(ax, title, "FO minus baseline, false-forgetting rate", "")
    ax.grid(True, color=GRID, linewidth=0.8, axis="x")
    ax.grid(False, axis="y")
    ax.axvline(0, color=AXIS, linewidth=1.2, zorder=1)

    for i, (name, d, ci, fav) in enumerate(rows):
        c = GOOD if fav else (CRIT if ci[0] > 0 else MUTED)
        ax.plot(ci, [i, i], color=c, linewidth=2.4, solid_capstyle="round", zorder=2)
        ax.plot([d], [i], marker="o", markersize=8, color=c,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0].replace("_", " ") for r in rows], fontsize=8, color=INK_2)
    ax.invert_yaxis()
    fig.text(0.01, 0.015,
             "negative favours FO  ·  bars are 95% CI from 10000 paired bootstraps  ·  "
             "green = CI entirely favourable, red = entirely against, grey = spans zero",
             color=MUTED, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def fig_robustness(track_c: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    df = pd.DataFrame(
        [
            {"noise": c["noise_multiplier"], "demand": c["demand_scale"],
             "method": m, "ff": v["false_forgetting_rate"]}
            for c in track_c["cells"] for m, v in c["methods"].items()
        ]
    )
    if df.empty:
        return
    cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), dpi=160)
    for ax, meth in zip(axes, ["FO", _best_baseline(df)]):
        sub = df[df["method"] == meth]
        piv = sub.pivot_table(index="demand", columns="noise", values="ff", aggfunc="mean")
        im = ax.imshow(piv.values, cmap=cmap, aspect="auto", vmin=0, vmax=1, origin="lower")
        ax.set_xticks(range(len(piv.columns)))
        ax.set_xticklabels([f"{c:g}" for c in piv.columns], fontsize=8)
        ax.set_yticks(range(len(piv.index)))
        ax.set_yticklabels([f"{i:g}" for i in piv.index], fontsize=8)
        _style(ax, meth.replace("_", " "), "sensor-noise multiplier", "demand-perturbation scale")
        ax.grid(False)
        for a in range(piv.shape[0]):
            for b in range(piv.shape[1]):
                val = piv.values[a, b]
                ax.text(b, a, f"{val:.2f}", ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if val > 0.55 else INK)
    fig.suptitle("SYNTHETIC ROBUSTNESS STUDY - false-forgetting rate, mean over budgets and seeds",
                 color=INK, fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def _best_baseline(df: pd.DataFrame) -> str:
    m = df[df["method"] != "FO"].groupby("method")["ff"].mean()
    return str(m.idxmin()) if len(m) else BASELINES[0]


def fig_blind_spot(frozen: dict, path: Path) -> None:
    """Model-based FO criterion B_kappa_eta by budget, straight from the freeze."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sel = frozen["selection"]["budgets"]
    budgets = sorted(sel.keys(), key=int)
    x = [int(k) for k in budgets]
    series = {}
    for name in ["FO"] + BASELINES:
        vals = []
        for k in budgets:
            e = sel[k].get(name)
            vals.append(e["fo_metrics"]["B_blind_spot_rate"] if e else np.nan)
        series[name] = vals

    ranked = sorted(
        [b for b in BASELINES if b in series],
        key=lambda b: np.nanmean(series[b]),
    )
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    _style(ax, "Model-based blind-spot rate B(kappa,eta) by sensor budget",
           "sensor budget k", "B  =  P[ d_S(z) <= eta | d_ref(z) >= kappa ]")
    for b in ranked[3:]:
        ax.plot(x, series[b], color=MUTED, linewidth=1.2, alpha=0.55)
    for i, b in enumerate(ranked[:3]):
        ax.plot(x, series[b], color=HL[i], linewidth=2.0, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(b.replace("_", " "), (x[-1], series[b][-1]), xytext=(6, 0),
                    textcoords="offset points", color=HL[i], fontsize=8, va="center")
    ax.plot(x, series["FO"], color=FO_COLOR, linewidth=2.6, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate("FO", (x[-1], series["FO"][-1]), xytext=(6, 0),
                textcoords="offset points", color=FO_COLOR, fontsize=9,
                fontweight="bold", va="center")
    ax.set_xticks(x)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.16)
    fig.text(0.01, 0.01, "FO optimises this quantity directly; the baselines do not. "
             "It is a design-time criterion, not an outcome.", color=MUTED, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
