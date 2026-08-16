"""PHASE 16 -- blind confirmatory data generation.

MUST NOT RUN before PROTOCOLE_PHASE16_CONFIRMATOIRE.md is committed. The script
refuses to start unless that file exists and its recorded SHA256 matches, so the
ordering rule is enforced by the code rather than by discipline.

Seeds are disjoint from Phase 14 by construction: Phase 14 used
1000000000 + 7919*i for i in 0..49 (max 1000388031); Phase 16 uses
2000000000 + 7919*i. The overlap check is executed and recorded.

The fault/normal pairing is exact: for every seed, one IDV=0 run is generated
and shared by the 21 faults of that seed, so delta = fault - normal has the
identical noise realisation on both sides.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase14_tep_harness as H

REPO = Path(__file__).resolve().parents[1]
P16 = REPO / "phase16_tep"
PROTOCOL = P16 / "PROTOCOLE_PHASE16_CONFIRMATOIRE.md"
OUT = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen16")

FAULTS = list(range(1, 22))
FAULT_SAMPLE = 160
N_CHANNELS = 41
N_SEEDS = 50
NOISE_LEVELS = [2.0, 4.0, 8.0]
NOISE_COHORT_SEEDS = 20            # dimensioned in the protocol, before generation

PHASE14_SEEDS = {1000000000 + 7919 * i for i in range(50)}
SEEDS = [2000000000 + 7919 * i for i in range(N_SEEDS)]


def guard() -> str:
    if not PROTOCOL.exists():
        raise SystemExit("REFUSED: the confirmatory protocol is not committed yet.")
    digest = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    print(f"protocol SHA256 {digest}", flush=True)
    overlap = PHASE14_SEEDS & set(SEEDS)
    if overlap:
        raise SystemExit(f"REFUSED: {len(overlap)} Phase 14 seeds would be reused.")
    print(f"seed disjointness verified: 0 of {len(SEEDS)} overlap Phase 14", flush=True)
    return digest


def one(args):
    idv, si, scale, worker = args
    X, _ = H.generate(OUT / f"work_{worker}", idv=idv, seed=float(SEEDS[si]),
                      noise_scale=scale)
    return idv, si, scale, X[FAULT_SAMPLE:, :N_CHANNELS].T.astype(np.float32)


def run(jobs, tag, workers=4):
    t0, store = time.time(), {}
    jobs = [(k, si, sc, i % workers) for i, (k, si, sc) in enumerate(jobs)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (k, si, sc, arr) in enumerate(ex.map(one, jobs, chunksize=1), 1):
            store[(k, si, sc)] = arr
            if n % 100 == 0:
                el = time.time() - t0
                print(f"  [{tag}] {n}/{len(jobs)} {el:.0f}s eta {el/n*(len(jobs)-n):.0f}s",
                      flush=True)
    print(f"  [{tag}] {len(jobs)} runs in {time.time()-t0:.0f}s", flush=True)
    return store


def main() -> int:
    digest = guard()
    OUT.mkdir(parents=True, exist_ok=True)
    (P16 / "logs").mkdir(parents=True, exist_ok=True)

    manifest = pd.DataFrame({
        "seed_index": range(N_SEEDS), "seed_value": SEEDS,
        "used_in_phase14": [s in PHASE14_SEEDS for s in SEEDS],
        "in_noise_cohort": [i < NOISE_COHORT_SEEDS for i in range(N_SEEDS)],
    })
    manifest.to_csv(P16 / "NEW_SEEDS_MANIFEST.csv", index=False)

    jobs = [(0, si, 1.0) for si in range(N_SEEDS)]
    jobs += [(k, si, 1.0) for si in range(N_SEEDS) for k in FAULTS]
    print(f"nominal: {len(jobs)} runs", flush=True)
    nominal = run(jobs, "nominal")
    np.savez_compressed(OUT / "nominal.npz",
                        **{f"{k}_{si}": v for (k, si, _), v in nominal.items()})

    for sc in NOISE_LEVELS:
        jobs = [(0, si, sc) for si in range(NOISE_COHORT_SEEDS)]
        jobs += [(k, si, sc) for si in range(NOISE_COHORT_SEEDS) for k in FAULTS]
        print(f"noise x{sc}: {len(jobs)} runs", flush=True)
        st = run(jobs, f"noise{sc}")
        np.savez_compressed(OUT / f"noise_{sc}.npz",
                            **{f"{k}_{si}": v for (k, si, _), v in st.items()})

    (P16 / "GENERATION_RECORD.json").write_text(json.dumps({
        "protocol_sha256": digest, "n_seeds": N_SEEDS, "seeds": SEEDS,
        "phase14_overlap": 0, "faults": FAULTS,
        "nominal_realisations": N_SEEDS * len(FAULTS),
        "noise_cohort_seeds": NOISE_COHORT_SEEDS,
        "noise_levels": NOISE_LEVELS,
        "noise_realisations_per_level": NOISE_COHORT_SEEDS * len(FAULTS),
    }, indent=2))
    print("GENERATION COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
