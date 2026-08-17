"""PHASE 20-DR -- figures. All annotations are computed from the result files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "phase20_dr"
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


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_ladder(res):
    te = pd.DataFrame(res["ladder"]["test"]).set_index("model")
    con = {c["contrast"]: c for c in res["ladder"]["contrasts"]}
    order = ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]
    lab = {"R0": "R0\nn capteurs", "R1": "R1\nVisibilité", "R2": "R2\nIsolabilité",
           "R3": "R3\nRobustesse", "R4": "R4\nVis+Iso", "R5": "R5\nVis+Rob",
           "R6": "R6\nIso+Rob", "R7": "R7\nles trois"}
    cols = [MUTE, BLUE, ORANGE, AQUA, MUTE, MUTE, MUTE, INK]
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    v = [te.auroc[m] for m in order]
    ax.bar(range(8), v, color=cols, width=0.66)
    for i, m in enumerate(order):
        ax.text(i, v[i] + 0.006, f"{v[i]:.3f}", ha="center", fontsize=8.5, color=INK)
    ax.axhline(0.5, color=MUTE, lw=0.9, ls=":")
    ax.text(7.45, 0.505, "hasard", ha="right", fontsize=8, color=MUTE)
    ax.set_xticks(range(8))
    ax.set_xticklabels([lab[m] for m in order], fontsize=8)
    ax.set_ylabel("AUROC sur TEST — prédiction de l'échec du diagnostic")
    ax.set_ylim(0.45, max(v) + 0.06)
    d = con["R7-R0"]
    ax.set_title("Échelle de readiness R0–R7, TEST jamais ouvert avant cet endpoint\n"
                 f"R7 − R0 = {d['delta_auroc']:+.3f} "
                 f"[{d['ci_low']:+.3f}; {d['ci_high']:+.3f}] — verdict {d['verdict']}")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_readiness_ladder.png", bbox_inches="tight")
    plt.close(fig)


def fig_contrasts(res):
    con = pd.DataFrame(res["ladder"]["contrasts"])
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    y = np.arange(len(con))[::-1]
    for i, r in con.iterrows():
        c = AQUA if r.verdict == "YES" else (BLUE if r.verdict == "WEAK" else MUTE)
        ax.plot([r.ci_low, r.ci_high], [y[i], y[i]], color=c, lw=2.6,
                solid_capstyle="round")
        ax.plot([r.delta_auroc], [y[i]], "o", color=c, ms=6)
        ax.text(r.ci_high + 0.004, y[i], r.verdict, va="center", fontsize=8, color=c)
    ax.axvline(0, color=INK, lw=1.0)
    for s in (-0.02, 0.02):
        ax.axvline(s, color=ORANGE, lw=0.9, ls="--")
    ax.text(0.02, len(con) - 0.4, "seuil de pertinence pratique ±0,02",
            fontsize=8, color=ORANGE, ha="left")
    ax.set_yticks(y)
    ax.set_yticklabels(con.contrast, fontsize=8.5)
    ax.set_xlabel("Δ AUROC sur TEST — IC 95 % bootstrap apparié, 2 000 tirages "
                  "au niveau configuration")
    ax.set_title("Contrastes pré-enregistrés de l'échelle de readiness")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_ladder_contrasts.png", bbox_inches="tight")
    plt.close(fig)


def fig_degradation():
    d = pd.read_csv(OUT / "CLASSIFIER_DEGRADATION_TEST.csv")
    d = d[d.family != "restore"]
    fams = ["baseline", "drop_one", "drop_group", "noise", "downsample", "bias", "drift"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0), sharey=True)
    for ax, tgt, col in zip(axes, ("valve", "pump"), (BLUE, ORANGE)):
        s = d[d.target == tgt]
        pos, labs = [], []
        for k, f in enumerate(fams):
            v = s[s.family == f].balanced_accuracy.to_numpy()
            ax.scatter(np.full(len(v), k) + np.linspace(-.16, .16, len(v)), v,
                       s=22, color=col, alpha=0.8, edgecolor="none")
            pos.append(k)
            labs.append(f"{f}\n(n={len(v)})")
        b = s[s.condition == "baseline"].balanced_accuracy.iloc[0]
        ax.axhline(b, color=MUTE, lw=1.0, ls="--")
        ax.text(6.4, b + 0.006, f"référence {b:.3f}", ha="right", fontsize=8, color=MUTE)
        ax.set_xticks(pos)
        ax.set_xticklabels(labs, fontsize=7.5)
        ax.set_title(f"cible : {tgt}")
        despine(ax)
    axes[0].set_ylabel("exactitude équilibrée sur TEST")
    fig.suptitle("Dégradation du classifieur gelé sous les 38 conditions "
                 "pré-enregistrées", fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_classifier_degradation.png", bbox_inches="tight")
    plt.close(fig)


def fig_attribution(res):
    cont = pd.read_csv(OUT / "ATTRIBUTION_CONTINGENCY.csv", index_col=0)
    M = cont.to_numpy(dtype=float)
    P = M / np.maximum(M.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    im = ax.imshow(P, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(P.shape[0]):
        for j in range(P.shape[1]):
            ax.text(j, i, f"{P[i, j]:.2f}\n{int(M[i, j])}", ha="center", va="center",
                    fontsize=7.5, color="white" if P[i, j] > 0.55 else INK)
    ax.set_xticks(range(P.shape[1]))
    ax.set_xticklabels([c.replace("_", "\n") for c in cont.columns], fontsize=7.5)
    ax.set_yticks(range(P.shape[0]))
    ax.set_yticklabels([c.replace("|", " ou\n").replace("_", " ")
                        for c in cont.index], fontsize=7.5)
    ax.set_xlabel("cause attribuée par l'architecture")
    ax.set_ylabel("cause attendue,\ndéclarée avant résultats")
    a = res["attribution"]
    ax.set_title(f"Attribution de la cause d'échec — exactitude stricte "
                 f"{a['strict_accuracy']:.3f} contre hasard {a['chance_accuracy']:.3f}, "
                 f"NMI {a['nmi']:.3f}, n={a['n_scored']}")
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="part de la ligne")
    fig.tight_layout()
    fig.savefig(FIG / "fig4_attribution.png", bbox_inches="tight")
    plt.close(fig)


def fig_action(res):
    pc = pd.DataFrame(res["action_test"]["per_case"])
    pt = res["action_test"]["point"]
    ac = {c["contrast"]: c for c in res["action_test"]["contrasts"]}
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.1),
                             gridspec_kw={"width_ratios": [1.55, 1]})
    ax = axes[0]
    lab = [f"{r.group}\n{r.target}" for r in pc.itertuples()]
    x = np.arange(len(pc))
    w = 0.2
    for k, (s, c, nm) in enumerate([("degraded", MUTE, "dégradé"),
                                    ("random", GRID, "aléatoire"),
                                    ("generic", BLUE, "générique"),
                                    ("guided", ORANGE, "guidé readiness")]):
        ax.bar(x + (k - 1.5) * w, pc[f"balacc_{s}"], width=w, color=c, label=nm)
    ax.set_xticks(x)
    ax.set_xticklabels(lab, fontsize=7.5)
    ax.set_ylabel("exactitude équilibrée sur TEST après action")
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    ax.set_title("Par cas dégradé (groupe supprimé × composant)", pad=22)
    despine(ax)

    ax = axes[1]
    keys = ["guided-generic", "guided-random", "guided-degraded", "generic-degraded"]
    y = np.arange(len(keys))[::-1]
    for i, k in enumerate(keys):
        r = ac[k]
        c = ORANGE if k == "guided-generic" else MUTE
        ax.plot([r["ci_low"], r["ci_high"]], [y[i], y[i]], color=c, lw=2.6,
                solid_capstyle="round")
        ax.plot([r["delta_balanced_accuracy"]], [y[i]], "o", color=c, ms=6)
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels(keys, fontsize=8.5)
    ax.set_xlabel("Δ exactitude équilibrée, IC 95 % bootstrap configuration")
    g = ac["guided-generic"]
    ax.set_title("Contraste décisif : guidé − générique\n"
                 f"{g['delta_balanced_accuracy']:+.3f} "
                 f"[{g['ci_low']:+.3f}; {g['ci_high']:+.3f}]")
    despine(ax)
    fig.tight_layout()
    fig.savefig(FIG / "fig5_action_test.png", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.load(open(OUT / "PHASE20_DR_RESULTS.json"))
    fig_ladder(res)
    fig_contrasts(res)
    fig_degradation()
    fig_attribution(res)
    fig_action(res)
    print("figures written to", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
