# Call Report Folder

The Call Report folder contains all data derived from FFIEC call reports, organized to facilitate data processing and analysis for the Basel III study. This folder includes raw data, intermediate formats, and processed datasets ready for analysis.

## CSV

The `CSV/` directory contains the intermediate analytical datasets generated
from the raw FFIEC Call Reports.

Rather than storing a single dataset, the pipeline progressively transforms the
raw regulatory filings into increasingly analysis-ready representations. Each
subdirectory corresponds to a distinct stage of the data engineering process.

---

### Processing Workflow

```
TXT
 │
 ▼
Cleaned
 │
 ▼
Schedules
 │
 ▼
Interleaved
 │
 ├──────────────┐
 ▼              ▼
Distributed Lag Dynamic Lag
```

---

### Cleaned/

Converts the raw FFIEC TXT files into standardized CSV datasets.

This stage performs parsing, formatting, column normalization, and basic data
quality checks while preserving the original quarterly observations.

Purpose:

- convert raw regulatory files into machine-readable datasets
- standardize variables across reporting periods
- remove malformed observations

---

### Schedules/

Merges individual FFIEC reporting schedules into a single quarterly dataset.

Each reporting schedule (RC, RC-B, RC-C, RC-R, etc.) is horizontally combined
using the institution identifier, producing one comprehensive Call Report for
each bank and quarter.

Purpose:

- reconstruct complete quarterly balance sheets
- preserve schedule relationships
- provide a unified regulatory dataset

---

### Interleaved/

Transforms quarterly snapshots into longitudinal bank histories.

Rather than treating each quarter independently, observations belonging to the
same institution are organized chronologically to facilitate temporal analysis.

Purpose:

- create longitudinal datasets
- enable trend analysis
- prepare for lag construction

**Reason**

Call Reports are not structurally uniform across institutions or time.
Advanced Approaches (AA) and non-Advanced Approaches (non-AA) institutions,
along with changes in FFIEC reporting standards, frequently report equivalent
economic concepts using different MDRM codes or different reporting
definitions.

The interleaving stage reconciles these structural differences into a common
representation so that equivalent financial concepts are aligned across all
institutions. This harmonized dataset enables subsequent temporal analysis,
distributed lag construction, dynamic ratio calculations, and Jensen-Shannon
divergence without introducing artifacts from regulatory reporting
differences.

---

### Distributed Lag/

Appends historical observations from previous quarters to each bank.

For every observation quarter, variables from earlier reporting periods are
merged into the same record.

Purpose:

- provide historical context
- support lag-based modeling
- preserve prior quarterly observations

---

### Dynamic Lag/

Transforms lagged observations into rates of change.

Rather than comparing absolute values alone, this stage computes changes
between reporting periods.

Examples include

- q0
- q0q1
- q0q2
- q0q3

These variables capture the evolution of financial ratios immediately preceding
future structural events.

Purpose:

- measure balance-sheet dynamics
- quantify acceleration and deceleration
- prepare inputs for Jensen-Shannon divergence analysis

## Folder Structure

### 1. **PDF/**
   - **Description:** Visual versions of the FFIEC call reports for manual inspection and validation.
   - **Contents:**  
     - Files in PDF format, organized by financial quarter (e.g., `20240630.pdf`).
   - **Usage:** Used for manual verification and reference.

### 2. **TXT/**
   - **Description:** Raw data files downloaded from the FFIEC CDR (Central Data Repository).
   - **Contents:**  
     - Subfolders for each financial quarter, named by the quarter’s end date (e.g., `20240630/`).
     - Files in native text format as provided by FFIEC.
   - **Usage:**  
     - Input for data preprocessing and conversion into CSV format (found in the CSV folder).
     - Provides an unaltered source for reproducibility.

### 3. **CSV/**
   - **Description:** Contains processed data in CSV format, structured for analysis.
   - **Subfolders:**
     - **Cleaned/**:  
       - Processed datasets converted from TXT files.
       - Files named by financial quarter (e.g., `20240630_cleaned.csv`).
     - **Schedules/**:  
       - Merged datasets for each financial quarter, providing a comprehensive horizontal view of all schedules.
       - Files named by financial quarter (e.g., `20240630_schedules.csv`).
     - **Interleaved/**:  
       - Vertical analysis of call report data, enabling temporal comparisons and trend identification.
       - Files named by financial quarter (e.g., `20240630_interleaved.csv`).
   - **Usage:**  
     - Cleaned data serves as the basis for merging and interleaving steps.
     - Schedules and Interleaved folders provide processed datasets for specific types of analysis.

## How to Use This Folder
1. **For Raw Data:**
   - Refer to the `TXT/` subfolder for unprocessed FFIEC call report data by quarter.
2. **For Processed Data:**
   - Use the `CSV/` subfolders for datasets ready for analysis:
     - Start with `Cleaned/` for initial data.
     - Use `Schedules/` or `Interleaved/` depending on the type of analysis required.
3. **For Validation:**
   - Refer to the `PDF/` subfolder for visual cross-checking of raw call report data.

## Additional Notes
- Each subfolder includes its own `README.md` file with more detailed instructions and metadata.
- For reproducibility instructions and code, refer to the main `README.md` in the Basel3 repository.
