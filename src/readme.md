# Basel3 source code

The code in `src/` turns FFIEC Call Reports into bank-level ratios and changes in those ratios, attaches material-event flags, builds the corresponding peer groups, and compares their distributions. The current pipeline ends with the JSD column filter. The RWA programs and intergroup analysis are separate from that execution plan.

Component guides: [Call Reports](call%20reports/readme.md),
[ratios](ratios/readme.md), [material events](material%20events/readme.md),
[peer groups](peer%20groups/readme.md), [JSD](jsd/readme.md),
[measures](measures/readme.md), and [RWA](RWA/readme.md).

## Run the pipeline

Run these commands from the repository root, the directory containing `requirements.txt`, `pipeline/` and `src/`:

```sh
python3 -m pip install -r requirements.txt
python3 "src/call reports/prepare_call_reports.py" --plan
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py
```

The first preview lists the Call Report quarters required by the material-event settings. The manager's dry run shows all configured commands and input/output paths. Neither preview downloads reports or starts processing. The final command runs the pipeline, beginning with the download and preparation stage.

To use another configuration, pass it to either command:

```sh
python3 "src/call reports/prepare_call_reports.py" --config path/to/config.yaml --plan
python3 pipeline/Task_manager_Global_yaml_driven.py --config path/to/config.yaml
```

The manager passes the actual configuration path to preparation through the reserved `{config_path}` argument. An alternate configuration therefore supplies its own material-event dates; preparation does not fall back to the default YAML.

## Download the required Call Reports

`call reports/prepare_call_reports.py` runs as stage `0.0`, before TXT conversion. It reads `--start-date` and `--end-date` from the configured `Material_events_download.py` tasks, currently `6.0.1`, `6.0.2` and `6.0.3`. It takes the union of the quarter-end dates in those ranges and adds the three preceding quarters needed by the current P1Q/P2Q/P3Q calculations.

With the current event range of `2014-01-01` through `2024-12-31`, preparation downloads:

- **44 reporting quarters:** 2014Q1 through 2024Q4.
- **3 history quarters:** 2013Q2, 2013Q3 and 2013Q4.

Each of the 47 downloads is the **Call Reports -- Single Period**, **Tab Delimited** product from the [FFIEC bulk-data page](https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx). The script reads the site's reporting-date choices and submits the download form using `requests`. It does not require Selenium, ChromeDriver or an open browser.

The ZIPs and extracted bulk reports are local data, excluded from Git. A user obtains them by running preparation; they are not uploaded with the source code.

| Location relative to the repository | Contents |
| --- | --- |
| `data/FFIEC/archives/YYYYMMDD.zip` | Downloaded single-period ZIP |
| `data/TXT/FFIEC CDR Call Bulk All Schedules YYYYMMDD/` | Extracted TXT files, directly inside the quarter folder |
| `data/FFIEC/quarters/YYYYMMDD.json` | File inventory, sizes, checksums and preparation result for that quarter |
| `data/FFIEC/prepared.json` | Required dates and completion record, written after every requested quarter passes verification |
| `data/FFIEC_backups/` | Previous quarter folders retained when their contents are replaced |

Preparation checks ZIP integrity, reporting dates, required POR/ENT/RC files, split-schedule parts and the extracted file inventory. Downloads and extraction finish in temporary locations before replacing a quarter folder. A failed quarter stops the pipeline before conversion.

On a normal rerun, valid cached ZIPs are reused. Extracted files are checked against the archive; missing or changed files are restored from it. Existing Markdown documentation is retained. Use `--refresh` when you want to fetch the reports again, including amendments published since the previous download:

```sh
python3 "src/call reports/prepare_call_reports.py"
python3 "src/call reports/prepare_call_reports.py" --refresh
```

The first command prepares the data without starting the remaining pipeline. `--txt-dir`, `--cache-dir` and `--manifest` override its output locations. `--retries` defaults to 3 and `--timeout` to 180 seconds per HTTP read. `--history-quarters` defaults to 3, matching the current dynamic-ratio calculations. Use `--help` for the full argument list.

Preparation does not change the analysis calendars. In particular, `Material Events/quarters_basel3.csv` currently admits 2014Q1 through 2024Q2 into the final peer panels. Downloading the earlier history and 2024Q3/Q4 reports does not add those dates to that calendar.

### Running preparation in Sublime Text

Open `prepare_call_reports.py` and build it with a Python 3 interpreter that has the project requirements installed. The script needs no arguments for the default configuration and resolves its default paths from its own location, so the working directory does not need to be the repository root. Use a build command with `--plan` if you want a preview instead of a download.

## Processing order

The default configuration contains **20 tasks**. Several tasks call the same program with different arguments.

| Task | Program relative to `src/` | Work |
| --- | --- | --- |
| `0.0` | `call reports/prepare_call_reports.py` | Download and verify all required quarterly source files |
| `1.0` | `call reports/call_reports_mkdir_txt_csvs_global.py` | Convert TXT schedules to CSV; use POR to attach the FDIC certificate to each bank's schedule rows |
| `2.0` | `call reports/Call_Report_Merged_Cleaned_Global.py` | Merge the schedules selected for each reporting period |
| `2.1` | `call reports/numeric_only.py` | Apply the numeric cleaning step |
| `3.0` | `call reports/Call_Reports_v4_0.py` | Calculate current-quarter ratios using the installed `callreports` domain methods |
| `4.0` | `ratios/Dynamic_Ratios.py` | Calculate P1Q/P2Q/P3Q ratios and their changes relative to the current quarter, matching banks by `CERT` |
| `6.0.1`–`6.0.3` | `material events/FDIC API/Material_events_download.py` | Download de novo, failure and merger records in three concurrent tasks |
| `6.1` | `material events/FDIC API/Material_events_cleaned.py` | Clean the selected material-event downloads |
| `6.1.1` | `material events/FDIC API/Material_events_delete_api.py` | Remove matching RAW event downloads after cleaning |
| `6.2`–`6.4` | `material events/Material_events_flag.py` | Apply de novo, failure and merger flags in that order, using each stage's quarter map |
| `7.0` | `peer groups/base/Material_events_peer_group_basel3.py` | Write quarterly Failures, Mergers and Survivors files for each selected horizon |
| `7.1` | `peer groups/horizons/Material_events_peer_group_basel3.py` | Select quarterly files using `quarters_basel3.csv` and concatenate each group/horizon panel |
| `8.0` | `jsd/binning/Material_events_JSD_binning_basel3.py` | Count numeric values in the selected bins, separately for each group and horizon |
| `8.1.1` | `jsd/pmf/Material_events_JSD_probabilities_basel3.py` | Normalize each histogram column into a PMF; zero-total columns remain zero |
| `8.2` | `jsd/calculation/Material_events_JSD_basel3.py` | Compare Survivors–Failures, Survivors–Mergers and Mergers–Failures for each selected horizon/bin specification |
| `8.3.0.1` | `measures/intragroup/JSD_intragroup_filter.py` | Keep columns whose first-row JSD result meets the configured threshold, currently `0.3` |

For a selected horizon `h`, failure and merger membership comes from `FAILURE_Th == 1` and `MERGER_Th == 1`. The two selections are independent; a row with both flags appears in both event groups. Survivors exclude rows flagged for either event at that horizon. The calendar stage selects files by the date in their filenames and preserves their rows and columns when concatenating them.

The JSD calculation aligns PMFs by their `Bin` labels and compares the columns shared by each pair. It retains the existing square-root Jensen–Shannon calculation with natural logarithms. See the [calculation guide](jsd/calculation/readme.md) for the formula and handling of zero values.

## Select horizons and bins

The top of `pipeline/pipeline_config_dynamic.yaml` contains the shared selection:

```yaml
parameters:
  horizons: [1, 2, 3, 4]
  bins1: [20, 30, 50, 100]
  bins2: 5
  bins3: 1
```

**The default runs T1, T2, T3 and T4 with all four original bin specifications.** A user who needs a subset can change these values—for example, `horizons: [1, 3]` and `bins1: [20, 50]`. The selection reaches both peer-group stages, binning, PMFs, JSD calculation and the final filter. The same values expand into the expected input/output paths.

`bins1` lists the bin counts across −1 to 1. `bins2` is the count across 1 to 2. `bins3` is the single unbounded upper interval and currently accepts only `1`. With the defaults, the four specifications contain **26, 36, 56 and 106 bins**. Exactly 2 belongs to the final interval, labeled `[2.00, inf)`, preserving the original value assignment. Filenames record the central count, such as `_binned_20.csv`; changing `bins2` updates that specification's output rather than creating a second filename.

The peer programs require `--horizons`; binning also requires `--bins1`. PMF, calculation and filter programs require `--horizons` and `--bins`, with `--bins` receiving the selected `bins1` values. The YAML supplies these arguments. Material-event tasks separately receive `--events` and their input, output and calendar paths.

## Files and output locations

The processing programs are listed in the table above. The remaining source components are:

- `Basel3_Global_Filepath.py`: shared paths rooted at this repository.
- `callreports/`: the independently installable CallReports definitions and local ZIP/TXT conversion and merging library. See its [usage guide](callreports/README.md).
- `call reports/Call_Reports_v4_0.py`: Basel3's 76 ratio calculations, using the installed `callreports` definitions directly.
- `measures/intergroup/JSD_intergroup_call_reports.py`: intergroup analysis, not scheduled in the current YAML.
- `RWA/`: interest-rate research organized under stable `data/`, `calibration/` and `models/` domains. See the [RWA domain map](RWA/readme.md) for their components, entry points and data flow.

Generated Call Report files follow this directory structure:

```text
data/
├── TXT/FFIEC CDR Call Bulk All Schedules YYYYMMDD/
├── FFIEC/
│   ├── archives/
│   ├── quarters/
│   └── prepared.json
├── FFIEC_backups/
└── CSV/
    ├── Schedules/YYYYMMDD/
    ├── Cleaned/
    ├── Interleaved/
    └── Dynamic_Lag/Cleaned/
```

Material-event files, peer panels and JSD results are written under `Material Events/`. The event folders are `DE NOVO`, `Failures` and `Mergers`; peer processing also creates `Survivors`. Each peer group has `Horizons/` and `JS Divergence/Basel III T+h/` outputs. The three comparison files go to `Material Events/JSD/BASEL III T+h/`; the final filtered files go to the corresponding `Material Events/IG/BASEL III T+h/` folder.

## Execution and logs

The YAML's `execution` section is an ordered list of phases. Each phase finishes before the next starts. The default plan runs only the three FDIC downloads concurrently; the other tasks run sequentially. The manager also supports nested `concurrent_branches` for separately configured workflows.

Every configured task must appear once in the execution plan. Dependencies validate prerequisites and do not add omitted tasks automatically. Script paths are relative to `src/`; declared artifact paths and the default working directory are relative to the repository root. The manager checks required inputs and outputs and stops when a task returns an error.

Each run writes per-task logs under `pipeline_logs/<run-id>/`. The manager executes every scheduled task; it does not skip tasks by input hash. Preparation's verified ZIP reuse is separate from that execution behavior.
