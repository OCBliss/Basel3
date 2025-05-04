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

## Outcome (Step 06.4)

Each row now has both **failure** and **merger** flags across a 4-quarter horizon, allowing:
- Tripartite outcome classification for systemic multi-horizon event modeling
- Censored-event analysis

---
