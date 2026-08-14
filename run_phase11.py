#!/usr/bin/env python3
"""
Phase 11 -- reproduction of the EPA / Seth et al. 2016 source-inversion study.

    python3 run_phase11.py                 # run every gate that can run
    python3 run_phase11.py --zip <path>    # point at the official ZIP explicitly

GATE ORDER IS THE POINT. The FO phase does not open unless R1-R5 pass, so this
script cannot produce an FO number from an unreproduced experiment.

    R0  ingest    locate the official ZIP, SHA256 it, unpack read-only,
                  inventory what is actually inside
    R1  Network Size        reproduce, compare to the official XLSX
    R2  Time Horizon        idem
    R3  Measurement Error   idem
    R4  Modeling Error      idem
    R5  Sensor Placement    idem
    R6  scorecard           REPRODUCTION_SCORECARD.csv
    FO  diagnostics on the reproduced event-level data (gated on R1-R5)

CURRENT STATE: R0 FAILS -- the ZIP is not present and cannot be downloaded.

Two inputs the brief assumes are missing from this environment:

  1. Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip
     Not in the session uploads directory; every EPA host is denied by the
     network egress policy. Exact errors in phase11_epa/EPA_DATA_MANIFEST.json.

  2. REPRODUCTION_GATE_PROTOCOL.md
     Referenced by the brief as mandatory, defining Gates R0-R6. Never
     supplied. The gate definitions below are therefore reconstructed from the
     brief's own step 6/7 and are NOT authoritative.

R1-R5 are deliberately left unimplemented rather than guessed. Their inputs are
the ZIP's internal layout, the paper's experimental parameters and the WST
configuration, none of which can be inferred without the artefacts. Writing
plausible-looking code against an imagined layout would produce something that
runs and means nothing. Per the brief: do not replace this experiment with an
ad hoc simulation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
P11 = REPO / "phase11_epa"
RAW = P11 / "raw"
LOGS = REPO / "logs"

ZIP_NAME = "Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip"
SEARCH_DIRS = [
    P11,
    REPO / "phase10_reset" / "data" / "epa_source_inversion",
    REPO,
    Path("/root/.claude/uploads"),
    Path("/home/user"),
    Path("/tmp"),
]
EPA_URLS = [
    f"https://pasteur.epa.gov/uploads/149/{ZIP_NAME}",
    "https://catalog.data.gov/api/3/action/package_show?id=A-pg4z-149",
    "https://sciencehub.epa.gov/sciencehub/datasets",
    "https://edg.epa.gov/metadata/rest/document?id=A-pg4z-149",
]

GATES = ["R1_network_size", "R2_time_horizon", "R3_measurement_error",
         "R4_modeling_error", "R5_sensor_placement"]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_zip(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        hit = next((p for p in d.rglob(ZIP_NAME) if p.is_file()), None)
        if hit:
            return hit
        # tolerate a renamed copy of the same dataset
        for p in d.rglob("*.zip"):
            if "pg4z" in p.name.lower() or "sourceinversion" in p.name.lower():
                return p
    return None


def try_download() -> tuple[Path | None, list[dict]]:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = P11 / ZIP_NAME
    failures = []
    for url in EPA_URLS:
        p = subprocess.run(
            ["curl", "-sS", "--fail", "--location", "--max-time", "180",
             "-o", str(dest), url],
            capture_output=True, text=True,
        )
        if p.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return dest, failures
        failures.append({"url": url, "curl_exit": p.returncode,
                         "stderr": p.stderr.strip()[:300]})
        dest.unlink(missing_ok=True)
    return None, failures


def make_read_only(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            p.chmod(p.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def gate_r0(explicit_zip: str | None) -> dict:
    """Ingest. Returns a gate record; never fabricates on failure."""
    P11.mkdir(parents=True, exist_ok=True)
    zp = find_zip(explicit_zip)
    downloaded_failures: list[dict] = []
    if zp is None:
        zp, downloaded_failures = try_download()

    if zp is None:
        return {
            "gate": "R0_ingest", "status": "FAILED",
            "reason": "official ZIP not present and not downloadable",
            "zip_name": ZIP_NAME,
            "searched": [str(d) for d in SEARCH_DIRS],
            "download_failures": downloaded_failures,
            "consequence": "R1-R6 and the FO phase do not run; no results are produced",
        }

    digest = sha256_of(zp)
    RAW.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp) as zf:
        bad = zf.testzip()
        if bad is not None:
            return {"gate": "R0_ingest", "status": "FAILED",
                    "reason": f"corrupt archive member: {bad}",
                    "zip_sha256": digest}
        names = zf.namelist()
        # refuse path traversal before extracting anything
        for n in names:
            if n.startswith("/") or ".." in Path(n).parts:
                return {"gate": "R0_ingest", "status": "FAILED",
                        "reason": f"unsafe path in archive: {n}"}
        zf.extractall(RAW)
    make_read_only(RAW)

    inventory = []
    for p in sorted(RAW.rglob("*")):
        if p.is_file():
            inventory.append({"path": str(p.relative_to(RAW)),
                              "bytes": p.stat().st_size,
                              "sha256": sha256_of(p)})
    return {
        "gate": "R0_ingest", "status": "PASSED",
        "zip_path": str(zp), "zip_sha256": digest, "zip_bytes": zp.stat().st_size,
        "n_files": len(inventory), "raw_dir": str(RAW.relative_to(REPO)),
        "raw_is_read_only": True,
        "inventory": inventory,
    }


def gate_unimplemented(name: str) -> dict:
    return {
        "gate": name, "status": "NOT_RUN",
        "reason": (
            "Implementation is gated on artefacts that are absent: the ZIP's "
            "internal layout, the Seth et al. 2016 experimental parameters, and "
            "REPRODUCTION_GATE_PROTOCOL.md which defines the pass criteria. "
            "Coding against an imagined layout would run and mean nothing."
        ),
        "unresolved_parameters": ["UNRESOLVED_PARAMETER: all -- specification unavailable"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", dest="zip_path", default=None)
    args = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    P11.mkdir(parents=True, exist_ok=True)

    print("[R0] ingest")
    r0 = gate_r0(args.zip_path)
    print(f"     {r0['status']}: {r0.get('reason', r0.get('zip_sha256', ''))}")

    gates = [r0]
    if r0["status"] != "PASSED":
        gates += [gate_unimplemented(g) for g in GATES]
        gates.append({"gate": "R6_scorecard", "status": "NOT_RUN",
                      "reason": "no reproduction results to score"})
        gates.append({"gate": "FO_phase", "status": "NOT_OPENED",
                      "reason": "R1-R5 did not pass; the brief forbids opening "
                                "the FO phase before they do"})
        verdicts = {
            "EPA_REPRODUCTION": "EPA_REPRODUCTION_FAILED",
            "EPA_REPRODUCTION_note": (
                "FAILED here means NOT ATTEMPTED for lack of the dataset, not "
                "attempted-and-mismatched. No experiment was run, so nothing was "
                "compared to the official XLSX."
            ),
            "FO_DIAGNOSTIC_EXTERNAL": "NOT_EVALUATED",
            "FO_RECONSTRUCTIBILITY_EXTERNAL": "NOT_EVALUATED",
            "fo_v2_created": False,
        }
    else:
        print("     ZIP ingested. R1-R5 still require the paper parameters and")
        print("     REPRODUCTION_GATE_PROTOCOL.md; see the report.")
        gates += [gate_unimplemented(g) for g in GATES]
        verdicts = {
            "EPA_REPRODUCTION": "EPA_REPRODUCTION_FAILED",
            "EPA_REPRODUCTION_note": "R0 passed; R1-R5 not implementable without the specification",
            "FO_DIAGNOSTIC_EXTERNAL": "NOT_EVALUATED",
            "FO_RECONSTRUCTIBILITY_EXTERNAL": "NOT_EVALUATED",
            "fo_v2_created": False,
        }

    out = {"gates": gates, "verdicts": verdicts}
    (P11 / "PHASE11_GATES.json").write_text(json.dumps(out, indent=2) + "\n")

    for g in gates:
        print(f"  {g['gate']:24s} {g['status']}")
    print()
    for k, v in verdicts.items():
        if not k.endswith("_note"):
            print(f"  {k} = {v}")
    print(f"\nwrote {(P11 / 'PHASE11_GATES.json').relative_to(REPO)}")
    return 0 if r0["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
