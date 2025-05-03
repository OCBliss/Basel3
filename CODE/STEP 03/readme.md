# Step 03 — Feature Extraction and Interleaving of Call Report Observations

## Overview

This script takes bank-specific Call Report CSVs from the `/Cleaned/` directory and generates analytic features via ratio computations using balance sheet, securities, and regulatory capital components.

Each bank's quarterly record is processed into two parallel observations (entry1 and entry2) from separate column sets (RCON and RCFD). These are interleaved and deduplicated to produce a final bank-quarter feature vector.

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
- One row per `IDRSSD` (bank), interleaving entry1 and entry2
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

Ensure the following directory structure exists:
Call Report/
├── CSV/
│ ├── Cleaned/
│ └── Interleaved/
└── CODE/
└── Basel3_Global_Filepath.py # must define BASEL3_ROOT


