# Interest-rate acquisition, calibration and recursive simulation

The RWA workflow retrieves Treasury yields, estimates mu/theta/sigma histories
across eight maturities, estimates dynamics for every parameter branch, and
advances one continuing trajectory of **rate, sigma and xi**. It recalculates
separate family dependence and CIR coefficients before every actual increment,
including the first. Its current endpoint is a serial trajectory with complete
calibration and covariance records. Exposure valuation and duration-adjusted RWA
remain downstream research stages.

## Model calculations

- [State factors and fitted μ/θ/diffusion coefficients](models/parameter_hierarchy/readme.md#state-and-coefficient-names)
- [Initialization and the complete 2,520-row history](models/parameter_hierarchy/readme.md#historical-initialization-estimates-need-their-own-warmup)
- [Full eight-maturity covariance calculation](models/parameter_hierarchy/readme.md#covariance-calculation-for-all-eight-maturities)
- [Repairing every factor at all eight tenors](models/parameter_hierarchy/readme.md#repairing-each-factor-at-every-tenor)
- [Cholesky calculation and all three 8×8 factors](models/parameter_hierarchy/readme.md#cholesky-calculation)
- [Brownian covariance and shock transformation](models/parameter_hierarchy/readme.md#brownian-covariance-and-the-shock-transformation)
- [Every-increment dependency and update order](models/parameter_hierarchy/readme.md#every-increment-calculation)

Each family's current level history produces its own C → R → L and Q = hR.
The three factors transform three independent eight-component normal vectors.
Every increment also refits xi's coefficients and rate/sigma's conditional
drifts, then advances xi, sigma using new xi, and rate using new sigma. The
updated states become part of the next covariance and calibration window.

Tenor repair covers first-pass μ/θ/σ, all three second-pass parameter branches,
and each recursive family. Healthy maturities anchor weak speeds; the repair
reprofiles the linked coefficients within a likelihood budget. During recursion,
rate/sigma's known higher-state variances remain fixed in that fit. This parameter
repair is distinct from optional correlation conditioning and the legacy NSS
commands; it does not rewrite historical rate quotes.

## Run the complete workflow

Run commands from the repository root. Install [requirements](../../requirements.txt)
and choose new `snapshot_dir` and `output_dir` values in the
[live configuration](../../pipeline/rwa_live/config.yaml). Do not create those
directories beforehand.

```bash
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

The preview resolves the plan without downloading or fitting. The real run
retrieves a new snapshot, verifies its provenance and executes the model. The
[live guide](../../pipeline/rwa_live/readme.md) describes settings and retries.

## Execution order

Acquisition and the model are the two shell-level stages. The model handles its
historical calibration and recursive calculations internally. Standalone legacy
NS/NSS and reconstruction scripts are not prerequisites.

| Order | Purpose and inputs | Output and next consumer |
| --- | --- | --- |
| 1. Acquire observations | [`data/yields/acquire.py`](data/yields/acquire.py) downloads FRED yields; validates dates, quotes, freshness and bounded causal fills. | Raw bytes, per-tenor prepared CSVs and `snapshot.json`, consumed by model verification. |
| 2. Verify and select history | [`models/parameter_hierarchy/workflow.py`](models/parameter_hierarchy/workflow.py) verifies source/prepared hashes, repeats preparation, applies cutoff/missingness policy and aligns maturities. | Common chronological yields with explicit transition intervals. |
| 3. Fit historical rate parameters | `calibrate_panel()` applies rolling CIR fits and coupled likelihood-budgeted ridge treatment to every tenor. | Date/maturity `mu`, `theta`, `sigma` histories with raw and stabilized estimates. |
| 4. Fit every parameter branch | `calibrate_parameters()` applies the same rolling estimator separately to mu, theta and sigma. | Speed, long-run mean and diffusion histories for all three branches, retained in `parameter_dynamics.csv`. |
| 5. Initialize recursive states | `walk_history()` aligns observed rates, first-pass sigma and the sigma branch's second-pass diffusion, then retains the requested complete state history. | At least 2,520 aligned estimate dates by default; `initial_history.npz` preserves the starting buffer, intervals and labels for replay. |
| 6. Recalculate dependence | `family_covariances()` computes, for each actual increment, three separate level covariances, normalized correlations, Cholesky factors and Brownian covariances. | Per-family 8×8 matrices; each factor transforms only its own eight-element shock vector. |
| 7. Self-calibrate and advance | `simulate_walk()` refits xi's CIR coefficients and fits rate/sigma drifts conditionally on their known varying higher-state histories; it updates xi, sigma using new xi, and rate using new sigma. It projects and audits each update, then appends it to the rolling history. | One serial trajectory and an audit for every numerical increment, including substeps. |
| 8. Continue and export | `run_years()` continues subsequent years from the previous year's final history, anchors and RNG state. Write yearly trajectories, covariance archives and restart state. | Completed year manifests and, after all requested years finish, the root completion manifest. |

[`core.py`](models/parameter_hierarchy/core.py) supplies the CIR estimator and
coupled stabilization. [`covariance.py`](models/parameter_hierarchy/covariance.py)
keeps family matrices distinct. [`recursive.py`](models/parameter_hierarchy/recursive.py)
coordinates each numerical increment, and
[`covariance_archive.py`](models/parameter_hierarchy/covariance_archive.py)
records the matrices and shocks actually used. Rate and sigma use right-endpoint higher-state history in their conditional
transition variance; xi retains a freely fitted diffusion. These are internal calculations,
not extra commands to run independently. The
[model guide](models/parameter_hierarchy/readme.md) defines equations, initialization,
projection, regularization and the implementation's interpretation of the PDF.

## History requirements and direct execution

The default `history_window=2520` requires **2,520 dates of parameter estimates**,
not merely 2,520 source quotes. Both rolling calibration passes need earlier data.
The minimum common source count is:

```text
yield_window + parameter_window + history_window - 2
2520 + 252 + 2520 - 2 = 5290
```

Missing-date selection can reduce available history. A snapshot must begin early
enough to satisfy the actual common count; unavailable estimates are not filled.
`--recent-rows 0` uses all selected history; any explicit truncation must still
satisfy this minimum and changes the initialization of prior-date ridge anchors.

For existing inputs, use the [local-input configuration](../../pipeline/rwa_hierarchy/readme.md)
or invoke the same model directly:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-serial-run \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

To use a verified snapshot, add `--input` and `--input-manifest` as shown in the
[yield-data guide](data/yields/readme.md). To continue across two forecast years
in one run, set `--years 2`. Year two continues year one's state and random stream;
years are not independent ensemble paths.

The default forecast `dt=1/252` and `steps_per_year=252` form one year.
Their product must equal one. `substeps` splits each reported step; every substep
also triggers dependence estimation, calibration and archive output.

Historical defaults use the observation clock and causal forward-fill.
`--time-basis act365f --missing-policy observed` selects genuine common-date
quotes and actual historical calendar gaps divided by 365. Historical and future
intervals remain aligned with the rolling buffer. Windows count observations;
ACT/365F does not generate a future business-day calendar or historical vintages.

## Source domains and legacy workflow

| Domain | Components |
| --- | --- |
| [Data](data/readme.md) | [Yield acquisition](data/yields/readme.md), [parameter reconstruction](data/parameters/readme.md) |
| [Calibration](calibration/readme.md) | Standalone [yield fitting](calibration/yields/readme.md), [NS/NSS repair](calibration/curves/readme.md) |
| [Models](models/readme.md) | [Recursive hierarchy](models/parameter_hierarchy/readme.md), numerical core and covariance archives |

The separate legacy sequence remains: standalone yield calibration →
[CURVE assembly](../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md) →
mu/theta NS/NSS repair → parameter reconstruction. Those commands replace their
configured legacy outputs. Independent NS/NSS smoothing and the integrated
model's coupled likelihood stabilization have different assumptions; retain each
run's method, inputs and audits when comparing or reusing them.

## Results and validation

Historical outputs are `yield_parameters.csv`, `parameter_dynamics.csv`, `RAW/`,
`CURVE/`, `transition_intervals.csv` and `initial_history.npz`. The root manifest's
`files_sha256` records the initial-history and historical-export hashes.
Each `year_NNNN/` contains a three-state
trajectory, per-increment covariance records, restart data and a completion
manifest. See the [output guide](../../RWA/Experimental/HIERARCHY/readme.md).
The former four-state ensemble arrays and quantile summaries are incompatible
with this serial output contract and are not generated by the current workflow.

Verify a completed run from its preserved starting history and increment records:

```bash
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run --recalibrate
```

Default verification checks hashes, rolling covariances, applied shocks, ordered
updates, clocks and year-restart continuity without new random draws. The optional
recalibration check also recomputes conditional lower-family drift fits and xi's
CIR fit from the stored history and causal anchors. See the
[model guide](models/parameter_hierarchy/readme.md#verify-a-completed-run) for cost
and interpretation.

Use the [test guide](../../tests/readme.md) to run isolated checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

Review actual results, identification warnings, likelihood costs, correlation
adjustments, source exclusions and boundary projections. Replaying a trajectory
checks computational provenance; it does not prove forecasting superiority or
separate estimation noise from economic risk. Cash flows, discount-curve
construction, valuation, loss definitions and capital mapping remain unfinished.
