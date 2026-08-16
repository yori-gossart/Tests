"""
PHASE TEP -- data generation for the FROZEN protocol (commit cb307f9).

Runs the official simulator over the pre-registered grid and stores nothing but
raw simulator output. No FO quantity, no classifier, no threshold appears here.

Grid, taken verbatim from PROTOCOLE_PREENREGISTRE_TEP.json:
    21 disturbances x 50 frozen seeds, at nominal noise
    the paired IDV=0 baseline is generated ONCE PER SEED and shared by the 21
    faults of that seed -- it is the same run, so 1100 simulations rather
    than 2100
    noise levels 2, 4, 8 regenerated for the TRAIN seeds, where E* lives
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase14_tep_harness as H

REPO = Path(__file__).resolve().parents[1]
PROTO = json.loads((REPO / "phase14_tep" / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
OUT = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")

SEEDS = PROTO["seeds"]["list"]
FAULTS = PROTO["disturbances"]["ids"]
FAULT_SAMPLE = 160          # 8 h at 180 s sampling
N_CHANNELS = 41             # XMEAS only, XMV excluded: no declared sigma there
TRAIN_IDX = list(range(0, 25))
NOISE_EXTRA = [2.0, 4.0, 8.0]


def one(args) -> tuple:
    idv, seed_idx, scale, worker = args
    wd = OUT / f"work_{worker}"
    X, _ = H.generate(wd, idv=idv, seed=float(SEEDS[seed_idx]), noise_scale=scale)
    return idv, seed_idx, scale, X[FAULT_SAMPLE:, :N_CHANNELS].T.astype(np.float32)


def run_grid(jobs: list, tag: str, n_workers: int = 4) -> dict:
    t0 = time.time()
    store, done = {}, 0
    jobs = [(idv, si, sc, i % n_workers) for i, (idv, si, sc) in enumerate(jobs)]
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        for idv, si, sc, arr in ex.map(one, jobs, chunksize=1):
            store[(idv, si, sc)] = arr
            done += 1
            if done % 100 == 0:
                el = time.time() - t0
                print(f"  [{tag}] {done}/{len(jobs)}  {el:.0f}s  "
                      f"eta {el/done*(len(jobs)-done):.0f}s", flush=True)
    print(f"  [{tag}] done {done} runs in {time.time()-t0:.0f}s", flush=True)
    return store


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    # nominal: every seed needs its IDV=0 twin plus the 21 faults
    jobs = [(0, si, 1.0) for si in range(len(SEEDS))]
    jobs += [(k, si, 1.0) for si in range(len(SEEDS)) for k in FAULTS]
    print(f"nominal grid: {len(jobs)} simulator runs", flush=True)
    nominal = run_grid(jobs, "nominal")

    np.savez_compressed(
        OUT / "nominal.npz",
        **{f"{k}_{si}": v for (k, si, _), v in nominal.items()})
    print("saved nominal.npz", flush=True)

    # extra noise levels, TRAIN seeds only -- that is the population E* is
    # frozen on, and the population B*/B_dynamic are compared over
    for sc in NOISE_EXTRA:
        jobs = [(0, si, sc) for si in TRAIN_IDX]
        jobs += [(k, si, sc) for si in TRAIN_IDX for k in FAULTS]
        print(f"noise x{sc}: {len(jobs)} simulator runs", flush=True)
        store = run_grid(jobs, f"noise{sc}")
        np.savez_compressed(
            OUT / f"noise_{sc}.npz",
            **{f"{k}_{si}": v for (k, si, _), v in store.items()})
        print(f"saved noise_{sc}.npz", flush=True)

    print("GENERATION COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
