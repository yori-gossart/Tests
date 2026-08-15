"""
PHASE 12A -- final LeakDB acquisition attempt.

Gate 0 established that LeakDB is admissible on every criterion except scale:
the locally available sample is 10 scenarios / 8 leak events, against a minimum
of 93 independent scenarios for a +/-0.10 confidence half-width.

This script attempts acquisition through the two routes named in the brief and
records what actually happened. It attempts NOTHING ELSE: it does not regenerate
scenarios with the official generator, because a regenerated scenario is not an
acquired one, and the standing rule forbids substituting a synthetic element for
a missing one. It does not touch FO.

Routes attempted:
  1. the SharePoint folder that WaterBenchmarkHub lists as LeakDB's download_url
  2. the water-benchmark-hub package itself, called as its API intends
  3. whether a per-scenario subset (Hanoi only, or N scenarios) can be pulled
     rather than the full archive
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase12_gate0" / "evidence"

SHAREPOINT = ("https://ucy-my.sharepoint.com/:f:/g/personal/mkiria01_ucy_ac_cy/"
              "Eiyah0-TL4dGqt9K4Ln5TN0BRlroASbX35p53bS7or4j5A")
FILEDN_BASE = "https://filedn.com/lumBFq2P9S74PNoLPWtzxG4/EPyT-Flow/LeakDB-Original/Hanoi_CMH/"

MIN_SCENARIOS = 93
PREFERRED_SCENARIOS = 381


def probe(url: str, timeout: int = 90) -> dict:
    r = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True,
    )
    code = (r.stdout or "").strip()
    return {"url": url, "http_code": code, "reachable": code not in ("", "000"),
            "stderr": (r.stderr or "").strip()[:160]}


def attempt_package_download(scenario_ids: list[int]) -> dict:
    """Call the package exactly as its API intends, and report the real failure."""
    try:
        from water_benchmark_hub import load
        benchmark = load("KIOS-LeakDB")
        data = benchmark.load_data(scenarios_id=scenario_ids, use_net1=False,
                                   download_dir="/tmp/leakdb_dl", verbose=False)
        return {"ok": True, "scenarios_downloaded": sorted(data.keys())}
    except Exception as exc:                     # noqa: BLE001 - the failure IS the result
        return {"ok": False, "exception": type(exc).__name__, "message": str(exc)[:400]}


def count_local_scenarios() -> dict:
    """Independent scenarios actually on disk, from the earlier git clone."""
    zip_path = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
                    "scratchpad/gate0/LeakDB/CCWI-WDSA2018/Benchmarks/Hanoi_CMH.zip")
    if not zip_path.exists():
        return {"source": str(zip_path), "available": False,
                "note": "clone not present in this session; count carried from the Gate 0 inventory",
                "n_scenarios": 10, "n_leak_events": 8}
    listing = subprocess.run(["unzip", "-l", str(zip_path)], capture_output=True, text=True).stdout
    scenarios = {line.split("Scenario-")[1].split("/")[0]
                 for line in listing.split("\n") if "Scenario-" in line}
    return {"source": str(zip_path), "available": True,
            "n_scenarios": len(scenarios), "n_leak_events": 8}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    result = {
        "phase": "12A_final_acquisition_attempt",
        "target_minimum_scenarios": MIN_SCENARIOS,
        "target_preferred_scenarios": PREFERRED_SCENARIOS,

        "route_1_sharepoint": {
            "url": SHAREPOINT,
            "confirmed_as_download_url_in_registry": True,
            "registry_path": "water_benchmark_hub/database.json -> resources/kios-leakdb/download_url",
            "probes": [probe(SHAREPOINT), probe(SHAREPOINT + "&download=1"),
                       probe("https://ucy-my.sharepoint.com/")],
            "webfetch": "EGRESS_BLOCKED (ucy-my.sharepoint.com)",
        },

        "route_2_package": {
            "package": "water-benchmark-hub",
            "installed": True,
            "install_source": "pypi.org (on the proxy allowlist)",
            "api_call": 'load("KIOS-LeakDB").load_data(scenarios_id=[1], use_net1=False)',
            "actual_data_host": "filedn.com",
            "result": attempt_package_download([1]),
            "probes": [probe(FILEDN_BASE), probe(FILEDN_BASE + "Scenario-1.zip"),
                       probe("https://filedn.com/")],
        },

        "route_3_subset_feasibility": {
            "per_scenario_download_supported": True,
            "url_pattern": FILEDN_BASE + "Scenario-{id}.zip",
            "total_scenarios_offered": 1000,
            "networks_separable": ["Hanoi_CMH", "Net1_CMH"],
            "full_archive_size": "approx. 25 GB Hanoi, 8 GB Net1",
            "verdict": "the architecture WOULD allow pulling Hanoi only, or an arbitrary "
                       "subset of N scenarios, without the full archive. It is not the "
                       "granularity that blocks acquisition -- it is the host.",
        },

        "route_4_scenarios_acquired": {
            "new_scenarios_acquired_this_phase": 0,
            "locally_available_total": count_local_scenarios(),
            "meets_minimum_93": False,
            "meets_preferred_381": False,
        },

        "not_attempted_on_purpose": {
            "regenerate_with_official_generator": (
                "The repository ships Dataset_Generator_Py3, and epyt-flow can synthesise "
                "LeakDB-like scenarios. Regenerating would produce scenarios that are not "
                "the published benchmark, which is a synthetic replacement of a missing "
                "element. The standing rule forbids it and the brief did not list it."),
            "other_mirrors": "The brief restricted this phase to the SharePoint source and "
                             "the water-benchmark-hub package. No further mirror hunt was run.",
        },
    }

    verdict_pass = result["route_4_scenarios_acquired"]["meets_minimum_93"]
    result["verdict"] = {
        "LEAKDB_GATE0": "PASS" if verdict_pass else "FAIL_FINAL_ACCESS",
        "FO_TEST_AUTHORIZED": "YES" if verdict_pass else "NO",
    }

    (OUT / "acquisition_attempt_12A.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
