# Q3 frozen paper experiment

Experiment ID: `544eee966fe270395af7`. Definition fingerprint: `0ada3086f2e8384f6cfb7a8cfc1b14c907f232f67e9c874b8e10c7b4e867b70e`.

The final matrix contains 120 paired scenes × 5 default policies (600 runs), plus
20 random seeds × 4 single-module joint ablations (80 runs). Scenario order is
random 50, annulus 20, center 10, hash 20, worstrecv 20. Seed =
2026091200 + 100000 × scenario index + 97 × within-scenario index.
Every policy uses a fresh scene with the same exact source and error-field fingerprints.

## Reproduce or audit

From the repository root, with Python 3.12 and NumPy 2.3.5 (no SciPy needed):

```sh
python3 -B B_locator/Q3/reproduce.py --audit-only
python3 -B B_locator/Q3/reproduce.py --smoke
python3 -B B_locator/Q3/reproduce.py --out /path/to/new-experiment
```

`--audit-only` only replays existing actions and never constructs/runs a robot.
`--smoke` writes to a separate smoke subdirectory. A new experiment runs serially;
existing finished traces are validated and skipped. Incompatible algorithm/config
hashes raise an error instead of overwriting data. Audit/report script changes do
not invalidate or rerun algorithms. `--max-new-runs N` can bound a partial new run.
The stored source snapshot contains all Q3 Python modules, the current runner,
nine loaded expectation maps, their manifest and the fallback map; SHA256.json
verifies their bytes. The immutable algorithm/field definition excludes reporting
script revisions. The discarded early src/run_p3_paper.py was not an imported
algorithm dependency and is excluded from the final manifest.

## Metric definitions

T = travel_m/5 + 5*N_measure + N_switch + 5*N_clear_success + 3*N_clear_failure.
The initial location is (0,0) and measuring channel is 1. Only a measurement
changes the measuring channel; clear and enter/exit do not. Every distance,
switch, dt and cumulative timestamp is independently recomputed from raw actions.
The cumulative sum never uses a reported timestamp as its next starting value.
Final metrics are derived from this reconstruction and checked against report,
mock statistics and post-exit truth. The paper primary metric is the complete T,
reported as mean and P90. The per-source statistic is mean(T/cleared), with null
for cleared=0 and a disclosed defined-value count. All status values,
including failed and incomplete-clear runs, remain in aggregates. Last-clear time
and tail after last clear are diagnostics and are undefined when no clear succeeds.
The bootstrap uses 4000 paired scene resamples, RNG seed 20260912, fresh for each
comparison. A positive saving means the comparison uses less time than the reference.
Both total time and per-source time have percentile 95% confidence intervals.

The simulator virtual limit is 360000 s. The 1200 s allowance is real computation
time. Historical policy construction/run wall times were recorded without a timer;
all are summarized, but local wall measurements are not official online validation.
Future new runs install a 1200 s timer and retain timeouts as failed cases.

## Coverage and information isolation

The independent 5 m grid audit uses only actual no_signal responses for each
uncleared channel and successful-clear actions to retire channels. Any positive
observation left uncleared blocks completion. Identical observation station sets
are deduplicated and cached. All 320 claimed continuous-cell
completions are audited (320 numerical passes).
This numerical audit is not a continuous proof. A separate independent 50 m
closed-square-cell reconstruction checks all cells intersecting the disk at
radius 1000 − 50/sqrt(2) − 1e-6; its triangle-inequality argument certifies entire
cells. 320 such reconstructions pass.

The runtime truth wrapper logs calls and permits them only after accepted exit.
AST inspection covers every method in the eight decision classes, with sensitive
arena properties and dynamic getattr calls separately listed. Module-level mock
tests and scene-generation helpers are outside decision scope. This is transparent
inspection plus a runtime guard, not a security sandbox.

## Files and provenance

- paired_results.json / .csv: the authoritative 680 rows, each pointing to one trace.
- traces/: only final referenced traces; raw actions/configuration/report/truth are preserved.
- summary.json: all cases, each scenario, all baselines and four paired ablations.
- coverage_audit.json: per-run/per-channel verification and deduplicated observation sets.
- audit_report.json: timing, truth, configuration, static-source, pairing and payload-integrity checks.
- evidence_map.json: paper claims linked to precise evidence and limitations.
- source_snapshot/: verified algorithm, field and current audit-runner bytes.

600 redundant early traces and obsolete metadata are moved (never deleted) to
`tmp/q3-paper-scratch/previous-products/`. Movements and hashes are listed in the
audit report. Historical provenance fields are retained in traces; the separate
audit_provenance section records this audit and canonical raw-payload hashes.
Earlier runner metadata was refreshed after reporting edits, so its hash is not
claimed to prove the exact historical runner bytes. Algorithm/field hashes remain
verified. This audit did not rerun any policy.
