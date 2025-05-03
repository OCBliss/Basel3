# Step 02 — Merge Call Report Schedules into Cleaned Quarterly CSVs

## Overview

This script consolidates FFIEC Call Report schedules from each quarter into a unified, bank-level `.csv` file. It appends key schedules to a base `ENT` file (`Entity Information`) using `IDRSSD` as the join key, skipping duplicate columns and handling structural variation across years.

The result is a series of quarterly "Cleaned Call Report" files placed in: 
<ROOT_DIR>/Call Report/CSV/Cleaned/Cleaned_Call_Report_<YYYYMMDD>.csv


These cleaned outputs are the direct inputs to **Step 02.1**, where longitudinal transformations, lagged ratios, and dynamic metrics are computed for Jensen-Shannon divergence (JSD), CET1, and liquidity-risk modeling.

---

## Directory Structure



---

## Key Functions

### `find_code_dir()`
Dynamically traverses parent directories to find the `CODE/` folder, making the script path-agnostic.

### `merge_files_sequentially(base_file_path, files_to_append, output_path)`
Merges schedule CSVs into a single DataFrame by sequentially appending columns. Ensures columns are only appended if not already present.

### `determine_files_to_append(input_directory, subfolder)`
Returns a list of expected schedule filenames for a given quarter. Logic is branch-conditional depending on:
- FFIEC format versions (which changed over the years)
- Number of parts in each schedule

---

## Output Structure

Each `Cleaned_Call_Report_<YYYYMMDD>.csv` contains:

- One row per bank (`IDRSSD`)
- Columns from:
  - ENT (entity metadata)
  - RC (balance sheet)
  - RC-B (securities)
  - RC-R Part I and II (capital)
  - RC-O (off-balance sheet)
  - RCE (equity)
  - Other schedules depending on the year

---

## Usage

Ensure:

1. You have run **Step 01** and generated `.csv` schedules under: <ROOT_DIR>/Call Report/CSV/Schedules/<YYYYMMDD>/
   
