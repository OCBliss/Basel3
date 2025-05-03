# Step 04.1 — Cleaning Distributed Lag Panel Files

## Overview

This script takes the distributed-lag panel datasets created in **Step 04** and performs final cleaning for modeling. Specifically, it:
- Identifies rows that begin with valid identifiers (e.g., non-empty `CERT`)
- Replaces all `NaN` or empty cells in those rows with `0`
- Preserves structurally empty or invalid rows (e.g., header glitches or malformed rows) by skipping them

This step is critical for ensuring consistency in modeling inputs, preventing propagation of `NaN` values during divergence or slope calculations.

---

## Input Requirements

- Files from Step 04 in: `/Call Report/CSV/Distributed_Lag/RAW/`
- File Format: `Distributed_Cleaned_Call_Report_<YYYYMMDD>.csv`

---

## Output

- Directory: `/Call Report/CSV/Distributed_Lag/Cleaned/`

- For each input file:
- All valid rows will have their missing values filled with `0`
- Output files preserve original structure and column names

---

## Logic Summary

1. Load each CSV file from the `/RAW/` folder
2. For each row:
 - If the **first column** (typically `CERT` or `IDRSSD`) is non-empty:
   - Replace all `NaN` or empty cells in that row with `0`
 - Else:
   - Leave row untouched
3. Save the updated DataFrame to `/Cleaned/`

---

## Why This Matters

Many models (e.g., Jensen-Shannon divergence, slope metrics) require complete data for numerical operations. However, blanket-filling all missing values would corrupt structurally invalid rows. This step ensures:

✅ Valid financial entries are cleaned and ready  
✅ Broken rows are left untouched and filtered out later  
✅ Modeling inputs are zero-imputed only where meaningful

---

## Next Step

Proceed to **Step 05** (or Step 05.0):
- Run filtration-adaptive ratio modeling
- Calculate forward slopes or percent deltas

---
