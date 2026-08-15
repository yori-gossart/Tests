"""
PHASE 12A -- Gate 0 accessibility and eligibility probe for the next external
benchmark. Candidates: KIOS-Research/LeakDB (primary), GraphLeak (secondary).

This script RECORDS what was actually tested. It does not run any experiment,
does not touch FO, and does not generate or substitute any data. Every number
it writes was produced by a real call: a git ls-remote, an HTTP request, an
archive listing, an EPANET simulation, or a closed-form CI computation.

The one thing it deliberately does NOT do is paper over a missing artefact with
a regenerated one. The EPA branch failed precisely there, and the rule for this
phase is explicit: no synthetic replacement of a missing element.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase12_gate0" / "evidence"

# Where the two candidate clones live. Kept outside the repo: they are 160 MB
# and 6.6 GB respectively and are re-clonable from the recorded commit.
SCRATCH = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/gate0")


def probe_url(url: str, timeout: int = 60) -> dict:
    """One real HTTP request. HTTP=000 means the proxy refused the tunnel."""
    r = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True,
    )
    code = (r.stdout or "").strip()
    return {"url": url, "http_code": code,
            "reachable": code not in ("", "000"),
            "stderr": (r.stderr or "").strip()[:200]}


def probe_git(url: str) -> dict:
    r = subprocess.run(["git", "ls-remote", url], capture_output=True, text=True, timeout=180)
    head = (r.stdout or "").split("\n")[0].split("\t")[0] if r.returncode == 0 else None
    return {"url": url, "reachable": r.returncode == 0, "head_commit": head,
            "stderr": (r.stderr or "").strip()[:200]}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def hanley_mcneil_se(auc: float, n_pos: int, n_neg: int) -> float:
    q1, q2 = auc / (2 - auc), 2 * auc * auc / (1 + auc)
    return float(np.sqrt((auc * (1 - auc) + (n_pos - 1) * (q1 - auc ** 2)
                          + (n_neg - 1) * (q2 - auc ** 2)) / (n_pos * n_neg)))


def statistical_power_leakdb() -> dict:
    """What a verdict on the LOCALLY AVAILABLE LeakDB sample could resolve.

    The independent unit is the scenario, not the timestep: the 17520 timesteps
    inside a scenario share one network realisation, one demand series and one
    leak, so they are not 17520 independent observations.
    """
    out = {"n_scenarios": 10, "n_leak_free": 4, "n_leaky": 6, "n_leak_events": 8,
           "n_junctions": 31, "independent_unit": "scenario"}
    out["wilson_ci_95"] = {
        f"n={n},k={k}": {"p": round(k / n, 3),
                         "ci": [round(v, 3) for v in wilson(k, n)],
                         "half_width": round((wilson(k, n)[1] - wilson(k, n)[0]) / 2, 3)}
        for n in (8, 10) for k in (n // 2, int(0.8 * n))
    }
    out["b_star_granularity"] = {
        "support_size_max": 8,
        "distinct_attainable_values": [round(i / 8, 3) for i in range(9)],
        "smallest_resolvable_difference": 0.125,
        "note": "B* is a proportion over the frozen support E*; with |E*| <= 8 "
                "two sensor designs cannot differ by less than 12.5 points.",
    }
    out["auroc_ci_95"] = {
        f"n_pos={p},n_neg={q},auc={a}": {
            "se": round(hanley_mcneil_se(a, p, q), 3),
            "ci": [round(max(0.0, a - 1.96 * hanley_mcneil_se(a, p, q)), 3),
                   round(min(1.0, a + 1.96 * hanley_mcneil_se(a, p, q)), 3)]}
        for (p, q) in [(4, 4), (6, 2), (8, 2)] for a in (0.75, 0.90)
    }
    req = {}
    for target in (0.10, 0.05):
        n = 1
        while True:
            lo, hi = wilson(n // 2, n)
            if (hi - lo) / 2 <= target:
                break
            n += 1
        req[f"half_width_{target}"] = n
    out["scenarios_required"] = req
    lo, hi = wilson(2, 3)
    out["held_out_split"] = {
        "split": "50/50 over scenarios -> 3 leaky train / 3 leaky test",
        "test_ci_at_k2_n3": [round(lo, 3), round(hi, 3)],
        "ci_width": round(hi - lo, 3),
    }
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    access = {
        "git_remotes": [probe_git(u) for u in [
            "https://github.com/KIOS-Research/LeakDB",
            "https://github.com/gasiepgodoy/WDN-Models-and-Data-Sets",
        ]],
        "http_endpoints": [probe_url(u) for u in [
            "https://zenodo.org/api/records/13985057",
            "https://zenodo.org/record/1313116",
            "https://doi.org/10.5281/zenodo.1313116",
            "https://drive.google.com/drive/folders/1Q_JQO2OZhejQEd0BMdx0UGcRaDo85ENC",
            "https://www.sba.org.br/cba2024/papers/paper_7042.pdf",
            "https://raw.githubusercontent.com/KIOS-Research/LeakDB/master/README.md",
        ]],
        "note": "http_code 000 = the agent egress proxy refused the CONNECT tunnel "
                "(403), not a dead host. git over https to github.com is allowed; "
                "zenodo.org, drive.google.com and sba.org.br are not.",
    }
    (OUT / "accessibility_probe.json").write_text(json.dumps(access, indent=2))
    print(json.dumps(access, indent=2))

    power = statistical_power_leakdb()
    (OUT / "statistical_power_leakdb.json").write_text(json.dumps(power, indent=2))
    print("\n--- statistical power on the locally available LeakDB sample ---")
    print(json.dumps(power, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
