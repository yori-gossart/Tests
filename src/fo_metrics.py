"""
PHASE B -- minimal diagnostic repair of the FO metric. Not a new optimiser.

TWO METRICS
-----------
B_dynamic  -- the historical FO-v1 metric, reproduced exactly:

    d_S(z)   = max_t max_{j in S} |dp[z,j,t]| / sigma_j
    E_kappa  = { z : d_R(z) >= kappa }              R = the rich reference
    B(S)     = P[ d_S(z) <= eta | z in E_kappa ]

    Its conditioning set E_kappa is recomputed from whatever sigma it is handed.
    That is the defect: sigma is a property of the MEASUREMENT CONDITIONS, so the
    population of scenarios the metric claims to be about silently changes when
    the noise changes. Two values of B computed under different noise are not
    comparable, because they are fractions of different denominators. Worse, in
    the direction that flatters the metric: raising sigma shrinks E_kappa to the
    loudest scenarios, which are exactly the easy ones, so B improves for a
    reason that has nothing to do with the sensor set.

B_star     -- support-frozen. The scenario support is fixed ONCE, from a rich
    reference and a nominal TRAIN noise, and then never moves:

    E*       = { z : d_R(z; sigma_train) >= kappa }     frozen once
    B*(S)    = P[ d_S(z; sigma_eval) <= eta | z in E* ]

    The denominator |E*| is a constant of the study. Only the numerator responds
    to evaluation-time noise, so B* values are comparable across noise levels,
    across networks, and across time.

test_b_star_denominator_invariance() proves the denominator claim by
construction rather than by assertion, and shows B_dynamic failing the same
test.

B* IS NOT USED TO CHOOSE ANY HYPER-PARAMETER ON ANY TEST SET. It is defined
here so that Phase E can ask whether an FO-style score has diagnostic value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def visibility(delta: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """d[z, j] = max_t |dp[z,j,t]| / sigma_j, from a (n_scen, n_sensors, T) tensor."""
    return np.abs(delta).max(axis=2) / sigma[None, :]


def b_dynamic(delta: np.ndarray, sigma: np.ndarray, subset, kappa: float,
              eta: float) -> dict:
    """FO-v1 metric. The support is recomputed from `sigma` every call."""
    vis = visibility(delta, sigma)
    eligible = vis.max(axis=1) >= kappa          # <- moves with sigma
    if eligible.sum() == 0:
        return {"B": float("nan"), "support_size": 0, "n_blind": 0}
    d_S = vis[eligible][:, list(subset)].max(axis=1)
    return {
        "B": float(np.mean(d_S <= eta)),
        "support_size": int(eligible.sum()),
        "n_blind": int(np.sum(d_S <= eta)),
    }


@dataclass
class FrozenSupport:
    """The scenario support E*, fixed once and carried around explicitly."""

    mask: np.ndarray          # boolean over scenarios
    kappa: float
    sigma_train: np.ndarray
    reference_sensors: list[int]

    @property
    def size(self) -> int:
        return int(self.mask.sum())


def freeze_support(delta: np.ndarray, sigma_train: np.ndarray, kappa: float,
                   reference_sensors: list[int] | None = None) -> FrozenSupport:
    """Fix E* once, from the rich reference under nominal TRAIN noise."""
    n_sensors = delta.shape[1]
    ref = list(range(n_sensors)) if reference_sensors is None else list(reference_sensors)
    vis = visibility(delta, sigma_train)
    return FrozenSupport(
        mask=vis[:, ref].max(axis=1) >= kappa,
        kappa=float(kappa),
        sigma_train=np.asarray(sigma_train, dtype=float).copy(),
        reference_sensors=ref,
    )


def b_star(delta: np.ndarray, sigma_eval: np.ndarray, subset,
           support: FrozenSupport, eta: float) -> dict:
    """Support-frozen metric. Denominator is `support.size`, always."""
    if support.size == 0:
        return {"B_star": float("nan"), "support_size": 0, "n_blind": 0}
    vis = visibility(delta, sigma_eval)
    d_S = vis[support.mask][:, list(subset)].max(axis=1)
    return {
        "B_star": float(np.mean(d_S <= eta)),
        "support_size": support.size,          # invariant by construction
        "n_blind": int(np.sum(d_S <= eta)),
    }


# ---------------------------------------------------------------------------
# Unit test
# ---------------------------------------------------------------------------


def test_b_star_denominator_invariance(seed: int = 0, verbose: bool = True) -> dict:
    """B*'s denominator must not move when the evaluation noise moves; B's does.

    Uses a synthetic tensor so the test depends on no data file.
    """
    rng = np.random.default_rng(seed)
    n_scen, n_sensors, n_t = 400, 12, 7
    # Scenario amplitudes must span several decades, otherwise every scenario
    # sits far above kappa at every noise level tested, the dynamic support
    # never moves, and the test passes vacuously without exercising the defect.
    amplitude = 10.0 ** rng.uniform(-3.0, 0.0, size=(n_scen, 1, 1))
    shape = rng.lognormal(mean=0.0, sigma=0.5, size=(n_scen, n_sensors, n_t))
    delta = amplitude * shape
    sigma_train = np.full(n_sensors, 0.05)
    subset = [0, 3, 5, 9]
    kappa = eta = 3.0

    support = freeze_support(delta, sigma_train, kappa)
    multipliers = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]

    dyn_supports, star_supports, dyn_vals, star_vals = [], [], [], []
    for m in multipliers:
        sigma_eval = sigma_train * m
        d = b_dynamic(delta, sigma_eval, subset, kappa, eta)
        s = b_star(delta, sigma_eval, subset, support, eta)
        dyn_supports.append(d["support_size"])
        star_supports.append(s["support_size"])
        dyn_vals.append(d["B"])
        star_vals.append(s["B_star"])

    star_invariant = len(set(star_supports)) == 1
    dyn_varies = len(set(dyn_supports)) > 1

    result = {
        "noise_multipliers": multipliers,
        "B_dynamic_support_sizes": dyn_supports,
        "B_star_support_sizes": star_supports,
        "B_dynamic_values": [round(v, 4) for v in dyn_vals],
        "B_star_values": [round(v, 4) for v in star_vals],
        "B_star_denominator_invariant": bool(star_invariant),
        "B_dynamic_denominator_varies": bool(dyn_varies),
        "PASS": bool(star_invariant and dyn_varies),
    }
    if verbose:
        print("noise x        :", multipliers)
        print("B      support :", dyn_supports, "  <- moves: the defect")
        print("B*     support :", star_supports, "  <- frozen by construction")
        print("B      value   :", result["B_dynamic_values"])
        print("B*     value   :", result["B_star_values"])
        print("PASS           :", result["PASS"])
    if not result["PASS"]:
        raise AssertionError(f"B* invariance test failed: {result}")
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(test_b_star_denominator_invariance(), indent=2))
