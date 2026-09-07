# Basel III Pipeline for Central Bank Paper

This project automates the processing of call reports and material events into regulatory metrics compliant with Basel III standards, as outlined by the Bank for International Settlements (BIS). It is designed for bank research and dynamically executes workflows based on `pipeline_config_dynamic.yaml`.

Use `pipeline/Task_manager_Global_yaml_driven.py` to run the workflow.
 
**Purpose:** yaml-driven task manager for executing the JSD analysis on call reports and RWA analysis on CMT data from FRED.

## Current Workflow

The current configuration contains 19 tasks for Call Report preparation, material events, peer groups, JSD and the final column filter. RWA components remain separately documented under `src/RWA/` and `RWA/`.

The manager reads `pipeline/pipeline_config_dynamic.yaml`. Its ordered execution phases, declared dependencies, input/output checks and per-task logs control the run. Independent FDIC downloads run concurrently; each later phase waits for the preceding phase to finish.

Run from the repository root:

```sh
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py
```

`--dry-run` displays expanded commands and expected artifacts without executing scripts. `--config` selects another YAML file; `--list` lists the configured tasks. Logs are written to `pipeline_logs/<run-id>/` by default. The manager executes the configured tasks on each run; it does not skip tasks by input hash.

## Shared Horizon and Bin Selection

The configuration starts with:

```yaml
parameters:
  horizons: [1, 2, 3, 4]
  bins1: [20, 30, 50, 100]
  bins2: 5
  bins3: 1
```

The default runs all four horizons and all four central bin counts. As an optional subset, changing `horizons` to `[1, 3]` and `bins1` to `[20, 50]` selects those horizons and central bin counts throughout the peer/JSD stages. `{horizons}`, `{bins1}`, `{bins2}` and `{bins3}` are expanded in YAML argument lists and artifact paths. A selection therefore controls both script work and the files checked by the manager.

`bins1` is the count across −1 to 1; `bins2` is the count across 1 to 2; `bins3` is one unbounded upper bin. The default specification with 20 central bins has 26 bins in total. The filename suffix records `bins1`, so changing `bins2` updates the output for that central count. See the [binning documentation](jsd/binning/readme.md) for boundaries and filenames.

## Direct Processing Programs

| Tasks | Program(s) |
| --- | --- |
| `1.0`–`4.0` | Five configured Call Report/ratio tasks |
| `6.0.1`–`6.4` | Eight material-event tasks calling one downloader, one cleaner, one RAW deletion program and one flagging program |
| `7.0` | `peer groups/base/Material_events_peer_group_basel3.py` |
| `7.1` | `peer groups/horizons/Material_events_peer_group_basel3.py` |
| `8.0` | `jsd/binning/Material_events_JSD_binning_basel3.py` |
| `8.1.1` | `jsd/pmf/Material_events_JSD_probabilities_basel3.py` |
| `8.2` | `jsd/calculation/Material_events_JSD_basel3.py` |
| `8.3.0.1` | `measures/intragroup/JSD_intragroup_filter.py` |

The shared peer programs require `--horizons`. Binning requires `--horizons` and `--bins1`, with `--bins2` and `--bins3` supplied from the shared configuration. PMF, calculation and filter programs require `--horizons` and `--bins`, where `--bins` receives the selected `bins1` counts. All accept `--material-dir`.

Material-event arguments remain independent: downloading and flagging require `--events` with one or more of `de_novo`, `failures` and `mergers`; cleaning and deletion default to all three when omitted. The YAML supplies those selections explicitly. See the [material-event CLI](material%20events/readme.md) and [FDIC API CLI](material%20events/FDIC%20API/readme.md).

### Directory Structure
- `pipeline/`:
  - `Task_manager_Global_yaml_driven.py`
  - `pipeline_config_dynamic.yaml`
- `data/`:
  - `CSV/`:
    - `Schedules/`:
      - `20240630/`:
        - `FFIEC CDR Call Schedule RC 06302024.csv`
    - `Cleaned/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Interleaved/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Dynamic_Lag/`:
      - `Cleaned/`:
        - `Dynamic_Cleaned_Call_Report_20240630.csv`
  - `TXT/`:
  - `PDF/`:
- `src/`: subroot directory containing all scripts.
  - `call reports/`:
    - `call_reports_mkdir_txt_csvs_global.py`
    - `Call_Report_Merged_Cleaned_Global.py`
    - `numeric_only.py`
    - `Call_Report.py`
    - `Call_Reports_v3_1.py`
  - `ratios/`:
    - `Dynamic_Ratios.py`
  - `material events/`:
    - `FDIC API/`:
      - `Material_events_download.py`
      - `Material_events_cleaned.py`
      - `Material_events_delete_api.py`
    - `Material_events_flag.py`
  - `peer groups/`:
    - `base/`:
      - `Material_events_peer_group_basel3.py`
    - `horizons/`:
      - `Material_events_peer_group_basel3.py`
  - `jsd/`:
    - `binning/`:
      - `Material_events_JSD_binning_basel3.py`
    - `pmf/`:
      - `Material_events_JSD_probabilities_basel3.py`
    - `calculation/`:
      - `Material_events_JSD_basel3.py`
  - `measures/`:
    - `intragroup/`:
      - `JSD_intragroup_filter.py`
    - `intergroup/`:
      - `JSD_intergroup_call_reports.py`

## Further Configuration

Additional schedule or regulatory-epoch workflows can be expressed through the manager's `sequential`, `concurrent_groups`, `concurrent_branches` and `intermediate_steps` phases. `execution` is an ordered list of phase mappings. Every configured task must appear once in the execution plan, and its dependencies must agree with that plan. See the [pipeline guide](../pipeline/readme.md) for the current parameter and argument format.

## Prerequisites

Use Python 3 with `pyyaml`, `pandas`, `numpy` and `requests` installed in the interpreter that runs the pipeline:

```sh
python3 -m pip install pyyaml pandas numpy requests
```

The shared path module resolves the project from `src/Basel3_Global_Filepath.py`; the project does not need an enclosing `CODE/` directory. The default configuration is `pipeline/pipeline_config_dynamic.yaml`.
