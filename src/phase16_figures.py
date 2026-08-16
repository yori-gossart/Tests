"""PHASE 16 figures. Palette: validated categorical slots 1-3, light surface."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
P16 = REPO / "phase16_tep"
FIG = P16 / "figures"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#b8b7b0", "#e6e5e0"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.edgecolor": GRID, "grid.color": GRID,
                     "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold"})
THRESH = 0.02


def recessive(ax, xgrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x" if xgrid else "y", lw=0.8, alpha=0.9); ax.set_axisbelow(True)


def fig1_hypotheses(res):
    h = {k: v for k, v in res["hypotheses"].items() if "delta_auroc" in v}
    d = pd.DataFrame([{"h": k.split("_", 1)[0], "label": k.split("_", 1)[1].replace("_", " "),
                       **v} for k, v in h.items()]).sort_values("delta_auroc")
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    y = np.arange(len(d))
    for i, (_, r) in enumerate(d.iterrows()):
        c = S3 if r.verdict == "YES" else (S1 if r.verdict == "WEAK" else MUTED)
        ax.plot([r.ci_lo, r.ci_hi], [i, i], lw=2, color=c, solid_capstyle="round")
        ax.plot(r.delta_auroc, i, "o", ms=9, color=c, mec=SURFACE, mew=2, zorder=3)
        ax.text(max(r.ci_hi, THRESH) + 0.004, i, f"{r.delta_auroc:+.4f}  {r.verdict}",
                va="center", fontsize=9, color=INK2)
    ax.axvline(0, color=INK2, lw=1)
    ax.axvline(THRESH, color=S2, lw=1.6, ls=(0, (4, 3)))
    ax.text(THRESH, len(d) - 0.35, " seuil 0,02", fontsize=8.5, color=S2, va="center")
    ax.set_yticks(y, [f"{r.h}  {r.label}" for _, r in d.iterrows()], fontsize=9)
    ax.set_xlabel("Δ AUROC hors échantillon (IC 95 % apparié, bootstrap par graine)")
    ax.set_title("Hypothèses confirmatoires — aucune n'atteint le seuil de pertinence",
                 loc="left")
    recessive(ax, xgrid=True); fig.tight_layout()
    fig.savefig(FIG / "fig1_hypotheses.png", dpi=170); plt.close(fig)


def fig2_models(res):
    m = pd.DataFrame(res["model_comparison"]).sort_values("auroc")
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    hi = {"M9_STANDARD_FULL": S3, "M10_STANDARD_PLUS_FO_BSTAR": S1}
    ax.barh(range(len(m)), m.auroc, color=[hi.get(n, MUTED) for n in m.model],
            height=0.68, zorder=2)
    for i, (_, r) in enumerate(m.iterrows()):
        ax.text(r.auroc + 0.004, i, f"{r.auroc:.4f}", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(m)), [n.replace("_", " ") for n in m.model], fontsize=8.5)
    ax.set_xlim(0.5, 1.0); ax.set_xlabel("AUROC (Phase 16, cohorte nominale aveugle)")
    ax.set_title("M9 (standards seuls) contre M10 (standards + FO + B*)", loc="left")
    recessive(ax, xgrid=True); fig.tight_layout()
    fig.savefig(FIG / "fig2_models.png", dpi=170); plt.close(fig)


def fig3_loo(res):
    d = pd.DataFrame(res["leave_one_fault_out"]).sort_values("delta_auroc")
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    ax.bar(range(len(d)), d.delta_auroc, color=S1, width=0.7, zorder=2)
    ax.axhline(0, color=INK2, lw=1)
    ax.axhline(THRESH, color=S2, lw=1.6, ls=(0, (4, 3)))
    ax.text(len(d) - 0.5, THRESH * 1.06, "seuil 0,02", fontsize=8.5, color=S2, ha="right")
    ax.set_xticks(range(len(d)), [f"−IDV{int(f)}" for f in d.excluded_fault],
                  fontsize=8, rotation=45)
    ax.set_ylabel("Δ AUROC  M10 − M9")
    ax.set_title("Leave-one-fault-out sur H8 : le signe ne dépend d'aucune panne unique,\n"
                 "et le seuil n'est jamais atteint", loc="left")
    recessive(ax); fig.tight_layout()
    fig.savefig(FIG / "fig3_leave_one_fault_out.png", dpi=170); plt.close(fig)


def fig4_noise():
    n = pd.read_csv(P16 / "NOISE_ROBUSTNESS.csv")
    g = n.groupby("noise_scale").agg(bs=("B_star_support", "median"),
                                     bd=("B_dynamic_support", "median")).reset_index()
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(g.noise_scale, g.bs, "-o", lw=2, ms=8, color=S1, mec=SURFACE, mew=1.6,
            label="B*  (support gelé)", zorder=3)
    ax.plot(g.noise_scale, g.bd, "-o", lw=2, ms=8, color=S2, mec=SURFACE, mew=1.6,
            label="B_dynamic  (support recalculé)", zorder=3)
    for _, r in g.iterrows():
        ax.text(r.noise_scale, r.bs + 12, f"{int(r.bs)}", ha="center", fontsize=9, color=S1)
        ax.text(r.noise_scale, r.bd - 26, f"{int(r.bd)}", ha="center", fontsize=9, color=S2)
    ax.set_xscale("log", base=2)
    ax.set_xticks(g.noise_scale, [f"×{s:g}" for s in g.noise_scale])
    ax.set_xlabel("Niveau de bruit (XNS mis à l'échelle, données régénérées)")
    ax.set_ylabel("Taille du support (scénarios)")
    ax.set_title("H4 répliquée en aveugle : le support de B* tient, celui de B_dynamic non",
                 loc="left")
    ax.legend(frameon=False, loc="center left", fontsize=9, labelcolor=INK2)
    recessive(ax); fig.tight_layout()
    fig.savefig(FIG / "fig4_bstar_structural.png", dpi=170); plt.close(fig)


def fig5_per_fault():
    d = pd.read_csv(P16 / "PER_FAULT_RESULTS.csv").dropna(subset=["auroc_fo"])
    d = d.sort_values("auroc_fo")
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    x = np.arange(len(d))
    ax.bar(x - 0.2, d.auroc_fo, width=0.38, color=S1, label="FO  d_S", zorder=2)
    ax.bar(x + 0.2, d.auroc_iso, width=0.38, color=S3,
           label="Isolabilité standard (ratio de marge)", zorder=2)
    ax.axhline(0.5, color=INK2, lw=1, ls=(0, (4, 3)))
    ax.set_xticks(x, [f"IDV{int(f)}" for f in d.fault], fontsize=8.5, rotation=45)
    ax.set_ylabel("AUROC au sein de la panne"); ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK2)
    ax.set_title("Réplication aveugle : l'isolabilité standard couvre les pannes\n"
                 "où FO reste au niveau du hasard", loc="left")
    recessive(ax); fig.tight_layout()
    fig.savefig(FIG / "fig5_per_fault.png", dpi=170); plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((P16 / "CONFIRMATORY_RESULTS.json").read_text())
    fig1_hypotheses(res); fig2_models(res); fig3_loo(res); fig4_noise(); fig5_per_fault()
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
