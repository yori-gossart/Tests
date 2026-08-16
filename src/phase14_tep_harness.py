"""
PHASE 14 -- TEP acquisition harness: compile and drive the OFFICIAL simulator.

Nothing here is a reimplementation. temain_mod.f and teprob.f are taken from
camaramm/tennessee-eastman-profBraatz and edited only where the simulator's own
instructions say to edit them:

    temain_mod.f line 220  NPTS    number of 1-second steps
    temain_mod.f line 226  SSPTS   steady-state steps before the disturbance
    temain_mod.f line 367  IDV(k)  which of the 21 disturbances is armed
    temain_mod.f 346-360   output file paths ("To change the file name and path,
                           modify lines 346-360 accordingly")
    teprob.f     line 1187 G       the random-number seed, whose historical
                           values for d00_tr..d21_tr sit in the comments below it

No physics, no controller and no noise model is touched. This module produces
data only; it computes nothing about FO.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

REPO_SRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
                "scratchpad/tep/tennessee-eastman-profBraatz")

# The 15 output files, in the order the simulator's own Table 1 documents them.
MV_FILES = ["TE_data_mv1.dat", "TE_data_mv2.dat", "TE_data_mv3.dat"]
ME_FILES = [f"TE_data_me{i:02d}.dat" for i in range(1, 12)]


def prepare_sources(workdir: Path, idv: int, seed: float, npts: int, sspts: int,
                    noise_scale: float = 1.0) -> None:
    """Apply exactly the four documented edits, and nothing else."""
    workdir.mkdir(parents=True, exist_ok=True)
    main_src = (REPO_SRC / "temain_mod.f").read_text()
    prob_src = (REPO_SRC / "teprob.f").read_text()

    # 1) simulation length and steady-state prefix
    main_src = re.sub(r"NPTS = \d+", f"NPTS = {npts}", main_src, count=1)
    main_src = re.sub(r"SSPTS = 3600 \* 8", f"SSPTS = {sspts}", main_src, count=1)

    # 2) which disturbance is armed. IDV=0 means normal operation: the armed
    #    line is then neutralised rather than deleted, keeping line numbers.
    if idv == 0:
        main_src = main_src.replace("                 IDV(12)=1",
                                    "                 IDV(12)=0")
    else:
        main_src = main_src.replace("                 IDV(12)=1",
                                    f"                 IDV({idv})=1")

    # 3) output paths: the header explicitly sanctions changing these, and the
    #    literal '~' is never expanded by Fortran, so it must change anyway.
    main_src = main_src.replace("FILE='~/", "FILE='").replace("STATUS='new'", "STATUS='unknown'")

    # 4) the seed
    prob_src = re.sub(r"G=4651207995\.D0", f"G={seed:.1f}D0", prob_src, count=1)

    # 5) the MEASUREMENT-NOISE LEVEL. XNS(1..41) are the process's own declared
    #    per-channel measurement standard deviations, applied additively by
    #    TESUB6. Scaling them changes the noise LEVEL while leaving the physics,
    #    the controllers and the disturbances untouched -- this is the axis FO's
    #    sigma_eval is defined against, and the one B* exists to survive.
    if noise_scale != 1.0:
        def _scale(m: re.Match) -> str:
            return f"XNS({m.group(1)})={float(m.group(2)) * noise_scale:.10f}D0"
        prob_src = re.sub(r"XNS\((\d+)\)=([0-9.]+)D0", _scale, prob_src)

    (workdir / "temain_mod.f").write_text(main_src)
    (workdir / "teprob.f").write_text(prob_src)


def compile_sim(workdir: Path) -> dict:
    r = subprocess.run(["gfortran", "-std=legacy", "-O2", "-o", "te_sim",
                        "temain_mod.f", "teprob.f"],
                       cwd=workdir, capture_output=True, text=True, timeout=900)
    return {"returncode": r.returncode, "stderr": r.stderr.strip()[:400],
            "binary_exists": (workdir / "te_sim").exists()}


def run_sim(workdir: Path, timeout: int = 1800) -> dict:
    for f in list(workdir.glob("TE_data_*.dat")):
        f.unlink()
    r = subprocess.run(["./te_sim"], cwd=workdir, capture_output=True, text=True,
                       timeout=timeout)
    return {"returncode": r.returncode, "stdout_tail": r.stdout.strip()[-200:],
            "stderr": r.stderr.strip()[:400]}


def assemble(workdir: Path) -> np.ndarray:
    """Reassemble the 15 files into the (n_samples, 52) layout of the .dat sets.

    The published d*.dat files carry XMEAS(1..41) then XMV(1..11); XMV(12), the
    agitator speed, is held constant by the controller and is not among the 52.
    """
    me = [np.loadtxt(workdir / f, ndmin=2) for f in ME_FILES]
    mv = [np.loadtxt(workdir / f, ndmin=2) for f in MV_FILES]
    xmeas = np.hstack(me)                 # 41 columns
    xmv = np.hstack(mv)                   # 12 columns
    n = min(xmeas.shape[0], xmv.shape[0])
    return np.hstack([xmeas[:n, :41], xmv[:n, :11]])


def generate(workdir: Path, idv: int, seed: float, npts: int = 172800,
             sspts: int = 3600 * 8, noise_scale: float = 1.0) -> tuple[np.ndarray, dict]:
    prepare_sources(workdir, idv, seed, npts, sspts, noise_scale)
    build = compile_sim(workdir)
    if build["returncode"] != 0:
        raise RuntimeError(f"compile failed: {build}")
    run = run_sim(workdir)
    if run["returncode"] != 0:
        raise RuntimeError(f"run failed: {run}")
    return assemble(workdir), {"build": build, "run": run, "idv": idv, "seed": seed,
                               "noise_scale": noise_scale}
