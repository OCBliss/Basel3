# RWA hierarchy pipeline

[config.yaml](config.yaml) runs the
[endogenous parameter hierarchy](../../src/RWA/models/parameter_hierarchy/readme.md)
through the repository's YAML task manager. It is a separate one-task workflow;
the [default Call Report/JSD configuration](../pipeline_config_dynamic.yaml)
retains its own execution plan.

## Prepare and run

Install the [repository requirements](../../requirements.txt). Supply the eight
`RWA/FRED/DGS{1,2,3,5,7,10,20,30}.csv` input histories, each containing
`observation_date` and its named DGS column. The workflow reads existing files;
it does not fetch new quotes.

Before each real run, set `parameters.output_dir` in `config.yaml` to a **new**
directory inside `Basel3_repo`. Do not create that directory beforehand. All
commands below run from the repository root:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml
```

The dry run resolves the configuration and displays the command and artifact
paths without starting the model or creating directories/logs. It does not test
numerical suitability of the data. A real run writes task logs under
`pipeline_logs/<run-id>/` unless `log_root` is configured.

## Settings

| YAML parameter | Default | Effect |
| --- | --- | --- |
| `output_dir` | `RWA/Experimental/HIERARCHY/run` | New destination for one complete run. Existing destinations are rejected. |
| `yield_window` | `2520` | Observations in each trailing first-pass yield fit. |
| `parameter_window` | `252` | Observations in each trailing fit to estimated mu, theta and sigma histories. |
| `recent_rows` | `3024` | Retain this many of the most recent common input dates; zero uses all common dates. |
| `paths` | `256` | Number of joint simulated paths. |
| `steps` | `20` | Number of reported forecast increments after the initial state. |
| `substeps` | `4` | Internal Euler increments per reported increment. |
| `seed` | `1234` | Reproducible simulation seed. |
| `noise_replicates` | `0` | Disable the estimation-noise benchmark; use at least two to enable it. Sixteen gives a small diagnostic at additional cost. |

The model's other defaults include `dt = 1/252`, all eight maturities, likelihood
repair budget `2`, fallback theta `0.25` and correlation shrinkage `0.05`.
Changing `substeps` refines the numerical approximation while keeping each
reported increment's duration unchanged. The
[model guide](../../src/RWA/models/parameter_hierarchy/readme.md) explains the settings,
minimum history, units, diagnostics and Python interface.

## YAML path and execution contract

The single step is `rwa_hierarchy`, with this source path:

```yaml
path: RWA/models/parameter_hierarchy/workflow.py
```

Script paths resolve relative to `src/`, so this value deliberately omits a
leading `src/`. Input/output artifact paths and the default task working
directory resolve from the repository root, even though the YAML now lives in
this nested directory. Arguments are a list; values such as `"{output_dir}"`
expand from the top-level `parameters` block.

`dependencies: {}` is an explicit empty dependency mapping and the execution
plan is `sequential: [rwa_hierarchy]`. Keep these entries when modifying this
configuration. The step must occur exactly once in the execution plan. Do not
add `output_dir` to `create_dirs`: the model intentionally refuses an existing
output destination.

## Results and failure handling

The configured completion artifacts are `manifest.json`,
`parameter_dynamics.csv`, `scenario_summary.csv` and `scenarios.npz` beneath
`output_dir`. The workflow additionally writes `yield_parameters.csv`,
per-maturity `RAW/` histories and three `CURVE/` tables. The manifest records
settings, source hashes, regularization/dependence diagnostics, boundary
projections and the optional estimation-noise benchmark; it is written last.
An output directory without a completion manifest is incomplete.

The task manager checks declared inputs, subprocess status and declared output
existence, stopping on a failed task. The model rejects paths escaping the
repository, existing output destinations, invalid histories/settings,
insufficient calibration history and excessive simulation size. Excessive
mean-reversion speed for the chosen step requires more substeps. Inspect the
task log and any partial output, correct the cause, and choose a new output
directory before rerunning; existing results are not overwritten.

The current finite hierarchy simulates yield, mu, theta and sigma jointly while
holding second-level calibration fixed. Estimated parameter volatility includes
estimation noise. It does not yet recalibrate each simulated path, value
exposures or calculate RWA capital. Use the output contracts and validation
limits in the [model guide](../../src/RWA/models/parameter_hierarchy/readme.md) when
building a downstream consumer.

## Verification

Use the repository-local temporary-file setup in the
[test guide](../../tests/readme.md), then run:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_hierarchy.py -v
python3 -B -m unittest discover -s tests -p test_pipeline_manager.py -v
```

The hierarchy tests execute this actual configuration through the manager with
isolated two-tenor fixtures and reduced numerical settings, then check
completion. They also exercise direct CLI output, downstream reconstruction,
causality, numerical behavior and path boundaries. The manager suite verifies
configuration parsing, argument expansion, dependency ordering and failures.
