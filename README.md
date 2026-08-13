# FO / Frontière d'Oubli — external validation attempt on BattLeDIM / L-Town

Pre-registered comparison of the FO sensor-selection criterion against eight
optimal-experimental-design and topological baselines on the BattLeDIM 2020
L-Town benchmark, under a protocol frozen before the test year was opened.

## Read this first

**This repository cannot produce `VALIDATED_EXTERNALLY`, and does not claim it.**
The published BattLeDIM SCADA files could not be downloaded: Zenodo record
4017659 and `battledim.ucy.ac.cy` are both denied by this environment's network
egress policy, and no mirror of the CSVs exists on any reachable host. Exact
errors for every attempt are in [`data/raw/PROVENANCE.json`](data/raw/PROVENANCE.json).

What *was* recoverable from the organisers' own repository is the complete
generating pipeline — the network models, the leak schedules for both years, the
official generator and the official MATLAB scoring code — so the SCADA is
regenerated rather than downloaded. Evidence is therefore split into three
tracks that are never merged into a single claim:

| Track | Label | What it can support |
|---|---|---|
| A | `EVENT_HELDOUT_2018` | Leave-one-leak-event-out over the 14 events of 2018 |
| B | `OFFICIAL_ARTEFACT_RECONSTRUCTED_BENCHMARK` | The frozen protocol on a *regenerated* 2019 — **not** the published SCADA |
| C | `SYNTHETIC_ROBUSTNESS_STUDY` | Whether the ordering survives injected noise and demand variation |

Permitted global verdicts: `STRONG_INTERNAL_BENCHMARK_SUPPORT`, `PROMISING`,
`INCONCLUSIVE`, `NOT_SUPPORTED`. `VALIDATED_EXTERNALLY` is absent from the
`GLOBAL_VERDICTS` tuple in [`src/analyse.py`](src/analyse.py) and an assertion
enforces that the emitted verdict is one of the four.

## Four findings that qualify every number here

- **F1** The published 2018/2019 SCADA CSVs are unreachable. Everything runs on
  regenerated data.
- **F2** `L-TOWN_v2_Real.inp` carries only 365 days of demand patterns at a 300 s
  pattern step, while the configuration asks for two years. EPANET indexes
  patterns modulo their length, so a regenerated 2019 repeats the 2018 demands
  verbatim. Verified empirically.
- **F3** The released `dataset_generator.py` applies no measurement noise. It
  defines an uncertainty range and never uses it, so it is not the exact version
  that produced the published CSVs.
- **F4** The organisers ship the 2019 ground truth inside the same file as the
  2018 configuration, so it was visible during the mandatory data inventory,
  before the freeze existed. Recorded, not concealed.

`src/validate_regeneration.py` tests whether F2 applies to the *real* benchmark
by comparing the regenerated leak flows against the 23 official `Leak_p*.xlsx`
series shipped with the scoring code.

## Reproduce

```bash
pip install -r requirements.txt
python3 run_full_validation.py
```

One command. Every stage is skipped when its output exists, so an interrupted
run resumes without repeating the hydraulic simulations. Total cold-start cost
is roughly four hours, dominated by three one-year simulations.

## How the contamination barrier works

It is enforced twice, not promised:

1. **Ordering** — `run_full_validation.py` stage 7 refuses to open 2019 unless
   `FROZEN_PROTOCOL.json` and its SHA256 already exist.
2. **Runtime** — `src/freeze_protocol.py` patches `builtins.open` and
   `numpy.load` so that any read of a 2019 or evaluation artefact raises. The
   guard is armed for the whole freeze, so a contaminated protocol aborts rather
   than being written.

Everything tunable is fixed in that one file: `sigma`, `kappa`, `eta`, the OED
prior scale, the CUSUM slack and alarm threshold, the refractory and
localisation windows, the ridge penalty, all seeds, and the sensor subset every
method picks at every budget.

## Layout

```
run_full_validation.py     one-command entry point, nine stages
src/
  fetch_data.sh            official artefacts, digest-verified
  audit_data.py            SHA256 / shape / period / missing -> DATA_MANIFEST.json
  regenerate_scada.py      faithful port of the official generator (reference)
  regenerate_chunked.py    resumable chunked equivalent, verified bit-exact
  sensitivity.py           leak-sensitivity library; emitter model verified
  selection.py             FO criterion + eight baselines
  detector.py              the one detector every method shares
  evaluate.py              official BattLeDIM scoring, ported from MATLAB
  freeze_protocol.py       the freeze and its runtime guard
  tracks.py                Track A and Track B
  robustness.py            Track C and the anti-bias controls
  stats.py                 10000-resample paired bootstraps
  analyse.py               tables, figures, verdicts, final report
  validate_regeneration.py fidelity against the official leak series
data/raw/                  official artefacts, never modified
data/processed/            regenerated SCADA and the sensitivity library
results/  figures/  logs/
FO_BATTLEDIM_EXTERNAL_VALIDATION_FINAL.md
```

## Things that are tested rather than asserted

- The EPANET emitter stands in for the BattLeDIM orifice leak to within
  **4.6e-07** relative error, checked against wntr's own `add_leak`.
- Chunked simulation is **bit-identical** to the single-run reference:
  `max_abs_diff = 0.0` across all five published channels.
- Greedy sensor selection reaches the exhaustive optimum at k=4 (**gap 0.0**,
  203 subsets tied), measured by enumerating all 40920 subsets.

## Known limitations

Beyond F1–F4: the scenario space is junction-level and mapped to pipes by
averaging endpoint signatures; search is greedy above k=4; Track A has 14 events
and Track B 23, so intervals are wide; and the decision thresholds (20 %
relative reduction, 2-point recall margin) are project-internal rules, not
field standards.
