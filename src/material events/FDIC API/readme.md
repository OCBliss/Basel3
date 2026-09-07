The five existing entry points accept command-line arguments supplied by `pipeline/pipeline_config_dynamic.yaml`. The three download entry points share `Material_events_download.py`; each defaults to its original event when run without `--events`.

| Entry point | Arguments |
|---|---|
| `Material_events_de_novo_download_v2.py`, `Material_events_Failures_download_v2.py`, `Material_events_mergers_download_v2.py` | `--events`, `--material-dir`, `--start-date`, `--end-date`, `--limit` |
| `Material_events_cleaned.py`, `Material_events_delete_api.py` | `--events`, `--material-dir` |

Event choices are `de_novo`, `failures`, and `mergers`. Cleaning and deletion default to all three. Downloads retain the default date range `2014-01-01` through `2024-12-31` and limit `10000`. The default material directory comes from `Basel3_Global_Filepath.py`.

For example, YAML step `6.0.2` passes `--events failures --material-dir "Material Events" --start-date 2014-01-01 --end-date 2024-12-31 --limit 10000`. The manager passes these arguments from its `args` list and runs relative paths from the step's working directory. `inputs`, `outputs`, and `create_dirs` describe pipeline artifacts; they do not set script arguments automatically.

The pipeline still runs the three downloads concurrently, waits for all three, cleans the event files, and then deletes matching RAW downloads before flagging. Cleaning retains the existing CERT transformations and output column order. All five entry points support `--help`; importing them does not download, clean, or delete data.

# Step 06.0 — FDIC API Ingestion for De Novo, Mergers, and Failure Events

## Directory
- `src/`:
  - material events/:
    - `FDIC API/`:
        - Material_events_de_novo_download_v2.py
        - Material_events_Failures_download_v2.py
        - Material_events_mergers_download_v2.py
        - Material_events_download.py (shared implementation)
        - Material_events_delete_api.py
        - Material_events_cleaned.py

## Purpose

This script retrieves **De Novo chartering events** directly from the  
**FDIC BankFind Suite API**

It provides the foundational *raw ingestion layer* for all downstream  
material-event processing (Steps 06.1.1 → 06.2 → 06.3 → …).

---

## Key Functionality

- **Auto-locates** `Basel3_Global_Filepath.py` to dynamically determine `ROOT_DIR`
- **Generates FDIC API query strings** using:
  - `CHANGECODE` filters
    - (e.g., **110** = De Novo)
    - (**221,...,224** = Mergers)
    - (**211** = Failures)
  - `EFFDATE` date ranges
- **Fetches** all matching events from the API’s `/history` endpoint
- **Flattens** nested JSON content into a clean tabular DataFrame
- **Normalizes columns**, inserting missing ones so schema remains stable
- **Derives `ESTYEAR`** from ISO `ESTDATE` fields
- **Outputs** a fully structured CSV named:


into the De Novo RAW dataset folder

---

## API Query Logic

The FDIC endpoint:


is queried using:

- `CHANGECODE:110`  
- `EFFDATE:[2014-01-01 TO 2024-12-31]`  
- Full 30-column field list including:
  - charter details  
  - organization type  
  - region metadata  
  - ACQ/FRM-prefix variables  
  - de novo flag indicators  

The script gracefully handles:
- Missing fields  
- Sparse variables  
- Unexpected API payloads  

---

## Output Structure

Each raw ingestion CSV includes:

| Field | Description |
|-------|-------------|
| `CERT` | Institution certificate number |
| `ESTDATE` | Date the institution was established |
| `EFFDATE` | Effective date of event |
| `NEW_CHARTER_DENOVO_FLAG` | Indicates de novo status |
| `ORGTYPE` / `ORGTYPE_NUM` | Institution organization type |
| `CHANGECODE_DESC` | Description of event type |
| `FDICREGION` | Supervisory region |
| `ESTYEAR` | Derived column (yyyy) |

…and 25+ other FDIC metadata fields.

All fields are **schema-aligned**, ensuring downstream cleaning scripts  
(Step 06.1.1) operate reliably.

---

## File Output

### De Novo

- Material Events/
  - └── DE NOVO/
    - └── RAW/
      - └── BankFind Suite API - de novo.csv

### Mergers

- Material Events/
  - └── Mergers/
    - └── RAW/
      - └── BankFind Suite API - Mergers.csv

### Failures

- Material Events/
  - └── Failures/
    - └── RAW/
      - └── BankFind Suite API - Failures.csv


---

## Next Step

Proceed to **Step 06.1.1**:

- Apply signature-based deletion rules to remove BankFind Suite–labeled  
  or interim/sparse cleaned files before assigning event outcomes.
