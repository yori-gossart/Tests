"""PHASE 21-IR -- figures. All annotations computed from the result files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "phase21_ir"
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

MLAB = {"M1_logreg": "LogReg", "M2_rbf_svm": "RBF-SVM",
        "M3_random_forest": "RF", "M4_hist_gradient_boosting": "GBM"}
SCORES = ["B5_mahalanobis", "B4_knn_dist", "B6_conformal_aps", "ISO_RAW", "ISO_FIT",
          "B2_entropy", "B3_margin", "B1_max_prob", "COMBO_best_plus_iso",
          "ISO_FROZEN_ORACLE"]
SLAB = {"B1_max_prob": "B1 max prob", "B2_entropy": "B2 entropie",
        "B3_margin": "B3 marge 1-2", "B4_knn_dist": "B4 kNN", "B5_mahalanobis": "B5 Mahalanobis",
        "B6_conformal_aps": "B6 conformal", "ISO_RAW": "ISO_RAW", "ISO_FIT": "ISO_FIT",
        "COMBO_best_plus_iso": "COMBO", "ISO_FROZEN_ORACLE": "ISO_FROZEN (oracle)"}


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_cells(res):
    sm = pd.read_csv(OUT / "CELL_SUMMARY.csv")
    sc = pd.read_csv(OUT / "CELL_SCORES.csv")
    p = sc.pivot_table(index=["dataset", "model"], columns="score", values="auroc")
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    lab, iso, lo, hi, best = [], [], [], [], []
    for r in sm.itertuples():
        lab.append(f"{r.dataset}\n{MLAB[r.model]}")
        iso.append(r.iso_fit_auroc)
        lo.append(r.iso_fit_ci_low)
        hi.append(r.iso_fit_ci_high)
        best.append(p.loc[(r.dataset, r.model), r.best_baseline_on_calib])
    x = np.arange(len(lab))
    ax.errorbar(x, iso, yerr=[np.array(iso) - lo, np.array(hi) - np.array(iso)],
                fmt="o", color=ORANGE, ms=6, lw=1.6, capsize=3, label="ISO_FIT (IC 95 %)")
    ax.plot(x, best, "s", color=BLUE, ms=6, label="meilleure baseline (choisie sur CALIB)")
    ax.axhline(0.5, color=MUTE, ls=":", lw=0.9)
    ax.text(len(lab) - 0.4, 0.508, "hasard", ha="right", fontsize=8, color=MUTE)
    ax.axhline(0.70, color=AQUA, ls="--", lw=1.0)
    ax.text(-0.4, 0.712, "seuil gelé 0,70", fontsize=8, color=AQUA)
    ax.set_xticks(x)
    ax.set_xticklabels(lab, fontsize=7.5)
    ax.set_ylabel("AUROC de prédiction d'ERREUR sur TEST")
    ax.set_ylim(0.42, 1.0)
    ax.legend(fontsize=8, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.30))
    c = res["criteria"]
    nb = int(sum(np.array(iso) < np.array(best)))
    ax.set_title("12 cellules jeu × modèle — ISO_PRED généralise au-dessus du hasard "
                 f"partout,\net reste sous la meilleure baseline dans {nb} cas sur "
                 f"{len(iso)} (médiane ISO_FIT {c['c1_median_auroc']:.3f})")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_cells.png", bbox_inches="tight")
    plt.close(fig)


def fig_contrasts():
    c = pd.read_csv(OUT / "CELL_CONTRASTS.csv").drop_duplicates(
        ["dataset", "model", "contrast"])
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.8), sharey=True)
    for ax, pref, ttl in ((axes[0], "ISO_FIT - ", "ISO_FIT − meilleure baseline"),
                          (axes[1], "COMBO", "COMBO (baseline + isolabilité) − baseline")):
        d = c[c.contrast.str.startswith(pref)].drop_duplicates(["dataset", "model"])
        d = d.sort_values(["dataset", "model"]).reset_index(drop=True)
        y = np.arange(len(d))[::-1]
        for i, r in d.iterrows():
            col = AQUA if (r.delta_auroc >= 0.02 and r.excludes_zero) else (
                ORANGE if (r.delta_auroc < 0 and r.excludes_zero) else MUTE)
            ax.plot([r.ci_low, r.ci_high], [y[i], y[i]], color=col, lw=2.6,
                    solid_capstyle="round")
            ax.plot([r.delta_auroc], [y[i]], "o", color=col, ms=5.5)
        ax.axvline(0, color=INK, lw=1.0)
        ax.axvline(0.02, color=AQUA, lw=0.9, ls="--")
        ax.set_yticks(y)
        ax.set_yticklabels([f"{r.dataset} / {MLAB[r.model]}" for r in d.itertuples()],
                           fontsize=8)
        ng = int(((d.delta_auroc >= 0.02) & d.excludes_zero).sum())
        nl = int(((d.delta_auroc < 0) & d.excludes_zero).sum())
        ax.set_title(f"{ttl}\nmédiane {d.delta_auroc.median():+.3f} — "
                     f"{ng}/{len(d)} gains confirmés, {nl}/{len(d)} pertes signif.",
                     fontsize=9.0, pad=8)
        ax.set_xlabel("Δ AUROC, IC 95 % bootstrap apparié")
        despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_contrasts.png", bbox_inches="tight")
    plt.close(fig)


def fig_scores():
    sc = pd.read_csv(OUT / "CELL_SCORES.csv")
    p = sc.pivot_table(index=["dataset", "model"], columns="score", values="auroc")
    med = p[SCORES].median()
    fig, ax = plt.subplots(figsize=(8.8, 4.0))
    cols = []
    for s in SCORES:
        cols.append(ORANGE if s.startswith("ISO_F") and "FROZEN" not in s else
                    (AQUA if s == "COMBO_best_plus_iso" else
                     (MUTE if s == "ISO_FROZEN_ORACLE" else BLUE)))
    ax.bar(range(len(SCORES)), med.values, color=cols, width=0.66)
    for i, s in enumerate(SCORES):
        ax.text(i, med[s] + 0.008, f"{med[s]:.3f}", ha="center", fontsize=8)
    for i, s in enumerate(SCORES):
        ax.scatter(np.full(len(p), i) + np.linspace(-.17, .17, len(p)), p[s],
                   s=13, color=INK, alpha=0.35, zorder=3, edgecolor="none")
    ax.axhline(0.5, color=MUTE, ls=":", lw=0.9)
    ax.set_xticks(range(len(SCORES)))
    ax.set_xticklabels([SLAB[s] for s in SCORES], fontsize=7.5, rotation=30, ha="right")
    ax.set_ylabel("AUROC médiane sur les 12 cellules")
    ax.set_ylim(0.40, 1.0)
    ax.set_title("ISO_PRED bat nettement les baselines de distance (Mahalanobis, kNN)\n"
                 "et reste sous les baselines de probabilité (max prob, entropie, marge)")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_scores.png", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.load(open(OUT / "PHASE21_IR_RESULTS.json"))
    fig_cells(res)
    fig_contrasts()
    fig_scores()
    print("figures ->", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
