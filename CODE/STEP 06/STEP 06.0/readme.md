# Step 06.0 — FDIC API Ingestion for De Novo, Mergers, and Failure Events

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
