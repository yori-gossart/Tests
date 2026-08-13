"""
The single detection + localisation pipeline used by EVERY sensor-selection
method in this study.

Only the sensor subset S changes between methods. The nominal model, the
residual definition, the CUSUM statistic, the alarm rule, the re-baselining
rule and the localisation rule are byte-identical, so any performance
difference is attributable to the selection strategy and to nothing else.

PIPELINE
--------
1. Nominal model. For each candidate sensor j, ridge regression of the measured
   pressure on exogenous inputs that are available to every method regardless
   of S -- the three inlet flows, the tank level, three daily harmonics and
   day-of-week dummies:

       p_hat_j(t) = w_j . x(t),   x(t) in R^15

   Including inlet flow is what removes system-wide demand variation: a leak
   raises total inflow but its pressure signature is spatially structured, so
   the residual keeps the spatial information the sensor placement controls.

2. Residual and scale.  r_j(t) = p_j(t) - p_hat_j(t),
   sigma_j = 1.4826 * MAD(r_j) over the training index (robust to the leaks
   that are present in the training year).

3. Statistic. Two-sided CUSUM per sensor on the standardised residual, which
   responds to abrupt steps and to the slow ramps of incipient leaks alike:

       C+_j(t) = max(0, C+_j(t-1) + z_j(t) - k)
       C-_j(t) = max(0, C-_j(t-1) - z_j(t) - k)
       g_S(t)  = max_{j in S} max(C+_j(t), C-_j(t))

4. Alarm and re-baseline. Alarm when g_S(t) > h. Because BattLeDIM leaks
   persist and overlap, an alarm resets every CUSUM and shifts each sensor's
   baseline by the residual level it has just reached, so a standing leak does
   not mask the next one.

5. Localisation. At an alarm, the residual change vector over the preceding
   window is matched by cosine similarity against the leak-sensitivity library
   restricted to S; the arg-max scenario junction is the predicted location.

k (CUSUM slack) and h (alarm threshold) are frozen from 2018 and never touched
afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

N_HARMONICS = 3
RIDGE_LAMBDA = 1.0


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------


def build_features(ts: pd.DatetimeIndex, flows: np.ndarray, level: np.ndarray) -> np.ndarray:
    """x(t) = [1, flows(3), level(1), daily harmonics(6), day-of-week(6)] -> R^17."""
    n = len(ts)
    tod = (ts.hour * 3600 + ts.minute * 60 + ts.second).to_numpy() / 86400.0
    cols = [np.ones(n), flows, level.reshape(n, -1)]
    harm = []
    for m in range(1, N_HARMONICS + 1):
        harm.append(np.sin(2 * np.pi * m * tod))
        harm.append(np.cos(2 * np.pi * m * tod))
    cols.append(np.column_stack(harm))
    dow = ts.dayofweek.to_numpy()
    cols.append(np.column_stack([(dow == d).astype(float) for d in range(6)]))
    return np.column_stack([c if c.ndim > 1 else c.reshape(n, 1) for c in cols])


def ridge_fit(X: np.ndarray, Y: np.ndarray, lam: float = RIDGE_LAMBDA) -> np.ndarray:
    """Ridge weights, intercept column excluded from the penalty."""
    d = X.shape[1]
    P = np.eye(d) * lam
    P[0, 0] = 0.0
    return np.linalg.solve(X.T @ X + P, X.T @ Y)


# ---------------------------------------------------------------------------
# Nominal model
# ---------------------------------------------------------------------------


@dataclass
class NominalModel:
    weights: np.ndarray     # (n_features, n_sensors)
    sigma: np.ndarray       # (n_sensors,)
    sensor_ids: list[str]

    def residuals(self, X: np.ndarray, P: np.ndarray) -> np.ndarray:
        return P - X @ self.weights

    def standardised(self, X: np.ndarray, P: np.ndarray) -> np.ndarray:
        return self.residuals(X, P) / self.sigma[None, :]


def fit_nominal(X: np.ndarray, P: np.ndarray, train_mask: np.ndarray,
                sensor_ids: list[str]) -> NominalModel:
    W = ridge_fit(X[train_mask], P[train_mask])
    R = P[train_mask] - X[train_mask] @ W
    med = np.median(R, axis=0)
    mad = np.median(np.abs(R - med[None, :]), axis=0)
    sigma = np.maximum(1.4826 * mad, 1e-3)
    return NominalModel(weights=W, sigma=sigma, sensor_ids=sensor_ids)


# ---------------------------------------------------------------------------
# CUSUM detection
# ---------------------------------------------------------------------------


def cusum_detect(Z: np.ndarray, subset: list[int], k: float, h: float,
                 min_gap: int) -> list[dict]:
    """Two-sided CUSUM over `subset`, with reset + baseline shift on alarm.

    Z        : (T, n_sensors) standardised residuals
    min_gap  : samples that must elapse before a new alarm can fire
    Returns alarms as {'index', 'sensor', 'sign'}.
    """
    T = Z.shape[0]
    cols = np.asarray(subset, dtype=int)
    Zs = Z[:, cols]
    m = len(cols)
    cp = np.zeros(m)
    cn = np.zeros(m)
    base = np.zeros(m)
    alarms: list[dict] = []
    last = -min_gap - 1

    for t in range(T):
        z = Zs[t] - base
        cp = np.maximum(0.0, cp + z - k)
        cn = np.maximum(0.0, cn - z - k)
        stat = np.maximum(cp, cn)
        j = int(np.argmax(stat))
        if stat[j] > h and (t - last) > min_gap:
            alarms.append(
                {"index": int(t), "sensor": int(cols[j]), "sign": 1 if cp[j] >= cn[j] else -1}
            )
            last = t
            # Re-baseline on the level just reached so a standing leak does not
            # permanently saturate the statistic and mask later events.
            lo = max(0, t - min_gap)
            base = np.median(Zs[lo : t + 1], axis=0)
            cp[:] = 0.0
            cn[:] = 0.0
    return alarms


def cusum_statistic(Z: np.ndarray, subset: list[int], k: float) -> np.ndarray:
    """Un-thresholded max-CUSUM trace, for threshold-sensitivity analysis."""
    cols = np.asarray(subset, dtype=int)
    Zs = Z[:, cols]
    m = len(cols)
    cp = np.zeros(m)
    cn = np.zeros(m)
    out = np.zeros(Z.shape[0])
    for t in range(Z.shape[0]):
        z = Zs[t]
        cp = np.maximum(0.0, cp + z - k)
        cn = np.maximum(0.0, cn - z - k)
        out[t] = np.max(np.maximum(cp, cn))
    return out


# ---------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------


@dataclass
class Localiser:
    signatures: np.ndarray   # (n_sensors, n_scen), mean pressure drop per scenario
    scenarios: np.ndarray

    def predict(self, resid_change: np.ndarray, subset: list[int]) -> tuple[str, float]:
        A = self.signatures[np.asarray(subset, dtype=int), :]
        nrm = np.linalg.norm(A, axis=0)
        nrm = np.where(nrm > 1e-12, nrm, 1.0)
        U = A / nrm[None, :]
        v = resid_change
        vn = np.linalg.norm(v)
        if vn < 1e-12:
            return str(self.scenarios[0]), 0.0
        sim = U.T @ (v / vn)
        # A leak lowers pressure, so the residual points along -Delta p.
        i = int(np.argmax(-sim))
        return str(self.scenarios[i]), float(-sim[i])


def residual_change(Z: np.ndarray, t: int, window: int) -> np.ndarray:
    """Level shift at t: median over the window ending at t minus the median
    over the window before it."""
    a0, a1 = max(0, t - window), t + 1
    b0, b1 = max(0, t - 2 * window), max(1, t - window)
    return np.median(Z[a0:a1], axis=0) - np.median(Z[b0:b1], axis=0)


# ---------------------------------------------------------------------------
# End-to-end run for one sensor subset
# ---------------------------------------------------------------------------


def run_subset(
    Z: np.ndarray,
    subset: list[int],
    k: float,
    h: float,
    min_gap: int,
    localiser: Localiser,
    window: int,
    timestamps: pd.DatetimeIndex,
) -> list[dict]:
    """Detect and localise with one sensor subset. Returns the report list in
    BattLeDIM submission shape: {'time', 'index', 'predicted_node', 'score'}."""
    alarms = cusum_detect(Z, subset, k, h, min_gap)
    out = []
    for a in alarms:
        t = a["index"]
        node, score = localiser.predict(residual_change(Z, t, window)[subset], subset)
        out.append(
            {
                "index": t,
                "time": str(timestamps[t]),
                "predicted_node": node,
                "score": score,
                "trigger_sensor": int(a["sensor"]),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_year(directory: Path, year: int, sensor_ids: list[str]):
    """Load a regenerated SCADA year and assemble (timestamps, X, P)."""
    pres = pd.read_csv(directory / f"{year}_SCADA_Pressures.csv", parse_dates=["Timestamp"])
    flow = pd.read_csv(directory / f"{year}_SCADA_Flows.csv", parse_dates=["Timestamp"])
    lvl = pd.read_csv(directory / f"{year}_SCADA_Levels.csv", parse_dates=["Timestamp"])

    ts = pd.DatetimeIndex(pres["Timestamp"])
    P = pres[sensor_ids].to_numpy(dtype=np.float64)
    F = flow.drop(columns=["Timestamp"]).to_numpy(dtype=np.float64)
    L = lvl.drop(columns=["Timestamp"]).to_numpy(dtype=np.float64)
    X = build_features(ts, F, L)
    return ts, X, P
