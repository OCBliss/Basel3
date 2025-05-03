# Step 05.1 — Clean Dynamic Lag Panel (Pre-JSD)

## Purpose

This step cleans the output generated from Step 05 by:
- Dropping auxiliary identifiers (e.g., IDRSSD lag values)
- Renaming key fields for consistency
- Normalizing filenames for downstream use

This is the **final preprocessing step** before Jensen-Shannon Divergence (JSD) and systemic risk analytics are applied.

---

## Input

- Dynamic lagged panel files from: `/Call Report/CSV/Dynamic_Lag/RAW/`
- Dynamic_Distributed_Cleaned_Call_Report_20211231.csv
Dynamic_Distributed_20200331.csv

---

## Output

- Cleaned panel files written to: `/Call Report/CSV/Dynamic_Lag/Cleaned/`
- New filenames are replaced with: DDRL_Cleaned_Call_Report_20211231.csv
Dynamic_Distributed_20200331.csv


---

## Operations

1. **Column Removal**
 - The following are dropped:
   ```
   IDRSSD_q0, IDRSSD_q0q1, IDRSSD_q0q2, IDRSSD_q0q3
   RCON9999_q0q1, RCON9999_q0q2, RCON9999_q0q3
   CERT_q0
   ```

2. **Column Renaming**
 - `RCON9999_q0` ➜ `RCON9999`  
   (ensures consistent quarter tagging)

3. **File Renaming**
 - If file starts with `Dynamic_Distributed_`, it's renamed to:
   ```
   DDRL_<suffix>
   ```
 - Otherwise, just prepends `DDRL_`



---

## Outcome

This results in a cleaned, consistent dataset of dynamic lagged features ready for:

- `Material Events` flagging
- Peer group filtering

---
