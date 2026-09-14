# Acquire Treasury yields and run the parameter model

[config.yaml](config.yaml) connects current yield retrieval and preparation to the
existing interest-rate parameter hierarchy. Both stages run through the real
pipeline manager with an explicit dependency. This workflow produces verified
input snapshots, parameter estimates and scenarios; it does not calculate
security-level duration losses or duration-adjusted RWA.

## Run from the repository root

Install [requirements](../../requirements.txt). Before running, edit
`parameters.snapshot_dir` and `parameters.output_dir` in [config.yaml](config.yaml)
to two new directory names inside the repository. Do not create those directories;
the producing stages create them after their validation succeeds.

```bash
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

The preview resolves the plan without downloading yields or running calibration.
The live command performs an HTTPS download. Existing snapshot/model output
locations are rejected; changing only the model output name is insufficient for
another complete acquisition run. Use new values for both on each repeat.

## Stages and dependency direction

| Stage | Source entry point | Output consumed next |
| --- | --- | --- |
| `acquire_yields` | `src/RWA/data/yields/acquire.py` | `snapshot.json`, preserved `raw/fred.csv`, prepared `series/DGS*.csv` |
| `rwa_hierarchy` | `src/RWA/models/parameter_hierarchy/workflow.py` | Calibration tables, scenarios and result `manifest.json` |

Script `path` entries in YAML are relative to `src/`. Data paths and parameterized
output locations resolve from the repository root. The manager's dependency map
runs from producer to dependent:

```yaml
dependencies:
  acquire_yields: [rwa_hierarchy]

execution:
  - sequential: [acquire_yields, rwa_hierarchy]
```

The model receives both `--input {snapshot_dir}/series` and
`--input-manifest {snapshot_dir}/snapshot.json`. It verifies hashes, source paths
and the maturity contract, and independently regenerates prepared CSVs and
quality metadata from the preserved raw bytes before calibration. Its result
manifest records this acquisition provenance. Reversing the dependency map would
require the acquisition stage to wait for its own downstream consumer.

The default Call Report/JSD pipeline remains separate. The existing
[local-input hierarchy configuration](../rwa_hierarchy/readme.md) also remains
available when retrieval is not part of the requested run.

## Settings

| Parameter | Default | Effect |
| --- | --- | --- |
| `snapshot_dir` | `RWA/FRED/snapshots/run` | New raw/prepared input snapshot |
| `output_dir` | `RWA/Experimental/HIERARCHY/live-run` | New model result directory |
| `start` | `2010-01-01` | First permitted observation date |
| `max_fill_days` | `7` | Calendar-day quote-gap/fill limit |
| `max_age_days` | `7` | Maximum last-genuine-quote age relative to requested end |
| `yield_window` | `2520` | Observations in each first-pass calibration window |
| `parameter_window` | `252` | Observations in each parameter-process window |
| `recent_rows` | `3024` | Last common-history rows used by the model; `0` uses all |
| `paths`, `steps`, `substeps` | `256`, `20`, `4` | Scenario count, reported steps and internal Euler increments per step |
| `seed` | `1234` | Reproducible simulation random seed for fixed inputs/settings |
| `forecast_mode` | `recursive` | Pathwise recalibration; use `frozen` for origin coefficients and dependence. |
| `recalibrate_every` | `1` | Reported-step cadence for recursive updates; zero disables updates. |
| `time_basis` | `observation` | Historical transition clock: `observation` or `act365f`. |
| `missing_policy` | `forward-fill` | Causal fills or `observed` genuine common-date quotes. |
| `dt` | `0.003968253968253968` | Future reported-step year fraction (1/252); also the historical interval in observation mode. |

Acquisition defaults to all eight supported maturities and a requested end of the
local current date. The YAML does not currently expose an `end` parameter; use
the [acquisition CLI](../../src/RWA/data/yields/readme.md) for a fixed cutoff, or
explicitly add and pass `--end` when adapting a copy of this configuration.
The estimation-noise benchmark is disabled unless explicitly added to the
model arguments; use zero or at least two replicates.

The 2010 start is a bounded history choice. Validation still checks the actual
returned data; the chosen start does not justify imputing arbitrary gaps or
assuming every series is continuous. Freshness is measured from each last
**genuine** quote, not from a filled endpoint.

## Configure elapsed-time calibration

The saved YAML preserves the historical observation-clock/forward-fill defaults.
To fit genuine observations using actual historical year fractions, set these
existing entries in its `parameters` block:

```yaml
time_basis: act365f
missing_policy: observed
dt: 0.003968253968253968
```

The model arguments already pass these settings. `observed` reads original
`DGS<n>` values and retains only dates genuinely observed across all selected
tenors; it does not fit prepared fill values. ACT/365F divides the calendar time
between retained dates by 365 days, including weekends, gaps and leap years.
Both rolling calibration passes, dependence residuals, the optional noise
benchmark and recursive history buffers use those historical intervals.

Windows and `recent_rows` remain observation counts, so a common count can span
different dates under the two policies. `dt` remains the regular **future**
year-fraction increment; use `0.0027397260273972603` for 1/365 if that forecast grid
is intended. No business-day/holiday forecast calendar is generated. Substeps
refine each future increment without creating extra calibration observations.

Review `transition_intervals.csv`, the manifest's `time_convention`, source
exclusions and fitted-parameter audits. Retaining actual durations does not remove
Euler approximation error, informative-missingness bias or estimation noise, and
it does not construct an arbitrage-free spot curve. See the [model guide](../../src/RWA/models/parameter_hierarchy/readme.md)
and [elapsed-time tests](../../tests/test_rwa_elapsed_time.py).

## Outputs, failures and reruns

The [yield-data guide](../../src/RWA/data/yields/readme.md) specifies the five-column
prepared series, raw-response retention, seven-day defaults, bounded retries and
8 MiB response cap. This is FRED's public graph CSV HTTPS GET route and needs no
API key; it is not an implementation of the separate keyed observations API.

The [model guide](../../src/RWA/models/parameter_hierarchy/readme.md) describes
`yield_parameters.csv`, `parameter_dynamics.csv`, RAW/CURVE exports,
`scenario_summary.csv`, `scenarios.npz`, historical `transition_intervals.csv`
and the final completion manifest. Forecast outputs include `elapsed_years`. Check
both the snapshot's quality report and the model's diagnostics. Successful
execution does not establish statistical identification or forecast superiority.

If acquisition fails, the dependent model must not run. If modeling fails after
acquisition succeeds, the completed source snapshot remains usable; a model
directory without a completion manifest is incomplete. To retry modeling against
that same verified snapshot, use the direct model command in the yield-data guide
with a new model output directory instead of redownloading into an existing path.
For a fresh full run, choose two new paths and run the manager again.

Retrieved history reflects revisions available at download time. Restricting
observation dates is not historical real-time-vintage retrieval. The model still
uses a finite parameter hierarchy with pathwise recalibration of the second-level
coefficients and full joint dependence. Exposure valuation is a separate stage.

## Verification

Use the repository-local temporary/cache setup in the
[test guide](../../tests/readme.md) for isolated checks:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_yield_data.py -v
python3 -B -m unittest discover -s tests -p test_rwa_hierarchy.py -v
```

The acquisition tests exercise malformed/network failures, chronological filling,
freshness, publication and provenance verification; hierarchy checks cover model
contracts and actual manager execution on isolated inputs. A live run additionally
checks the current source response and produces its own snapshot and model
manifests; inspect both before treating the pipeline as complete.


## Forecast mode and update cadence

The configuration selects `forecast_mode: recursive` and `recalibrate_every: 1`.
Each path recalibrates mu/theta/sigma dynamics and full joint dependence from its
own rolling history before its next reported step. Set `forecast_mode: frozen`
for the origin-calibration benchmark, or increase `recalibrate_every` to compare
less frequent updates. Changes to a path's calibration cannot use future draws
or another path's simulated observations. The model guide specifies numerical
bounds, failure behavior and per-path diagnostics in `recursive_calibration`.
