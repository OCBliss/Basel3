# Call Report preparation and conversion

The pipeline reads the tab-delimited FFIEC schedules under `data/TXT/`. The older root-level `Call Report/` directory and the PDF reference reports are not inputs.

## Prepare the required quarters

Task `0.0` runs `prepare_call_reports.py`. It reads the material-event download date ranges from the active YAML, adds the three previous quarters required for ratio changes, and downloads **Call Reports — Single Period** ZIPs. It validates and extracts them before conversion starts.

From the repository root, inspect the required quarters without downloading:

```sh
python3 "src/call reports/prepare_call_reports.py" --plan
```

The current configuration requires 47 quarters, from 2013Q2 through 2024Q4. Extracted files go directly inside `data/TXT/FFIEC CDR Call Bulk All Schedules YYYYMMDD/`. ZIPs and validation records are retained under `data/FFIEC/`; these downloaded files are ignored by Git. See the [source guide](../readme.md) for configuration, repair and rerun options.

## Convert TXT files to schedule CSVs

Task `1.0` runs `call_reports_mkdir_txt_csvs_global.py`. For each quarterly folder it:

1. Reads the POR file and builds the `IDRSSD` to FDIC certificate mapping.
2. Converts each other TXT file to CSV, keeping its original filename stem.
3. Inserts `FDIC Certificate Number` after `IDRSSD` and drops rows whose first field is blank, including schedule-description rows.
4. Writes the files under `data/CSV/Schedules/YYYYMMDD/`.

The POR file supplies identifiers; it is not itself exported as a schedule CSV. All paths resolve from this checkout through `src/Basel3_Global_Filepath.py`.

A direct conversion run prints an error and skips a quarter without a usable POR mapping. The normal pipeline first validates the archives and required source files in task `0.0`.

## Continue processing

The YAML then merges each quarter's schedules, removes nonnumeric columns, calculates current-quarter ratios, and runs the dynamic-ratio stage. Their files are under `data/CSV/Cleaned/`, `data/CSV/Interleaved/` and `data/CSV/Dynamic_Lag/Cleaned/`. The lag lookup is the tracked `data/CSV/quarter_flag.csv`.

Run the configured sequence from the repository root:

```sh
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py
```

The [pipeline guide](../../pipeline/readme.md) describes the execution order. The [ratio catalogue](../ratios/variables.md) lists the calculated columns.
