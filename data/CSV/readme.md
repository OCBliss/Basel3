# Call Report reference tables and generated CSVs

This directory contains the tracked [quarter mapping](quarter_flag.csv) and
reference tables [quarter_map.csv](quarter_map.csv) and [quarters.csv](quarters.csv).
The pipeline creates the analytical subdirectories listed below; their data is
not included in a fresh clone.

| Generated location | Producer and contents | Next consumer |
| --- | --- | --- |
| `Schedules/YYYYMMDD/` | TXT conversion adds FDIC certificates using POR and writes each schedule under its original filename stem | Schedule merge |
| `Cleaned/` | Schedule merge joins selected fields to ENT by `IDRSSD`; numeric cleaning adjusts selected fields | Current and historical ratio calculations |
| `Interleaved/` | Current-quarter ratio calculation | Dynamic ratios |
| `Dynamic_Lag/Cleaned/` | Current ratios and proportional changes against earlier quarters, aligned by `CERT` | Material-event flagging |

For example, conversion of `FFIEC CDR Call Schedule RC 06302024.txt` produces
`Schedules/20240630/FFIEC CDR Call Schedule RC 06302024.csv`. Subsequent merged
files use `Cleaned_Call_Report_20240630.csv`; the dynamic output uses
`Dynamic_Cleaned_Call_Report_20240630.csv`.

Run from the repository root after installing the requirements:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py
```

The first command previews the plan. The second downloads required source
reports and executes processing. See the [data guide](../readme.md) for archive
and output locations, [Call Report programs](../../src/call%20reports/readme.md)
for processing details and [ratio definitions](../../src/ratios/variables/readme.md)
for calculated fields. Generated files can be replaced on rerun.
