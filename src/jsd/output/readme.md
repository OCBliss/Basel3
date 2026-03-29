# Step 08.2.0.5 — Matrix Construction of JSD Metrics by Horizon

## Purpose

This script builds *Jensen-Shannon Divergence (JSD)* matrices by variable group across **Basel III horizon windows T+1 to T+4**, organizing precomputed divergence files into time-series panels for downstream visualization and comparative analysis.

---

## Key Functionality

- **Auto-locates** `Basel3_Global_Filepath.py` to determine the `ROOT_DIR` dynamically
- **Scans all** `JSD_*.csv` files within `Material Events/JSD/BASEL III T+1..T+4`
- **Parses column names** using regex pattern:

RCB-<group_id>_<lag_suffix>
Example: RCB-2312-02_q0q2

- **Groups columns** by RCB group and organizes JSD values across time horizons
- **Builds and saves** one output CSV per `(peer_group, RCB-group)` pair into:

/Material Events/JSD/Matrix Outputs/JSD_<peer_meta>_<group>.csv


---

## Output Structure

Each matrix CSV has:

| Lag Suffix | BASEL III T+1 | BASEL III T+2 | BASEL III T+3 | BASEL III T+4 |
|------------|----------------|----------------|----------------|----------------|
| q0         | ...            | ...            | ...            | ...            |
| q0q1       | ...            | ...            | ...            | ...            |
| q0q2       | ...            | ...            | ...            | ...            |
| q0q3       | ...            | ...            | ...            | ...            |

- One CSV is created per `(peer_meta, RCB-group)` combination
- Values are pulled from the **first row** of each JSD_*.csv file (assumed single-row)

---

## Why It Matters

This step unifies JSD divergence statistics into a **coherent time-panel format** for each variable group, enabling:

- Consistent **comparison of risk signal intensity** across Basel III horizons
- Clearer **visualization of temporal dynamics** in systemic risk divergence
- Downstream feeding into modal or macroprudential policy frameworks

---

## File Naming Convention

For a source JSD file:

JSD_survivors_vs_failures_100.csv

And a group like `RCB-0211-1754`, the output will be:

/Matrix Outputs/JSD_survivors_vs_failures_20_RCB-0211-1754.csv
