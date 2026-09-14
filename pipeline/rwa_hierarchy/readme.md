# Run the recursive model from existing yield inputs

[config.yaml](config.yaml) runs the interest-rate model against supplied Treasury
yield histories without acquisition. It calibrates all historical parameter
branches, then advances one continuing rate/sigma/xi trajectory with separate
family dependence and calibration refreshed at every actual increment.

## Run

Install [requirements](../../requirements.txt) and work from the repository root.
Set `parameters.output_dir` to a new repository-local directory before execution.
Do not pre-create it.

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml
```

The dry run resolves commands and artifacts without executing the model. The
real run uses `RWA/FRED/DGS*.csv`; these historical files must contain enough common
observations. For current retrieved data and snapshot verification, use the
[live workflow](../rwa_live/readme.md) or the direct snapshot command in the
[model guide](../../src/RWA/models/parameter_hierarchy/readme.md).

## History and serial forecast settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `yield_window` | `2520` | Observations per historical rate calibration |
| `parameter_window` | `252` | Estimates per historical parameter-process calibration |
| `history_window` | `2520` | Complete aligned rate/sigma/xi estimate dates retained for recursion |
| `recent_rows` | `0` | Use all selected source rows; an explicit positive cap must include all warmups |
| `years` | `1` | Consecutive forecast years, each continuing the preceding year |
| `steps_per_year` | `252` | Reported increments in a year |
| `dt` | `0.003968253968253968` | Reported-step years; its product with steps per year must be one |
| `substeps` | `1` | Actual Euler increments per reported step; each recalibrates and archives |
| `correlation_regularization` | `0` | Preserve empirical family correlations; any positive adjustment must be explicit |
| `seed` | `1234` | Initialize one random stream, continued across years |
| `time_basis` | `observation` | Historical fixed observation clock or `act365f` date gaps |
| `missing_policy` | `forward-fill` | Causal fills or `observed` genuine common-date quotes |

The model needs at least `yield_window + parameter_window + history_window - 2`
common source observations: **5,290** at default settings. A 2,520-row yield input
cannot produce 2,520 fitted dates. Missing-date selection can reduce the usable
count; the model rejects insufficient history instead of padding estimates.

Set `years: 2` for a two-year continuous trajectory. The second year starts from
the preceding history, RNG and ridge anchors, not the historical origin. There
is no ensemble-path setting, frozen mode or reduced update cadence. Every actual
increment—including the first—refreshes all three dependence structures and fits
all three state families before xi → sigma → rate advancement.

## Historical elapsed time

To use genuine quotes and actual historical year fractions, set:

```yaml
time_basis: act365f
missing_policy: observed
```

ACT/365F divides calendar gaps by 365 days. Windows remain counts of observations
or fitted dates. Historical interval arrays follow the states through both
calibration passes and recursive buffers; each simulated substep supplies its
own year fraction. Future `dt` and `steps_per_year` define the forecast grid, not
a generated holiday calendar. If changing to 365 reported steps per year, change
both settings so their product remains one.

## YAML and outputs

The single task's source path is relative to `src/`:

```yaml
path: RWA/models/parameter_hierarchy/workflow.py
```

Input/output paths resolve from the repository root. Keep the explicit empty
`dependencies` mapping and the single `rwa_hierarchy` entry in the sequential
execution plan. Arguments expand from the top-level parameter block. Do not add
the model destination to `create_dirs` because the model rejects existing outputs.

The root output contains historical calibration tables, RAW/CURVE exports,
`transition_intervals.csv`, `initial_history.npz` and a completion `manifest.json`.
Each `year_NNNN/`
contains `trajectory.csv`, `trajectory.npz`, a per-increment `covariance/` archive,
`restart.npz` and its year manifest. See the
[output guide](../../RWA/Experimental/HIERARCHY/readme.md) for exact dimensions.
This replaces the former four-state ensemble output contract.

The manager checks declared inputs, subprocess exit status and output existence.
The model rejects invalid histories, insufficient warmup, undefined correlations,
unusable fits and invalid time settings. It streams audit records, so a failure
can leave partial data; completion manifests distinguish successful results.
Choose a new destination after correcting a failed run. A completed trajectory
does not calculate exposure valuation or capital/RWA.

## Verification
The [model verifier](../../src/RWA/models/parameter_hierarchy/readme.md#verify-a-completed-run)
checks a completed run from its preserved starting history, file hashes and
per-increment records. Its optional recalibration check repeats the fitted model
coefficients as well as replaying the saved transitions.


Use the [test guide](../../tests/readme.md) for isolated checks and run:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
python3 -B -m unittest discover -s tests -p test_pipeline_manager.py -v
```

Review the actual results and generated audits. Deterministic step checks,
separate covariance identities, archive replay and configured execution test
computational behavior; they do not establish forecast superiority.
