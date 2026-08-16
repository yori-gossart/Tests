"""PHASE 15 figures. Palette: validated categorical slots 1-3 on the light surface."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
P15 = REPO / "phase15_tep"
FIG = P15 / "figures"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#b8b7b0", "#e6e5e0"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.edgecolor": GRID, "grid.color": GRID,
                     "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold"})

NICE = {"rf_entropy": "Entropie RF (aval)", "rf_margin": "Marge RF (aval)",
        "iso_margin_ratio": "Ratio de marge (isolabilité)",
        "iso_d_nearest": "Distance au concurrent",
        "mahalanobis": "Mahalanobis / T²", "l2_channels": "Norme L2 canaux",
        "fo_d_S": "FO  d_S", "rms": "RMS", "mean_abs": "SNR moyen", "kl_gauss": "KL gaussienne"}


def recessive(ax, xgrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x" if xgrid else "y", lw=0.8, alpha=0.9); ax.set_axisbelow(True)


def fig1(v):
    a = pd.DataFrame(v["A_visibility_family"])
    a = a[a.split == "val"].sort_values("auroc")
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    colors = [S1 if m == "fo_d_S" else (MUTED if m.startswith("rf_") else S3)
              for m in a.metric]
    ax.barh(range(len(a)), a.auroc, color=colors, height=0.68, zorder=2)
    for i, (_, r) in enumerate(a.iterrows()):
        ax.text(r.auroc + 0.004, i, f"{r.auroc:.3f}", va="center", fontsize=9,
                color=INK if r.metric == "fo_d_S" else INK2,
                fontweight="bold" if r.metric == "fo_d_S" else "normal")
    ax.set_yticks(range(len(a)), [NICE[m] for m in a.metric])
    for t, m in zip(ax.get_yticklabels(), a.metric):
        t.set_fontweight("bold" if m == "fo_d_S" else "normal")
        t.set_color(INK if m == "fo_d_S" else INK2)
    ax.set_xlim(0.5, 1.0); ax.set_xlabel("AUROC pour l'échec (VALID, poolé)")
    ax.set_title("FO se classe 7e sur 10\ntrois métriques standards de readiness le dépassent",
                 loc="left")
    recessive(ax, xgrid=True); fig.tight_layout()
    fig.savefig(FIG / "fig1_metric_ranking.png", dpi=170); plt.close(fig)


def fig2(v):
    o = pd.DataFrame(v["C_bstar_operational"])
    o = o[o.target == "val_failure_rate"].copy()
    o["abs_rho"] = o.spearman.abs()
    o = o.sort_values("abs_rho")
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    colors = [S1 if s == "b_star_equiv" else S3 for s in o.statistic]
    ax.barh(range(len(o)), o.abs_rho, color=colors, height=0.66, zorder=2)
    for i, (_, r) in enumerate(o.iterrows()):
        ax.text(r.abs_rho + 0.008, i, f"{r.abs_rho:.3f}", va="center", fontsize=9, color=INK2)
    lbl = {"b_star_equiv": "B*", "q05": "q05", "q10": "q10", "minimum": "minimum",
           "mean": "moyenne", "cvar05": "CVaR 5 %", "cvar10": "CVaR 10 %",
           "design_size": "taille du design"}
    ax.set_yticks(range(len(o)), [lbl[s] for s in o.statistic])
    for t, s in zip(ax.get_yticklabels(), o.statistic):
        t.set_fontweight("bold" if s == "b_star_equiv" else "normal")
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("|ρ de Spearman| entre la statistique et le taux d'échec du design")
    ax.set_title("Sur le MÊME support gelé, toute statistique de queue ordinaire\nclasse les designs mieux que B*",
                 loc="left")
    recessive(ax, xgrid=True); fig.tight_layout()
    fig.savefig(FIG / "fig2_bstar_vs_tails.png", dpi=170); plt.close(fig)


def fig3(v):
    m = pd.DataFrame(v["D_model_ladder"]).sort_values("auroc")
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    hi = {"M9_STANDARD_FULL": S3, "M10_STANDARD_PLUS_FO_BSTAR": S1}
    colors = [hi.get(n, MUTED) for n in m.model]
    ax.barh(range(len(m)), m.auroc, color=colors, height=0.68, zorder=2)
    for i, (_, r) in enumerate(m.iterrows()):
        ax.text(r.auroc + 0.004, i, f"{r.auroc:.4f}", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(m)), [n.replace("_", " ") for n in m.model], fontsize=8.5)
    ax.set_xlim(0.55, 0.98); ax.set_xlabel("AUROC (VALID)")
    ax.set_title("M10 (standards + FO + B*) dépasse M9 (standards seuls) de 0,0014",
                 loc="left")
    recessive(ax, xgrid=True); fig.tight_layout()
    fig.savefig(FIG / "fig3_model_ladder.png", dpi=170); plt.close(fig)


def fig4(v):
    r = pd.DataFrame(v["E_regimes"])
    lbl = {"1_lowvis_lowiso": "vis. faible\niso. faible", "2_lowvis_highiso": "vis. faible\niso. forte",
           "3_highvis_lowiso": "vis. forte\niso. faible", "4_highvis_highiso": "vis. forte\niso. forte"}
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(range(len(r)), r.failure_rate, color=[S2, S3, S3, S3], width=0.62, zorder=2)
    for i, (_, x) in enumerate(r.iterrows()):
        ax.text(i, x.failure_rate + 0.012, f"{x.failure_rate:.3f}\nn={int(x.n)}",
                ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(r)), [lbl[s] for s in r.regime], fontsize=9)
    ax.set_ylim(0, 0.62); ax.set_ylabel("Taux d'échec (VALID)")
    ax.set_title("Les deux axes comptent — mais l'axe visibilité peut être\nn'importe quelle norme standard",
                 loc="left")
    recessive(ax); fig.tight_layout()
    fig.savefig(FIG / "fig4_regimes.png", dpi=170); plt.close(fig)


def fig5(v):
    b = pd.DataFrame(v["B_per_fault"]); b = b[b.split == "val"].dropna(subset=["auroc_fo_d_S"])
    b = b.sort_values("auroc_fo_d_S")
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    x = np.arange(len(b))
    ax.bar(x - 0.2, b.auroc_fo_d_S, width=0.38, color=S1, label="FO  d_S", zorder=2)
    ax.bar(x + 0.2, b.auroc_iso_margin_ratio, width=0.38, color=S3,
           label="Ratio de marge (isolabilité)", zorder=2)
    ax.axhline(0.5, color=INK2, lw=1, ls=(0, (4, 3)))
    ax.set_xticks(x, [f"IDV{int(f)}" for f in b.fault], fontsize=8.5, rotation=45)
    ax.set_ylabel("AUROC au sein de la panne"); ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK2)
    ax.set_title("Là où FO échoue (IDV 13, 21, 9, 8), l'isolabilité standard prend le relais",
                 loc="left")
    recessive(ax); fig.tight_layout()
    fig.savefig(FIG / "fig5_fo_vs_isolability.png", dpi=170); plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    v = json.loads((P15 / "PHASE15_TABLES.json").read_text())
    fig1(v); fig2(v); fig3(v); fig4(v); fig5(v)
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
