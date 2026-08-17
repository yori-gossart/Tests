"""PHASE 23-RT -- figures. All annotations computed from the result files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "phase23_rt"
FIG = OUT / "figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF, INK, MUTE, GRID = "#fcfcfb", "#1c1c1a", "#6b6b66", "#e3e3df"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTE, "ytick.color": MUTE, "font.size": 9,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.dpi": 140, "legend.frameon": False,
})

MLAB = {"M1_logreg": "LogReg", "M2_random_forest": "RF",
        "M3_gradient_boosting": "GBM", "M4_rbf_svm": "SVM"}
DLAB = {"GAMETES_Epistasis_2_Way_20atts_0.1H_EDM_1_1": "GAMETES",
        "adult": "adult", "agaricus_lepiota": "agaricus", "allhypo": "allhypo"}


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def lab(r):
    return f"{DLAB[r.dataset]} / {MLAB[r.model]}"


def fig_delta_augrc(res):
    d = pd.read_csv(OUT / "DELTAS.csv").sort_values(["dataset", "model"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = np.arange(len(d))[::-1]
    for i, r in d.iterrows():
        sig = r.delta_augrc_ci_low > 0 or r.delta_augrc_ci_high < 0
        col = AQUA if (sig and r.delta_augrc > 0) else (ORANGE if sig else MUTE)
        ax.plot([r.delta_augrc_ci_low, r.delta_augrc_ci_high], [y[i], y[i]], color=col,
                lw=2.6, solid_capstyle="round")
        ax.plot([r.delta_augrc], [y[i]], "o", color=col, ms=5.5)
        if r.holm_rejected:
            ax.text(r.delta_augrc_ci_high + 0.0008, y[i], "Holm ✓", va="center",
                    fontsize=7.5, color=col)
    ax.axvline(0, color=INK, lw=1.0)
    a = res["aggregation"]
    ax.axvline(a["MEDIAN_DELTA_AUGRC_ALL"], color=BLUE, ls="--", lw=1.1)
    ax.text(a["MEDIAN_DELTA_AUGRC_ALL"], -1.35,
            f"médiane {a['MEDIAN_DELTA_AUGRC_ALL']:+.5f}", fontsize=8, color=BLUE,
            ha="center")
    ax.set_yticks(y)
    ax.set_yticklabels([lab(r) for r in d.itertuples()], fontsize=8.5)
    ax.set_ylim(-1.9, len(d) - 0.4)
    ax.set_xlabel("Δ AUGRC = AUGRC(STANDARD_META) − AUGRC(ISO_META), "
                  "IC 95 % bootstrap apparié, 10 000 tirages")
    ax.set_title("Gain de triage apporté par ISO — positif = ISO améliore\n"
                 f"{a['n_positive_augrc']}/12 cellules positives, "
                 f"{a['n_ci_contains_zero']}/12 avec IC contenant 0")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_delta_augrc.png", bbox_inches="tight")
    plt.close(fig)


def fig_iso_auroc(res):
    d = pd.read_csv(OUT / "DELTAS.csv").sort_values(["dataset", "model"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    x = np.arange(len(d))
    for i, r in d.iterrows():
        ok = r.auroc_iso_ci_low > 0.50
        col = AQUA if ok else MUTE
        ax.plot([x[i], x[i]], [r.auroc_iso_ci_low, r.auroc_iso_pred_for_error * 2
                               - r.auroc_iso_ci_low], color=col, lw=2.2)
        ax.plot([x[i]], [r.auroc_iso_pred_for_error], "o", color=col, ms=6)
    ax.axhline(0.50, color=INK, lw=1.0)
    ax.axhline(0.55, color=BLUE, ls="--", lw=1.0)
    ax.text(-0.4, 0.556, "seuil gelé 0,55", fontsize=8, color=BLUE)
    ax.set_xticks(x)
    ax.set_xticklabels([lab(r).replace(" / ", "\n") for r in d.itertuples()], fontsize=7.5)
    ax.set_ylabel("AUROC de ISO_PRED pour prédire ERROR (TEST)")
    g = res["gates"]["GATE1_ERROR_RISK_REPLICATED"]
    ax.set_title("GATE 1 — la propriété Phase 21 se réplique sur 2 jeux sur 4\n"
                 f"médiane {g['median_auroc_iso']:.3f} ≥ 0,55, mais seulement "
                 f"{g['frac_ci_above_half']*100:.0f} % des cellules ont un IC > 0,50 "
                 "(⅔ exigés)")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_iso_auroc.png", bbox_inches="tight")
    plt.close(fig)


def fig_operational():
    d = pd.read_csv(OUT / "DELTAS.csv").sort_values(["dataset", "model"]).reset_index(drop=True)
    o = pd.read_csv(OUT / "OPERATING_POINT.csv")
    oo = o[o.score.isin(["STANDARD_META", "ISO_META"])]
    piv = oo.pivot_table(index=["dataset", "model"], columns="score",
                         values="error_capture_test")
    dep = (piv["ISO_META"] - piv["STANDARD_META"])
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    x = np.arange(len(d))
    w = 0.38
    rank = d.delta_error_capture_10.to_numpy()
    depv = np.array([dep.loc[(r.dataset, r.model)] for r in d.itertuples()])
    ax.bar(x - w / 2, rank, width=w, color=BLUE, label="classement TEST (Δ EC@10)")
    ax.bar(x + w / 2, depv, width=w, color=ORANGE,
           label="déploiement à seuil gelé sur CALIB")
    ax.axhline(0, color=INK, lw=1.0)
    ax.axhline(0.05, color=AQUA, ls="--", lw=1.2)
    ax.text(len(d) - 0.6, 0.05 - 0.008, "seuil gelé du gate 5 : +0,05",
            fontsize=8.5, color=AQUA, ha="right", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels([lab(r).replace(" / ", "\n") for r in d.itertuples()], fontsize=7.5)
    ax.set_ylabel("Δ ERROR_CAPTURE à 10 % de budget de revue")
    ax.legend(fontsize=8.5, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    ax.set_title("GATE 5 — le gain opérationnel est douze fois trop petit, et il "
                 "change de signe\n"
                 f"médiane par classement {np.median(rank):+.4f} ; "
                 f"médiane au seuil de déploiement gelé {np.median(depv):+.4f}")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_operational.png", bbox_inches="tight")
    plt.close(fig)


def fig_relation():
    d = pd.read_csv(OUT / "DELTAS.csv")
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    cols = {"GAMETES_Epistasis_2_Way_20atts_0.1H_EDM_1_1": ORANGE, "adult": BLUE,
            "agaricus_lepiota": MUTE, "allhypo": AQUA}
    for ds, g in d.groupby("dataset"):
        ax.scatter(g.auroc_iso_pred_for_error, g.delta_error_capture_10, s=70,
                   color=cols[ds], label=DLAB[ds], edgecolor="none", alpha=0.9)
    ax.axhline(0, color=INK, lw=1.0)
    ax.axvline(0.50, color=MUTE, ls=":", lw=1.0)
    ax.axhline(0.05, color=AQUA, ls="--", lw=1.0)
    ax.text(0.755, 0.052, "+0,05 exigé", fontsize=8, color=AQUA, ha="right")
    ax.text(0.505, ax.get_ylim()[0] * 0.85, "hasard", fontsize=8, color=MUTE)
    ax.set_xlabel("AUROC de ISO_PRED pour ERROR — capacité propre d'ISO")
    ax.set_ylabel("Δ ERROR_CAPTURE@10 apporté par ISO")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.set_title("Le motif central : là où ISO a du signal il n'apporte rien,\n"
                 "et là où il apporte quelque chose il n'a pas de signal")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_relation.png", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.load(open(OUT / "PHASE23_RT_RESULTS.json"))
    fig_delta_augrc(res)
    fig_iso_auroc(res)
    fig_operational()
    fig_relation()
    print("figures ->", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
