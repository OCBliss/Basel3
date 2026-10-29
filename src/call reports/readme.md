# Call Report preparation, conversion and ratios

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

The YAML then merges each quarter's schedules, removes the `RCON9224` text column and sets `RCON9999` from the filename, calculates current-quarter ratios, and runs the dynamic-ratio stage. Their files are under `data/CSV/Cleaned/`, `data/CSV/Interleaved/` and `data/CSV/Dynamic_Lag/Cleaned/`. The lag lookup is the tracked `data/CSV/quarter_flag.csv`.

Run the configured sequence from the repository root:

```sh
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py
```

The [pipeline guide](../../pipeline/readme.md) describes the execution order. The [ratio catalogue](../ratios/variables/readme.md) lists the calculated columns.

## Ratio API and caller

The installed [CallReports package](../callreports/README.md) provides `CallReport_031`, `CallReport_051`, their schedule methods, historical-quarter lookup and division behavior. `Call_Reports_v4_0.py` imports that package and constructs `report_051` and `report_031` for each bank row. Each of its two entries contains all 76 ratios plus `IDRSSD`, `RCON9999` and `CERT`, with the full form and method path written in every expression.

The 031 entry uses 051 domestic-deposit calls for all 17 `RCE-*` ratios. Its `RC-2200-Item21` numerator also uses 051 domestic deposits; the denominator uses 031 liabilities. The remaining 031 expressions call the 031 instance. Both entries are written out separately, including repeated expressions.

Task `3.0` calls v4 with its input, output, quarter map and `P0` date supplied by YAML. `Dynamic_Ratios.py` remains the separate task `4.0`; it imports v4's ratio calculation and calls it for `P1Q`, `P2Q` and `P3Q`.

To run the current-ratio stage after source cleaning:

```sh
python3 "src/call reports/Call_Reports_v4_0.py" --input-dir data/CSV/Cleaned --output-dir data/CSV/Interleaved --quarter-map data/CSV/quarter_flag.csv --date P0
```

The same paths are defaults resolved from the caller's location, so a normal Python build from an editor or another working directory can run it without arguments. `--date` also accepts `P1Q`, `P2Q`, `P3Q` and `P1Y`. Install the project requirements first; the caller imports the installed `callreports` package directly.

The downloaded 2013 files omit six capital columns: `RCOAA223`, `RCOAP840`, `RCOAP859`, `RCFAA223`, `RCFAP840` and `RCFAP859`. Before passing a pre-2014 row to the API, the caller supplies missing values for absent columns in that list. It preserves supplied values and leaves the input row unchanged. This keeps unavailable capital ratios missing without substituting another form's fields.
