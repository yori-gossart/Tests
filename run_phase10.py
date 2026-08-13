#!/usr/bin/env python3
"""
Phase 10 entry point: reset / audit / pure reconstructibility.

    python3 run_phase10.py            # run every phase that can run
    python3 run_phase10.py --phase A  # a single phase

    A  forensic audit of the frozen FO-v1 result
    B  B_dynamic vs B* support-frozen metric, plus the invariance test
    C  acquire the EPA source-identification dataset
    D  pure reconstructibility on the EPA test cases   (requires C)
    E  is the FO score a useful failure predictor?
    F  verdicts

FO-v1 IS FROZEN. No phase here re-runs or modifies it; Phase A only reads its
committed outputs.

PHASE C IS EXPECTED TO FAIL IN THIS ENVIRONMENT. Every EPA host is denied by the
network egress policy (exact errors in phase10_reset/EPA_DATA_MANIFEST.json).
Phase D therefore does not run, and no substitute dataset is used. Drop the
official ZIP at

    phase10_reset/data/epa_source_inversion/Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip

and re-run; the pipeline picks it up from there with nothing else to change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "src"
OUT = REPO / "phase10_reset"
EPA_DIR = OUT / "data" / "epa_source_inversion"
EPA_ZIP = EPA_DIR / "Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip"

EPA_URLS = [
    "https://pasteur.epa.gov/uploads/149/Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip",
    "https://catalog.data.gov/api/3/action/package_show?id=A-pg4z-149",
    "https://sciencehub.epa.gov/sciencehub/datasets",
    "https://edg.epa.gov/metadata/rest/document?id=A-pg4z-149",
]

PY = sys.executable


def run(cmd, log_name):
    (REPO / "logs").mkdir(exist_ok=True)
    log = REPO / "logs" / log_name
    print(f"    $ {' '.join(map(str, cmd))}")
    with open(log, "w") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO)
    if p.returncode != 0:
        raise SystemExit(f"failed (exit {p.returncode}); see {log}")


def phase_a():
    run([PY, str(SRC / "phase10_audit.py")], "p10_audit.log")


def phase_b():
    run([PY, str(SRC / "fo_metrics.py")], "p10_metrics.log")


def phase_c() -> bool:
    """Try the prescribed sources in order. Returns True only on real acquisition."""
    EPA_DIR.mkdir(parents=True, exist_ok=True)
    if EPA_ZIP.exists():
        digest = hashlib.sha256(EPA_ZIP.read_bytes()).hexdigest()
        print(f"    ZIP already present: {EPA_ZIP.name} sha256={digest}")
        return True
    failures = []
    for i, url in enumerate(EPA_URLS, start=1):
        print(f"    [{i}/{len(EPA_URLS)}] {url}")
        p = subprocess.run(
            ["curl", "-sS", "--fail", "--location", "--max-time", "120",
             "-o", str(EPA_ZIP), url],
            capture_output=True, text=True,
        )
        if p.returncode == 0 and EPA_ZIP.exists() and EPA_ZIP.stat().st_size > 0:
            print(f"    acquired: sha256={hashlib.sha256(EPA_ZIP.read_bytes()).hexdigest()}")
            return True
        failures.append({"url": url, "exit": p.returncode,
                         "stderr": p.stderr.strip()[:300]})
        EPA_ZIP.unlink(missing_ok=True)
    print("    BLOCKED -- no source reachable. Exact errors:")
    for f in failures:
        print(f"      {f['url']}\n        {f['stderr']}")
    print(f"    recorded in {(OUT / 'EPA_DATA_MANIFEST.json').relative_to(REPO)}")
    return False


def phase_d(acquired: bool):
    if not acquired:
        print("    SKIPPED: Phase C did not acquire the dataset.")
        print("    No substitute dataset is used, by instruction. "
              "PURE_RECONSTRUCTIBILITY_RESULTS.csv stays schema-only with 0 rows.")
        return
    raise SystemExit(
        "Phase D implementation is gated on the real dataset layout, which "
        "cannot be inferred without the ZIP. Re-run with the ZIP present and "
        "implement the loader against its actual contents."
    )


def phase_e():
    run([PY, str(SRC / "phase10_diagnostic.py")], "p10_diagnostic.log")


def phase_f():
    run([PY, str(SRC / "phase10_verdicts.py")], "p10_verdicts.log")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=list("ABCDEF"), default=None)
    args = ap.parse_args()
    want = args.phase

    acquired = False
    if want in (None, "A"):
        print("[A] forensic audit of FO-v1"); phase_a()
    if want in (None, "B"):
        print("[B] B / B* metrics and invariance test"); phase_b()
    if want in (None, "C", "D"):
        print("[C] EPA dataset acquisition"); acquired = phase_c()
    if want in (None, "D"):
        print("[D] pure reconstructibility"); phase_d(acquired)
    if want in (None, "E"):
        print("[E] FO as a failure predictor"); phase_e()
    if want in (None, "F"):
        print("[F] verdicts"); phase_f()
    print("\nphase 10 complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
