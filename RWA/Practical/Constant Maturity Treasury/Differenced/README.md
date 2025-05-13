# Generate Rolling 1-Year Yield Shocks (Differenced Treasury Curves)

## Purpose

This step transforms **Constant Maturity Treasury (CMT)** yield data into **year-ahead forward differences**, simulating 1-year changes in the term structure of interest rates. This forward-differenced format is useful for:

- **Volatility estimation**
- **Scenario analysis**
- **Shock calibration under Basel III**

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/RWA/Practical/Constant%20Maturity%20Treasury/Differenced/README_SVENSKA.md)

---

## Input

Cleaned and merged yield curve data produced in **Step 9**:

`/RWA/Practical/Constant Maturity Treasury/Cleaned/`


Each file must contain:
- `observation_date` column
- Multiple columns of yields (e.g., `DGS1`, `DGS5`, `DGS10`, etc.)

---

## Output

The script produces forward-differenced files in:

`/RWA/Practical/Constant Maturity Treasury/Differenced/`


The output file is named: `differenced_<original_file>.csv`


---

## Methodology

1. **1-Year Offset (Default: 252 business days)**:
   For each date `t`, subtract the rate at `t - 252` from the rate at `t`, per maturity column.

2. **Filtering Threshold (Default: 0.0)**:
   Only retain positive differences (i.e., `ΔRate > threshold`), replacing others with blank cells. This helps isolate **shock-only scenarios**.

3. **Transformation Logic**:
   For each maturity:
   - ΔRate_t = Rate_t - Rate_{t-252}
  

4. **Column Naming**:
- `observation_date` retained
- Other columns match original maturities (`DGS1`, `DGS10`, etc.)

---

## Example Output (Head)

| observation_date | DGS1 | DGS5 | DGS10 |
|------------------|------|------|--------|
| 2023-12-29       | 0.30 |      | 0.15   |
| 2023-12-28       | 0.10 | 0.25 |        |
| ...              | ...  | ...  | ...    |

Blank cells represent zero or negative changes (filtered out).

---

## Parameters

- `offset = 252`  
Number of business days (~1 year) to lag for differencing

- `threshold = 0.0`  
Minimum difference to retain a value; others are replaced with `''`

---

## Use Case

These forward-difference curves can be used to:
- Estimate empirical shock distributions
- Calibrate PDMM-Heston volatility parameters
- Simulate historical scenarios for stress testing

---

