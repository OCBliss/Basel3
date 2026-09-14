# Recursive model outputs and serial-year archives

Each child directory is a separately initialized model run. Generated runs are
excluded from Git; this guide is tracked. Source snapshots remain under
[FRED snapshots](../../FRED/snapshots/readme.md). Within a run, `year_0002` continues
`year_0001`; it is not an independent scenario drawn from the same origin.

## Produce a run

Install [requirements](../../../requirements.txt) and obtain a
[sufficiently long snapshot](../../../src/RWA/data/yields/readme.md). From the
repository root, choose a new model destination:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-yield-snapshot/series \
  --input-manifest RWA/FRED/snapshots/my-yield-snapshot/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

Do not create the destination beforehand. Default initialization requires at
least **5,290 common source observations** to produce 2,520 aligned rate/sigma/xi
history dates after both calibration warmups. The first-pass mu/theta/sigma
histories and all three second-pass branches are retained. `--recent-rows 0`
uses all selected inputs; an insufficient positive limit fails.

Add `--time-basis act365f --missing-policy observed` for genuine common-date quotes
and calendar-gap historical calibration. For historical local DGS inputs, omit
both input arguments. The [model guide](../../../src/RWA/models/parameter_hierarchy/readme.md)
and [pipeline guide](../../../pipeline/rwa_live/readme.md) explain full settings.

## Root files

| File | Contract |
| --- | --- |
| `yield_parameters.csv` | Historical date/maturity CIR mu/theta/sigma, raw estimates and ridge audits |
| `parameter_dynamics.csv` | Historical date/maturity/parameter second-pass fits for every mu/theta/sigma branch |
| `RAW/DGS<n>_with_parameters.csv` | Chronological model-used yields and first-pass parameters, including unavailable warmup |
| `CURVE/{mu,theta,sigma}_curve.csv` | Date-keyed wide maturity panels from the same fits |
| `transition_intervals.csv` | Historical start/end dates and `dt_years` |
| `initial_history.npz` | Starting `history` with default shape `(2520,3,8)`, `history_dt`, `maturities`, `state_names` and ISO-string `dates` |
| `manifest.json` | Overall completion, settings, source provenance, calibration/time conventions, serial-year records and `files_sha256` for initialization/historical exports; written last |

FRED yields retain percentage-point units. RAW's DGS and `yield_clean` columns
contain model-used values: causal fills in forward-fill mode or genuine common-date
quotes in observed mode. Preserve the source snapshot for original missingness.
RAW/CURVE columns do not encode their clock; retain the manifest and interval file.
The [reconstruction consumer](../../../src/RWA/data/parameters/readme.md) accepts
compatible historical exports but its six-column result omits these audits.

## Each year directory

| File | Contract |
| --- | --- |
| `trajectory.csv` | Long table: `step,elapsed_years,state,maturity,value` |
| `trajectory.npz` | `states` with axes `(reported step including origin, 3 states, maturity)`, `state_names`, `maturities`, `elapsed_years` and boundary projections |
| `covariance/step_000000.npz`, ... | Matrices, coefficients, before/after states and realized shocks for every actual Euler increment |
| `covariance/index.jsonl` | Consecutive increment inventory with checksums and elapsed interval bounds |
| `covariance/manifest.json` | Completion and integrity information for the increment archive |
| `restart.npz` | Final `history`, matching `history_dt`, `prior_thetas` and `maturities`; the year manifest supplies the matching RNG state |
| `manifest.json` | Year completion, calibration/projection audits, random-generator and ridge-anchor continuation records |

State order is `rate`, `sigma`, `xi`; each has eight maturities by default.
There is **no ensemble axis**. A year has `steps_per_year` reported steps and
`steps_per_year * substeps` actual increments. Both covariance estimation and
CIR recalibration occur before every actual increment, including increment zero.
Substeps therefore add archive records and calibration observations.

`--years 2` keeps the ending history, RNG and prior calibration anchors when it
starts the next year. This is serial time continuation. The default year is 252
reported increments of 1/252 year each; `steps_per_year * dt` must equal one.
Trajectory `elapsed_years` is measured from the overall forecast origin.
Covariance increment times are local to their year directory; add the year index
minus one to place them on the overall forecast clock. This is an explicit
elapsed-time grid, not a generated holiday calendar.

## Read an increment record

Every matrix field has shape `(3, maturity, maturity)`: one separate matrix per
state family. The archive distinguishes level covariance `factor_covariance` C,
normalized `raw_correlation`, used `correlation` R, its `cholesky` L, and
`brownian_covariance` Q. They satisfy `L @ L.T = R` and `Q = dt_years * R`.
Each realized `brownian_increments` family is an eight-element vector.
`normal_shocks` and the archived factors reproduce `sqrt(dt_years) * L @ Z`.

`coefficients` records theta/long-run-mean/diffusion by family;
`coefficient_names` labels that axis. For xi, diffusion is freely fitted. For
rate and sigma it is the actual transition multiplier, respectively new sigma
and new xi. Their drifts are fitted conditionally on known right-endpoint
higher-state history, rather than fitting a substitute constant diffusion.
`state_before`, `state_after` and the JSON
`calibration_audit` show the values and ridge treatment actually used. The update
uses new xi in sigma's shock, then new sigma in rate's shock. The `diffusion_source`
audit labels distinguish an applied higher-state value from xi's fitted diffusion;
historical coefficient tables retain their own original estimation meanings.

Correlation regularization defaults to zero. If explicitly selected, its alpha,
the original level covariance and raw correlation are retained. Undefined
zero-variance correlations fail even with regularization. Keep all records and
manifests together when checking or replaying a run.

## Verify the saved evidence

From the repository root, verify a completed run without generating new shocks:

```bash
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run
```

The [verifier](../../../src/RWA/models/parameter_hierarchy/verify.py) starts from
`initial_history.npz`, checks hashes, rebuilds rolling covariances, and replays
every archived shock and ordered update. It checks trajectory timing and the
state/interval continuity of yearly restarts. Keep the root initialization,
historical exports, yearly manifests and complete increment archives together.

Add `--recalibrate` to recompute the conditional rate/sigma drift fits and xi CIR
fits at every increment from the historical/simulated window and prior anchors:

```bash
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run --recalibrate
```

This deeper check adds model-fitting work. Default replay validates the applied
coefficients and recorded transitions; recalibration also checks their derivation.
A successful check establishes consistency of the saved evidence, not scientific
validity or independently authenticated source data.

## Compatibility, failures and interpretation

This format replaces the former four-state ensemble `scenarios.npz` and
`scenario_summary.csv` interfaces. Existing consumers must migrate to the labelled
three-state trajectory and serial-year layout. Years must not be treated as
independent draws or used to manufacture ensemble confidence intervals.

The archive is streamed. A failure can leave useful partial records without a
completion manifest; their presence does not make the run complete. Existing
output directories are rejected. Correct invalid settings, insufficient history,
failed correlations or unusable fits, then choose a new destination for a fresh run.
There are no discarded failed paths or silent replacements of missing states.

Review the [model assumptions](../../../src/RWA/models/parameter_hierarchy/readme.md)
and [test instructions](../../../tests/readme.md). Recursive calibration retains
estimation noise and regularization effects. A complete trajectory is neither an
arbitrage-free discount curve nor a valuation or capital/RWA result.
