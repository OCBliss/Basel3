## Directory ##
- `src/`:  
  - `ratios/`:
    - Call_Reports_Distributed_Ratios3.py
    - Clean_Distributed_Ratios2.py
    - Call_Reports_Dynamic_Ratios3.py
    - Clean_dynamic_ratio2.py

# Step 04 — Distributed Lag Construction for Panel Data

## Overview

This script constructs a **distributed-lag panel dataset** from interleaved Call Report files by merging each bank’s current-quarter data with their values from the **next 3 quarters**. The result is a horizontally stacked DataFrame per bank-quarter, enabling analysis of forward changes and risk trajectory.

These are saved as `Distributed_Call_Report_YYYYMMDD.csv` and form the base panel for Jensen-Shannon divergence modeling and other temporal diagnostics.

---

# Step 04.1 — Cleaning Distributed Lag Panel Files

## Overview

This script takes the distributed-lag panel datasets created in **Step 04** and performs final cleaning for modeling. Specifically, it:
- Identifies rows that begin with valid identifiers (e.g., non-empty `CERT`)
- Replaces all `NaN` or empty cells in those rows with `0`
- Preserves structurally empty or invalid rows (e.g., header glitches or malformed rows) by skipping them

This step is critical for ensuring consistency in modeling inputs, preventing propagation of `NaN` values during divergence or slope calculations.

---

# Step 05 — Dynamic Lag Panel Construction

## Purpose

This step transforms the distributed panel data into a dynamic lag structure by calculating **quarter-over-quarter percentage changes** (slopes) for all numeric features across three prior lags. It enables dynamic signal tracking and temporal trend inference.

---

## Input

- Cleaned distributed-lag datasets from **Step 04.1**: `/Call Report/CSV/Distributed_Lag/Cleaned/`
- Required Filename Format: `Distributed_Cleaned_Call_Report_<YYYYMMDD>.csv`
- A `quarters.csv` file in: `/Call Report/CSV/quarters.csv`

---

## Output

- Directory: `/Call Report/CSV/Dynamic_Lag/RAW/`
- 
- For each input file:
- Output is named:
  ```
  Dynamic_Distributed_Cleaned_Call_Report_<YYYYMMDD>.csv
  ```

---

## Methodology

For each input file:

1. **Determine Quarters**  
 - Extract the quarter from the filename (e.g., `20211231`)
 - Use `quarters.csv` to find the 3 subsequent quarters (i.e., q0q1, q0q2, q0q3)

2. **Dynamic Lag Creation**
 - For each base column (e.g., `RCB-0211-1754`):
   - Retain the value as `col_q0`
   - Compute percent deltas vs. prior quarters:
     - `col_q0q1 = (q0 / q1) - 1`
     - `col_q0q2 = (q0 / q2) - 1`
     - `col_q0q3 = (q0 / q3) - 1`
   - If a denominator is 0, delta is defaulted to 0

3. **Output Assembly**
 - All deltas are appended by suffix: `_q0`, `_q0q1`, `_q0q2`, `_q0q3`
 - Each row is indexed by `CERT` (bank identifier)

---

## Example Columns in Output
- `CERT`
- `RCB-0211-1754_q0`
- `RCB-0211-1754_q0q1`
- `RCB-0211-1754_q0q2`
- `RCB-0211-1754_q0q3`
- `RCB-G304-Item4a_q0`
- `RCB-G304-Item4a_q0q1`


---

## Significance

These quarter-to-quarter percentage change features are central to:

- Jensen-Shannon Divergence tracking
- Lagged covariate trend analysis
- Early warning indicator PMF construction

By creating this structured panel, we enable downstream statistical diagnostics to analyze temporal variance across regulatory ratios, liquidity, capital, and mitigate simultaneity and reverse causality concerns.

---



