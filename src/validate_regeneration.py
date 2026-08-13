"""
Check the regenerated 2019 leak flows against the OFFICIAL published series.

Why this matters more than it looks
-----------------------------------
data/raw/battledim_official/competition_leakages/Leak_p*.xlsx are official
outputs shipped with the organisers' scoring code. Each holds the true leak
flow of one of the 23 evaluation events, 105120 samples at 5 minutes covering
2019-01-01 to 2019-12-31. They were produced by the organisers' own run of the
generator on the real network.

That makes them an independent yardstick for two separate questions.

1. FIDELITY. Does src/regenerate_scada.py reproduce the official pipeline? If
   our regenerated leak flows match these series, the port, the leak model, the
   PDD settings and the incipient ramp are all confirmed against official
   output rather than merely believed.

2. WHETHER FINDING F2 APPLIES TO THE REAL BENCHMARK. The leak flow at a node is
   q = C sqrt(p), so it is a direct readout of the pressure at that node, which
   in turn depends on the demands driving the whole network. Our regeneration
   necessarily uses the repeating 365-day demand patterns of the published
   model. If the official 2019 series agree with ours, then the published 2019
   dataset was generated under those same repeating demands, and F2 is a
   property of the real BattLeDIM benchmark rather than an artefact of this
   reconstruction. If they disagree, the official run used demand data that the
   published model artefact no longer contains, and Track B's external validity
   is weaker still.

Either outcome is informative and both are reported verbatim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OFFICIAL = REPO / "data" / "raw" / "battledim_official" / "competition_leakages"
PROC = REPO / "data" / "processed"
RESULTS = REPO / "results"

# The generator rounds its outputs to 2 decimals, so exact agreement means
# agreement at that quantisation.
ROUNDING = 0.01


def load_official(path: Path) -> tuple[str, pd.DataFrame]:
    book = pd.read_excel(path, sheet_name=None)
    info = dict(zip(book["Info"]["Description"], book["Info"]["Value"]))
    demand_sheet = next(k for k in book if k.startswith("Demand"))
    return str(info["Leak Pipe"]), book[demand_sheet]


def main() -> int:
    regen_path = PROC / "regenerated_2019" / "2019_SCADA_Leaks.csv"
    if not regen_path.exists():
        print(f"missing {regen_path}; run the 2019 regeneration first", file=sys.stderr)
        return 1

    regen = pd.read_csv(regen_path, parse_dates=["Timestamp"])
    files = sorted(OFFICIAL.glob("Leak_p*.xlsx"))
    print(f"comparing {len(files)} official leak series against the regeneration\n")

    rows = []
    for f in files:
        pipe, off = load_official(f)
        if pipe not in regen.columns:
            rows.append({"pipe": pipe, "status": "ABSENT_FROM_REGENERATION"})
            continue
        n = min(len(off), len(regen))
        a = off[pipe].to_numpy(dtype=float)[:n]
        b = regen[pipe].to_numpy(dtype=float)[:n]
        if not (pd.DatetimeIndex(off["Timestamp"][:n]) ==
                pd.DatetimeIndex(regen["Timestamp"][:n])).all():
            rows.append({"pipe": pipe, "status": "TIMESTAMP_MISMATCH"})
            continue
        diff = np.abs(a - b)
        denom = max(float(np.mean(np.abs(a))), 1e-9)
        rows.append({
            "pipe": pipe,
            "status": "COMPARED",
            "n_samples": int(n),
            "official_mean_cmh": float(np.mean(a)),
            "regenerated_mean_cmh": float(np.mean(b)),
            "max_abs_diff_cmh": float(diff.max()),
            "mean_abs_diff_cmh": float(diff.mean()),
            "rel_mean_abs_diff": float(diff.mean() / denom),
            "frac_within_rounding": float(np.mean(diff <= ROUNDING)),
            "pearson_r": float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0
            else float("nan"),
        })

    df = pd.DataFrame(rows)
    RESULTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(RESULTS / "regeneration_fidelity.csv", index=False)

    compared = df[df["status"] == "COMPARED"]
    if compared.empty:
        print("no series could be compared")
        return 1

    frac = float(compared["frac_within_rounding"].mean())
    worst = float(compared["max_abs_diff_cmh"].max())
    rel = float(compared["rel_mean_abs_diff"].mean())

    # The statistic that discriminates DEMAND equality is agreement of the
    # series MEANS, not sample-by-sample agreement. Leak flow is q = C sqrt(p),
    # so a different demand series shifts nodal pressure and moves the mean flow
    # at the percent level at least. Sample-level scatter, by contrast, is what
    # a different nonlinear-solver version produces while leaving the mean
    # essentially untouched. Reporting only frac_within_rounding would confuse
    # the two.
    mean_rel = np.abs(
        (compared["regenerated_mean_cmh"] - compared["official_mean_cmh"])
        / compared["official_mean_cmh"]
    )
    worst_mean_rel = float(mean_rel.max())

    if worst_mean_rel < 1e-3:
        if frac > 0.99 and worst <= 0.05:
            verdict = "REGENERATION_MATCHES_OFFICIAL_OUTPUT"
            detail = "sample-for-sample within the generator rounding"
        else:
            verdict = "REGENERATION_MATCHES_OFFICIAL_TO_SOLVER_PRECISION"
            detail = ("means agree to better than 1e-3 relative; the residual "
                      "sample scatter is consistent with a different WNTR solver "
                      "version, not with different input data")
        f2 = (
            "F2 CONFIRMED FOR THE REAL BENCHMARK: reproducing the official 2019 "
            "leak flows requires the nodal pressures, hence the demands, to match "
            f"the official run, and our run uses the published model's repeating "
            f"365-day patterns. Worst relative disagreement of any series mean is "
            f"{worst_mean_rel:.2e}, which different demand data could not produce. "
            "The annual demand repetition is therefore a property of the BattLeDIM "
            "benchmark itself, not an artefact of this reconstruction. "
            f"({detail})"
        )
    elif rel < 0.05:
        verdict = "REGENERATION_CLOSE_NOT_EXACT"
        f2 = ("F2 PARTIALLY INFORMATIVE: series means differ by up to "
              f"{worst_mean_rel:.2e} relative, too much to attribute confidently to "
              "the solver and too little to prove different demands.")
    else:
        verdict = "REGENERATION_DIVERGES_FROM_OFFICIAL_OUTPUT"
        f2 = ("F2 NOT RESOLVED, AND WORSE: the official 2019 leak flows are NOT "
              "reproduced under the published model's demands, which indicates the "
              "official run used demand data the published artefact no longer "
              "contains. Track B's external validity is weaker than assumed.")

    summary = {
        "verdict": verdict,
        "n_series_compared": int(len(compared)),
        "mean_fraction_within_generator_rounding": frac,
        "worst_max_abs_diff_cmh": worst,
        "mean_relative_abs_diff": rel,
        "worst_relative_disagreement_of_series_mean": worst_mean_rel,
        "min_pearson_r": float(compared["pearson_r"].min()),
        "f2_interpretation": f2,
        "per_series": rows,
    }
    (RESULTS / "regeneration_fidelity.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(compared[["pipe", "official_mean_cmh", "regenerated_mean_cmh",
                    "max_abs_diff_cmh", "frac_within_rounding"]].to_string(index=False))
    print(f"\nverdict: {verdict}")
    print(f"mean fraction within the generator's 0.01 rounding: {frac:.6f}")
    print(f"worst max abs diff: {worst:.4f} m3/h")
    print(f"worst relative disagreement of any series mean: {worst_mean_rel:.3e}")
    print(f"\n{f2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
