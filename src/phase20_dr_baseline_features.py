"""PHASE 20-DR -- dump the unperturbed 136-feature matrix.

Same frozen code path as phase20_dr_run.py (build_features on the baseline
condition), written to disk so the analysis stage can rank sensors and measure
class separations on TRAIN without recomputing the sensor files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from phase20_dr_run import build_features, conditions, load_raw, stress_scale, SEED

OUT = Path(__file__).resolve().parents[1] / "phase20_dr"


def main() -> int:
    raw, prof, _ = load_raw()
    scale = stress_scale(raw)
    base = conditions()[0]
    assert base["name"] == "baseline"
    X, names, avail = build_features(raw, base, scale, np.random.default_rng(SEED))
    np.save(OUT / "BASELINE_FEATURES.npy", X)
    (OUT / "FEATURE_NAMES.txt").write_text("\n".join(names) + "\n")
    print(f"baseline features {X.shape}, sensors available={int(avail.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
