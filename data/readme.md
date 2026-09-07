# Call Report data

The pipeline downloads and processes FFIEC Call Reports in this directory. A fresh clone includes the reference quarter tables; the ZIP archives, extracted TXT files and generated CSVs are created locally when the pipeline runs.

## Download and run

After installing the repository's [requirements](../requirements.txt), run these commands from the repository root:

```sh
# Preview the required quarters without downloading anything.
python3 "src/call reports/prepare_call_reports.py" --plan

# Run the pipeline, starting with Call Report preparation.
python3 "pipeline/Task_manager_Global_yaml_driven.py"
```

Stage `0.0` in the [pipeline YAML](../pipeline/pipeline_config_dynamic.yaml) runs [prepare_call_reports.py](../src/call%20reports/prepare_call_reports.py) before TXT-to-CSV conversion. It reads the date ranges from the configured material-event download stages and adds the preceding three quarters needed for the dynamic ratios. The current 2014–2024 settings require 47 quarters, from 2013Q2 through 2024Q4.

The downloader selects **Call Reports — Single Period**, **Tab Delimited** from FFIEC. It validates each ZIP and extracts its TXT files into the quarter's folder. A rerun reuses valid cached archives and verifies the extracted files; missing or changed files are restored. If a required quarter cannot be prepared, the pipeline stops before conversion. See the [source guide](../src/readme.md) for alternative configurations, refresh options and standalone execution.

## Files produced here

All paths below are relative to `data/`.

| Location | Contents and producing stage |
| --- | --- |
| `FFIEC/archives/YYYYMMDD.zip` | Downloaded ZIP for one quarter (`0.0`) |
| `FFIEC/quarters/YYYYMMDD.json` | Inventory and checksums for the extracted quarter (`0.0`) |
| `FFIEC/prepared.json` | Completion record written only after every required quarter passes verification (`0.0`) |
| `TXT/FFIEC CDR Call Bulk All Schedules YYYYMMDD/` | Extracted FFIEC TXT schedules, including the POR file used to map `IDRSSD` to FDIC certificate number (`0.0`) |
| `CSV/Schedules/YYYYMMDD/` | Individual schedule CSVs with the certificate number added from POR; POR itself is not converted to CSV (`1.0`) |
| `CSV/Cleaned/Cleaned_Call_Report_YYYYMMDD.csv` | Selected schedules joined to ENT by `IDRSSD` (`2.0`). The following step removes `RCON9224` when present and sets `RCON9999` from the filename (`2.1`). |
| `CSV/Interleaved/Cleaned_Call_Report_YYYYMMDD.csv` | Current-quarter ratios (`3.0`) |
| `CSV/Dynamic_Lag/Cleaned/Dynamic_Cleaned_Call_Report_YYYYMMDD.csv` | Current ratios and changes against the previous one, two and three quarters, aligned by `CERT` (`4.0`) |

When preparation replaces an existing TXT quarter folder, the previous version is retained under `FFIEC_backups/`. These backups, the download cache and generated data are excluded from Git.

## Quarter reference tables

[CSV/quarter_flag.csv](CSV/quarter_flag.csv) is an input to the date-aware Call Report code. Its `P0` column identifies the current quarter; `P1Q`, `P2Q`, `P3Q` and `P1Y` identify relative periods, and `Quarter` gives the quarter number. It must remain available in a fresh clone.

[CSV/quarter_map.csv](CSV/quarter_map.csv) contains the same period mappings without `Quarter`. [CSV/quarters.csv](CSV/quarters.csv) is an older quarter list. Both are retained as reference files; the current pipeline does not read them.

The material-event window tables are separate inputs in [Material Events](../Material%20Events/). They govern event flags and the dates admitted to the combined peer panels. Downloading additional reports does not rewrite those tables or extend their analysis windows.

Material-event flags and subsequent peer/JSD results are written under `Material Events/`. The eight saved bank Call Report PDFs are under [PDF/Call Reports](../PDF/Call%20Reports/), alongside the [PDF guide](../PDF/readme.md).
