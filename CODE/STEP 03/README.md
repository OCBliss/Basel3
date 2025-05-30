# Step 03 — Feature Extraction and Interleaving of Call Report Observations

## Overview

This script takes bank-specific Call Report CSVs from the `/Cleaned/` directory and generates analytic features via ratio computations using balance sheet, securities, and regulatory capital components.

Each bank's quarterly record is processed into two parallel observations (entry1 and entry2) from separate column sets (RCON and RCFD). These are interleaved and deduplicated to produce a final bank-quarter feature vector.

 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/CODE/STEP%2003/README_SVENSKA.md)

## Retrospective Scripts: CET1 and RWA Notes

This repository includes multiple vertical aggregation scripts for Call Report data, with tradeoffs between stability and coverage:

### `call_reports_vertical_retrospective3c.py`
- ✅ **Stable** — does **not** produce typecasting or coercion errors
- ✅ Safely processes historical report structure for aggregation and alignment
- ❌ **Does not include** CET1 threshold metrics or risk-weighted asset (RWA) duration adjustments
- ➤ Recommended for structural validation, pre-JSD or filter-stage pipeline runs

### `call_reports_vertical_retrospective4b.py`
- ✅ **Includes** CET1 threshold metrics and RWA duration adjustments for capital calibration
- ⚠️ **May raise casting errors** due to percentage-formatted cells (e.g., `"34.5%"`) being interpreted as strings
- ✅ These errors can be manually resolved:
  - Open the `.csv` in Excel
  - Change column format from `Percentage` → `Number`
  - Save and re-run the script
- ➤ This workaround consistently succeeds and allows full capital reconstruction logic to proceed

> 📌 Note: Automated dtype coercion should now be fixed in v1.0 for `call_reports_vertical_retrospective4.py`

### `call_reports_vertical_retrospective5.py`
- ✅ **Includes** Depositor behavior using RC-E Part I.
  - NSFR claims
  - NML claims
    - depository heterogeneity
    - stable transactional deposits
    - non-Kolmorogovian withdrawal behavior
    - non-Markovian withdrawal behavior
---

## Input

- Directory: <ROOT_DIR>`/Call Report/CSV/Cleaned/`


- Each file must already have:
- `RCON9999` encoded as integer date
- FDIC Certificate numbers assigned
- `RCON9224` removed (done in Step 02.1)

---

## Output

- Directory: <ROOT_DIR>`/Call Report/CSV/Interleaved/`


- Each output file contains:
- One row per `IDRSSD` (bank), interleaving `entry1` and `entry2`
- Feature columns capturing:
  - AFS-to-HTM ratios
  - Fair value vs amortized cost relationships
  - CET1 / RWA regulatory capital strength
  - Schedule RC, RCB, and RCR-based ratios
  - Maturity buckets for securities
- Duplicates resolved by keeping the row with the fewest blank cells

---

## Feature Methodology

- **Entry 1** is derived from `RCON` prefixed variables  
- **Entry 2** is derived from `RCFD` prefixed variables  
- Features are calculated using conditional logic by quarter, ensuring correct treatment of evolving report line definitions

- Categories include:
- **Balance Sheet Composition:** Asset/liability/equity decomposition (Schedule RC)
- **Securities Book Values:** HTM and AFS (Schedule RC-B)
- **Maturity Buckets:** Based on repricing horizons (Memoranda M2a, M2b)
- **Regulatory Capital:** CET1, AOCI-adjusted CET1, RWA (Schedule RC-R)
- **Domain-specific Ratios:** e.g., `G300` residential MBS vs aggregate exposure

---

## Usage

Ensures the following directory structure exists:

<ROOT_DIR>/Call Report/:

  - CSV/
    - Cleaned/
    - Interleaved/: **Step 03**
      - Cleaned/: **Step 03.1**


