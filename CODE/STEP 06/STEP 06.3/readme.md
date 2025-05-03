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

## Next Step

Proceed to **Step 06.4**:
- Merge **merger flags** for banks that were absorbed into others (non-failure exits)
- Derive full event-type labeling: {Survivor, Failure, Merger}
