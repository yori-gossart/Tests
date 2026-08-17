"""PHASE 22-BR -- figures. All annotations computed from the result files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "phase22_br"
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
WEAK = 0.70
DMIN = 0.020


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_regime():
    c = pd.read_csv(OUT / "CELLS_MAIN.csv").sort_values(["dataset", "model"])
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    x = np.arange(len(c))
    cols = [ORANGE if w else MUTE for w in c.confidence_weak]
    ax.bar(x, c.auroc_calib_prob_best, color=cols, width=0.64)
    for i, r in enumerate(c.itertuples()):
        ax.text(i, r.auroc_calib_prob_best + 0.008, f"{r.auroc_calib_prob_best:.3f}",
                ha="center", fontsize=7.5)
    ax.axhline(WEAK, color=BLUE, ls="--", lw=1.2)
    ax.text(-0.45, WEAK + 0.012, "seuil gelé 0,70", fontsize=8.5, color=BLUE)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r.dataset}\n{MLAB[r.model]}" for r in c.itertuples()],
                       fontsize=7.5)
    ax.set_ylabel("AUROC sur CALIBRATION de PROB_BEST → ERROR")
    ax.set_ylim(0.55, 1.0)
    nw = int(c.confidence_weak.sum())
    nds = c[c.confidence_weak].dataset.nunique()
    ax.set_title("Régime déterminé sur CALIBRATION seule, avant toute ouverture du TEST\n"
                 f"{nw} cellules CONFIDENCE_WEAK (orange), dans {nds} jeu"
                 f"{'x' if nds > 1 else ''} sur 3 — le critère gelé en exige 3")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_regime.png", bbox_inches="tight")
    plt.close(fig)


def fig_confirmatory(res):
    d = pd.read_csv(OUT / "DELTAS_WEAK_CELLS.csv").sort_values(["dataset", "model"])
    cr = res["criteria"]
    fig, ax = plt.subplots(figsize=(8.4, 3.5))
    y = np.arange(len(d) + 1)[::-1]
    for i, r in enumerate(d.itertuples()):
        col = AQUA if r.holm_confirmed_gain else MUTE
        ax.plot([r.ci_low, r.ci_high], [y[i], y[i]], color=col, lw=2.8,
                solid_capstyle="round")
        ax.plot([r.delta_auroc], [y[i]], "o", color=col, ms=6)
        ax.text(r.ci_high + 0.002, y[i], f"p={r.p_raw:.3f}"
                + (" Holm ✓" if r.holm_rejected else " Holm ✗"),
                va="center", fontsize=7.5, color=col)
    lo, hi = cr["4_stratified_ci"]
    sm = cr["3_global_median_delta_auroc"]
    ax.plot([lo, hi], [y[-1], y[-1]], color=ORANGE, lw=3.2, solid_capstyle="round")
    ax.plot([sm], [y[-1]], "D", color=ORANGE, ms=7)
    ax.axvline(0, color=INK, lw=1.0)
    ax.axvline(DMIN, color=BLUE, ls="--", lw=1.0)
    ax.text(DMIN + 0.001, y[-1] - 0.45, "seuil gelé +0,020", fontsize=8, color=BLUE)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.dataset} / {MLAB[r.model]}" for r in d.itertuples()]
                       + ["estimateur stratifié"], fontsize=8.5)
    ax.set_ylim(-0.9, len(d) + 0.5)
    ax.set_xlabel("Δ AUROC = META_ISO − META_BASE, IC 95 % bootstrap apparié")
    ax.set_title("Test confirmatoire sur les cellules CONFIDENCE_WEAK\n"
                 f"médiane stratifiée {sm:+.4f}, IC [{lo:+.4f} ; {hi:+.4f}] — "
                 f"sous le seuil et l'IC contient 0")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_confirmatory.png", bbox_inches="tight")
    plt.close(fig)


def fig_shift():
    cs = pd.read_csv(OUT / "CELLS_SHIFT.csv").set_index("model")
    ds = pd.read_csv(OUT / "DELTAS_SHIFT.csv")
    sc = pd.read_csv(OUT / "SCORES_SHIFT.csv")
    p = sc.pivot_table(index="model", columns="score", values="auroc")
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.0))
    ax = axes[0]
    order = list(cs.index)
    xx = np.arange(len(order))
    cols = [ORANGE if cs.confidence_weak[m] else MUTE for m in order]
    ax.bar(xx, [cs.auroc_calib_prob_best[m] for m in order], color=cols, width=0.6)
    ax.axhline(WEAK, color=BLUE, ls="--", lw=1.2)
    ax.set_xticks(xx)
    ax.set_xticklabels([MLAB[m] for m in order], fontsize=8.5)
    ax.set_ylabel("AUROC CALIB de PROB_BEST → ERROR")
    ax.set_ylim(0.5, 1.0)
    ax.set_title("Régime sous dérive temporelle réelle\n(TRAIN batches 1-4, "
                 "CALIB 5-6, TEST 7-10)", fontsize=9.5)
    despine(ax)
    ax = axes[1]
    y = np.arange(len(ds))[::-1]
    for i, r in enumerate(ds.itertuples()):
        col = AQUA if r.delta_auroc > 0 else ORANGE
        ax.plot([r.ci_low, r.ci_high], [y[i], y[i]], color=col, lw=3.0,
                solid_capstyle="round")
        ax.plot([r.delta_auroc], [y[i]], "o", color=col, ms=6.5)
        ax.text(r.delta_auroc, y[i] + 0.22, f"{r.delta_auroc:+.3f}", ha="center",
                fontsize=8.5, color=col)
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels([MLAB[r.model] for r in ds.itertuples()], fontsize=8.5)
    ax.set_ylim(-0.6, len(ds) - 0.3)
    ax.set_xlabel("Δ AUROC, IC 95 %")
    ax.set_title("Les deux cellules faibles sont de signes opposés,\n"
                 "toutes deux significatives — aucun appui", fontsize=9.5)
    despine(ax)
    fig.suptitle("Analyse NATURAL_TEMPORAL_SHIFT — rapportée séparément, "
                 "hors des critères du §9", fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_natural_shift.png", bbox_inches="tight")
    plt.close(fig)


def fig_relation():
    c = pd.read_csv(OUT / "CELLS_MAIN.csv")
    sc = pd.read_csv(OUT / "SCORES_MAIN.csv")
    p = sc.pivot_table(index=["dataset", "model"], columns="score", values="auroc")
    cs = pd.read_csv(OUT / "CELLS_SHIFT.csv")
    ss = pd.read_csv(OUT / "SCORES_SHIFT.csv")
    ps = ss.pivot_table(index=["dataset", "model"], columns="score", values="auroc")
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    for df, pv, mk, nm in ((c, p, "o", "analyse principale"),
                           (cs, ps, "^", "dérive temporelle")):
        for r in df.itertuples():
            k = (r.dataset, r.model)
            dl = pv.loc[k, "META_ISO"] - pv.loc[k, "META_BASE"]
            col = ORANGE if r.confidence_weak else MUTE
            ax.plot([r.auroc_calib_prob_best], [dl], mk, color=col, ms=7,
                    mfc=col if r.confidence_weak else "none", mew=1.4)
    ax.axhline(0, color=INK, lw=1.0)
    ax.axvline(WEAK, color=BLUE, ls="--", lw=1.2)
    ax.axhline(DMIN, color=AQUA, ls=":", lw=1.0)
    ax.text(WEAK + 0.005, ax.get_ylim()[1] * 0.92, "seuil de régime 0,70",
            fontsize=8.5, color=BLUE)
    ax.text(0.99, DMIN + 0.004, "+0,020", fontsize=8, color=AQUA, ha="right")
    ax.set_xlabel("AUROC CALIB de PROB_BEST → ERROR  (faible ← → fort)")
    ax.set_ylabel("Δ AUROC sur TEST = META_ISO − META_BASE")
    h = [plt.Line2D([], [], marker="o", ls="", color=ORANGE, ms=7,
                    label="CONFIDENCE_WEAK"),
         plt.Line2D([], [], marker="o", ls="", color=MUTE, mfc="none", ms=7,
                    label="confiant (descriptif)"),
         plt.Line2D([], [], marker="^", ls="", color=MUTE, mfc="none", ms=7,
                    label="dérive temporelle")]
    ax.legend(handles=h, fontsize=8, loc="upper right")
    ax.set_title("La relation prédite par H22 n'est pas là : les cellules faibles\n"
                 "ne gagnent pas, et les cellules confiantes perdent souvent")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_relation.png", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.load(open(OUT / "PHASE22_BR_RESULTS.json"))
    fig_regime()
    fig_confirmatory(res)
    fig_shift()
    fig_relation()
    print("figures ->", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
