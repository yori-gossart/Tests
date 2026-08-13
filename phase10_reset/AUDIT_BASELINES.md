# AUDIT_BASELINES — verification of the ten FO-v1 baselines

Scope: verify that each baseline in `src/selection.py` computes what its name
claims, and that FO-v1's comparison was not rigged by a mis-implemented
opponent. FO-v1 itself is **not re-run and not modified**.

Classification of each finding: **[reproduced]** = re-derived directly from the
code and re-executed here; **[derived]** = follows analytically from the code;
**[limit]** = a stated limitation.

---

## 0. The setting that makes classical OED ill-posed

`theta` has `n_scen = 782` components; budgets are `k <= 12`. The Fisher
information `M(S) = H_S^T H_S / sigma^2` therefore has rank `<= 12` and is
singular. **[derived]**

Consequence: `det M(S) = 0`, `trace M(S)^-1 = inf`, `lambda_min M(S) = 0` for
*every* candidate S. Classical D-, A- and E-optimality are not merely expensive
here — they are **undefined**, and would rank all subsets identically. Any
implementation that returns a finite, discriminating number for "D-optimal" in
this setting is computing something else and must say so.

FO-v1 handles this with two named adaptations rather than one silent one.

---

## 1. `D_optimal_bayesian` — VERIFIED

Claim: Bayesian D-optimality under `theta ~ N(0, tau^2 I)`, i.e.
`max log det(H_S^T H_S / sigma^2 + I_n / tau^2)`.

Implementation evaluates `log det(I_k + (tau^2/sigma^2) H_S H_S^T)`.

Verification **[derived]**: by the Weinstein–Aronszajn identity,

```
det(I_n/tau^2 + H^T H/sigma^2) = tau^(-2n) · det(I_k + (tau^2/sigma^2) H H^T)
```

The dropped factor `tau^(-2n)` is constant across subsets of a given size, so
the *ranking* is exact, not approximate. Reducing an n×n determinant (n=782) to
k×k (k≤12) is the only reason the 1000-design sweeps in this audit were
affordable.

**Correct, and correctly named.**

## 2. `A_optimal_bayesian` — VERIFIED

Claim: `min trace((H_S^T H_S/sigma^2 + I/tau^2)^-1)`.

Implementation returns `(tau^4/sigma^2) · trace(G^-1 H_S H_S^T)` with
`G = I_k + (tau^2/sigma^2) H_S H_S^T`, maximised.

Verification **[derived]**: Woodbury gives
`trace(M^-1) = tau^2 n - (tau^4/sigma^2) trace(G^-1 H H^T)`. The first term is
constant across subsets, so maximising the returned quantity is exactly
minimising the posterior covariance trace. **Correct, and correctly named.**

## 3. `E_optimal_observable_subspace` — CORRECTLY RENAMED, WAS A REAL TRAP

Claim as named: the E-criterion **on the observable subspace**, i.e.
`lambda_min(I_k + (tau^2/sigma^2) H_S H_S^T)`.

Verification **[derived]**: literal Bayesian E-optimality is **degenerate**
here. `H_S^T H_S` is rank-deficient for `k < n`, so it has eigenvalue 0 with
multiplicity `n - k`, and

```
lambda_min(H_S^T H_S/sigma^2 + I_n/tau^2) = 1/tau^2   for EVERY subset S
```

A literal implementation would have returned a constant and ranked all designs
equally — silently turning "E-optimal" into a random tie-break. FO-v1 detected
this, renamed the criterion, and documented it. **This is a genuine trap that
was correctly avoided.**

**[limit]** The renamed criterion is a legitimate quantity but it is *not*
classical E-optimality. The meaningful classical E variant is the rank-reduced
one (§6).

## 4. `bayesian_information_gain` — VERIFIED, AND KNOWN-DEGENERATE WITH §1

Claim: `I(y_S; theta) = 0.5 log det(I + (tau^2/sigma^2) H_S H_S^T)`.

Verification **[derived]**: this is exactly half of §1's returned value. The two
criteria are therefore **monotone transforms of one another and must select the
identical subset**.

**[reproduced]** They do. Counting *distinct* selected subsets in
`FROZEN_PROTOCOL.json`, among the 11 methods (FO + 10 baselines):

| budget | distinct designs / 11 methods | collapsed group |
|---|---|---|
| k=4 | 9 | D-bayes = A-bayes = info-gain |
| k=6 | 8 | D-bayes = A-bayes = E-observable = info-gain |
| k=8 | 8 | D-bayes = A-bayes = E-observable = info-gain |
| k=12 | 9 | D-bayes = info-gain; A-bayes = E-observable |

Identical Spearman correlations follow, e.g. D-opt-bayesian and info-gain both
−0.545 at k=8 on 2018 in `SURROGATE_CORRELATIONS.csv`.

**[limit]** FO-v1 reported ten baselines. Measured, they are **7 to 8 distinct
designs depending on budget**, not ten. This does not favour FO — the collapsed
group is precisely the one that *beat* FO — but "FO lost to ten independent
baselines" overstates the independence of the comparison, and the final report
says 7–8.

*(An earlier draft of this audit estimated "roughly six" without counting. The
table above is the measured count and supersedes it.)*

## 5. `goal_oriented_oed` — VERIFIED AS SPECIFIED, NON-STANDARD

Implementation: maximise the minimum angular separation between normalised
scenario signatures restricted to S, over a fixed 400-scenario sample.

**[derived]** This targets *isolability* (two scenarios with parallel signatures
are indistinguishable at any SNR), which is a different objective from D/A/E
(which target magnitude variance). That is a defensible reading of
"goal-oriented OED" for a source-location goal.

**[limit]** It is not a citation-exact reproduction of any single published
goal-oriented OED formulation, and it uses a sampled subset of scenario pairs
rather than all `C(782,2)`. Both choices are frozen and seeded. It should be
described as "goal-oriented (isolability) OED, as specified here", not as a
literature-standard method.

## 6. `D/A/E_optimal_rank_reduced` — VERIFIED

Claim: classical D/A/E optimality on the leading `r = 4` right singular vectors
of `H`.

**[derived]** For `k >= r` the reduced Gram `H~_S^T H~_S` is generically full
rank, so all three classical criteria are well defined. Correct, and correctly
named.

**[limit]** `r = 4` is tied to the smallest budget. At k=12 the design is
optimised over a 4-dimensional projection while 8 further directions are
observable and ignored. This *handicaps* the rank-reduced baselines at large
budgets — again, not in FO's favour.

## 7. `topological_dispersion` — VERIFIED

Greedy max-min pipe-length dispersion, seeded from the farthest-apart pair.
Deterministic; contains no hydraulics. Correctly named.

## 8. `centrality` — VERIFIED WITH ONE CAVEAT

Top-k weighted betweenness. **[limit]** `networkx.betweenness_centrality` is
called with `k=min(200, n_nodes)` pivot sampling and `seed=0`, so it is an
*approximation* of betweenness, not exact betweenness. It is deterministic
under the fixed seed and identical across all runs, so the comparison is fair,
but the label should read "approximate (sampled) betweenness".

## 9. `random` — VERIFIED

100 replications per budget, seeded `seed + k`. Correct.

## 10. Optimiser parity — VERIFIED, AND THIS IS THE STRONGEST CHECK

**[reproduced]** Every method at every budget uses the same greedy forward
selection. The greedy optimality gap was measured, not assumed: exhaustive
enumeration of all `C(33,4) = 40920` subsets for the FO criterion returned
`absolute_gap = 0.0` with 203 subsets tied at the optimum.

So FO-v1's loss is **not** attributable to FO being under-optimised. At k=4 FO
reached the global optimum of its own criterion and still lost on the endpoint.

---

## Verdict of the baseline audit

**No baseline was found to be mis-implemented in a way that disadvantaged FO.**
Every error found runs the other way, or is neutral:

| Finding | Direction |
|---|---|
| Four Bayesian criteria collapse to one design | neutral to FO; inflates apparent baseline count |
| Rank-reduced fixed at r=4 | handicaps the baselines at large k |
| Betweenness is sampled, not exact | neutral, deterministic |
| Goal-oriented OED is a specified variant, not a literature standard | neutral |
| FO reached its own global optimum at k=4 | rules out under-optimisation of FO |

The one substantive correction to the FO-v1 write-up: **there are 7 to 8
distinct baseline designs depending on budget, not ten.**
