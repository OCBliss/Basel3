# Step 11 — Compute Expected Drift of Treasury Yields (Forward Differences)

## Purpose

This step processes forward-differenced Treasury rate data (from previous differencing steps) and computes the **expected drift**—that is, the **average positive yield change**—for each constant maturity term (1Y, 3Y, 5Y, etc.).

These expected drifts can be used to:
- **Calibrate forward-looking interest rate scenarios**
- **Anchor regulatory stress parameters**
- **Generate realistic forward rate paths for RWA modeling**

---

## Input

Differenced files from the previous pipeline step (e.g., Step 9 or prior Step 10):
- `/RWA/Constant Maturity Treasury/Differenced/differenced_<source_file>.csv`


Each file contains:
- A `observation_date` column
- Forward-difference columns like `DGS1`, `DGS3`, `DGS5`, `DGS10`, `DGS20`, `DGS30`
- Cells with either a float value or blank (if difference ≤ 0)

---

## Output

A single CSV summarizing average (non-zero) forward yield changes:


| file                  | DGS1  | DGS3  | DGS5  | DGS10 | DGS20 | DGS30 |
|-----------------------|-------|-------|-------|-------|-------|-------|
| differenced_DGS.csv   | 0.18  | 0.22  | 0.25  | 0.19  | 0.15  | 0.14  |

Only columns present in each file will be averaged. Missing or blank values are skipped.

---

## Methodology

1. Load each column in `differenced_*.csv` file from the differenced directory
2. Coerce all values to numeric (ignore blanks)
3. Compute `mean(skipna=True)` for each maturity column:

E[ΔRate] = average of all positive 1-year forward changes

4. Write a summary table where each row corresponds to a file, and columns are expected drifts

---

## Use Case

Expected drifts computed here can be:
- Used as **mean shocks** in stochastic rate simulations
- Embedded into **forward-looking Basel III capital scenarios**
- Input into gamma distribution fitting, stress test thresholds, or portfolio loss estimators

---

## Next Step

Proceed to **Step 12**:
- Fit parameters to models (e.g., CIR, AR, etc.) to the differenced curves
