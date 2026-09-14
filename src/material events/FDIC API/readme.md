# FDIC event retrieval and preparation

These three programs provide event records for the [flagging stage](../readme.md).
The [pipeline configuration](../../../pipeline/pipeline_config_dynamic.yaml)
executes the downloads concurrently for separate event types, then cleans their
outputs and removes matching RAW files. All paths below are relative to the
repository root.

## Run

Install the repository requirements and execute:

```bash
python3 "src/material events/FDIC API/Material_events_download.py" \
  --events de_novo failures mergers --material-dir "Material Events" \
  --start-date 2014-01-01 --end-date 2024-12-31 --limit 10000
python3 "src/material events/FDIC API/Material_events_cleaned.py" \
  --events de_novo failures mergers --material-dir "Material Events"
```

After inspecting the cleaned outputs, the RAW cleanup command is:

```bash
python3 "src/material events/FDIC API/Material_events_delete_api.py" \
  --events de_novo failures mergers --material-dir "Material Events"
```

The normal pipeline runs this deletion automatically in task `6.1.1`. It
recursively removes files whose names or text contain `BankFind Suite` within
the selected RAW directories. It does not delete the cleaned event files.

## Retrieval

`Material_events_download.py` sends a GET request to
`https://banks.data.fdic.gov/api/history` with the selected `EFFDATE` interval,
event codes, field list and result limit. It flattens each response row, inserts
missing selected fields, derives `ESTYEAR` from `ESTDATE` and writes a CSV.

| Selection | Change codes | Output beneath `Material Events/` |
| --- | --- | --- |
| `de_novo` | 110 | `DE NOVO/RAW/BankFind Suite API - de novo.csv` |
| `failures` | 211 | `Failures/RAW/BankFind Suite API - Failures.csv` |
| `mergers` | 221, 222, 223, 224 | `Mergers/RAW/BankFind Suite API - mergers.csv` |

`--events` is required. The other options default to the values shown above;
the default material directory resolves from the source location. Each event
uses one request. The downloader currently has no pagination, timeout or retry
policy. A non-200 response or missing `data` field is printed and can leave an
existing output untouched. Consequently, successful process exit alone does
not establish complete, fresh event coverage. The pipeline checks declared
files but cannot detect this form of stale input.

## Cleaning and certificate semantics

`Material_events_cleaned.py` reads each selected RAW directory and writes files
with the same names under its sibling `Cleaned/` directory. It retains a fixed
column order, inserts absent columns as blanks and derives the common `CERT`
column according to the selected event type.

De novo rows retain `CERT`. For failure and merger data, the cleaner renames
`OUT_CERT` when present and also renames `ACQ_CERT` to `CERT`. The current download
field lists supply `ACQ_CERT`, not `OUT_CERT`, for those events. Downstream flags
therefore use the acquiring institution's certificate from that input; they
must not be described as verified labels of failed or absorbed institutions
without resolving the identity definition. Inputs containing both certificate
fields also require care because renaming can create duplicate column names.

Cleaning warns about malformed CSV rows and prints processing errors while
continuing. Inspect errors and output coverage before using the files for an
outcome analysis. `--events` defaults to all three types for cleaning and RAW
cleanup. All programs support `--help` and defer processing until execution.
