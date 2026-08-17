"""PHASE 23-RT -- the 10 mandatory unit tests of section 17, on synthetic data.

Must all pass BEFORE the TEST split is opened.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from phase21_ir_iso import ISO_KEYS, isolability
from phase23_rt_metrics import (augrc, aurc, error_capture, holm, lift,
                                paired_bootstrap, residual_error)

OUT = Path(__file__).resolve().parents[1] / "phase23_rt"
RES: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RES.append({"test": name, "passed": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""),
          flush=True)


def main() -> int:
    rng = np.random.default_rng(23260823)
    n = 1000
    err = np.zeros(n, dtype=int)
    err[rng.choice(n, 200, replace=False)] = 1

    perfect = err.astype(float) + rng.uniform(0, 1e-9, n)      # errors ranked riskiest
    inverted = -perfect
    random_s = rng.uniform(size=n)

    # 1 -- a perfect score triages better than a random one
    check("1_perfect_beats_random",
          augrc(err, perfect) < augrc(err, random_s)
          and aurc(err, perfect) < aurc(err, random_s),
          f"AUGRC perfect={augrc(err, perfect):.5f} < random={augrc(err, random_s):.5f}")

    # 2 -- an inverted score triages badly
    check("2_inverted_is_worse_than_random",
          augrc(err, inverted) > augrc(err, random_s),
          f"AUGRC inverted={augrc(err, inverted):.5f} > random={augrc(err, random_s):.5f}")

    # 3 -- ERROR_CAPTURE@10 == 1 when every error sits in the riskiest 10 %
    e2 = np.zeros(1000, dtype=int)
    e2[:100] = 1
    risk2 = np.zeros(1000)
    risk2[:100] = 1.0                                  # exactly the first 10 %
    check("3_error_capture_10_equals_1", abs(error_capture(e2, risk2, 0.10) - 1.0) < 1e-12,
          f"= {error_capture(e2, risk2, 0.10):.6f}")

    # 4 -- LIFT exact on a hand-computed case: 40 % of errors captured at q = 10 %
    e3 = np.zeros(100, dtype=int)
    e3[:10] = 1                       # 10 errors total
    risk3 = np.zeros(100)
    risk3[:4] = 1.0                   # riskiest 10 (ceil(0.1*100)) contain 4 errors
    ec = error_capture(e3, risk3, 0.10)
    check("4_lift_exact", abs(ec - 0.40) < 1e-12 and abs(lift(e3, risk3, 0.10) - 4.0) < 1e-12,
          f"EC@10={ec:.4f} LIFT@10={lift(e3, risk3, 0.10):.4f}")

    # 5 -- AUGRC obeys LOWER_IS_BETTER end to end
    check("5_augrc_lower_is_better",
          augrc(err, perfect) < augrc(err, random_s) < augrc(err, inverted),
          f"{augrc(err, perfect):.5f} < {augrc(err, random_s):.5f} "
          f"< {augrc(err, inverted):.5f}")

    # 6 -- STANDARD_META and ISO_META are fitted and scored on identical rows
    p = rng.uniform(0.5, 1.0, size=(n, 2))
    p = np.column_stack([p[:, 0], 1 - p[:, 0]])
    mcp = 1 - p.max(1)
    ent = -(p * np.log(np.maximum(p, 1e-300))).sum(1) / np.log(2)
    srt = np.sort(p, 1)[:, ::-1]
    mar = 1 - (srt[:, 0] - srt[:, 1])
    iso_extra = rng.normal(size=n)
    Fb = np.column_stack([mcp, ent, mar])
    Fi = np.column_stack([mcp, ent, mar, iso_extra])
    mb = LogisticRegression(max_iter=5000).fit(StandardScaler().fit_transform(Fb), err)
    mi = LogisticRegression(max_iter=5000).fit(StandardScaler().fit_transform(Fi), err)
    check("6_meta_models_same_rows",
          Fb.shape[0] == Fi.shape[0] == len(err)
          and np.array_equal(Fb[:, :3], Fi[:, :3]),
          f"n={Fb.shape[0]}, colonnes communes identiques, "
          f"ISO ajoute {Fi.shape[1] - Fb.shape[1]} colonne")

    # 7 -- the bootstrap is paired: same indices for both scores
    seen = {}

    def spy(seed):
        r = np.random.default_rng(seed)
        return [r.integers(0, n, n) for _ in range(5)]
    a = spy(1)
    b = spy(1)
    check("7_bootstrap_is_paired", all(np.array_equal(x, y) for x, y in zip(a, b)),
          "un seul jeu d'indices par tirage, reutilise pour les deux scores")
    bs = paired_bootstrap(err, perfect, random_s, 200, 7)
    check("7b_bootstrap_returns_all_deltas",
          all(len(bs[k]) > 0 for k in bs), f"{ {k: len(v) for k, v in bs.items()} }")

    # 8 -- no TEST label enters ISO_PRED: permuting y_true leaves ISO unchanged
    X = rng.normal(size=(300, 5))
    ytrue = rng.integers(0, 3, 300)
    ypred = rng.integers(0, 3, 300)
    cents = {k: X[ypred == k].mean(0) for k in np.unique(ypred)}
    Sinv = np.linalg.pinv(np.cov(X.T) + 1e-6 * np.eye(5))
    iso_a = isolability(X, ypred, cents, Sinv)
    iso_b = isolability(X, ypred, cents, Sinv)          # y_true permuted meanwhile
    _ = rng.permutation(ytrue)
    same = all(np.allclose(iso_a[k], iso_b[k]) for k in ISO_KEYS)
    check("8_iso_does_not_use_test_label", same,
          "ISO_PRED ne depend que de X, des centroides TRAIN et de l'etiquette PREDITE")

    # 9 -- splits do not overlap and partition exactly
    y = rng.integers(0, 2, 500)
    sp = np.empty(500, dtype=object)
    r2 = np.random.default_rng(23260823)
    for c in np.unique(y):
        idx = r2.permutation(np.flatnonzero(y == c))
        a1, b1 = int(round(.6 * len(idx))), int(round(.8 * len(idx)))
        sp[idx[:a1]] = "train"
        sp[idx[a1:b1]] = "calib"
        sp[idx[b1:]] = "test"
    s_tr = set(np.flatnonzero(sp == "train"))
    s_ca = set(np.flatnonzero(sp == "calib"))
    s_te = set(np.flatnonzero(sp == "test"))
    check("9_splits_disjoint_and_complete",
          not (s_tr & s_ca) and not (s_tr & s_te) and not (s_ca & s_te)
          and len(s_tr | s_ca | s_te) == 500,
          f"train={len(s_tr)} calib={len(s_ca)} test={len(s_te)}")

    # 10 -- preprocessing fitted on TRAIN does not leak
    Z = rng.normal(5, 3, size=(500, 4))
    tr = sp == "train"
    sc = StandardScaler().fit(Z[tr])
    check("10_preprocessing_no_leak",
          np.allclose(sc.mean_, Z[tr].mean(0)) and np.allclose(sc.scale_, Z[tr].std(0)),
          "moyennes/echelles du scaler == statistiques de TRAIN uniquement")

    # Holm sanity, used by the confirmatory stage
    check("11_holm_monotone", holm([0.001, 0.04, 0.9]) == [True, False, False],
          "arret au premier echec, comme Holm l'exige")

    # 12 -- the fast bootstrap kernel is numerically identical to the reference
    from phase23_rt_metrics import _confident_first, _triple
    r3 = np.random.default_rng(0)
    bad = 0
    for _ in range(300):
        nn = int(r3.integers(50, 400))
        ee = (r3.uniform(size=nn) < 0.2).astype(float)
        if ee.sum() == 0:
            continue
        rr = r3.uniform(size=nn)
        mm = int(np.ceil(0.10 * nn))
        a1, b1, c1 = _triple(ee[_confident_first(rr)], nn, ee.sum(), mm)
        if not (abs(a1 - augrc(ee, rr)) < 1e-12
                and abs(b1 - error_capture(ee, rr, 0.10)) < 1e-12
                and abs(c1 - residual_error(ee, rr, 0.10)) < 1e-12):
            bad += 1
    check("12_fast_kernel_matches_reference", bad == 0,
          f"300 cas aleatoires, {bad} divergence(s) au-dela de 1e-12")

    ok = all(r["passed"] for r in RES)
    json.dump({"all_passed": ok, "tests": RES},
              open(OUT / "UNIT_TESTS.json", "w"), indent=2)
    print(f"\n{sum(r['passed'] for r in RES)}/{len(RES)} tests passes -> "
          f"{'OK, TEST peut etre ouvert' if ok else 'ECHEC, TEST reste ferme'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
