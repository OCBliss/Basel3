# Workflow configuration and execution

[Task_manager_Global_yaml_driven.py](Task_manager_Global_yaml_driven.py) executes
Python tasks from a YAML configuration. The repository provides separate plans
for Call Report/JSD analysis and interest-rate calibration and simulation.
These are research workflows; running them does not certify regulatory compliance
or produce a completed duration-adjusted RWA calculation.

| Workflow | Configuration | Scope |
| --- | --- | --- |
| Call Report and JSD analysis | [Default configuration](pipeline_config_dynamic.yaml) | Acquire and prepare reports/events, build ratios and cohorts, and calculate distribution comparisons. |
| Existing-input interest-rate model | [RWA hierarchy](rwa_hierarchy/readme.md) | Calibrate and forecast from supplied Treasury yield histories. |
| Retrieval through interest-rate model | [Live RWA](rwa_live/readme.md) | Acquire a verified Treasury snapshot, then calibrate and forecast from it. |

All commands below run from the repository root after installing
[requirements](../requirements.txt). Configure input selections and output locations
before a real run; use a dry run to inspect the resolved execution plan.

The requirements install the local [CallReports library](../src/callreports/README.md).
Its definitions, TXT conversion and schedule merge can also be used independently
of these research workflows.

## Run the Configured Pipeline

The current YAML contains **20 tasks**, covering Call Reports through the final JSD column filter. RWA components remain separate from this execution list.

From the repository root:

```sh
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py
```

Task `0.0` receives the active YAML through the reserved `{config_path}` argument. It completes before conversion and stops the pipeline if any required quarter cannot be prepared. Quarter tables remain in the tracked root-level `Material Events/` folder; output folders are created at runtime.

Use `--config path/to/config.yaml` for another configuration or `--list` to list its tasks. A dry run displays commands, inputs and outputs without creating directories, logs or subprocesses. A real run writes per-task logs under `pipeline_logs/<run-id>/`, unless `log_root` is configured.

For environment setup and the complete guide index, see the [root README](../README.md).

## Run the separate RWA hierarchy

The endogenous parameter hierarchy has its own configuration. Preview or execute
it from the repository root:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml
```

Before each execution, set a new `parameters.output_dir` in that YAML. The default
is `RWA/Experimental/HIERARCHY/run`; an existing output directory is an error.
The configuration fits all eight FRED tenors and retains 2,520 aligned estimate
dates after rolling warmups. Default yield and parameter windows are 2,520 and
252, requiring at least 5,290 common source rows. It uses all selected source
history by default and advances one serial year in 252 reported increments.
Every actual increment, including numerical substeps, recalculates three separate
family dependence structures and recalibrates rate, sigma and xi. The update
order is xi → sigma using new xi → rate using new sigma. Do not pre-create the
output directory.

Historical calibration tables and RAW/CURVE exports accompany each year's
trajectory, covariance/shock archive, restart state and completion manifest.
Multiple years continue the same evolving history and RNG; they are not
independent ensemble paths. See the [RWA execution guide](../src/RWA/readme.md),
[configuration guide](rwa_hierarchy/readme.md) and
[model specification](../src/RWA/models/parameter_hierarchy/readme.md).

## Call Report/JSD horizon and bin settings

Edit the top-level block in `pipeline_config_dynamic.yaml`:

```yaml
parameters:
  horizons: [1, 2, 3, 4]
  bins1: [20, 30, 50, 100]
  bins2: 5
  bins3: 1
```

The default runs all four horizons and all four central bin counts. For an optional run with only T+1 and T+3 and central counts 20 and 50, change the first two values to `horizons: [1, 3]` and `bins1: [20, 50]`. The same selection flows through peer creation, calendar concatenation, binning, PMFs, JSD calculations and the final filter. There are no separate horizon scripts to enable or disable.

`bins1` supplies positive counts across −1 to 1; `bins2` supplies one positive count across 1 to 2; `bins3` currently accepts only `1` for the unbounded upper interval. With `bins2: 5`, a `bins1` value of 20 produces 26 bins including the final interval. Filenames retain the central count, for example `_binned_20.csv`; changing `bins2` updates that specification's outputs.

## Argument and Artifact Expansion

Each script definition uses an `args` **list**. For example, the binning task contains:

```yaml
path: "jsd/binning/Material_events_JSD_binning_basel3.py"
args: ["--horizons", "{horizons}", "--material-dir", "Material Events", "--bins1", "{bins1}", "--bins2", "{bins2}", "--bins3", "{bins3}"]
```

With the default parameter block, this becomes `--horizons 1 2 3 4 --material-dir "Material Events" --bins1 20 30 50 100 --bins2 5 --bins3 1`. The manager passes each argument directly to the Python subprocess.

The same placeholders are expanded in `inputs`, `outputs` and `create_dirs`. A path containing both `{horizons}` and `{bins1}` expands to every selected horizon/bin combination. Repeated `{horizons}` occurrences within one path use the same horizon. Missing parameter names are configuration errors.

Expansion is enabled by a top-level `parameters` section; configurations without that section preserve literal braces in arguments and paths.

Script paths are relative to `src/`. Artifact paths and the default working directory are relative to the project root. `cwd` can override a task's working directory; argument values themselves are passed through after parameter expansion.

## Execution Order

| Tasks | Work |
| --- | --- |
| `0.0` | Download, validate and extract the required FFIEC quarters from the active material-event date ranges |
| `1.0`, `2.0`, `2.1` | Convert, merge and numerically clean Call Reports |
| `3.0` | `call reports/Call_Reports_v4_0.py`: two explicit ratio entries using the installed `callreports` API |
| `4.0` | `ratios/Dynamic_Ratios.py`: current and three historical-quarter changes through the v4 caller |
| `6.0.1`, `6.0.2`, `6.0.3` | Concurrent calls to `Material_events_download.py`, with separate event arguments |
| `6.1`, `6.1.1` | Clean material events, then remove matching RAW downloads |
| `6.2`, `6.3`, `6.4` | Sequential calls to `Material_events_flag.py` for de novo, failures and mergers |
| `7.0` | `peer groups/base/Material_events_peer_group_basel3.py` |
| `7.1` | `peer groups/horizons/Material_events_peer_group_basel3.py` |
| `8.0` | `jsd/binning/Material_events_JSD_binning_basel3.py` |
| `8.1.1` | `jsd/pmf/Material_events_JSD_probabilities_basel3.py` |
| `8.2` | `jsd/calculation/Material_events_JSD_basel3.py` |
| `8.3.0.1` | `measures/intragroup/JSD_intragroup_filter.py` |

There are two direct peer-group programs, one binning program, one PMF program, one calculation program and one final filter program. They receive the shared selections through YAML. The filter also receives `--threshold 0.3` from its task definition.

The `execution` section is an ordered list. Each phase completes before the next begins. `sequential` and `intermediate_steps` run tasks in order; `concurrent_groups` runs independent tasks together; `concurrent_branches` can describe independent nested workflows. The current configuration runs only the three FDIC downloads concurrently.

Dependencies validate prerequisites without automatically adding omitted tasks. Every configured task must appear once in the execution plan. The manager checks script locations, artifact declarations and process exit codes, and stops on a failed task. It executes each configured task once per run; it does not skip work based on input hashes.

## Further Customization

Additional schedules or regulatory epochs can use the same phase types with their own declared scripts, arguments, paths and dependencies. Keep their execution plans and artifact declarations aligned. Horizon and bin choices within the current Basel III workflow belong in `parameters`, so those choices do not require copied script files or duplicated horizon branches.


## Retrieve yields and run the RWA model

The [live RWA workflow](rwa_live/readme.md) connects FRED retrieval to the hierarchy
with a verified snapshot, preserving the historical local input files. Choose new
snapshot and model output directories in its configuration, then run:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py --config pipeline/rwa_live/config.yaml
```

This two-task workflow is separate from both the default Call Report/JSD plan and
the one-task offline hierarchy plan. Its dependency mapping runs acquisition first.
