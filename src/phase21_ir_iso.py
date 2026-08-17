"""PHASE 21-IR -- the isolability score, copied VERBATIM from the Phase 20-DR
frozen code (src/phase20_dr_run.py, frozen at commit 894d2d5).

Not a single character of `isolability` below differs from the source. The
module self-checks this at import time by comparing the normalised source text
of the local function with the one extracted from src/phase20_dr_run.py, and
raises if they ever diverge.

fo_metrics is NOT imported. Visibility, Robustness, R7, FO and B* are absent.
"""

from __future__ import annotations

import hashlib
import inspect
import re
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent / "phase20_dr_run.py"


# ---- BEGIN VERBATIM COPY FROM src/phase20_dr_run.py -----------------------
def isolability(X: np.ndarray, y: np.ndarray, cents: dict, Sinv: np.ndarray) -> dict:
    ks = sorted(cents)
    C = np.stack([cents[k] for k in ks])
    diff = X[:, None, :] - C[None, :, :]
    d2 = np.maximum(np.einsum("nkc,cd,nkd->nk", diff, Sinv, diff), 0.0)
    own = np.array([ks.index(v) for v in y])
    mask = np.ones_like(d2, dtype=bool)
    mask[np.arange(len(y)), own] = False
    d_own = np.sqrt(d2[np.arange(len(y)), own])
    d_near = np.sqrt(np.where(mask, d2, np.inf).min(axis=1))
    cd = np.array([[np.sqrt(max((C[i] - C[j]) @ Sinv @ (C[i] - C[j]), 0.0))
                    for j in range(len(ks))] for i in range(len(ks))])
    np.fill_diagonal(cd, np.inf)
    cmin = np.array([cd[own[i]].min() for i in range(len(y))])
    return {"iso_d_nearest": d_near, "iso_margin_ratio": d_near / (d_own + 1.0),
            "iso_centroid_min": cmin}
# ---- END VERBATIM COPY ----------------------------------------------------


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def verify_verbatim() -> dict:
    """Compare this copy against the frozen Phase 20-DR source."""
    src = SRC.read_text()
    m = re.search(r"\ndef isolability\(.*?\n(?=\n\ndef )", src, re.S)
    if m is None:
        raise RuntimeError("isolability introuvable dans phase20_dr_run.py")
    origin = _norm(m.group(0))
    here = _norm(inspect.getsource(isolability))
    if origin != here:
        raise RuntimeError("DIVERGENCE: la copie n'est plus verbatim")
    return {"verbatim": True,
            "sha256_function": hashlib.sha256(origin.encode()).hexdigest(),
            "source_file": str(SRC.relative_to(SRC.parents[1])),
            "sha256_source_file": hashlib.sha256(src.encode()).hexdigest()}


ISO_KEYS = ["iso_d_nearest", "iso_margin_ratio", "iso_centroid_min"]

if __name__ == "__main__":
    import json
    print(json.dumps(verify_verbatim(), indent=2))
