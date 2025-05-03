# Step 02.1 — Finalize Cleaned Quarterly Files with Time Encoding

## Overview

This script prepares each `Cleaned_Call_Report_<YYYYMMDD>.csv` file for longitudinal concatenation and lagged feature generation. Specifically:

- Removes the obsolete `RCON9224` column if present.
- Overwrites the `RCON9999` column with an integer-encoded date (e.g., 20240331).
- Saves the result back in-place.

This preprocessing is necessary to enforce uniform temporal identifiers across all bank records before aggregation in **Step 03**.

---

## Input

This script expects files from **Step 02**, located in:
- <ROOT_DIR>`/Call Report/CSV/Cleaned/`
