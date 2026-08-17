"""PHASE 23-RT -- risk-triage metrics, implemented explicitly.

Formulas are exactly those written in PROTOCOLE_PHASE23_RT.md sections 12 to 15.
All scores are RISK scores: HIGHER = MORE LIKELY ERROR.
"""

from __future__ import annotations

import numpy as np

COVERAGES = (0.05, 0.10, 0.20)


def _confident_first(risk: np.ndarray) -> np.ndarray:
    """Indices sorted by ascending risk = most confident first. Stable."""
    return np.argsort(risk, kind="mergesort")


def augrc(err: np.ndarray, risk: np.ndarray) -> float:
    """Area under the GENERALISED risk-coverage curve. LOWER IS BETTER.

    Sort most-confident first. For k = 1..N:
        coverage        c_k = k / N
        generalised risk g_k = (1/N) * sum_{i<=k} e_i     <- denominator is N, not k
        AUGRC = (1/N) * sum_k g_k
    """
    e = np.asarray(err, dtype=float)[_confident_first(risk)]
    n = len(e)
    if n == 0:
        return float("nan")
    return float(np.mean(np.cumsum(e) / n))


def aurc(err: np.ndarray, risk: np.ndarray) -> float:
    """Area under the conditional risk-coverage curve. LOWER IS BETTER."""
    e = np.asarray(err, dtype=float)[_confident_first(risk)]
    n = len(e)
    if n == 0:
        return float("nan")
    return float(np.mean(np.cumsum(e) / np.arange(1, n + 1)))


def error_capture(err: np.ndarray, risk: np.ndarray, q: float) -> float:
    """Share of all TEST errors that fall in the q most risky observations."""
    e = np.asarray(err, dtype=float)
    tot = e.sum()
    if tot == 0:
        return float("nan")
    order = _confident_first(risk)[::-1]          # riskiest first
    m = int(np.ceil(q * len(e)))
    return float(e[order[:m]].sum() / tot)


def residual_error(err: np.ndarray, risk: np.ndarray, q: float) -> float:
    """Error rate among the observations kept after removing the q riskiest."""
    e = np.asarray(err, dtype=float)
    order = _confident_first(risk)[::-1]
    m = int(np.ceil(q * len(e)))
    keep = order[m:]
    if len(keep) == 0:
        return float("nan")
    return float(e[keep].mean())


def lift(err: np.ndarray, risk: np.ndarray, q: float) -> float:
    ec = error_capture(err, risk, q)
    return float(ec / q) if np.isfinite(ec) else float("nan")


def all_metrics(err: np.ndarray, risk: np.ndarray) -> dict:
    out = {"augrc": augrc(err, risk), "aurc": aurc(err, risk)}
    for q in COVERAGES:
        k = int(round(q * 100))
        out[f"error_capture_{k}"] = error_capture(err, risk, q)
        out[f"residual_error_{k}"] = residual_error(err, risk, q)
        out[f"lift_{k}"] = lift(err, risk, q)
    return out


def fixed_threshold_operating_point(err: np.ndarray, risk_test: np.ndarray,
                                    threshold: float) -> dict:
    """Threshold frozen on CALIBRATION, applied as-is to TEST."""
    e = np.asarray(err, dtype=float)
    rejected = risk_test >= threshold
    n = len(e)
    tot = e.sum()
    kept = ~rejected
    return {"threshold": float(threshold),
            "achieved_rejection_rate_test": float(rejected.mean()),
            "achieved_coverage_test": float(kept.mean()),
            "error_capture_test": float(e[rejected].sum() / tot) if tot else float("nan"),
            "residual_error_test": float(e[kept].mean()) if kept.any() else float("nan"),
            "n_rejected": int(rejected.sum())}


def _triple(e_sorted_conf: np.ndarray, n: int, tot: float, m: int) -> tuple:
    """(augrc, error_capture@10, residual_error@10) from ONE confident-first sort.

    Numerically identical to augrc / error_capture / residual_error; only the
    number of sorts differs. Verified by test 12.
    """
    cs = np.cumsum(e_sorted_conf)
    g = float(cs[-1])
    au = float(cs.sum() / (n * n))
    kept = n - m                                  # riskiest m removed = first n-m kept
    err_kept = float(cs[kept - 1]) if kept > 0 else 0.0
    ec = (g - err_kept) / tot
    re = err_kept / kept if kept > 0 else float("nan")
    return au, ec, re


def paired_bootstrap(err: np.ndarray, risk_a: np.ndarray, risk_b: np.ndarray,
                     n_boot: int, seed: int) -> dict:
    """Paired bootstrap of (a - b) style deltas.

    The SAME resampled indices are used for both scores in every draw, which is
    what makes the comparison paired.
    """
    e = np.asarray(err)
    n = len(e)
    rng = np.random.default_rng(seed)
    d_augrc = np.empty(n_boot)
    d_ec10 = np.empty(n_boot)
    d_re10 = np.empty(n_boot)
    m = int(np.ceil(0.10 * n))
    for b in range(n_boot):
        ii = rng.integers(0, n, n)               # one index set, used for both
        ee = e[ii].astype(float)
        tot = ee.sum()
        if tot == 0:
            d_augrc[b] = d_ec10[b] = d_re10[b] = np.nan
            continue
        au_a, ec_a, re_a = _triple(ee[_confident_first(risk_a[ii])], n, tot, m)
        au_b, ec_b, re_b = _triple(ee[_confident_first(risk_b[ii])], n, tot, m)
        d_augrc[b] = au_b - au_a                 # STANDARD - ISO
        d_ec10[b] = ec_a - ec_b
        d_re10[b] = re_b - re_a
    return {"delta_augrc": d_augrc[~np.isnan(d_augrc)],
            "delta_error_capture_10": d_ec10[~np.isnan(d_ec10)],
            "delta_residual_error_10": d_re10[~np.isnan(d_re10)]}


def ci_and_p(draws: np.ndarray) -> dict:
    if len(draws) == 0:
        return {"ci_low": float("nan"), "ci_high": float("nan"), "p_raw": float("nan")}
    lo, hi = np.percentile(draws, [2.5, 97.5])
    p = float(min(1.0, 2 * min((draws <= 0).mean(), (draws >= 0).mean())))
    return {"ci_low": float(lo), "ci_high": float(hi), "p_raw": p}


def holm(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    m = len(pvals)
    order = np.argsort(pvals)
    rej = [False] * m
    for i, k in enumerate(order):
        if pvals[k] <= alpha / (m - i):
            rej[k] = True
        else:
            break
    return rej
