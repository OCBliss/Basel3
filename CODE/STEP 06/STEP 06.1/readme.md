# Step 06.1 — Clean Material Event Records (De Novo, Mergers, Failures)

## Purpose

This step normalizes raw **Material Events** data to a consistent schema for downstream integration with panel data and Jensen-Shannon Divergence (JSD) labeling. These events include:
- **De Novo** charters
- **Mergers and Acquisitions**
- **Failures and Closures**

---

## Input

Three directories of raw event data:
- `/Material Events/DE NOVO/RAW/`
- `/Material Events/Mergers/RAW/`
- `/Material Events/Failures/RAW/`


Each folder contains CSVs from various FDIC event logs.

---

## Output

Cleaned event data exported to:
- `/Material Events/DE NOVO/Cleaned/`
- `/Material Events/Mergers/Cleaned/`
- `/Material Events/Failures/Cleaned/`


Each file is:
- Restructured with consistent column order
- Includes all necessary fields
- Harmonized so `CERT` always denotes the affected bank

---

## Operations

1. **Column Reconciliation**
   - For `Failures/` and `Mergers/`, renames `OUT_CERT` → `CERT`
   - Ensures presence of all expected fields (missing ones filled with blanks)

2. **Schema Alignment**
   - Reorders columns into canonical form:
     ```
     ["CERT", "ACQ_CERT", "ACQ_CHARTAGENT", "ACQ_CLASS", "ACQ_INSAGENT1", ...]
     ```

3. **Robust Parsing**
   - Ignores row-level parsing errors (`error_bad_lines=False`)
   - Issues warnings on malformed lines but proceeds with cleaning

---

## Example Output Row

| CERT | ACQ_CERT | ACQ_CHARTAGENT | ... | NEW_CHARTER_FLAG | REGAGENT |
|------|----------|----------------|-----|------------------|----------|
| 12345 | 45678 | OCC | ... | 1 | FDIC |

---
