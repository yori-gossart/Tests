#!/usr/bin/env python3
"""
Single entry point for the whole study.

    python3 run_full_validation.py            # run every stage that is missing
    python3 run_full_validation.py --force    # redo everything from scratch
    python3 run_full_validation.py --from 5   # resume at stage 5

Stages run in dependency order and each one is skipped when its output already
exists, so an interrupted run resumes without repeating the multi-hour
hydraulic simulations.

    1  fetch     official BattLeDIM artefacts (git + Git-LFS), digest-verified
    2  audit     SHA256 / shape / period / missing values -> DATA_MANIFEST.json
    3  simulate  regenerate 2018, the leak-free 2018 control, and 2019
                 (chunked and resumable; chunking is verified bit-exact
                  against the single-run reference implementation)
    4  library   leak-sensitivity library on the nominal model
    5  freeze    FROZEN_PROTOCOL.json (+ SHA256), guarded against 2019 reads
    6  track A   leave-one-leak-event-out over the 14 events of 2018
    7  track B   frozen protocol on the reconstructed 2019 year
    8  track C   synthetic robustness study and the anti-bias controls
    9  analyse   paired bootstraps, tables, figures, final report

STAGE ORDER IS THE CONTAMINATION BARRIER. Stage 5 must complete, and its digest
must be recorded, before stage 7 is allowed to read any 2019 artefact. The
freeze itself additionally installs a runtime guard that raises on any 2019
read, so the barrier is enforced by code and not only by ordering.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "src"
PROC = REPO / "data" / "processed"
RAW = REPO / "data" / "raw" / "battledim_official"
RESULTS = REPO / "results"
LOGS = REPO / "logs"

PY = sys.executable


def run(cmd: list[str], log_name: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / log_name
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    print(f"      log -> {log.relative_to(REPO)}")
    t0 = time.time()
    with open(log, "w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO)
    if proc.returncode != 0:
        tail = log.read_text().splitlines()[-25:]
        raise SystemExit(
            f"stage failed (exit {proc.returncode}): {' '.join(map(str, cmd))}\n"
            + "\n".join(tail)
        )
    print(f"      done in {time.time() - t0:.0f}s")


def exists(*paths: Path) -> bool:
    return all(p.exists() for p in paths)


def stage_1_fetch(force: bool) -> None:
    if not force and exists(RAW / "L-TOWN_v2_Real.inp", RAW / "dataset_configuration.yalm"):
        print("    already present, skipping")
        return
    run(["bash", str(SRC / "fetch_data.sh")], "01_fetch.log")


def stage_2_audit(force: bool) -> None:
    if not force and exists(REPO / "DATA_MANIFEST.json"):
        print("    already present, skipping")
        return
    run([PY, str(SRC / "audit_data.py")], "02_audit.log")


def stage_3_simulate(force: bool) -> None:
    jobs = [
        ("regenerated_2018", RAW / "dataset_configuration_historical.yalm", "03a_regen_2018.log"),
        ("regenerated_2018_noleak", PROC / "dataset_configuration_2018_noleak.yalm",
         "03b_regen_2018_noleak.log"),
        ("regenerated_2019", RAW / "dataset_configuration_evaluation.yalm", "03c_regen_2019.log"),
    ]
    make_noleak_config()
    for out_name, cfg, log in jobs:
        out = PROC / out_name
        if not force and (out / "REGENERATION_METADATA.json").exists():
            print(f"    {out_name}: already present, skipping")
            continue
        print(f"    {out_name}: simulating in resumable 15-day chunks (~1.5 h)")
        run([PY, str(SRC / "regenerate_chunked.py"), "--config", str(cfg),
             "--out", str(out), "--chunk-steps", "4320"], log)


def make_noleak_config() -> None:
    """Derive the leak-free 2018 control configuration from the official one."""
    import re

    out = PROC / "dataset_configuration_2018_noleak.yalm"
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    src = (RAW / "dataset_configuration_historical.yalm").read_text(encoding="latin-1")
    kept = [
        line.replace(
            "Configuration file for HISTORICAL DATASET",
            "DERIVED no-leak control: HISTORICAL 2018 with all leak events removed",
        )
        for line in src.split("\n")
        if not re.match(r"^- p\d+,", line)
    ]
    out.write_text("\n".join(kept), encoding="latin-1")
    print(f"    derived {out.relative_to(REPO)}")


def stage_4_library(force: bool) -> None:
    lib = PROC / "sensitivity_library.npz"
    if not force and lib.exists():
        print("    already present, skipping")
        return
    scratch = REPO / ".epanet_scratch"
    scratch.mkdir(exist_ok=True)
    log = LOGS / "04_library.log"
    print(f"    building (~25 min); log -> {log.relative_to(REPO)}")
    with open(log, "w") as fh:
        proc = subprocess.run(
            [PY, str(SRC / "sensitivity.py"),
             "--inp", str(RAW / "L-TOWN_v2_Model.inp"),
             "--config", str(RAW / "dataset_configuration_historical.yalm"),
             "--out", str(lib)],
            stdout=fh, stderr=subprocess.STDOUT, cwd=scratch,
        )
    if proc.returncode != 0:
        raise SystemExit("sensitivity library build failed; see " + str(log))


def stage_5_freeze(force: bool) -> None:
    if not force and exists(REPO / "FROZEN_PROTOCOL.json"):
        print("    already frozen, skipping (delete FROZEN_PROTOCOL.json to redo)")
        return
    run([PY, str(SRC / "freeze_protocol.py")], "05_freeze.log")


def stage_6_track_a(force: bool) -> None:
    out = RESULTS / "track_a_event_heldout_2018.json"
    if not force and out.exists():
        print("    already present, skipping")
        return
    run([PY, str(SRC / "tracks.py"), "--track", "a"], "06_track_a.log")


def stage_7_track_b(force: bool) -> None:
    if not exists(REPO / "FROZEN_PROTOCOL.json", REPO / "FROZEN_PROTOCOL.sha256"):
        raise SystemExit(
            "refusing to touch 2019: FROZEN_PROTOCOL.json and its digest must "
            "exist before the test year may be opened"
        )
    out = RESULTS / "track_b_reconstructed_2019.json"
    if not force and out.exists():
        print("    already present, skipping")
        return
    run([PY, str(SRC / "tracks.py"), "--track", "b"], "07_track_b.log")


def stage_8_track_c(force: bool) -> None:
    out = RESULTS / "track_c_robustness.json"
    if not force and out.exists():
        print("    already present, skipping")
        return
    run([PY, str(SRC / "robustness.py")], "08_track_c.log")


def stage_9_analyse(force: bool) -> None:
    run([PY, str(SRC / "analyse.py")], "09_analyse.log")


STAGES = [
    ("fetch official data", stage_1_fetch),
    ("audit data -> DATA_MANIFEST.json", stage_2_audit),
    ("regenerate SCADA (2018, no-leak control, 2019)", stage_3_simulate),
    ("build leak-sensitivity library", stage_4_library),
    ("FREEZE PROTOCOL (barrier before 2019)", stage_5_freeze),
    ("Track A: leave-one-leak-event-out on 2018", stage_6_track_a),
    ("Track B: frozen protocol on reconstructed 2019", stage_7_track_b),
    ("Track C: synthetic robustness study", stage_8_track_c),
    ("analysis, figures and final report", stage_9_analyse),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="ignore existing outputs")
    ap.add_argument("--from", dest="start", type=int, default=1, help="first stage to run")
    ap.add_argument("--to", dest="stop", type=int, default=len(STAGES))
    args = ap.parse_args()

    t0 = time.time()
    for i, (title, fn) in enumerate(STAGES, start=1):
        if i < args.start or i > args.stop:
            continue
        print(f"\n[{i}/{len(STAGES)}] {title}")
        fn(args.force)
    print(f"\nall requested stages complete in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
