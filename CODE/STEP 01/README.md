# Step 01 — TXT to CSV Preprocessing with FDIC Certificate Augmentation

## Overview

This preprocessing script converts FFIEC Call Report `.txt` files into standardized `.csv` format. It dynamically finds and loads project-specific filepaths, processes each quarterly folder of text files, extracts the FDIC Certificate Number (`FDIC CERT`) using the `POR` file, and writes out clean, augmented `.csv` files to a structured subdirectory layout.

The resulting files are saved in: <ROOT_DIR>`Call Report/CSV/Schedules/`

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/CODE/STEP%2001/README_SVENSKA.md)

---

## Dependencies

- Python ≥ 3.6
- `csv`, `os`, `sys`, `importlib.util`

---

## Functionality

- **Dynamic Filepath Resolution**  
  Locates `Basel3_Global_Filepath.py` anywhere on the system.
  
- **Directory Creation**  
  Ensures existence of necessary directories under `/TXT` and `/CSV`.

- **FDIC Certificate Augmentation**  
  Uses `FFIEC CDR Call Bulk POR.txt` to map `IDRSSD → FDIC CERT`.

- **Batch TXT → CSV Conversion**  
  Converts all non-POR `.txt` files in quarterly subfolders into `.csv` format, injecting the FDIC Certificate number as the second column.

- **Error Handling**  
  Skips subdirectories without a valid `POR` file or IDRSSD mapping.

---

## Output Structure

Each output `.csv` will contain:

1. `IDRSSD` — Institution identifier
2. `FDIC Certificate Number` — Mapped from POR file
3. Remaining columns — Original schedule columns

---

## Usage

Ensure the following conditions:

1. `Basel3_Global_Filepath.py` exists and defines `ROOT_DIR`.
2. FFIEC Call Report text data is placed into: <ROOT_DIR>`Call Reports/TXT/`
3. They are download from the FFIEC CDR, unzipped, and convert ending date MM:DD:YYYY --> YYYY:MM:DD
