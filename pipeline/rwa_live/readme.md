# Acquire yields and run the recursive interest-rate model

[config.yaml](config.yaml) connects verified Treasury yield acquisition to the
recursive rate/sigma/xi model. Historical calibration retains all mu/theta/sigma
branches. Simulation advances one continuing trajectory, refreshing three separate
family dependence structures and CIR fits at every actual Euler increment.
It does not produce security-level valuation or duration-adjusted RWA.

## Run from the repository root

Install [requirements](../../requirements.txt), then set `snapshot_dir` and
`output_dir` in the configuration to two new repository-local directories. Do not
create them beforehand. Select an acquisition `start` early enough to supply
all historical calibration warmups and the ongoing estimate history.

```bash
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

The preview downloads nothing and performs no calibration. The real command
retrieves a new FRED snapshot and runs the model after verifying it. For another
full run, choose two new output names; completed destinations are not overwritten.

## Stage order and provenance

| Task | Executable | Result |
| --- | --- | --- |
| `acquire_yields` | `src/RWA/data/yields/acquire.py` | Preserved raw response, prepared `series/DGS*.csv` and `snapshot.json` |
| `rwa_hierarchy` | `src/RWA/models/parameter_hierarchy/workflow.py` | Historical calibration tables, serial-year trajectories and covariance archives |

The manager's dependency map runs from producer to dependent:

```yaml
dependencies:
  acquire_yields: [rwa_hierarchy]

execution:
  - sequential: [acquire_yields, rwa_hierarchy]
```

Script paths in YAML are relative to `src/`; artifact paths resolve from the
repository root. The model receives both the prepared series directory and
`snapshot.json`. It verifies hashes and the maturity/path contract, regenerates
prepared CSVs and quality metadata from the preserved bytes, and records the
snapshot provenance in its result manifest. Acquisition failure prevents the
model from running.

The default [Call Report/JSD pipeline](../readme.md) is separate. The
[existing-input model configuration](../rwa_hierarchy/readme.md) skips retrieval.

## History must contain estimates after warmup

The model defaults to `yield_window: 2520`, `parameter_window: 252` and
`history_window: 2520`. It needs at least **5,290 common source observations**:

```text
yield_window + parameter_window + history_window - 2
```

The last window represents 2,520 dates of rate/sigma/xi history after both fitting
passes, not 2,520 raw observations before estimation. First-pass mu/theta/sigma
histories and all three second-pass branches are retained. Use an early source
start, such as `2000-01-01`, and let the actual common count determine sufficiency;
a calendar start is not proof that every needed quote exists.

`recent_rows: 0` uses all selected data. An explicit positive cap must still
satisfy the full minimum and changes the starting ridge anchors. Missing-date
selection can reduce usable observations. Neither missing quotes nor unavailable
parameter estimates are manufactured to satisfy the history requirement.

Acquisition enforces `max_fill_days: 7` and `max_age_days: 7` by default. The
[yield-data guide](../../src/RWA/data/yields/readme.md) specifies transport limits,
source validation and supported maturity selection. It uses the public FRED graph
CSV HTTPS GET endpoint without an API key; it does not use the separate keyed
observations API. Freshness refers to each last genuine quote, not a filled row.

## Forecast and clock settings

The forecast defaults are one year, 252 reported steps per year, `dt=1/252`, one
substep per reported step, seed 1234 and zero correlation regularization.
`steps_per_year * dt` must equal one. `years: 2` continues year two from year one's
ending history, RNG and ridge anchors; it is not a second independent path.
Each additional substep triggers its own dependence calculation, calibration,
ordered xi → sigma → rate update and archive record.

The default historical settings are `time_basis: observation` and
`missing_policy: forward-fill`. To use genuine common-date quotes and actual
historical date gaps, set:

```yaml
time_basis: act365f
missing_policy: observed
```

ACT/365F divides historical calendar gaps by 365. Windows count observations or
estimates, while future intervals use their configured year fractions. There is
no future holiday calendar. The preserved snapshot retains its original quotes
and filling audit even when the model selects only genuinely observed dates.

`correlation_regularization: 0` keeps empirical correlations. A positive alpha
must be explicitly chosen; it and the unadjusted matrices are archived. Undefined
zero-variance correlations cannot be repaired by that setting. The
[model guide](../../src/RWA/models/parameter_hierarchy/readme.md) details numerical
assumptions, boundary behavior and the distinction between estimated diffusion
coefficients and evolved volatility states.

## Outputs, failures and repeats

The root output retains `yield_parameters.csv`, `parameter_dynamics.csv`,
`RAW/`, `CURVE/`, `transition_intervals.csv` and `initial_history.npz`.
Every `year_NNNN/` contains a
three-state trajectory, an archive for all actual increments, restart data and a
completion manifest. The root manifest is written after all requested years
finish. See the [output contract](../../RWA/Experimental/HIERARCHY/readme.md).
The previous four-state ensemble scenario files are not the current interface.

If acquisition succeeds but modeling fails, its verified snapshot remains usable.
Retry the model directly against that snapshot with a new model destination;
do not redownload into an existing snapshot directory. Streamed model records
without the required completion manifests are partial evidence, not a completed
result. Inspect source exclusions, fit/ridge audits, correlations and projections.

Downloaded history includes revisions available at retrieval. An earlier date
cutoff is not historical real-time-vintage retrieval. Successful simulation does
not identify latent risk, establish forecast superiority or provide portfolio
valuation and capital mapping.

## Verification
The [model verifier](../../src/RWA/models/parameter_hierarchy/readme.md#verify-a-completed-run)
checks a completed run from its preserved starting history, file hashes and
per-increment records. Its optional recalibration check repeats the fitted model
coefficients as well as replaying the saved transitions.


Use the [test guide](../../tests/readme.md) for isolated checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
python3 -B -m unittest discover -s tests -p test_pipeline_manager.py -v
```

Check actual results for acquisition failures, provenance verification,
three-family covariance identities, ordered-step replay and configured execution.
A live run supplies its own source snapshot and model manifests for review.
