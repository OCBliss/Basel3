# Interest-rate calibration and scenario workflow

The RWA model estimates Treasury yield dynamics across eight maturities, estimates
processes for the resulting mu, theta and sigma histories, and simulates those
parameters jointly with yields. It supports both frozen calibration and recursive
pathwise recalibration. Its current endpoint is an auditable set of parameter
estimates and scenarios for the [RWA research area](../../RWA/README.md).
Exposure valuation, duration-sensitive losses, VaR and capital mapping remain
separate research stages.

## Run the complete workflow

Run all commands from the repository root. Install the
[Python requirements](../../requirements.txt), then choose new `snapshot_dir` and
`output_dir` values in [the live configuration](../../pipeline/rwa_live/config.yaml).
The stages create these directories; do not create them beforehand.

```bash
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

The preview resolves commands and artifact paths without downloading data or
running the model. The real run retrieves current FRED data, verifies a new
snapshot and executes the model. The [live pipeline guide](../../pipeline/rwa_live/readme.md)
documents its settings, dependency order and rerun behavior. The saved configuration
selects recursive forecasts; direct model commands default to frozen forecasts.

## Execution order

The canonical workflow consists of acquisition followed by one model command.
The model performs both calibration passes internally; the standalone legacy
calibration, NS/NSS and reconstruction scripts are not prerequisite tasks.

The manager first runs [`data/yields/acquire.py`](data/yields/acquire.py), then
[`models/parameter_hierarchy/workflow.py`](models/parameter_hierarchy/workflow.py).
Within the model command, the function calls follow this sequence:

```text
acquire.py: acquire_snapshot()
    → download_yields() → parse_yields() → write verified snapshot
workflow.py: main()
    → verify_snapshot() → read_yield_panel()
    → calibrate_panel()                 # yield → mu, theta, sigma histories
    → calibrate_parameters()            # each parameter → its own CIR history
    → forecast_inputs()                 # origin states and joint dependence
    → simulate() or simulate_recursive()
    → parameter_noise_diagnostic()      # optional; paths already generated
    → write_outputs()                   # completion manifest written last
```

Both calibration passes call [`core.py`](models/parameter_hierarchy/core.py)'s
`stabilize_panel()` and `fit_cir()`. Scenario steps use its `step_hierarchy()`.
[`recursive.py`](models/parameter_hierarchy/recursive.py) additionally refits
parameter dynamics and dependence from each path's available history. These
functions run inside the model process; they are not additional shell commands.

| Order | Operation | Result and next consumer |
| --- | --- | --- |
| 1 | **Retrieve and validate yields.** Download the requested FRED series, preserve original bytes, enforce date/freshness/gap limits and prepare bounded causal fills. | A new snapshot containing raw CSV, per-tenor series and `snapshot.json`. |
| 2 | **Verify and select model observations.** Reproduce snapshot preparation and check hashes; apply the observation cutoff, missing-quote policy, common-date alignment and optional history truncation. | A chronological yield panel with an explicit historical time convention. |
| 3 | **Calibrate yield dynamics.** At each rolling date, estimate mu, theta and sigma for every maturity. Diagnose weak mean reversion and jointly reprofile the coefficients within a likelihood-cost budget using cross-maturity or earlier-date anchors. | Stabilized first-pass parameter histories and their raw-fit/repair audits. |
| 4 | **Calibrate parameter dynamics.** Apply the rolling CIR fit and coupled ridge stabilization separately to the complete mu, theta and sigma histories across maturities. | Nine second-level coefficients per tenor: mean reversion, mean level and diffusion for each parameter process. |
| 5 | **Estimate joint dependence.** Standardize trailing innovations using the fitted drift, diffusion and historical intervals; estimate the full cross-state/cross-tenor correlation, shrink it and factor it. | Origin state, second-level coefficients and a joint shock factor. |
| 6 | **Generate scenarios.** Advance X, mu, theta and sigma with simultaneous left-point Euler steps. Frozen mode retains the origin calibration; recursive mode refits parameter processes and dependence using each path's own rolling history before subsequent shocks. | Joint paths, projection counts and, in recursive mode, path/origin recalibration diagnostics. |
| 7 | **Run the optional estimation-noise diagnostic.** When enabled, generate constant-parameter yield panels and rerun both rolling calibration passes and stabilization. | A conditional comparison showing how estimation and repair can themselves produce apparent parameter volatility. It does not alter the scenario paths. |
| 8 | **Export the completed run.** Write parameter tables, compatible RAW/CURVE tables, historical intervals, scenarios and summaries; write the completion manifest last. | Auditable outputs for model comparison and future valuation consumers. |

The [model specification](models/parameter_hierarchy/readme.md) gives the equations,
regularization rules, missing-data choices and failure behavior. In this finite
hierarchy, the fitted diffusion of the sigma process supplies xi; xi is not an
additional independently simulated state. Estimated parameter dynamics can include
estimation noise, even when the generating economic parameters are constant.

## Reuse existing inputs

The [local-input pipeline](../../pipeline/rwa_hierarchy/readme.md) reads
`RWA/FRED/DGS*.csv` without downloading or checking snapshot provenance. Its model
command can also be run directly, with an explicit forecast mode and new output:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/example-recursive-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --forecast-mode recursive --recalibrate-every 1 \
  --paths 32 --steps 10 --substeps 8
```

To reuse an acquired snapshot instead, supply both `--input` and
`--input-manifest` as shown in the [yield-data guide](data/yields/readme.md).
Enable the optional diagnostic with `--noise-replicates N`, where N is at least
two; it reruns both calibration passes for each replicate and adds computation.
Use `--forecast-mode frozen` for the origin-calibration comparison.

Defaults use `--time-basis observation --missing-policy forward-fill`: one fixed
historical interval per retained row. For genuine common-date quotes and actual
calendar durations, select `--time-basis act365f --missing-policy observed`.
Both rolling passes, dependence, the noise diagnostic and recursive buffers use
the selected historical intervals. Windows count observations. `--dt` remains
the regular future interval in years; forecasts do not generate a trading calendar.
An observation cutoff on a current download does not recover a historical vintage.

## Source organization and legacy workflow

| Domain | Components |
| --- | --- |
| [Data](data/readme.md) | [Yield acquisition](data/yields/readme.md) and [parameter reconstruction](data/parameters/readme.md) |
| [Calibration](calibration/readme.md) | Standalone [yield fitting](calibration/yields/readme.md) and [NS/NSS curve repair](calibration/curves/readme.md) |
| [Models](models/readme.md) | [Parameter hierarchy](models/parameter_hierarchy/readme.md): workflow, numerical core and recursive engine |

The legacy file-based sequence remains available for separate experiments:

1. Run standalone [yield calibration](calibration/yields/readme.md).
2. Assemble mu, theta and sigma panels using the
   [CURVE preparation recipe](../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md).
3. Run [mu/theta NS/NSS repair](calibration/curves/readme.md) and inspect its audit.
4. Run [parameter reconstruction](data/parameters/readme.md) to create the
   six-column histories described in [MLE VOL/RAW](../../RWA/Experimental/MLE%20VOL/RAW/readme.md).

These commands replace their configured legacy output files. Independent NS/NSS
smoothing and the canonical model's coupled likelihood stabilization have different
assumptions. Keep their methods, input histories and timing conventions explicit
when comparing or reusing outputs.

## Results, verification and research endpoint

A model run produces `yield_parameters.csv`, `parameter_dynamics.csv`, `RAW/`,
`CURVE/`, `transition_intervals.csv`, `scenarios.npz`, `scenario_summary.csv` and
`manifest.json` beneath its selected output directory. See the
[output guide](../../RWA/Experimental/HIERARCHY/readme.md) for schemas. A directory
without its completion manifest is incomplete. Review identification warnings,
likelihood costs, imputation/exclusion counts and boundary projections before
using scenarios downstream.

Use the environment and temporary-file instructions in the
[test guide](../../tests/readme.md), then run the RWA checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

Tests cover likelihood and interval calculations, causal windows, all parameter
branches, recursive path isolation, frozen equivalence, output contracts and
configured pipeline execution. Successful execution does not establish forecast
superiority, separate latent dynamics from measurement error or produce an
arbitrage-free discount curve. Completing duration-sensitive RWA requires explicit
curve construction, exposure cash flows and valuation, loss/risk definitions,
capital mapping and independent validation.
