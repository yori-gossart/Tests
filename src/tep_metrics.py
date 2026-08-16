"""Standard detectability / diagnosability metrics for TEP, implemented
INDEPENDENTLY of FO.

Nothing in this module imports fo_metrics or reuses any of its code. Each
statistic below is a textbook quantity with its reference; FO is computed
elsewhere and only compared against these.

Notation. For a realisation z and design S:
    W[j, t] = delta[z, j, t] / sigma_j        whitened deviation, sigma = XNS
    v[j]    = max_t |W[j, t]|                 per-channel visibility over time
    m[j]    = mean_t W[j, t]                  mean whitened deviation

VISIBILITY FAMILY
    max_abs        max_{j in S} v[j]
                   NOTE: this is definitionally identical to FO's d_S. It is
                   included precisely so the identity is visible in the tables
                   rather than asserted in prose.
    mean_abs       mean_{j in S, t} |W|
    rms            sqrt(mean_{j in S, t} W^2)
                   Within a fixed design, rms and the whitened L2 norm over
                   (j, t) differ by the constant sqrt(|S| T), so they are
                   rank-equivalent and produce identical AUROC. The L2 reported
                   here is therefore the L2 over CHANNELS of v, which is not a
                   monotone transform of rms.
    l2_channels    ||v_S||_2
    mahalanobis    m_S^T (Sigma_n[S,S])^-1 m_S
                   Hotelling's T^2 statistic against the null covariance
                   (Mahalanobis 1936; Hotelling 1931). Sigma_n is estimated
                   ONCE on TRAIN normal runs and never re-estimated.
    kl_gauss       KL( N(m_S, Sigma_f[S,S]) || N(0, Sigma_n[S,S]) )
                   = 0.5 [ tr(Sn^-1 Sf) + m^T Sn^-1 m - k + ln(det Sn/det Sf) ]
                   (Kullback & Leibler 1951; Gaussian closed form.)
                   With a COMMON covariance this reduces to half the
                   Mahalanobis distance and carries no extra information; the
                   per-scenario Sigma_f is what makes it distinct, because it
                   also senses a change in the covariance structure.

ISOLABILITY FAMILY -- computed from fault SIGNATURES, never from the classifier
    d_nearest      Mahalanobis distance from the realisation's mean whitened
                   profile to the nearest OTHER fault's TRAIN centroid
    d_mean_others  mean of those distances over all other faults
    kl_nearest     Gaussian KL to the nearest other fault's TRAIN centroid
                   under the pooled null covariance
    margin_ratio   d_nearest / (d_own + eps), a scale-free separability ratio

Covariance estimation uses Ledoit-Wolf shrinkage (Ledoit & Wolf 2004), which is
parameter-free; no ridge constant is chosen by hand anywhere in this module.
"""

from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf

EPS = 1e-12


# --------------------------------------------------------------- primitives

def whiten(delta: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """(n, C, T) deviation -> (n, C, T) whitened by the declared per-channel sigma."""
    return delta / sigma[None, :, None]


def per_channel_visibility(W: np.ndarray) -> np.ndarray:
    """v[z, j] = max_t |W|."""
    return np.abs(W).max(axis=2)


def mean_profile(W: np.ndarray) -> np.ndarray:
    """m[z, j] = mean_t W."""
    return W.mean(axis=2)


def null_covariance(W_normal: np.ndarray) -> np.ndarray:
    """Sigma_n from TRAIN normal runs, Ledoit-Wolf shrunk.

    W_normal is (n_runs, C, T) whitened normal-operation series. Each run is
    centred on its own mean so the estimate is of fluctuation, not of level.
    """
    X = np.concatenate([(w - w.mean(axis=1, keepdims=True)).T for w in W_normal], axis=0)
    return LedoitWolf(assume_centered=True).fit(X).covariance_


def scenario_covariance(W: np.ndarray) -> np.ndarray:
    """Sigma_f per realisation, (n, C, C), from the centred whitened window.

    Plain sample covariance: with T = 800 samples against at most C = 41
    channels the estimate is well conditioned, and using the same estimator for
    every realisation keeps the comparison across designs honest.
    """
    Wc = W - W.mean(axis=2, keepdims=True)
    return np.einsum("nct,ndt->ncd", Wc, Wc) / (W.shape[2] - 1)


# ------------------------------------------------------- visibility metrics

def visibility_metrics(W: np.ndarray, v: np.ndarray, m: np.ndarray,
                       Sf: np.ndarray, Sn: np.ndarray, ch: list[int]) -> dict:
    """All visibility statistics for one design, vectorised over realisations."""
    Ws, vs, ms = W[:, ch, :], v[:, ch], m[:, ch]
    k = len(ch)

    Sn_s = Sn[np.ix_(ch, ch)]
    Sn_inv = np.linalg.inv(Sn_s)
    sign_n, logdet_n = np.linalg.slogdet(Sn_s)

    maha = np.einsum("nc,cd,nd->n", ms, Sn_inv, ms)

    Sf_s = Sf[:, ch, :][:, :, ch]
    tr_term = np.einsum("cd,ndc->n", Sn_inv, Sf_s)
    sign_f, logdet_f = np.linalg.slogdet(Sf_s)
    kl = 0.5 * (tr_term + maha - k + (logdet_n - logdet_f))

    return {
        "max_abs": vs.max(axis=1),                       # identical to FO d_S
        "mean_abs": np.abs(Ws).mean(axis=(1, 2)),
        "rms": np.sqrt((Ws ** 2).mean(axis=(1, 2))),
        "l2_channels": np.sqrt((vs ** 2).sum(axis=1)),
        "mahalanobis": maha,
        "kl_gauss": kl,
        "kl_defined": np.asarray(sign_f > 0, dtype=float),
    }


# ------------------------------------------------------ isolability metrics

def fault_centroids(m_train: np.ndarray, y_train: np.ndarray,
                    faults: list[int]) -> dict[int, np.ndarray]:
    """Mean whitened profile per fault, from TRAIN only."""
    return {k: m_train[y_train == k].mean(axis=0) for k in faults}


def isolability_metrics(m: np.ndarray, y: np.ndarray, centroids: dict[int, np.ndarray],
                        Sn: np.ndarray, ch: list[int]) -> dict:
    """Distances from each realisation to the competing faults' TRAIN centroids.

    Uses only the fault signatures and the null covariance, so these are
    readiness metrics: they exist before any classifier is trained.
    """
    ms = m[:, ch]
    Sn_inv = np.linalg.inv(Sn[np.ix_(ch, ch)])
    ks = sorted(centroids)
    C = np.stack([centroids[k][ch] for k in ks])                 # (K, |S|)

    diff = ms[:, None, :] - C[None, :, :]                        # (n, K, |S|)
    d2 = np.einsum("nkc,cd,nkd->nk", diff, Sn_inv, diff)
    d2 = np.maximum(d2, 0.0)

    own = np.array([ks.index(int(t)) for t in y])
    mask = np.ones_like(d2, dtype=bool)
    mask[np.arange(len(y)), own] = False

    d_own = np.sqrt(d2[np.arange(len(y)), own])
    others = np.where(mask, d2, np.inf)
    d_nearest = np.sqrt(others.min(axis=1))
    d_mean_others = np.sqrt(np.where(mask, d2, np.nan)).astype(float)
    d_mean_others = np.nanmean(d_mean_others, axis=1)

    # Gaussian KL between two centroids under the shared null covariance is
    # half the squared Mahalanobis distance between them; reported for
    # completeness and flagged as such in the audit.
    kl_nearest = 0.5 * others.min(axis=1)

    return {
        "iso_d_nearest": d_nearest,
        "iso_d_mean_others": d_mean_others,
        "iso_kl_nearest": kl_nearest,
        "iso_margin_ratio": d_nearest / (d_own + 1.0),
        "iso_d_own": d_own,
    }


# ------------------------------------------------------- tail statistics on E*

def tail_statistics(d_S: np.ndarray, support_mask: np.ndarray, eta: float) -> dict:
    """Design-level statistics of visibility over a FIXED scenario support.

    b_star_equiv reproduces B*'s value from the same inputs, so that the
    question "is it B*'s construction, or merely a tail statistic on a fixed
    support?" can be answered by comparing columns rather than by argument.
    """
    x = d_S[support_mask]
    if x.size == 0:
        return {k: float("nan") for k in
                ["b_star_equiv", "q05", "q10", "minimum", "mean", "cvar05", "cvar10"]}
    q05 = float(np.quantile(x, 0.05))
    q10 = float(np.quantile(x, 0.10))
    return {
        "b_star_equiv": float(np.mean(x <= eta)),
        "q05": q05,
        "q10": q10,
        "minimum": float(x.min()),
        "mean": float(x.mean()),
        "cvar05": float(x[x <= q05].mean()) if np.any(x <= q05) else float(x.min()),
        "cvar10": float(x[x <= q10].mean()) if np.any(x <= q10) else float(x.min()),
    }
