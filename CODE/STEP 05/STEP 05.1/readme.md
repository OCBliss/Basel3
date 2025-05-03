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

## Next Step

Proceed to **Step 06**:
- `Material Events` cleaning
- `Material Events` flagging for peer group analysis
