# Material Events data

The files in this folder are data and reference tables. The programs that download, clean and flag events are under [`src/material events/`](../src/material%20events/readme.md).

## Quarter tables supplied with the repository

These CSVs stay at the root of `Material Events/` in both a clone and the YAML paths. They are not stored inside `src/`.

| File | Use |
| --- | --- |
| `quarters_de_novo.csv` | Supplies `Quarters`, `START_DATE` and `END_DATE` to de novo flagging in task `6.2` |
| `quarters_failures.csv` | Supplies the quarter, start date and four end dates to failure and merger flagging in tasks `6.3` and `6.4` |
| `quarters_basel3.csv` | Selects reporting-quarter filenames for the combined peer panels in task `7.1` |
| `quarters.csv` | Retained reference table; the current pipeline does not read it |

Each table has 42 reporting-quarter rows, from 2014Q1 through 2024Q2. Their different date columns are not interchangeable. The downloader does not regenerate or extend these research calendars. Call Report lag lookup uses the separate `data/CSV/quarter_flag.csv`.

## Other reference data

`events_definitions.csv` is the 235-entry event-code dictionary. `bank-data.csv` contains 90 annual observations for 1934–2023; `bank-data cleaned.csv` contains the same observations with reordered and renamed columns. These reference files are retained in Git. They are not inputs to the configured material-event tasks.

## Directories created during a run

The [pipeline configuration](../pipeline/pipeline_config_dynamic.yaml) creates the download directories before calling the FDIC API. Cleaning, flagging and analysis create their own output directories:

- `DE NOVO/`, `Failures/` and `Mergers/`: downloaded `RAW/`, `Cleaned/` event files and flagged `Call Reports/`.
- `Failures/`, `Mergers/` and `Survivors/`: `Horizons/` peer files and `JS Divergence/` histograms and PMFs.
- `JSD/`: comparisons for the selected horizons and bin specifications.
- `IG/`: the filtered comparison files.

These directories do not need placeholder files in GitHub. Their generated contents remain local and are ignored by Git. Task `6.1.1` removes the matching RAW downloads after cleaning; a subsequent run downloads them again.

Run from the repository root:

```sh
python3 pipeline/Task_manager_Global_yaml_driven.py
```
