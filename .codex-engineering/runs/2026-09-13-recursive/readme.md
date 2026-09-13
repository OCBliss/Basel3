# Pathwise recursive parameter calibration and dependence

This is the substantive model milestone following the supporting acquisition and
organization work. [recursive.py](../../../src/RWA/models/parameter_hierarchy/recursive.py)
recalibrates each simulated path's mu/theta/sigma process coefficients and full
joint innovation dependence from its own rolling history before later shocks.
The CLI and both RWA YAML workflows expose the mode and update cadence.

## Verification

- [Focused independent tests](focused-tests.log): frozen equivalence, causal
  update timing, all branches/tenors, standardized innovation calculations,
  path isolation, circular-buffer rollover, workload guards and actual CLI.
- [Final repository suite](final-suite.log): source, integration and existing
  Call Report/JSD regression evidence.
- [Empirical results](empirical-01/results.json): latest and held-out comparisons
  from saved actual calibration, with frozen/cadence 1/cadence 5 alternatives.
- [Live manager log](live-manager.log) and [configuration](live-config.yaml):
  full acquisition-to-recursive-simulation execution with new output locations.

## Reproduce the comparison

Install the root requirements and keep temporary/cache paths inside the repository
as described in [tests](../../../tests/readme.md). The validator reads the prior
verified live snapshot and calibration under RWA/FRED/snapshots/2026-09-13-live
and RWA/Experimental/HIERARCHY/2026-09-13-live; these local artifacts must exist.
It checks that source hashes do not change and refuses existing output directories.

```bash
python 3 -B .codex-engineering/runs/2026-09-13-recursive/validate_recursive.py \
  --output .codex-engineering/runs/2026-09-13-recursive/empirical-new
python 3 -B -m unittest discover -s tests -p test_rwa_recursive.py -v
```

See the [model guide](../../../src/RWA/models/parameter_hierarchy/readme.md) for
complete model commands, mathematics and output contracts. Re-running the saved
live configuration requires new snapshot/output directory names.

## Findings

The empirical comparison used 32 paths, ten forecast increments and four internal
substeps at the latest origin and one earlier held-out origin. Cadence 1 produced
288 path/origin recalibrations; cadence 5 produced 32. Every update origin had 32
separate path audit signatures, all three parameter diffusion branches changed,
and joint-correlation changes reached approximately 0.089. All simulated states
were positive, no boundary projection occurred, and likelihood costs stayed ≤2.

The latest cadence 1 run took 6.19 seconds; cadence 5 took 0.75 seconds. The entire
comparison, including held-out runs and diagnostics, took 16.08 seconds. Reported
peak resident memory is process-wide, not an isolated per-mode measurement.

At the held-out origin 2026-08-13 with observed target 2026-08-27, joint energy
scores were 0.188074(frozen),0.187938(cadence 1),0.188215(cadence 5). Paired Monte
Carlo intervals for the differences include zero. This single-origin check is
implementation/model evidence and does not establish forecast superiority.

JSD comparisons use shared edges with 30/50/100 bins and natural-log square-root
JSD, consistent with the repository's convention. Sparse histogram estimates
are sensitive to bin count and Monte Carlo sampling; independent frozen draws
supply a reference. The full result records quantiles, means, dispersion and
Monte Carlo intervals rather than selecting a favorable bin setting.

## Design and failure iteration

Each path keeps a circular history buffer. Recalibration only uses reported
states already generated on that path; numerical substeps are not extra data
observations. Simulated first-level states are preserved, while second-level
coefficients (including xi) and joint dependence are learned again. Frozen mode
has exact random-draw/output equivalence with the existing baseline.

Independent tests found an early workload guard allocated a huge origin list
before rejecting an excessive horizon. The implementation now checks integer
counts before allocation, factor operations and all work. It also bounds substep
advances and rejects nonfinite fitted likelihoods/audits. Failed paths abort with
path/step context; they are never filtered out of the reported sample.


## Full configured live run

The [live verification](live-verification.json), [model manifest](live-model-manifest.json.gz)
and [scenario summary](live-scenario-summary.csv) confirm the complete current-data
pipeline finished with 256 paths, 20 increments and 4,864 path/origin recalibrations.
All 198 regression tests passed in 45.096 seconds. No boundary projections occurred;
likelihood costs stayed within the configured budget. This run used the actual
YAML defaults, including every-step recalibration, rather than a reduced fixture.

The full live model manifest is stored as a lossless gzip archive to retain every
path/origin audit without expanding generated JSON throughout the source review.
The ordinary JSON verification file above provides its concise result summary.
