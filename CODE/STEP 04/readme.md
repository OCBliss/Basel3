## Directory ##
`CODE/STEP 04/`
- `STEP 04.0/`
- `STEP 04.1/`

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
