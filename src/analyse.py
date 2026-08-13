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


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def table_from_track(track: dict, is_track_a: bool) -> pd.DataFrame:
    rows = []
    if is_track_a:
        folds = track["folds"]
        budgets = sorted(folds[0]["budgets"].keys(), key=int)
        for k in budgets:
            for m in folds[0]["budgets"][k]["methods"]:
                det = [f["budgets"][k]["methods"][m]["held_out_detected"] for f in folds]
                dly = [f["budgets"][k]["methods"][m]["held_out_delay_h"] for f in folds]
                dst = [f["budgets"][k]["methods"][m]["held_out_localisation_m"] for f in folds]
                fps = [f["budgets"][k]["methods"][m]["false_positives_full_year"] for f in folds]
                eur = [f["budgets"][k]["methods"][m]["battledim_score_eur_full_year"] for f in folds]
                cpu = [f["budgets"][k]["methods"][m]["compute_time_s"] for f in folds]
                dly = [d for d in dly if d is not None]
                dst = [d for d in dst if d is not None]
                rows.append({
                    "budget": int(k), "method": m,
                    "recall": float(np.mean(det)),
                    "false_forgetting_rate": 1.0 - float(np.mean(det)),
                    "n_events_detected": int(np.sum(det)), "n_events": len(det),
                    "delay_mean_h": float(np.mean(dly)) if dly else np.nan,
                    "delay_median_h": float(np.median(dly)) if dly else np.nan,
                    "localisation_mean_m": float(np.mean(dst)) if dst else np.nan,
                    "localisation_median_m": float(np.median(dst)) if dst else np.nan,
                    "false_positives_mean": float(np.mean(fps)),
                    "battledim_score_eur_mean": float(np.mean(eur)),
                    "compute_time_s_mean": float(np.mean(cpu)),
                })
    else:
        for k, entry in track["budgets"].items():
            for m, r in entry["methods"].items():
                mt = r["metrics"]
                rows.append({
                    "budget": int(k), "method": m,
                    "recall": mt["recall"],
                    "false_forgetting_rate": mt["false_forgetting_rate"],
                    "precision": mt["precision"], "f1": mt["f1"],
                    "true_positives": mt["true_positives"],
                    "false_positives": mt["false_positives"],
                    "false_negatives": mt["false_negatives"],
                    "delay_mean_h": mt["detection_delay_mean_h"],
                    "delay_median_h": mt["detection_delay_median_h"],
                    "localisation_mean_m": mt["localisation_distance_mean_m"],
                    "localisation_median_m": mt["localisation_distance_median_m"],
                    "battledim_score_eur": mt["battledim_score_eur"],
                    "worst_per_leak_recall": mt["worst_per_leak_recall"],
                    "compute_time_s": mt["compute_time_s"],
                })
    df = pd.DataFrame(rows)
    return df.sort_values(["budget", "false_forgetting_rate"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, cols: list[str], budget: int) -> str:
    sub = df[df["budget"] == budget][cols].copy()
    for c in sub.columns:
        if sub[c].dtype.kind == "f":
            sub[c] = sub[c].map(lambda v: "-" if pd.isna(v) else f"{v:.3f}")
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    body = "\n".join("| " + " | ".join(str(v) for v in r) + " |"
                     for r in sub.itertuples(index=False))
    return "\n".join([head, sep, body])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


REPORT_NAME = "FO_BATTLEDIM_EXTERNAL_VALIDATION_FINAL.md"


def _ci_lines(comparison: dict, budget: str) -> str:
    entry = comparison["budgets"].get(budget)
    if not entry:
        return "_no comparison at this budget_"
    rows = ["| baseline | FO ff | baseline ff | abs diff | rel diff | 95% CI (abs) | CI favourable | recall loss (pts) |",
            "|---|---|---|---|---|---|---|---|"]
    for b, v in sorted(entry["baselines"].items(),
                       key=lambda kv: kv[1]["false_forgetting"]["absolute_difference"]):
        ff, d = v["false_forgetting"], v["decision"]
        rows.append(
            f"| {b} | {ff['mean_fo']:.3f} | {ff['mean_baseline']:.3f} | "
            f"{ff['absolute_difference']:+.3f} | "
            f"{(ff['relative_difference']*100):+.1f}% | "
            f"[{ff['ci95_absolute'][0]:+.3f}, {ff['ci95_absolute'][1]:+.3f}] | "
            f"{'yes' if ff['ci_entirely_favourable'] else 'no'} | "
            f"{(d['recall_loss_points']*100 if d['recall_loss_points'] is not None else float('nan')):+.1f} |"
        )
    return "\n".join(rows)


def write_report(ctx: dict) -> Path:
    manifest = ctx["manifest"]
    provenance = ctx["provenance"]
    frozen = ctx["frozen"]
    ta, tb, tc = ctx["track_a"], ctx["track_b"], ctx["track_c"]
    ca, cb = ctx["cmp_a"], ctx["cmp_b"]
    va, vb, vc = ctx["verdict_a"], ctx["verdict_b"], ctx["verdict_c"]
    vg, vg_reason = ctx["verdict_global"], ctx["verdict_global_reason"]
    df_a, df_b = ctx["df_a"], ctx["df_b"]
    budgets = sorted(cb["budgets"].keys(), key=int) if cb["budgets"] else []

    L: list[str] = []
    A = L.append

    A("# FO / Frontière d'Oubli — external validation attempt on BattLeDIM / L-Town")
    A("")
    A("## Verdicts")
    A("")
    A("| scope | verdict |")
    A("|---|---|")
    A(f"| `EVENT_HELDOUT_2018_VERDICT` | **{va}** |")
    A(f"| `RECONSTRUCTED_2019_VERDICT` | **{vb}** |")
    A(f"| `ROBUSTNESS_VERDICT` | **{vc}** |")
    A(f"| **global** | **{vg}** |")
    A("")
    A(f"{vg_reason}")
    A("")
    A("> `VALIDATED_EXTERNALLY` is **not** claimed and cannot be produced by this")
    A("> repository. The published BattLeDIM SCADA could not be downloaded, so FO has")
    A("> not been run on the real external dataset. The permitted global vocabulary is")
    A("> `STRONG_INTERNAL_BENCHMARK_SUPPORT` / `PROMISING` / `INCONCLUSIVE` /")
    A("> `NOT_SUPPORTED`, enforced in code by an assertion against `GLOBAL_VERDICTS`.")
    A("")
    A("---")
    A("")
    A("## 1. Data provenance")
    A("")
    src = provenance["source_used"]
    A(f"- **Source used**: {src['url']} @ `{src['commit']}` — {src['note']}")
    A(f"- **Licence**: {provenance['license']}")
    A(f"- **Citation**: {provenance['canonical_citation']}")
    A("")
    A("Download attempts, in the order the protocol prescribes:")
    A("")
    A("| # | target | result | exact error |")
    A("|---|---|---|---|")
    for a in provenance["attempts_in_protocol_order"]:
        err = a.get("exact_error") or a.get("detail", "")
        if isinstance(err, list):
            err = "; ".join(err)
        err = str(err).replace("\n", " ").replace("|", "\\|")[:220]
        A(f"| {a['order']} | {a['target'][:80]} | {a['result']} | `{err}` |")
    A("")
    A("**The published SCADA CSVs were never obtained.** Everything downstream runs on")
    A("data regenerated with the official generator, the official network model and the")
    A("official leak schedule — a pipeline that contains no random draw.")
    A("")
    A("### File digests")
    A("")
    A("| file | bytes | SHA256 |")
    A("|---|---|---|")
    for f in manifest["files"]:
        if "competition_leakages" in f["path"] or "scoring_functions" in f["path"]:
            continue
        A(f"| `{f['path']}` | {f['size_bytes']} | `{f['sha256']}` |")
    A("")
    A(f"Full manifest: `DATA_MANIFEST.json` ({manifest['n_files']} files, "
      f"{manifest['total_bytes']} bytes) with rows, columns, column names, temporal")
    A("coverage and missing-value counts per file.")
    A("")
    A("## 2. Critical findings about the artefacts")
    A("")
    for f in provenance["critical_findings"]:
        A(f"**{f['id']} ({f['severity']})** — {f['finding']}")
        A("")
    A("## 3. Methodology")
    A("")
    A("### 3.1 The FO criterion")
    A("")
    A("For a latent scenario `z`, a sensor network `S` and a rich reference `R`,")
    A("visibility in units of sensor noise is")
    A("")
    A("```")
    A("d_S(z) = max_t max_{j in S} |Delta p[z, j, t]| / sigma_j")
    A("```")
    A("")
    A("with `Delta p[z, j, t]` the pressure drop a reference-size leak in scenario `z`")
    A("induces at sensor `j` at operating snapshot `t`. With `d_ref = d_R`,")
    A("")
    A("```")
    A("E_kappa      = { z : d_ref(z) >= kappa }")
    A("B_kappa_eta(S) = P[ d_S(z) <= eta | d_ref(z) >= kappa ]")
    A("```")
    A("")
    A("`B` is the false-forgetting rate — the reconstructibility blind spot. Selection")
    A("minimises `B`, then breaks ties on the 5th percentile of visibility over")
    A("`E_kappa`, then the 10th percentile, then the mean, exactly as pre-registered.")
    A("")
    c = frozen["constants"]
    A(f"Frozen from 2018: `kappa = {c['kappa']}`, `eta = {c['eta']}`, "
      f"`tau = {c['tau']}`, CUSUM slack `k = {c['k_cusum']}`, alarm threshold "
      f"`h = {c['h_alarm']:.4f}`.")
    A("")
    A("### 3.2 Leak physics")
    A("")
    A("The BattLeDIM orifice leak `q = Cd A sqrt(2 g p)` with `Cd = 0.75` is reproduced")
    A("as an EPANET emitter with `C = Cd sqrt(2 g) A`. That equivalence is **tested**,")
    A("not asserted, against wntr's own `add_leak`: maximum relative deviation")
    A("**4.6e-07** over 72 steps. The library build aborts if it exceeds 2%.")
    A("")
    A("### 3.3 Identical detector")
    A("")
    A("Every method — FO and all baselines — uses the same pipeline: ridge nominal")
    A("model on exogenous inputs only (3 inlet flows, tank level, 3 daily harmonics,")
    A("day-of-week), robust MAD residual scaling, per-sensor two-sided CUSUM with")
    A("re-baselining, and cosine-similarity localisation against the leak-signature")
    A("library. Only the sensor subset differs.")
    A("")
    A("### 3.4 Baselines")
    A("")
    A("`theta` has 782 components against a budget of at most 12, so the Fisher")
    A("information is singular and **classical D-, A- and E-optimality are undefined**")
    A("here — they would rank every subset identically. Two well-posed adaptations are")
    A("implemented and named for what they are:")
    A("")
    A("- **Bayesian-regularised** (`*_bayesian`) — exact Bayesian D/A optimality under a")
    A("  `N(0, tau^2 I)` prior, evaluated through the determinant identity and Woodbury")
    A("  so the cost is `k x k` rather than `782 x 782`. No approximation.")
    A("- **Rank-r reduced** (`*_rank_reduced`) — classical D/A/E optimality on the")
    A("  leading `r = 4` right singular vectors of `H`.")
    A("- **`E_optimal_observable_subspace`** — deliberately *not* called Bayesian")
    A("  E-optimal. Literal Bayesian E-optimality is **degenerate** here:")
    A("  `lambda_min(H_S^T H_S/sigma^2 + I/tau^2) = 1/tau^2` for every subset. This is")
    A("  an anomaly of the setting, recorded rather than hidden.")
    A("- **`bayesian_information_gain`** — mutual information `I(y_S; theta)`.")
    A("- **`goal_oriented_oed`** — maximises the minimum angular separation between")
    A("  scenario signatures, targeting localisation rather than magnitude variance.")
    A("- **`topological_dispersion`** — greedy max-min pipe-length dispersion.")
    A("- **`centrality`** — top-k weighted betweenness.")
    A(f"- **`random`** — {c['n_random_replications']} replications per budget.")
    A("")
    A("Optimiser is identical across methods at each budget: exhaustive where")
    A("affordable (`k=4`, C(33,4)=40920), greedy forward otherwise, with both run at")
    A("`k=4` so the greedy gap is measured rather than assumed.")
    A("")
    A("## 4. Proof of freeze before 2019")
    A("")
    A(f"- `FROZEN_PROTOCOL.json` SHA256: `{ctx['frozen_sha']}`")
    A(f"- frozen at: `{frozen['frozen_utc']}`")
    A("- The freeze installs a runtime guard patching `builtins.open` and `numpy.load`")
    A("  so that **any** read of a 2019 or evaluation artefact raises. The guard is")
    A("  armed for the whole freeze, so a contaminated protocol aborts rather than")
    A("  being emitted silently.")
    A("- `run_full_validation.py` stage 7 refuses to open 2019 unless the frozen file")
    A("  and its digest already exist.")
    A("")
    A("**Honest caveat (F4).** The organisers ship the 2019 ground truth inside the")
    A("same file as the 2018 configuration, so it was visible during the mandatory")
    A("data inventory, before the freeze existed. The guard addresses the code path,")
    A("not that exposure. No threshold, hyper-parameter, sensor subset or FO quantity")
    A("is derived from any 2019 value, but the exposure is real and is recorded here")
    A("rather than concealed.")
    A("")
    A("## 5. Track A — `EVENT_HELDOUT_2018`")
    A("")
    A(f"Leave-one-leak-event-out over the {ta['n_events']} events of 2018. Per fold the")
    A("nominal model, sigma, the alarm threshold and every method's sensor subset are")
    A("re-derived without the held-out event.")
    A("")
    for k in budgets:
        A(f"### Budget k = {k}")
        A("")
        A(md_table(df_a, ["method", "recall", "false_forgetting_rate",
                          "n_events_detected", "delay_mean_h", "localisation_mean_m",
                          "false_positives_mean", "battledim_score_eur_mean"], int(k)))
        A("")
        A("Paired bootstrap, 10000 resamples, FO minus baseline:")
        A("")
        A(_ci_lines(ca, k))
        A("")
    A(f"**`EVENT_HELDOUT_2018_VERDICT` = {va}**")
    A("")
    A("![Track A](figures/track_a_false_forgetting.png)")
    A("")
    A("![Track A forest](figures/track_a_forest.png)")
    A("")
    A("## 6. Track B — `OFFICIAL_ARTEFACT_RECONSTRUCTED_BENCHMARK`")
    A("")
    A("> **This is not a validation on the published BattLeDIM SCADA.** It is the")
    A("> frozen protocol applied to a 2019 year regenerated from the official")
    A("> artefacts. Carry these with every number below:")
    A(">")
    for cav in tb["caveats"]:
        A(f"> - {cav}")
    A("")
    for k in budgets:
        A(f"### Budget k = {k}")
        A("")
        A(md_table(df_b, ["method", "recall", "false_forgetting_rate", "precision",
                          "f1", "false_positives", "delay_mean_h",
                          "localisation_mean_m", "battledim_score_eur",
                          "worst_per_leak_recall"], int(k)))
        A("")
        A("Paired bootstrap, 10000 resamples, FO minus baseline:")
        A("")
        A(_ci_lines(cb, k))
        A("")
    A(f"**`RECONSTRUCTED_2019_VERDICT` = {vb}**")
    A("")
    A("![Track B](figures/track_b_false_forgetting.png)")
    A("")
    A("![Track B forest](figures/track_b_forest.png)")
    A("")
    A("## 7. Track C — `SYNTHETIC_ROBUSTNESS_STUDY`")
    A("")
    A("Explicitly synthetic. Sensor noise and demand variation are injected with every")
    A("distribution frozen from 2018; nothing here was chosen after seeing Track B.")
    A("")
    A(f"- grid: noise multipliers {tc['grid']['noise_multipliers']}, demand scales "
      f"{tc['grid']['demand_scales']}, seeds {tc['grid']['seeds']}")
    A(f"- cells where FO is at least as good as every baseline: "
      f"{ctx['vc_detail'].get('cells_where_fo_dominates')} / "
      f"{ctx['vc_detail'].get('n_cells')} "
      f"({100*ctx['vc_detail'].get('fraction', 0):.0f}%)")
    A("")
    A(f"**`ROBUSTNESS_VERDICT` = {vc}**")
    A("")
    A("![Robustness](figures/robustness_heatmap.png)")
    A("")
    A("## 8. Negative controls and anti-bias checks")
    A("")
    ctrl = tc["controls"]
    if "C1_label_permutation" in ctrl:
        perm = ctrl["C1_label_permutation"]["false_forgetting_rate_per_replication"]
        fo_perm = float(np.mean([p["FO"] for p in perm]))
        A(f"- **C1 label permutation** ({len(perm)} replications, budget 8): FO "
          f"false-forgetting rises to **{fo_perm:.3f}** when leak labels are shuffled. "
          "A spatial advantage that survived permutation would indicate a bug or a "
          "leak of information; it must collapse, and this is the check.")
    if "C3_no_leak_false_alarms" in ctrl:
        A("- **C3 no-leak control**: alarms raised on the leak-free 2018 year "
          "(every one is a false alarm) — "
          f"`{json.dumps(ctrl['C3_no_leak_false_alarms']['counts_per_budget'])}`")
    if "C4_threshold_sensitivity" in ctrl:
        A("- **C4 threshold sensitivity**: reported across `h x "
          f"{list(ctrl['C4_threshold_sensitivity']['by_scale'].keys())}`. The best "
          "threshold is never selected using 2019.")
    if "C5_single_sensor_failure" in ctrl:
        A("- **C5 single-sensor failure** and **C6 successive removal**: per-method "
          "degradation curves in `results/track_c_robustness.json`.")
    A("- **C7 bootstrap by leak**: the paired bootstrap above resamples events.")
    A("- **C8 bootstrap by calendar period**: per-block false-forgetting rates in "
      "`results/track_c_robustness.json`.")
    A("")
    A("## 9. Anomalies kept")
    A("")
    A("- Literal Bayesian E-optimality is degenerate in this regime (§3.4).")
    A("- The published model artefact repeats its demand year (F2), so the")
    A("  reconstructed 2019 test set carries no demand novelty. This makes detection")
    A("  easier than on the real benchmark for **every** method, compresses the")
    A("  differences between them, and is the single strongest reason Track B cannot")
    A("  stand as external validation.")
    A("- The released generator applies no measurement noise and defines an unused")
    A("  uncertainty range (F3), indicating it is not the exact version that produced")
    A("  the published CSVs.")
    A("")
    A("## 10. Limitations")
    A("")
    A("1. **No published SCADA.** The decisive limitation. Zenodo and")
    A("   `battledim.ucy.ac.cy` are blocked by the egress policy; no mirror of the CSVs")
    A("   exists on any reachable host.")
    A("2. **Reconstructed test year.** Demands repeat between years; noise is absent.")
    A("3. **Early exposure to 2019 metadata** (F4).")
    A("4. **Scenario space is junction-level**, mapped to pipes by averaging endpoint")
    A("   signatures, rather than simulating a leak at every pipe midpoint.")
    A("5. **Greedy search above k=4**; the gap is measured at k=4 only.")
    A("6. **14 events in Track A, 23 in Track B** — small denominators, so the")
    A("   confidence intervals are wide and single events move them.")
    A("7. The decision thresholds (20% relative reduction, 2-point recall margin) are")
    A("   **project-internal rules, not field standards**.")
    A("")
    A("## 11. Reproducibility")
    A("")
    A("```")
    A("pip install -r requirements.txt")
    A("python3 run_full_validation.py")
    A("```")
    A("")
    A(f"Python {manifest['environment']['python']}, "
      f"numpy {frozen['versions']['numpy']}, pandas {frozen['versions']['pandas']}, "
      f"wntr {manifest['environment'].get('wntr')}. "
      f"Seed {c['seed']}; bootstrap seed {stats.BOOTSTRAP_SEED}, "
      f"{stats.N_BOOTSTRAP} resamples.")
    A("")
    A("| artefact | SHA256 |")
    A("|---|---|")
    A(f"| `DATA_MANIFEST.json` | `{ctx['manifest_sha']}` |")
    A(f"| `FROZEN_PROTOCOL.json` | `{ctx['frozen_sha']}` |")
    for name, digest in ctx["result_hashes"].items():
        A(f"| `{name}` | `{digest}` |")
    A("")

    path = REPO / REPORT_NAME
    path.write_text("\n".join(L) + "\n")
    return path


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _sha(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((REPO / "DATA_MANIFEST.json").read_text())
    provenance = json.loads((REPO / "data/raw/PROVENANCE.json").read_text())
    frozen = json.loads((REPO / "FROZEN_PROTOCOL.json").read_text())
    ta = json.loads((RESULTS / "track_a_event_heldout_2018.json").read_text())
    tb = json.loads((RESULTS / "track_b_reconstructed_2019.json").read_text())
    tc_path = RESULTS / "track_c_robustness.json"
    tc = json.loads(tc_path.read_text()) if tc_path.exists() else {"cells": [], "controls": {},
                                                                   "grid": {}}

    va_vec, vb_vec = track_a_vectors(ta), track_b_vectors(tb)
    ca = compare_track(va_vec, "EVENT_HELDOUT_2018")
    cb = compare_track(vb_vec, "OFFICIAL_ARTEFACT_RECONSTRUCTED_BENCHMARK")
    (RESULTS / "bootstrap_track_a.json").write_text(json.dumps(ca, indent=2) + "\n")
    (RESULTS / "bootstrap_track_b.json").write_text(json.dumps(cb, indent=2) + "\n")

    va, va_det = verdict_for(ca)
    vb, vb_det = verdict_for(cb)

    perm = tc.get("controls", {}).get("C1_label_permutation", {})
    reps = perm.get("false_forgetting_rate_per_replication", [])
    ordering_holds = True
    if reps:
        fo_perm = float(np.mean([r["FO"] for r in reps]))
        base_perm = float(np.mean([np.mean([v for kk, v in r.items() if kk != "FO"])
                                   for r in reps]))
        # Under permuted labels FO must NOT retain a clear advantage.
        ordering_holds = bool(fo_perm >= base_perm - 0.05)
    vc, vc_det = robustness_verdict(tc, ordering_holds) if tc.get("cells") else (
        "NOT_SUPPORTED", {"reason": "Track C not run"})

    vg, vg_reason = global_verdict(va, vb, vc)

    df_a, df_b = table_from_track(ta, True), table_from_track(tb, False)
    df_a.to_csv(RESULTS / "table_track_a_event_heldout_2018.csv", index=False)
    df_b.to_csv(RESULTS / "table_track_b_reconstructed_2019.csv", index=False)
    if tc.get("cells"):
        pd.DataFrame(
            [
                {"budget": c["budget"], "noise": c["noise_multiplier"],
                 "demand": c["demand_scale"], "seed": c["seed"], "method": m, **v}
                for c in tc["cells"] for m, v in c["methods"].items()
            ]
        ).to_csv(RESULTS / "table_track_c_robustness.csv", index=False)

    verdicts = {
        "EVENT_HELDOUT_2018_VERDICT": va,
        "RECONSTRUCTED_2019_VERDICT": vb,
        "ROBUSTNESS_VERDICT": vc,
        "GLOBAL_VERDICT": vg,
        "global_verdict_reason": vg_reason,
        "validated_externally_available": False,
        "why_not": (
            "FO has not been run on the published BattLeDIM SCADA or any comparable "
            "real external dataset; the published SCADA is unreachable (finding F1)."
        ),
        "permitted_global_vocabulary": list(GLOBAL_VERDICTS),
        "detail": {"track_a": va_det, "track_b": vb_det, "track_c": vc_det},
    }
    (RESULTS / "verdicts.json").write_text(json.dumps(verdicts, indent=2) + "\n")

    fig_blind_spot(frozen, FIGURES / "blind_spot_by_budget.png")
    fig_rate_vs_budget(va_vec, "Track A - EVENT_HELDOUT_2018 - false-forgetting rate",
                       FIGURES / "track_a_false_forgetting.png")
    fig_rate_vs_budget(vb_vec,
                       "Track B - RECONSTRUCTED 2019 (not published SCADA) - false-forgetting rate",
                       FIGURES / "track_b_false_forgetting.png")
    mid = sorted(ca["budgets"].keys(), key=int)[len(ca["budgets"]) // 2] if ca["budgets"] else None
    if mid:
        fig_forest(ca, mid, f"Track A - paired difference at k={mid}",
                   FIGURES / "track_a_forest.png")
        fig_forest(cb, mid, f"Track B - paired difference at k={mid}",
                   FIGURES / "track_b_forest.png")
    if tc.get("cells"):
        fig_robustness(tc, FIGURES / "robustness_heatmap.png")

    result_hashes = {
        p.name: _sha(p) for p in sorted(RESULTS.glob("*")) if p.is_file()
    }

    path = write_report(
        {
            "manifest": manifest, "provenance": provenance, "frozen": frozen,
            "track_a": ta, "track_b": tb, "track_c": tc,
            "cmp_a": ca, "cmp_b": cb,
            "verdict_a": va, "verdict_b": vb, "verdict_c": vc,
            "verdict_global": vg, "verdict_global_reason": vg_reason,
            "vc_detail": vc_det, "df_a": df_a, "df_b": df_b,
            "manifest_sha": _sha(REPO / "DATA_MANIFEST.json"),
            "frozen_sha": _sha(REPO / "FROZEN_PROTOCOL.json"),
            "result_hashes": result_hashes,
        }
    )
    print(f"EVENT_HELDOUT_2018_VERDICT   = {va}")
    print(f"RECONSTRUCTED_2019_VERDICT   = {vb}")
    print(f"ROBUSTNESS_VERDICT           = {vc}")
    print(f"GLOBAL_VERDICT               = {vg}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
