# CallReports

CallReports provides date-aware FFIEC Call Report definitions and local bulk-file
preparation. It uses pandas and NumPy for structured data handling. Its schedule
methods expose the reporting fields and calculations; users can choose their own
ratios without running Basel3's research pipeline.

## Installation

Python 3.8 or later is required, with compatible pandas and NumPy releases.
From the repository root, install this library alone:

```sh
python3 -m pip install .
```

For development, use `python3 -m pip install -e .`. The distribution is named
`CallReports`; the Python import and installed command are named `callreports`.
The package builds from this repository; a PyPI release is a separate operation.
A bare `pip install CallReports` must only be advertised after publication under
that name. The repository's `requirements.txt` installs this local library along
with the additional dependencies needed by Basel3.

## Use an existing structured CSV

The CSV must contain one row per bank and reporting quarter, with the original
FFIEC code headers. Select one bank row before constructing a report:

```python
import pandas as pd
from callreports import CallReport_051, safe_divide

table = pd.read_csv("Cleaned_Call_Report_20240331.csv", low_memory=False)
row = table.loc[table["IDRSSD"] == 101].iloc[0]
report = CallReport_051(row)
date = "P0"

assets = report.BalanceSheet.TotalAssets(date=date)
trading_share = safe_divide(
    report.BalanceSheet.TradingAssets(date=date),
    report.BalanceSheet.TotalAssets(date=date),
)
```

This example requires `IDRSSD`, `RCON9999`, `RCON2170`, `RCONJA22`,
`RCON3123` and `RCON3545`. `TotalAssets` retains the existing adjusted definition:
`RCON2170 - RCONJA22 + RCON3123` from 2018Q1 onward, and `RCON2170 + RCON3123`
earlier. For the raw reported field, use `report.Value("RCON2170", date=date)`.
Other methods require their own reporting fields. `Certificate()` additionally
requires `FDIC Certificate Number`. Pass numeric observations; pandas' CSV reader
usually infers these from FFIEC numeric columns. A dictionary or pandas Series
with the same headers can also supply a bank row. Missing current-quarter headers
raise `KeyError`; installing the library does not supply bank data.

`CallReport_051` uses domestic reporting fields. `CallReport_031` exposes its
separate consolidated form definitions, including `RCFD` fields. Choose the form
appropriate to the supplied data; this library does not automatically infer or
substitute reporting forms. FFIEC 041 is not a separate implemented class.

Methods retain the existing definitions, historical field changes, missing-value
behavior and `name=True` labels. `safe_divide` preserves missing observations and
returns zero for a known numerator divided by zero, matching the existing API.
Ordinary Python `/` uses the operands' own division behavior instead.

## Historical dates

`date="P0"` means the bound row's quarter. `P1Q`, `P2Q`, `P3Q` and `P1Y`
refer to one, two, three and four calendar quarters earlier. Supply the historical
rows explicitly; the library never downloads them or searches a Basel3 checkout:

```python
from callreports import CallReport_051, QuarterCache

history = QuarterCache(frames={20231231: previous_quarter_table})
report = CallReport_051(row, history=history)
previous_assets = report.BalanceSheet.TotalAssets(date="P1Q")
```

Historical rows match by `IDRSSD`, independently of row order. A `frames` mapping
may contain several quarter DataFrames; a single DataFrame with several quarters
is also accepted. For files, use `QuarterCache(data_dir="prepared")`; it reads
`Cleaned_Call_Report_YYYYMMDD.csv`, including the quarter folders produced below.
Ambiguous files and duplicate historical bank rows raise an error.

Without a supplied map, lag dates follow calendar quarter ends. An explicit
`map_file` path or DataFrame preserves custom mappings with columns `P0`, `P1Q`,
`P2Q`, `P3Q`, `P1Y` and optional `Quarter`. Missing historical observations remain
missing rather than being taken from the current quarter. The API expects valid
calendar quarter-end dates in `RCON9999` when using calendar lags.

## Prepare a downloaded FFIEC ZIP

Use a local **Call Reports — Single Period**, tab-delimited ZIP containing one
quarter's POR and ENT files and the desired schedules:

```sh
callreports prepare "Call_Reports_20240331.zip" --output-dir prepared
```

The equivalent command is `python3 -m callreports prepare ...`. No network request
is made. The reporting date is inferred from the FFIEC filenames; `--date
20240331` can specify it explicitly and must agree with those filenames.

The result is:

```text
prepared/20240331/
├── TXT/                                      # extracted originals
├── Schedules/                                # individual schedule CSVs
└── Cleaned_Call_Report_20240331.csv           # merged bank-quarter table
```

The Python equivalent returns the merged CSV's path:

```python
from callreports import prepare_archive

csv_path = prepare_archive("Call_Reports_20240331.zip", "prepared")
table = pd.read_csv(csv_path, low_memory=False)
report = CallReport_051(table.iloc[0])
```

Preparation attaches FDIC certificates using POR, drops TXT description rows and
merges all available schedules by `IDRSSD`. Ancillary files such as `Readme.txt`
are retained in TXT but are not treated as schedules. ENT defines the bank population and
order. A repeated column retains its first value, with ENT first and remaining
schedule filenames sorted. It sets `RCON9999` to the validated reporting date and
removes the legacy `RCON9224` text field. Other fields, text values and missing
observations are preserved. This is a structural merge, not statistical cleaning.

Mixed quarters, duplicate bank identifiers, invalid archives and inconsistent
reporting dates fail explicitly. Preparation stages a complete quarter before
publishing its directory and refuses to replace an existing quarter directory.
Source ZIPs remain unchanged. Archive limits are 512 MiB compressed and 2 GiB
uncompressed; unsafe member paths, links and duplicate names are rejected.

## Use extracted TXT or schedule CSVs

Each command operates on one reporting quarter:

```sh
callreports convert "downloaded-quarter" --output-dir schedules
callreports merge schedules --output Cleaned_Call_Report_20240331.csv
```

The corresponding functions are `convert_txt_to_csv(input_dir, output_dir)` and
`merge_schedules(input_dir, output_file=None, reporting_date=None)`.
`merge_schedules` returns a DataFrame, whether or not an output file is requested.
Lower-level `merge_schedule_files(base_file, files_to_append, output_file=None)`
supports an explicit subset of schedules, skips absent optional paths and returns
the merged DataFrame without applying the reporting-date cleanup.

## Basel3 integration and limits

Basel3 imports these definitions as a dependency. Its existing conversion and
merge entry points delegate to this library, while its selected schedule list,
76 research ratios, cohort definitions and distribution comparisons remain in
Basel3. The compatibility module `src/call reports/Call_Report.py` re-exports the
public definitions for existing callers.

The standalone merge includes all available schedules; Basel3 intentionally
retains its historical schedule selection. Local ZIP preparation does not include
Basel3's YAML-driven FFIEC downloader. Coverage depends on the implemented 031/051
methods and available source headers; it does not establish completeness across
all reporting forms, historical revisions or regulatory interpretations.

Package and existing Call Report regressions run from the repository root after
installing the development requirements:

```sh
python3 -m unittest discover -s tests -p 'test_callreports_package.py' -v
python3 -m unittest discover -s tests -p 'test_call_report*.py' -v
python3 -m unittest discover -s tests -p 'test_dynamic_ratios.py' -v
```
