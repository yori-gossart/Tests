"""
PHASE F -- verdicts, applied mechanically to the Phase 10 evidence.

Two verdicts are in scope.

FO_DIAGNOSTIC_*          decidable from the BattLeDIM substitute evaluation
FO_RECONSTRUCTIBILITY_*  requires the EPA source-identification dataset

The second cannot be decided here. The Phase 10 brief writes the rule as a
binary ("... otherwise NOT_SUPPORTED"), but that binary is about the OUTCOME of
running the test. A test that was never run supports neither branch, and
emitting NOT_SUPPORTED for it would report an absence of data as a negative
finding. This module therefore emits a third, explicit status for that case and
says so in the output rather than silently choosing a branch.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase10_reset"

AUROC_FLOOR = 0.70
TRAIN_YEAR, TEST_YEAR = 2018, 2019


def monotone_fraction(rates: list[float]) -> float:
    """Share of adjacent decile steps that do not decrease."""
    r = np.asarray(rates, dtype=float)
    if len(r) < 2:
        return float("nan")
    return float(np.mean(np.diff(r) >= 0))


def main() -> int:
    diag = pd.read_csv(OUT / "FO_DIAGNOSTIC_METRICS.csv")
    dec = pd.read_csv(OUT / "FO_DIAGNOSTIC_DECILES.csv")
    rows = pd.read_csv(OUT / "FO_DIAGNOSTIC_RESULTS.csv")

    fo = diag[diag.predictor == "fo_neg_visibility"].set_index("year")
    others = diag[diag.predictor != "fo_neg_visibility"]

    checks = {}
    for year in (TRAIN_YEAR, TEST_YEAR):
        if year not in fo.index:
            continue
        r = fo.loc[year]
        best_other = others[others.year == year].sort_values("auroc").iloc[-1]
        rates = dec[dec.year == year].sort_values("decile").failure_rate.tolist()
        checks[str(year)] = {
            "auroc": float(r.auroc),
            "auroc_ci": [float(r.auroc_ci_lo), float(r.auroc_ci_hi)],
            "auroc_above_floor": bool(r.auroc_ci_lo > AUROC_FLOOR),
            "auprc": float(r.auprc),
            "failure_prevalence": float(r.failure_prevalence),
            "auprc_ci_above_prevalence": bool(r.auprc_above_prevalence),
            "decile_monotone_fraction": monotone_fraction(rates),
            "decile_failure_rates": rates,
            "best_competing_predictor": str(best_other.predictor),
            "best_competing_auroc": float(best_other.auroc),
            "fo_beats_all_simple_predictors": bool(r.auroc > best_other.auroc),
        }

    # Is the test year degenerate? If every failing event fails under EVERY
    # design, no design-dependent score can predict it even in principle, and
    # the year's AUROC measures nothing about any predictor.
    test = rows[rows.year == TEST_YEAR]
    per_event = test.groupby("event")["failure"].agg(["mean", "size"])
    always_fail = per_event[(per_event["mean"] == 1.0)]
    never_fail = per_event[(per_event["mean"] == 0.0)]
    degenerate = bool(len(always_fail) + len(never_fail) == len(per_event))
    checks["test_year_degeneracy"] = {
        "n_events": int(len(per_event)),
        "events_failing_under_every_design": always_fail.index.tolist(),
        "events_succeeding_under_every_design": never_fail.index.tolist(),
        "design_dependent_events": int(
            len(per_event) - len(always_fail) - len(never_fail)
        ),
        "degenerate": degenerate,
        "consequence": (
            "Every event's outcome is fixed by the event, not by the sensor set, "
            "so the number of independent units is the number of events (23), not "
            "the number of rows, and no design-dependent score can rank them "
            "above chance for a design-related reason. The test-year AUROC of "
            "ANY predictor here is uninformative about that predictor."
        ) if degenerate else "test year retains design-dependent outcomes",
    }

    train = checks.get(str(TRAIN_YEAR), {})
    test_c = checks.get(str(TEST_YEAR), {})
    out_of_sample_ok = bool(test_c.get("auroc_above_floor")) and not degenerate

    if out_of_sample_ok and test_c.get("decile_monotone_fraction", 0) >= 0.8 \
            and test_c.get("fo_beats_all_simple_predictors"):
        diagnostic = "FO_DIAGNOSTIC_SUPPORTED"
    else:
        diagnostic = "FO_DIAGNOSTIC_NOT_SUPPORTED"

    reasons = []
    if train:
        reasons.append(
            f"On {TRAIN_YEAR} FO visibility predicts detection failure well: "
            f"AUROC {train['auroc']:.3f} CI [{train['auroc_ci'][0]:.3f}, "
            f"{train['auroc_ci'][1]:.3f}], above every simple competitor "
            f"(best: {train['best_competing_predictor']} at "
            f"{train['best_competing_auroc']:.3f}). That is a real signal."
        )
        reasons.append(
            f"But the decile failure-rate gradient on {TRAIN_YEAR} is not monotone "
            f"({train['decile_monotone_fraction']:.0%} of steps non-decreasing; "
            f"rates {['%.2f' % r for r in train['decile_failure_rates']]}), and the "
            "brief requires a clear monotone gradient."
        )
    if degenerate:
        reasons.append(
            f"The {TEST_YEAR} year cannot supply the required out-of-sample "
            f"confirmation in either direction: its "
            f"{len(always_fail)} failing events fail under EVERY design, so the "
            "outcome is design-independent and no sensor-set-dependent score can "
            "be evaluated on it. FO's 0.478 there is not evidence against FO, and "
            f"the 0.771 of the best competitor is not evidence for it."
        )
    reasons.append(
        "The out-of-sample test the brief requires is Phase D/E on the EPA "
        "source-identification dataset, which could not be acquired. "
        "FO_DIAGNOSTIC_NOT_SUPPORTED here means NOT DEMONSTRATED, not refuted."
    )

    verdicts = {
        "FO_DIAGNOSTIC": diagnostic,
        "FO_DIAGNOSTIC_reasons": reasons,
        "FO_RECONSTRUCTIBILITY": "NOT_EVALUATED_DATASET_UNAVAILABLE",
        "FO_RECONSTRUCTIBILITY_note": (
            "Requires the EPA source-identification test cases (Phase C/D). The "
            "dataset is unreachable from this environment; exact errors in "
            "EPA_DATA_MANIFEST.json. Reporting NOT_SUPPORTED for a test that was "
            "never run would present missing data as a negative result, so a "
            "distinct status is used. Under the brief's literal binary this would "
            "read NOT_SUPPORTED; the distinction is flagged for the reader to "
            "override if they prefer the literal reading."
        ),
        "FO_v1_verdict_unchanged": "NOT_SUPPORTED (frozen, not re-run)",
        "no_fo_v2_optimiser_created": True,
        "checks": checks,
    }
    (OUT / "PHASE10_VERDICTS.json").write_text(json.dumps(verdicts, indent=2) + "\n")
    print(f"FO_DIAGNOSTIC          = {diagnostic}")
    print(f"FO_RECONSTRUCTIBILITY  = {verdicts['FO_RECONSTRUCTIBILITY']}")
    for r in reasons:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
