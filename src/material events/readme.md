`Material_events_flag.py` handles de novo, failure, and merger flagging. Together with `FDIC API/Material_events_download.py`, `FDIC API/Material_events_cleaned.py`, and `FDIC API/Material_events_delete_api.py`, it forms the four-script material-event implementation.

The flag script requires `--events`, accepting one or more of `de_novo`, `failures`, and `mergers`. It runs selected stages in de novo → failures → mergers order, reading each stage's existing upstream CSV files. Optional arguments are `--material-dir`, `--input-dir`, `--output-dir`, and `--quarter-map`. Explicit input, output, or quarter-map overrides require one selected event. The default material directory comes from `Basel3_Global_Filepath.py`.

For example, from the repository root, run all three flagging stages:

```bash
python3 "src/material events/Material_events_flag.py" --events de_novo failures mergers
```

The YAML calls this script directly for steps `6.2`, `6.3`, and `6.4`, selecting one event per stage and supplying its paths. Step `6.3` uses:

```yaml
path: "material events/Material_events_flag.py"
args:
  - --events
  - failures
  - --material-dir
  - "Material Events"
  - --input-dir
  - "Material Events/DE NOVO/Call Reports"
  - --output-dir
  - "Material Events/Failures/Call Reports"
  - --quarter-map
  - "Material Events/quarters_failures.csv"
```

The implementation loads event dates and quarter windows into lookups once per stage. It retains each event's certificate/date conversions, all four failure/merger comparisons, intermediate CSV boundaries, filenames, and column order. Each flag remains an independent inclusive comparison between the existing START_DATE and its corresponding end date. The script supports `--help`; importing it does not process data.

# Step 06.2 — Flag De Novo Banks in Panel Data

## Purpose

This step flags all **de novo banks** in the dynamic lagged panel dataset based on their **establishment date** (ESTDATE) falling within a financial reporting quarter. It integrates structural charter events into time-series panel data by assigning a `DE_NOVO_FLAG = 1` when applicable.

---

## Input

- cleaned BankFind Suite data: `/Material Events/DE NOVO/Cleaned/`
- Quarter reference file mapping quarter identifiers to date ranges: `/Material Events/quarters_de_novo.csv`
- `/Call Report/CSV/Dynamic_Lag/Cleaned/`


---

## Output

Processed files are saved in: `/Material Events/DE NOVO/Call Reports/`
with filenames prefixed as: `DE NOVO_`


---

## Operations

1. **Quarter Matching**  
   - `RCON9999` in panel data maps to `Quarters` column  
   - `Quarters` file provides `START_DATE` and `END_DATE` for each quarter

2. **DE NOVO Eligibility**
   - For each row:
     - If `CERT` appears in DE NOVO dataset
     - And its `ESTDATE` falls **within** the current quarter’s start and end dates
     - Then `DE_NOVO_FLAG = 1`

3. **Export Flagged Dataset**
   - All original panel columns retained
   - Appends a new binary column: `DE_NOVO_FLAG` = {0, 1}

---

## Example Output Row

| CERT | RCON9999 | ... | DE_NOVO_FLAG |
|------|----------|-----|---------------|
| 12345 | 20190331 | ... | 1             |
| 67890 | 20190331 | ... | 0             |

---

# Step 06.3 — Flag Bank Failures in Lagged Panel Data

## Purpose

This step appends four **forward-looking failure flags** to each row in the quarterly bank panel. It identifies when a bank failed within T+1 to T+4 quarters **after** the observation date, allowing lag-aware labeling of terminal events for predictive modeling.

---

## Input

- Lagged call report panel with `DE_NOVO_FLAG` already applied: `/Material Events/DE NOVO/Call Reports/`
- Cleaned failure event data (FDIC EFFDATEs): `/Material Events/Failures/Cleaned/`
- Quarter lookup with forward-end dates: `/Material Events/quarters_failures.csv`


---

## Output

Saved files are stored in: `/Material Events/Failures/Call Reports/`
- with filenames updated from: `DE NOVO_<original>.csv`
- to: `Failures_<original>.csv`


---

## Features Added

For each bank-quarter (CERT, RCON9999), this step adds:
- `FAILURE_T1`: 1 if failure occurred within 1 quarter
- `FAILURE_T2`: 1 if within 2 quarters
- `FAILURE_T3`: 1 if within 3 quarters
- `FAILURE_T4`: 1 if within 4 quarters

These are **cumulative flags** — if `FAILURE_T3 = 1`, then `FAILURE_T1` and `T2` will also be 1.

---

## Operations

1. **Match CERT in Failure Dataset**
   - Compare bank `CERT` to failure records

2. **Convert EFFDATE to Integer**
   - For temporal comparison with quarter boundaries

3. **Determine if EFFDATE Falls in T+1 to T+4 Windows**
   - For each row, check if failure date falls within:
     - `START_DATE` to `END_DATE1` → `FAILURE_T1`
     - `START_DATE` to `END_DATE2` → `FAILURE_T2`
     - `...` and so on, up to `END_DATE4`

4. **Export**
   - Appends the four `FAILURE_T*` columns to the original DE NOVO panel file
   - Renames file to prefix it with `Failures_`

---

## Example Output Row

| CERT  | RCON9999 | DE_NOVO_FLAG | FAILURE_T1 | FAILURE_T2 | FAILURE_T3 | FAILURE_T4 |
|-------|----------|--------------|------------|------------|------------|------------|
| 12345 | 20200630 | 1            | 0          | 1          | 1          | 1          |

---

# Step 06.4 — Flag Bank Mergers in Lagged Panel Data

## Purpose

This step adds forward-looking **MERGER flags** to each observation in the bank-quarter panel. It indicates whether a bank was involved in a merger (absorbed by another institution) in the next 1 to 4 quarters. This supports survival modeling, divergence tracking, or categorical outcome labeling.

---

## Input

- Previously labeled panel with `FAILURE_T*` flags: `/Material Events/Failures/Call Reports/`
- Cleaned merger records with EFFDATEs: `/Material Events/Mergers/Cleaned/`
- Quarter-to-date mapping table with multi-horizon end dates: `/Material Events/quarters_failures.csv`

---

## Output

Saved files are written to: `/Material Events/Mergers/Call Reports/`


---

## Features Added

Each row is appended with the following indicators:

| Column      | Description                                         |
|-------------|-----------------------------------------------------|
| MERGER_T1   | 1 if bank merged in the next quarter                |
| MERGER_T2   | 1 if merged within two quarters                     |
| MERGER_T3   | 1 if merged within three quarters                   |
| MERGER_T4   | 1 if merged within four quarters                    |

Flags are cumulative. For instance, if `MERGER_T3 = 1`, then `MERGER_T1` and `MERGER_T2` will also be 1.

---

## Operations

1. **CERT Matching**  
   - Match each bank (by `CERT`) in the panel against merger events.

2. **EFFDATE Comparison**  
   - Compare merger EFFDATE to each quarter's forward time windows using:
     - `END_DATE1`, `END_DATE2`, `END_DATE3`, `END_DATE4`

3. **Flag Assignment**  
   - If EFFDATE falls within a given horizon, set the corresponding `MERGER_T*` flag to 1.

4. **Save Output**  
   - Appends flags to each quarterly file and renames the prefix for clarity.

---

## Example Output Row

| CERT  | RCON9999 | FAILURE_T1 | ... | MERGER_T1 | MERGER_T2 | MERGER_T3 | MERGER_T4 |
|-------|----------|-------------|-----|------------|------------|------------|------------|
| 78910 | 20200630 | 0           | ... | 1          | 1          | 1          | 1          |

---
