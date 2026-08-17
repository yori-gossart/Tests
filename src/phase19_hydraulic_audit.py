"""PHASE 19 -- Gate audit of the ZeMA / UCI hydraulic condition-monitoring rig.

AUDIT ONLY. No FO quantity, no performance number, no model. The script
establishes what the rig's experimental design can and cannot support.

The decisive question is not "are there 2205 cycles" but "how many INDEPENDENT
experiments are there". The official documentation states that four of the five
profile columns "describe degradation processes over time", which is a warning
that the cycle index is a trajectory, not a randomisation.
"""

from __future__ import annotations

import json
from itertools import groupby
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase19_hydraulic"
DATA = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/hyd/Hydraulic-systems/data")

SENSORS = {"PS1": 6000, "PS2": 6000, "PS3": 6000, "PS4": 6000, "PS5": 6000, "PS6": 6000,
           "EPS1": 6000, "FS1": 600, "FS2": 600, "TS1": 60, "TS2": 60, "TS3": 60,
           "TS4": 60, "VS1": 60, "SE": 60, "CE": 60, "CP": 60}
PROFILE_COLS = ["cooler_pct", "valve_pct", "pump_leak", "accumulator_bar", "stable"]
HEALTHY = {"cooler_pct": 100, "valve_pct": 100, "pump_leak": 0, "accumulator_bar": 130}


def runs(x: np.ndarray) -> list[int]:
    return [len(list(g)) for _, g in groupby(x)]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)

    prof = pd.read_csv(DATA / "profile.txt", sep="\t", header=None, names=PROFILE_COLS)
    n = len(prof)
    print(f"profile.txt: {prof.shape}", flush=True)

    # ---- A: integrity ----------------------------------------------------
    integrity = {"n_cycles": int(n), "expected_2205": bool(n == 2205), "sensors": {}}
    total_attr = 0
    for s, cols in SENSORS.items():
        a = np.loadtxt(DATA / f"{s}.txt", delimiter="\t")
        total_attr += a.shape[1]
        integrity["sensors"][s] = {
            "shape": list(a.shape), "expected_cols": cols,
            "cols_ok": bool(a.shape[1] == cols), "rows_ok": bool(a.shape[0] == n),
            "n_nan": int(np.isnan(a).sum()), "n_inf": int(np.isinf(a).sum()),
            "min": float(a.min()), "max": float(a.max()),
        }
        print(f"  {s:5s} {a.shape}  nan={np.isnan(a).sum()}  inf={np.isinf(a).sum()}",
              flush=True)
    integrity["total_attributes"] = total_attr
    integrity["expected_43680"] = bool(total_attr == 43680)
    integrity["profile_nan"] = int(prof.isna().sum().sum())

    # ---- A: component states and the fully healthy configuration ---------
    states = {c: {str(k): int(v) for k, v in prof[c].value_counts().sort_index().items()}
              for c in PROFILE_COLS}
    healthy_mask = np.ones(n, dtype=bool)
    for c, v in HEALTHY.items():
        healthy_mask &= (prof[c] == v).to_numpy()
    stable_healthy = healthy_mask & (prof["stable"] == 0).to_numpy()

    # ---- B: independence -------------------------------------------------
    seq = {}
    for c in PROFILE_COLS:
        r = runs(prof[c].to_numpy())
        seq[c] = {"n_runs": len(r), "n_changes": len(r) - 1,
                  "median_run_length": float(np.median(r)),
                  "max_run_length": int(max(r)), "min_run_length": int(min(r)),
                  "longest_runs": sorted(r, reverse=True)[:5]}

    combo = prof[list(HEALTHY)].astype(str).agg("|".join, axis=1)
    combo_runs = runs(combo.to_numpy())
    unique_combos = combo.nunique()
    combo_counts = combo.value_counts()

    # lag-1 agreement: probability that cycle i and i+1 share the same configuration
    same_next = float((combo.to_numpy()[:-1] == combo.to_numpy()[1:]).mean())

    independence = {
        "per_column_sequencing": seq,
        "distinct_configurations": int(unique_combos),
        "configuration_runs": {"n_runs": len(combo_runs),
                               "median_run_length": float(np.median(combo_runs)),
                               "max_run_length": int(max(combo_runs))},
        "prob_consecutive_cycles_same_configuration": same_next,
        "cycles_per_configuration": {
            "min": int(combo_counts.min()), "median": float(combo_counts.median()),
            "max": int(combo_counts.max())},
        "n_configurations_with_1_cycle": int((combo_counts == 1).sum()),
    }

    # ---- C: baseline -----------------------------------------------------
    baseline = {
        "n_fully_healthy_cycles": int(healthy_mask.sum()),
        "n_fully_healthy_and_stable": int(stable_healthy.sum()),
        "fully_healthy_positions": {
            "first": int(np.flatnonzero(healthy_mask)[0]) if healthy_mask.any() else None,
            "last": int(np.flatnonzero(healthy_mask)[-1]) if healthy_mask.any() else None,
            "n_contiguous_blocks": len([1 for k, _ in groupby(healthy_mask) if k]),
        },
    }

    # For a MATCHED baseline, a faulted configuration must share every OTHER
    # component state with a healthy one. Count how often that holds.
    matched = []
    comps = list(HEALTHY)
    for target in comps:
        others = [c for c in comps if c != target]
        key_other = prof[others].astype(str).agg("|".join, axis=1)
        healthy_other = set(key_other[(prof[target] == HEALTHY[target]).to_numpy()])
        for lvl in sorted(prof[target].unique()):
            if lvl == HEALTHY[target]:
                continue
            m = (prof[target] == lvl).to_numpy()
            share = float(np.mean([k in healthy_other for k in key_other[m]]))
            matched.append({"component": target, "level": int(lvl),
                            "n_cycles": int(m.sum()),
                            "frac_with_matched_healthy_context": share})
    baseline["matched_context_coverage"] = matched

    # ---- G: power under a leakage-free split -----------------------------
    power = {}
    for c in comps:
        vc = prof[c].value_counts().sort_index()
        r = runs(prof[c].to_numpy())
        power[c] = {"levels": {str(k): int(v) for k, v in vc.items()},
                    "n_blocks": len(r),
                    "note": "a leakage-free split must keep whole configuration blocks together"}
    independence["power_by_component"] = power

    result = {"source": {
        "official_host": "archive.ics.uci.edu",
        "official_host_reachable": False,
        "mirror_used": "github.com/Machine-Learning-FGA/Hydraulic-systems (data/)",
        "integrity_caveat": "the UCI original is unreachable from this environment, so the "
                            "mirror cannot be checksum-verified against it. Structural "
                            "conformance to the official documentation is verified instead.",
    }, "A_integrity": integrity, "A_states": states,
        "B_independence": independence, "C_baseline": baseline}

    (OUT / "AUDIT_HYDRAULIC.json").write_text(json.dumps(result, indent=2))
    pd.DataFrame(matched).to_csv(OUT / "MATCHED_BASELINE_COVERAGE.csv", index=False)
    pd.DataFrame([{"sensor": s, **v} for s, v in integrity["sensors"].items()]).to_csv(
        OUT / "SENSOR_INTEGRITY.csv", index=False)
    combo_counts.rename("n_cycles").to_csv(OUT / "CONFIGURATION_COUNTS.csv")

    print("\n=== A integrity ===")
    print(f"cycles={n} expected2205={integrity['expected_2205']} "
          f"total_attributes={total_attr} expected43680={integrity['expected_43680']}")
    print(f"NaN across all sensors: {sum(v['n_nan'] for v in integrity['sensors'].values())}")
    print("\n=== A component states ===")
    print(json.dumps(states, indent=1))
    print("\n=== B independence ===")
    print(json.dumps(independence, indent=1)[:2600])
    print("\n=== C baseline ===")
    print(json.dumps(baseline, indent=1)[:1800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
