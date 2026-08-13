"""
Sensor-selection methods: the FO criterion and eight baselines.

Every method consumes the SAME substrate -- the leak-sensitivity library built
by src/sensitivity.py -- and returns a subset S of the 33 candidate pressure
sensor locations for a given budget k. Nothing here reads any 2019 quantity.

NOTATION
--------
The library gives Delta p[z, j, t]: the pressure drop (m) at candidate sensor j,
at operating snapshot t, caused by a reference-size leak in scenario z.

Per-unit-leak design matrix, averaged over the operating snapshots:

    H[j, z] = mean_t Delta p[z, j, t] / q_ref(z)          [m per m^3/h]

with q_ref(z) the mean leak flow of that scenario. Linear-Gaussian measurement
model, theta the vector of (unknown) leak magnitudes:

    y_S = H_S theta + eps,      eps ~ N(0, sigma^2 I)

FO CRITERION (section 4 of the protocol)
----------------------------------------
Visibility of scenario z under sensor set S, in units of sensor noise:

    d_S(z) = max_t max_{j in S} |Delta p[z, j, t]| / sigma_j

Rich reference R = all 33 candidate locations, d_ref(z) = d_R(z). Then

    E_kappa       = { z : d_ref(z) >= kappa }
    B_kappa_eta(S) = P[ d_S(z) <= eta | z in E_kappa ]

B is the false-forgetting rate: the share of scenarios the rich reference can
see that S cannot. Selection minimises B, then breaks ties on the 5th
percentile of visibility over E_kappa, then the 10th, then the mean.

WHY THE CLASSICAL OED CRITERIA NEED AN EXPLICIT ADAPTATION
----------------------------------------------------------
theta has n_scen = 782 components while k <= 12, so the Fisher information
M(S) = H_S^T H_S / sigma^2 has rank <= 12 and is singular. det M(S) = 0,
trace M(S)^-1 = inf and lambda_min M(S) = 0 for EVERY candidate S, so classical
D-, A- and E-optimality are not merely hard to compute here, they are undefined
and would rank all subsets equally. Two adaptations restore well-posedness and
both are implemented and reported under names that say which one they are:

  (a) Bayesian-regularised. Prior theta ~ N(0, tau^2 I) makes the posterior
      precision  M(S) + I/tau^2  positive definite. D: max log det; A: min
      trace of inverse; E: max lambda_min. These are the exact Bayesian
      D/A/E-optimal designs for that prior, not approximations of the
      classical ones.
  (b) Rank-r reduced. Project theta onto the leading r right singular vectors
      of H (r <= min budget = 4), giving H~_S in R^{k x r}. Classical D/A/E
      optimality is well defined on that r-dimensional subspace for k >= r.

Bayesian information gain is the mutual information I(y_S; theta) for the same
linear-Gaussian prior, 0.5 log det(I + tau^2/sigma^2 H_S^T H_S); it coincides
with adaptation (a)'s D-criterion up to an additive constant, and is reported
separately because the protocol asks for both.

OPTIMISER
---------
Subset selection is combinatorial, and the criteria differ enormously in cost:
scoring one subset is a 4x4 determinant for Bayesian D but a 400x400 Gram for
the goal-oriented criterion. Enumerating C(33,4)=40920 subsets is therefore
affordable for some criteria and not for others.

Rather than let the search effort vary by method -- which would confound the
selection rule with how hard each was optimised -- EVERY method at EVERY budget
uses greedy forward selection. The optimality gap that choice costs is measured
rather than assumed: exhaustive_fo_blindspot() enumerates all 40920 subsets at
k=4 for the FO criterion using a bitset popcount (~0.3 s instead of minutes) and
reports how far greedy fell short. That diagnostic is reported on its own and is
never substituted into the comparison.
"""

from __future__ import annotations

import itertools
import json
import time
from math import comb
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

BUDGETS = (4, 6, 8, 10, 12)
EXHAUSTIVE_MAX_COMBINATIONS = 200_000  # k=4 -> 40920; k=6 -> 1.1M (excluded)


# ---------------------------------------------------------------------------
# Library container
# ---------------------------------------------------------------------------


@dataclass
class Library:
    delta: np.ndarray          # (n_scen, n_sensors, n_snapshots), metres
    leak_flow_cmh: np.ndarray  # (n_scen, n_snapshots)
    scenarios: np.ndarray
    sensors: np.ndarray
    times_s: np.ndarray
    diameter_m: float
    sigma: np.ndarray = field(default=None)  # (n_sensors,), metres

    @classmethod
    def load(cls, path: Path) -> "Library":
        z = np.load(path, allow_pickle=False)
        return cls(
            delta=z["delta"].astype(np.float64),
            leak_flow_cmh=z["leak_flow_cmh"].astype(np.float64),
            scenarios=z["scenarios"],
            sensors=z["sensors"],
            times_s=z["times_s"],
            diameter_m=float(z["diameter_m"]),
        )

    @property
    def n_scen(self) -> int:
        return self.delta.shape[0]

    @property
    def n_sensors(self) -> int:
        return self.delta.shape[1]

    def visibility(self, sigma: np.ndarray) -> np.ndarray:
        """d[z, j] = max_t |Delta p[z,j,t]| / sigma_j -- per-sensor visibility."""
        return np.abs(self.delta).max(axis=2) / sigma[None, :]

    def design_matrix(self) -> np.ndarray:
        """H[j, z] = mean_t Delta p[z,j,t] / mean_t q_ref(z)   [m per m^3/h]."""
        q = self.leak_flow_cmh.mean(axis=1)
        q = np.where(q > 1e-9, q, np.nan)
        H = self.delta.mean(axis=2).T / q[None, :]
        return np.nan_to_num(H, nan=0.0, posinf=0.0, neginf=0.0)


# ---------------------------------------------------------------------------
# FO criterion
# ---------------------------------------------------------------------------


def fo_objective(vis: np.ndarray, eligible: np.ndarray, kappa: float, eta: float):
    """Return a callable scoring a subset with the FO lexicographic objective.

    vis      : (n_scen, n_sensors) per-sensor visibility d_{j}(z)
    eligible : boolean mask of E_kappa
    Lower is better on the first element; the remaining three are negated
    percentiles/mean so that the whole tuple is minimised lexicographically.
    """
    vis_e = vis[eligible]  # (|E|, n_sensors)

    def score(subset: tuple[int, ...]):
        d_S = vis_e[:, list(subset)].max(axis=1)  # d_S(z) for z in E_kappa
        blind = float(np.mean(d_S <= eta))
        p05 = float(np.percentile(d_S, 5))
        p10 = float(np.percentile(d_S, 10))
        mean = float(np.mean(d_S))
        return (blind, -p05, -p10, -mean)

    _ = kappa  # kappa enters through `eligible`; kept in the signature for clarity
    return score


def fo_report(vis: np.ndarray, eligible: np.ndarray, subset, eta: float) -> dict:
    d_S = vis[eligible][:, list(subset)].max(axis=1)
    return {
        "B_blind_spot_rate": float(np.mean(d_S <= eta)),
        "visibility_p05": float(np.percentile(d_S, 5)),
        "visibility_p10": float(np.percentile(d_S, 10)),
        "visibility_mean": float(np.mean(d_S)),
        "visibility_min": float(np.min(d_S)),
        "n_eligible_scenarios": int(eligible.sum()),
    }


# ---------------------------------------------------------------------------
# OED criteria (all take H_S: k x n_param, return "higher is better")
# ---------------------------------------------------------------------------


def _gram(H_S: np.ndarray, sigma: float, tau: float) -> np.ndarray:
    """I_k + (tau^2/sigma^2) H_S H_S^T -- the k x k object every Bayesian
    criterion below reduces to."""
    k = H_S.shape[0]
    return np.eye(k) + (tau**2 / sigma**2) * (H_S @ H_S.T)


def crit_bayes_d(H_S, sigma, tau):
    """Bayesian D-optimality, log det of the posterior precision.

    Evaluated through the determinant identity
        det(H^T H/sigma^2 + I_n/tau^2) = tau^(-2n) det(I_k + tau^2/sigma^2 H H^T)
    so an n x n determinant with n = 782 becomes a k x k one with k <= 12. The
    dropped tau^(-2n) factor is constant across subsets and does not affect the
    ranking. This is exact, not an approximation.
    """
    sign, logdet = np.linalg.slogdet(_gram(H_S, sigma, tau))
    return logdet if sign > 0 else -np.inf


def crit_bayes_a(H_S, sigma, tau):
    """Bayesian A-optimality, minimise trace of the posterior covariance.

    By Woodbury, with M = I_n/tau^2 + H^T H/sigma^2,
        trace(M^-1) = tau^2 n - (tau^4/sigma^2) trace(G^-1 H H^T)
    where G = I_k + (tau^2/sigma^2) H H^T. The tau^2 n term is constant across
    subsets, so only the second term ranks designs. Exact, and k x k.
    """
    G = _gram(H_S, sigma, tau)
    HHt = H_S @ H_S.T
    return float((tau**4 / sigma**2) * np.trace(np.linalg.solve(G, HHt)))


def crit_bayes_e(H_S, sigma, tau):
    """E-criterion on the OBSERVABLE subspace: smallest eigenvalue of
    I_k + (tau^2/sigma^2) H_S H_S^T.

    Deliberately not called Bayesian E-optimal. The literal Bayesian E-optimal
    criterion is degenerate here: for k < n the Gram H_S^T H_S is rank-deficient,
    so lambda_min(H_S^T H_S / sigma^2 + I_n / tau^2) = 1/tau^2 for EVERY subset
    and the criterion ranks all designs identically. What remains informative is
    the worst-conditioned direction the sensors actually observe, which is what
    this returns. The degeneracy is reported rather than hidden.
    """
    return float(np.linalg.eigvalsh(_gram(H_S, sigma, tau))[0])


def crit_infogain(H_S, sigma, tau):
    """I(y_S; theta) = 0.5 log det(I + tau^2/sigma^2 H_S H_S^T), k x k form."""
    k = H_S.shape[0]
    M = np.eye(k) + (tau**2 / sigma**2) * (H_S @ H_S.T)
    sign, logdet = np.linalg.slogdet(M)
    return 0.5 * logdet if sign > 0 else -np.inf


def crit_classical_d(H_S):
    sign, logdet = np.linalg.slogdet(H_S.T @ H_S)
    return logdet if sign > 0 else -np.inf


def crit_classical_a(H_S):
    M = H_S.T @ H_S
    try:
        return -float(np.trace(np.linalg.inv(M)))
    except np.linalg.LinAlgError:
        return -np.inf


def crit_classical_e(H_S):
    return float(np.linalg.eigvalsh(H_S.T @ H_S)[0])


def crit_goal_oriented(Hn_S: np.ndarray, sample_idx: np.ndarray) -> float:
    """Goal-oriented OED for LOCALISATION: maximise the minimum angular
    separation between scenario signatures as seen by S. Two scenarios whose
    normalised signatures coincide on S are indistinguishable no matter how
    precisely they are measured, which is the failure mode localisation cares
    about -- distinct from D/A/E-optimality, which target magnitude variance.
    """
    A = Hn_S[:, sample_idx]                      # k x m
    nrm = np.linalg.norm(A, axis=0)
    nrm = np.where(nrm > 1e-12, nrm, 1.0)
    U = A / nrm[None, :]
    gram = U.T @ U
    np.fill_diagonal(gram, -np.inf)
    return -float(gram.max())                    # minimise the worst cosine


# ---------------------------------------------------------------------------
# Optimisers
# ---------------------------------------------------------------------------


def greedy_forward(n_sensors: int, k: int, score, minimise: bool):
    chosen: list[int] = []
    for _ in range(k):
        best, best_val = None, None
        for c in range(n_sensors):
            if c in chosen:
                continue
            val = score(tuple(sorted(chosen + [c])))
            if best_val is None or (val < best_val if minimise else val > best_val):
                best, best_val = c, val
        chosen.append(best)
    return tuple(sorted(chosen))


def exhaustive(n_sensors: int, k: int, score, minimise: bool):
    best, best_val = None, None
    for subset in itertools.combinations(range(n_sensors), k):
        val = score(subset)
        if best_val is None or (val < best_val if minimise else val > best_val):
            best, best_val = subset, val
    return best


def optimise(n_sensors: int, k: int, score, minimise: bool, allow_exhaustive: bool):
    from math import comb

    if allow_exhaustive and comb(n_sensors, k) <= EXHAUSTIVE_MAX_COMBINATIONS:
        return exhaustive(n_sensors, k, score, minimise), "exhaustive"
    return greedy_forward(n_sensors, k, score, minimise), "greedy_forward"


_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.int32)


def exhaustive_fo_blindspot(vis: np.ndarray, eligible: np.ndarray, eta: float,
                            k: int) -> dict:
    """Exhaustively minimise the FO blind-spot rate B over all C(33, k) subsets.

    A scenario is blind to S when no sensor in S sees it above eta, so B depends
    only on the boolean matrix seen[z, j] = vis[z, j] > eta. Packing that matrix
    into bits turns each subset evaluation into a handful of uint8 ORs plus a
    popcount table lookup, which is what makes full enumeration affordable
    (~0.3 s for k=4 rather than minutes).

    Ties on B are broken on the 5th percentile of visibility, then the 10th,
    then the mean -- the protocol's order -- but only among the tied subsets.
    """
    vis_e = vis[eligible]
    seen = vis_e > eta
    n_elig = seen.shape[0]
    packed = np.packbits(seen.T, axis=1)  # (n_sensors, ceil(n_elig/8))

    best_blind = None
    tied: list[tuple[int, ...]] = []
    for subset in itertools.combinations(range(seen.shape[1]), k):
        acc = packed[subset[0]].copy()
        for j in subset[1:]:
            acc |= packed[j]
        blind = n_elig - int(_POPCOUNT[acc].sum())
        if best_blind is None or blind < best_blind:
            best_blind, tied = blind, [subset]
        elif blind == best_blind:
            tied.append(subset)

    def tiebreak(s):
        d = vis_e[:, list(s)].max(axis=1)
        return (-np.percentile(d, 5), -np.percentile(d, 10), -d.mean())

    best = min(tied, key=tiebreak)
    return {
        "subset": list(best),
        "B_blind_spot_rate": best_blind / n_elig,
        "n_subsets_enumerated": comb(seen.shape[1], k),
        "n_tied_at_optimum": len(tied),
    }


# ---------------------------------------------------------------------------
# Topological baselines
# ---------------------------------------------------------------------------


def build_graph_distances(inp_path: Path, sensor_ids: list[str]) -> np.ndarray:
    """All-pairs shortest-path distance (pipe length weighted) between sensors."""
    import networkx as nx
    import wntr

    wn = wntr.network.WaterNetworkModel(str(inp_path))
    G = nx.Graph()
    for lname, link in wn.links():
        length = getattr(link, "length", 0.0) or 1.0
        G.add_edge(link.start_node_name, link.end_node_name, weight=float(length))
    D = np.zeros((len(sensor_ids), len(sensor_ids)))
    for i, a in enumerate(sensor_ids):
        lengths = nx.single_source_dijkstra_path_length(G, a, weight="weight")
        for j, b in enumerate(sensor_ids):
            D[i, j] = lengths.get(b, np.inf)
    return D


def betweenness_centrality(inp_path: Path, sensor_ids: list[str]) -> np.ndarray:
    import networkx as nx
    import wntr

    wn = wntr.network.WaterNetworkModel(str(inp_path))
    G = nx.Graph()
    for lname, link in wn.links():
        length = getattr(link, "length", 0.0) or 1.0
        G.add_edge(link.start_node_name, link.end_node_name, weight=float(length))
    bc = nx.betweenness_centrality(G, weight="weight", k=min(200, G.number_of_nodes()), seed=0)
    return np.array([bc.get(s, 0.0) for s in sensor_ids])


def maxmin_dispersion(D: np.ndarray, k: int) -> tuple[int, ...]:
    """Greedy max-min dispersion: repeatedly add the location farthest from the
    current set. Seeded with the pair at maximum separation."""
    n = D.shape[0]
    finite = np.where(np.isfinite(D), D, 0.0)
    i, j = np.unravel_index(np.argmax(finite), finite.shape)
    chosen = [int(i), int(j)]
    while len(chosen) < k:
        rest = [c for c in range(n) if c not in chosen]
        gains = [min(finite[c, s] for s in chosen) for c in rest]
        chosen.append(int(rest[int(np.argmax(gains))]))
    return tuple(sorted(chosen[:k]))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def select_all(
    lib: Library,
    sigma: np.ndarray,
    kappa: float,
    eta: float,
    tau: float,
    n_random: int,
    seed: int,
    inp_path: Path,
    budgets=BUDGETS,
    goal_sample: int = 400,
    allow_exhaustive: bool = True,
    topology: tuple[np.ndarray, np.ndarray] | None = None,
    verbose: bool = True,
) -> dict:
    """Select a sensor subset per method per budget.

    allow_exhaustive : False forces greedy everywhere. The LOLEO folds use this
        so that all 14 folds share one optimiser and the fold results are not a
        mixture of exhaustive and greedy searches.
    topology : optional precomputed (pairwise distance matrix, betweenness
        vector) so the all-pairs Dijkstra is not repeated for every fold.
    """
    rng = np.random.default_rng(seed)
    sensor_ids = [str(s) for s in lib.sensors]
    n_sensors = lib.n_sensors

    vis = lib.visibility(sigma)                      # (n_scen, n_sensors)
    d_ref = vis.max(axis=1)                          # rich reference
    eligible = d_ref >= kappa

    H = lib.design_matrix()                          # (n_sensors, n_scen)
    sigma_scalar = float(np.mean(sigma))

    # Rank-r reduced parameter space for the classical criteria.
    r = min(budgets)
    _, _, Vt = np.linalg.svd(H, full_matrices=False)
    H_red = H @ Vt[:r].T                             # (n_sensors, r)

    # Fixed scenario sample for the goal-oriented criterion (frozen seed).
    Hn = H / np.maximum(np.linalg.norm(H, axis=0, keepdims=True), 1e-12)
    goal_idx = rng.choice(lib.n_scen, size=min(goal_sample, lib.n_scen), replace=False)

    if topology is None:
        D_top = build_graph_distances(inp_path, sensor_ids)
        bc = betweenness_centrality(inp_path, sensor_ids)
    else:
        D_top, bc = topology

    out: dict = {
        "sensor_ids": sensor_ids,
        "kappa": kappa,
        "eta": eta,
        "tau": tau,
        "sigma_per_sensor_m": sigma.tolist(),
        "n_eligible_scenarios": int(eligible.sum()),
        "n_scenarios_total": int(lib.n_scen),
        "reduced_rank_r": int(r),
        "budgets": {},
    }

    for k in budgets:
        t0 = time.time()
        res: dict = {}

        fo_score = fo_objective(vis, eligible, kappa, eta)
        subset = greedy_forward(n_sensors, k, fo_score, minimise=True)
        res["FO"] = {"subset": list(subset), "optimiser": "greedy_forward"}

        if allow_exhaustive and k == min(budgets):
            # Diagnostic only: how much does greedy give away? Reported beside
            # the result, never substituted for it.
            ex = exhaustive_fo_blindspot(vis, eligible, eta, k)
            res["FO"]["greedy_gap_diagnostic"] = {
                "exhaustive_subset": ex["subset"],
                "exhaustive_B": ex["B_blind_spot_rate"],
                "greedy_B": fo_score(subset)[0],
                "absolute_gap": fo_score(subset)[0] - ex["B_blind_spot_rate"],
                "n_subsets_enumerated": ex["n_subsets_enumerated"],
                "n_tied_at_optimum": ex["n_tied_at_optimum"],
            }

        def wrap(fn):
            return lambda s: fn(H[list(s), :])

        methods = {
            "D_optimal_bayesian": lambda s: crit_bayes_d(H[list(s), :], sigma_scalar, tau),
            "A_optimal_bayesian": lambda s: crit_bayes_a(H[list(s), :], sigma_scalar, tau),
            "E_optimal_observable_subspace":
                lambda s: crit_bayes_e(H[list(s), :], sigma_scalar, tau),
            "bayesian_information_gain": lambda s: crit_infogain(H[list(s), :], sigma_scalar, tau),
            "D_optimal_rank_reduced": lambda s: crit_classical_d(H_red[list(s), :]),
            "A_optimal_rank_reduced": lambda s: crit_classical_a(H_red[list(s), :]),
            "E_optimal_rank_reduced": lambda s: crit_classical_e(H_red[list(s), :]),
            "goal_oriented_oed": lambda s: crit_goal_oriented(Hn[list(s), :], goal_idx),
        }
        for name, fn in methods.items():
            sub = greedy_forward(n_sensors, k, fn, minimise=False)
            res[name] = {"subset": list(sub), "optimiser": "greedy_forward"}

        res["topological_dispersion"] = {
            "subset": list(maxmin_dispersion(D_top, k)),
            "optimiser": "greedy_maxmin",
        }
        res["centrality"] = {
            "subset": sorted(int(i) for i in np.argsort(-bc)[:k]),
            "optimiser": "top_k_betweenness",
        }

        rr = np.random.default_rng(seed + k)
        randoms = [
            sorted(int(i) for i in rr.choice(n_sensors, size=k, replace=False))
            for _ in range(n_random)
        ]
        res["random"] = {"replications": randoms, "n_replications": len(randoms)}

        for name, entry in res.items():
            if name == "random":
                entry["fo_metrics_per_replication"] = [
                    fo_report(vis, eligible, tuple(s), eta) for s in entry["replications"]
                ]
            else:
                entry["fo_metrics"] = fo_report(vis, eligible, tuple(entry["subset"]), eta)
                entry["sensor_ids"] = [sensor_ids[i] for i in entry["subset"]]

        res["_wall_clock_s"] = round(time.time() - t0, 1)
        out["budgets"][str(k)] = res
        if verbose:
            print(f"budget k={k} done in {res['_wall_clock_s']}s", flush=True)

    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--library", default=str(REPO / "data/processed/sensitivity_library.npz"))
    ap.add_argument("--inp", default=str(REPO / "data/raw/battledim_official/L-TOWN_v2_Model.inp"))
    ap.add_argument("--sigma", type=float, default=0.05, help="sensor noise std, metres")
    ap.add_argument("--kappa", type=float, default=3.0)
    ap.add_argument("--eta", type=float, default=3.0)
    ap.add_argument("--tau", type=float, default=1.0)
    ap.add_argument("--n-random", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20180101)
    ap.add_argument("--out", default=str(REPO / "results/selection.json"))
    args = ap.parse_args()

    lib = Library.load(Path(args.library))
    sigma = np.full(lib.n_sensors, args.sigma)
    res = select_all(
        lib, sigma, args.kappa, args.eta, args.tau,
        args.n_random, args.seed, Path(args.inp),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"wrote {out}")
