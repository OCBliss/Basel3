# Merge and Clean FRED Constant Maturity Treasury Data

## Purpose

This step consolidates multiple **Constant Maturity Treasury (CMT)** series from the FRED database into a single unified time series file. It ensures all rates are aligned by date, missing values are forward-filled, and the result is ready for use in duration-sensitive Basel III modeling.

- Use `Constant_Maturity_Treasury_Cleaned2a.py` first

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/RWA/Practical/Constant%20Maturity%20Treasury/Cleaned/README_SVENSKA.md)

---

## Input

Daily Treasury yield data (downloaded from FRED):

| Maturity | Filename |
|----------|----------|
| 1 Year   | `DGS1.csv` |
| 3 Year   | `DGS3.csv` |
| 5 Year   | `DGS5.csv` |
| 10 Year  | `DGS10.csv` |
| 20 Year  | `DGS20.csv` |
| 30 Year  | `DGS30.csv` |

These files are expected in:

`/RWA/FRED/`

### `observation_date` currently not formatted correctly
Each file must contain:
- A `observation_date` column (e.g., `12/31/23`)
- A yield value column (e.g., `DGS10`)

---

## Output

The script produces:

`/RWA/Practical/Constant Maturity Treasury/Cleaned/combined_fred_treasury_data.csv`


This output:
- Has one row per `observation_date`
- Contains columns for each maturity’s yield
- Is sorted in **reverse chronological order**
- Fills in missing values via **backward fill** (`bfill`)

---

## Methodology

1. **Load `Basel3_Global_Filepath.py`** to dynamically resolve filepaths
2. Read all CMT series using `'observation_date'` as the key
3. Join all series horizontally on date
4. Convert `observation_date` to datetime and sort descending
5. Backfill missing yields using the next available future value
6. Write output to `combined_fred_treasury_data.csv`

---

## Example Output (Head)

| observation_date | DGS1 | DGS3 | DGS5 | DGS10 | DGS20 | DGS30 |
|------------------|------|------|------|-------|-------|-------|
| 12/29/23       | 4.85 | 4.63 | 4.52 | 4.12  | 4.05  | 4.00  |
| 12/28/23       | 4.82 | 4.60 | 4.50 | 4.10  | 4.03  | 3.98  |
| ...              | ...  | ...  | ...  | ...   | ...   | ...   |

---

## Use Case

This unified Treasury dataset is used for:
- **Interest rate term structure modeling**
- **Risk-weight calibration**
- **Yield curve interpolation**
- **Scenario generation in RWA/PDMM-Heston models**

---

## Next Step

Proceed to **Differencing**: `Constant_Maturity_Treasury_Differenced5a.py`
- Currently fixing directory setup
