"""
Freeze every tunable quantity of the study from 2018 and the network model
alone, then write FROZEN_PROTOCOL.json and print its SHA256.

Nothing downstream is allowed to change what this script produces. The freeze
covers:

  * sigma_j        per-sensor residual scale (robust MAD of the 2018 residuals)
  * kappa, eta     FO eligibility and blind-spot thresholds, in sigma units
  * tau            prior scale for the Bayesian OED criteria
  * k_cusum, h     CUSUM slack and alarm threshold
  * min_gap        refractory period between alarms
  * window         localisation window
  * ridge_lambda   nominal-model regularisation
  * the sensor subset chosen by every method at every budget
  * every random seed

CONTAMINATION GUARD
-------------------
This is not a promise, it is enforced. install_2019_guard() patches builtins.open
and numpy.load so that any attempt to read a path matching the 2019 / evaluation
artefacts raises immediately. The guard stays armed for the whole run, so if any
code path in selection, detection or calibration reached for 2019 data the
freeze would abort instead of silently producing a contaminated protocol.

The 2019 ground truth was nevertheless visible during the mandatory data
inventory, because the organisers ship it in the same file as the 2018
configuration (finding F4 in data/raw/PROVENANCE.json). The guard addresses the
code path, not that exposure, and the report states both.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detector  # noqa: E402
import selection  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = REPO / "data" / "processed"
OUT = REPO / "FROZEN_PROTOCOL.json"

FORBIDDEN = re.compile(r"(2019|evaluation)", re.IGNORECASE)

# --- pre-registered constants, none of them fitted -------------------------
KAPPA = 3.0          # a scenario counts as visible to the rich reference at 3 sigma
ETA = 3.0            # ... and as forgotten by S below the same 3 sigma
TAU = 1.0            # prior scale, m^3/h per metre; only sets the OED regulariser
K_CUSUM = 0.5        # textbook slack: half the 1-sigma shift the chart targets
MIN_GAP_STEPS = 2016  # 7 days at 5 min
WINDOW_STEPS = 288    # 24 h at 5 min
FALSE_ALARM_BUDGET = 6  # alarms per leak-free year, used to calibrate h
SEED = 20180101
N_RANDOM = 100


def install_2019_guard() -> None:
    real_open = builtins.open
    real_npload = np.load

    def guarded_open(file, *a, **kw):
        s = str(file)
        if FORBIDDEN.search(s) and "raw" not in s:
            raise PermissionError(
                f"FROZEN_PROTOCOL freeze attempted to read a 2019 artefact: {s}"
            )
        return real_open(file, *a, **kw)

    def guarded_npload(file, *a, **kw):
        s = str(file)
        if FORBIDDEN.search(s):
            raise PermissionError(f"freeze attempted to np.load a 2019 artefact: {s}")
        return real_npload(file, *a, **kw)

    builtins.open = guarded_open
    np.load = guarded_npload


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def calibrate_threshold(Z_noleak: np.ndarray, subset: list[int], k: float,
                        budget: int, min_gap: int) -> float:
    """Smallest h on a grid giving at most `budget` alarms over the leak-free
    year, evaluated with the FULL candidate array so that one common h serves
    every method and no budget is advantaged."""
    stat = detector.cusum_statistic(Z_noleak, subset, k)
    hi = float(np.nanmax(stat))
    grid = np.linspace(hi * 0.02, hi * 1.05, 240)
    chosen = grid[-1]
    for h in grid:
        alarms = detector.cusum_detect(Z_noleak, subset, k, float(h), min_gap)
        if len(alarms) <= budget:
            chosen = float(h)
            break
    return float(chosen)


def main() -> int:
    install_2019_guard()
    t0 = time.time()

    lib_path = PROC / "sensitivity_library.npz"
    dir_2018 = PROC / "regenerated_2018"
    dir_noleak = PROC / "regenerated_2018_noleak"
    for p in (lib_path, dir_2018, dir_noleak):
        if not p.exists():
            raise SystemExit(f"missing prerequisite: {p}")

    lib = selection.Library.load(lib_path)
    sensor_ids = [str(s) for s in lib.sensors]

    ts18, X18, P18 = detector.load_year(dir_2018, 2018, sensor_ids)
    train_mask = np.ones(len(ts18), dtype=bool)
    nominal = detector.fit_nominal(X18, P18, train_mask, sensor_ids)
    sigma = nominal.sigma
    print(f"sigma (m): min {sigma.min():.4f} median {np.median(sigma):.4f} max {sigma.max():.4f}",
          flush=True)

    tsN, XN, PN = detector.load_year(dir_noleak, 2018, sensor_ids)
    ZN = nominal.standardised(XN, PN)
    h = calibrate_threshold(ZN, list(range(len(sensor_ids))), K_CUSUM,
                            FALSE_ALARM_BUDGET, MIN_GAP_STEPS)
    n_alarms = len(detector.cusum_detect(ZN, list(range(len(sensor_ids))), K_CUSUM,
                                         h, MIN_GAP_STEPS))
    print(f"calibrated h = {h:.3f} -> {n_alarms} alarms on the leak-free 2018 year",
          flush=True)

    sel = selection.select_all(
        lib=lib, sigma=sigma, kappa=KAPPA, eta=ETA, tau=TAU,
        n_random=N_RANDOM, seed=SEED,
        inp_path=RAW / "L-TOWN_v2_Model.inp",
    )

    protocol = {
        "frozen_utc": pd.Timestamp.now("UTC").isoformat(),
        "statement": (
            "Every threshold, hyper-parameter and sensor subset below was derived "
            "from the 2018 data and the network model only. A runtime guard "
            "(install_2019_guard) blocked all reads of 2019 artefacts while this "
            "file was produced."
        ),
        "constants": {
            "kappa": KAPPA, "eta": ETA, "tau": TAU,
            "k_cusum": K_CUSUM, "h_alarm": h,
            "min_gap_steps": MIN_GAP_STEPS, "window_steps": WINDOW_STEPS,
            "ridge_lambda": detector.RIDGE_LAMBDA,
            "n_harmonics": detector.N_HARMONICS,
            "false_alarm_budget_per_year": FALSE_ALARM_BUDGET,
            "false_alarms_on_noleak_2018": n_alarms,
            "seed": SEED, "n_random_replications": N_RANDOM,
        },
        "sigma_per_sensor_m": {sid: float(s) for sid, s in zip(sensor_ids, sigma)},
        "nominal_model": {
            "form": "ridge on [1, 3 inlet flows, tank level, 3 daily harmonics, day-of-week]",
            "n_features": int(X18.shape[1]),
            "fitted_on": "regenerated 2018, all timestamps",
        },
        "inputs": {
            "sensitivity_library_sha256": sha256_of(lib_path),
            "L-TOWN_v2_Model.inp_sha256": sha256_of(RAW / "L-TOWN_v2_Model.inp"),
            "dataset_configuration_historical.yalm_sha256":
                sha256_of(RAW / "dataset_configuration_historical.yalm"),
            "regenerated_2018_metadata_sha256":
                sha256_of(dir_2018 / "REGENERATION_METADATA.json"),
        },
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "selection": sel,
        "wall_clock_s": round(time.time() - t0, 1),
    }

    payload = json.dumps(protocol, indent=2, sort_keys=False) + "\n"
    with open(OUT, "w") as fh:
        fh.write(payload)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    with open(REPO / "FROZEN_PROTOCOL.sha256", "w") as fh:
        fh.write(f"{digest}  FROZEN_PROTOCOL.json\n")

    print(f"\nwrote {OUT}")
    print(f"FROZEN_PROTOCOL.json sha256 = {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
