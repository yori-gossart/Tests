"""PHASE TEP -- figures for the frozen-protocol report.

Palette: validated categorical slots 1-3 (blue / orange / aqua) on the light
surface, all-pairs clean. Aqua carries a contrast WARN against the surface, so
every series that uses it also carries a direct label (the relief rule).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "phase14_tep" / "results"
FIG = REPO / "phase14_tep" / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#b8b7b0"
GRID = "#e6e5e0"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "grid.color": GRID, "grid.linewidth": 0.8,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
})

LABEL = {"fo_d_S": "FO  d_S", "entropy": "Entropie (RF)",
         "top1_top2_margin": "Marge top1–top2 (RF)", "snr_mean": "SNR moyen",
         "count_above_3sigma": "Canaux > 3σ", "smallest_singular_value": "Plus petite v. sing.",
         "design_size": "Taille du design (contrôle)"}


def recessive(ax, xgrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x" if xgrid else "y", lw=0.8, alpha=0.9)
    ax.set_axisbelow(True)


def fig1_forest(v):
    d = pd.DataFrame(v["primary_auroc"])
    d = d[d.split == "test"].sort_values("mean_auroc")
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = np.arange(len(d))
    for i, (_, r) in enumerate(d.iterrows()):
        is_fo = r.metric == "fo_d_S"
        c = S1 if is_fo else MUTED
        ax.plot([r.ci_lo, r.ci_hi], [i, i], lw=2, color=c, solid_capstyle="round")
        ax.plot(r.mean_auroc, i, "o", ms=9, color=c, mec=SURFACE, mew=2, zorder=3)
        ax.text(r.ci_hi + 0.006, i, f"{r.mean_auroc:.3f}", va="center", fontsize=9,
                color=INK if is_fo else INK2,
                fontweight="bold" if is_fo else "normal")
    ax.axvline(0.5, color=INK2, lw=1, ls=(0, (4, 3)))
    ax.text(0.503, -0.42, "hasard", fontsize=8.5, color=INK2, va="center")
    ax.set_yticks(y, [LABEL[m] for m in d.metric],
                  fontweight=["bold" if m == "fo_d_S" else "normal" for m in d.metric][0])
    for t, m in zip(ax.get_yticklabels(), d.metric):
        t.set_fontweight("bold" if m == "fo_d_S" else "normal")
        t.set_color(INK if m == "fo_d_S" else INK2)
    ax.set_xlim(0.45, 1.03)
    ax.set_xlabel("AUROC pour l'échec de reconstruction\n(moyenne par design, IC 95 % bootstrap sur les réalisations)")
    ax.set_title("FO se classe 3e sur 7 — TEST, 315 réalisations", loc="left")
    recessive(ax, xgrid=True)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_auroc_forest.png", dpi=170)
    plt.close(fig)


def fig2_deciles(v):
    d = pd.DataFrame(v["deciles"])
    d = d[(d.split == "test") & (d.metric == "fo_d_S")].sort_values("decile")
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    ax.bar(d.decile, d.failure_rate, width=0.68, color=S1, zorder=2)
    for _, r in d.iterrows():
        ax.text(r.decile, r.failure_rate + 0.018, f"{r.failure_rate:.2f}",
                ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(d.decile)
    ax.set_xlabel("Décile de FO d_S   (1 = le moins visible)")
    ax.set_ylabel("Taux d'échec de reconstruction")
    ax.set_ylim(0, 0.98)
    ax.set_title("Le taux d'échec chute de 0,86 à ~0,05 le long des déciles de FO")
    recessive(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_fo_deciles.png", dpi=170)
    plt.close(fig)


def fig3_by_size(v):
    d = pd.DataFrame(v["by_design_size"])
    d = d[d.split == "test"].sort_values("design_size")
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    series = [("auroc_top1_top2_margin", S2, "Marge top1–top2 (RF)"),
              ("auroc_fo_d_S", S1, "FO  d_S"),
              ("auroc_snr_mean", S3, "SNR moyen")]
    for col, c, lab in series:
        ax.plot(d.design_size, d[col], "-o", lw=2, ms=7, color=c,
                mec=SURFACE, mew=1.6, label=lab, zorder=3)
        ax.text(d.design_size.iloc[-1] * 1.08, d[col].iloc[-1], lab,
                fontsize=9, color=c, va="center", fontweight="bold")
    ax.set_xscale("log")
    ax.set_xticks(d.design_size, [str(s) for s in d.design_size])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(2.6, 105)
    ax.set_ylim(0.75, 0.96)
    ax.set_xlabel("Nombre de canaux dans le design")
    ax.set_ylabel("AUROC (moyenne des designs de cette taille)")
    ax.set_title("FO se dégrade quand l'instrumentation augmente ; la marge du RF non",
                 loc="left")
    recessive(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_auroc_by_design_size.png", dpi=170)
    plt.close(fig)


def fig4_bstar(v):
    b = pd.DataFrame(v["b_star_vs_dynamic"])
    g = b.groupby("noise_scale").agg(bs=("B_star_support", "median"),
                                     bd=("B_dynamic_support", "median")).reset_index()
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(g.noise_scale, g.bs, "-o", lw=2, ms=8, color=S1, mec=SURFACE, mew=1.6,
            label="B*  (support gelé)", zorder=3)
    ax.plot(g.noise_scale, g.bd, "-o", lw=2, ms=8, color=S2, mec=SURFACE, mew=1.6,
            label="B_dynamic  (support recalculé)", zorder=3)
    for _, r in g.iterrows():
        ax.text(r.noise_scale, r.bs + 14, f"{int(r.bs)}", ha="center", fontsize=9, color=S1)
        ax.text(r.noise_scale, r.bd - 30, f"{int(r.bd)}", ha="center", fontsize=9, color=S2)
    ax.set_xscale("log", base=2)
    ax.set_xticks(g.noise_scale, [f"×{s:g}" for s in g.noise_scale])
    ax.set_ylim(-40, 470)
    ax.set_xlabel("Niveau de bruit de mesure (XNS mis à l'échelle, données régénérées)")
    ax.set_ylabel("Taille du support E*  (scénarios)")
    ax.set_title("B* tient son dénominateur ; celui de B_dynamic s'effondre de 408 à 8")
    ax.legend(frameon=False, loc="center left", fontsize=9, labelcolor=INK2)
    recessive(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_bstar_vs_bdynamic.png", dpi=170)
    plt.close(fig)


def fig5_per_fault(v):
    d = pd.DataFrame(v["per_fault"])
    d = d[(d.split == "test") & d.auroc_fo_d_S.notna()].sort_values("auroc_fo_d_S")
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    colors = [MUTED if a < 0.6 else S1 for a in d.auroc_fo_d_S]
    ax.bar(range(len(d)), d.auroc_fo_d_S, width=0.7, color=colors, zorder=2)
    ax.axhline(0.5, color=INK2, lw=1, ls=(0, (4, 3)))
    ax.text(-0.45, 0.52, "hasard", fontsize=8.5, color=INK2, ha="left")
    for i, (_, r) in enumerate(d.iterrows()):
        if r.auroc_fo_d_S < 0.6:
            ax.text(i, r.auroc_fo_d_S + 0.02, f"{r.auroc_fo_d_S:.2f}",
                    ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(d)), [f"IDV{int(f)}" for f in d.fault], fontsize=8.5, rotation=45)
    ax.set_ylabel("AUROC de FO au sein de la panne")
    ax.set_ylim(0, 1.02)
    ax.set_title("FO tombe au hasard sur IDV 13, 8, 21 et 9\ndes pannes fortes mais confusables", loc="left")
    recessive(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig5_per_fault_auroc.png", dpi=170)
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    v = json.loads((RES / "VERDICT_TABLES.json").read_text())
    fig1_forest(v); fig2_deciles(v); fig3_by_size(v); fig4_bstar(v); fig5_per_fault(v)
    print("figures written:", sorted(p.name for p in FIG.glob("*.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
