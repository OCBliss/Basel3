# Steps for Practical Non-Parallel Rate Shocks

⚠️ ATTENTION: Start with **Step 09** [here](https://github.com/OCBliss/Basel3/tree/main/RWA/Practical/Constant%20Maturity%20Treasury/Cleaned)

Experimental

This module is intended to estimate duration-driven expected losses across Treasury maturities and allocate those losses to government securities reported in Call Report schedules (RCONA549–RCONA555). The resulting adjustments will be used to derive a duration-adjusted RWA measure for research purposes. Development is ongoing.

### Directory Structure
- `Constant Maturity Treasury/`: `autoregressive_fitting_v3a.py`.
  - `Cleaned/`: Cleans CMT data `RWA/FRED/`.
  - `Differenced/`: Performs rolling differencing for non-parallel drift calculations.
  - `EXP_DRIFT/`: Performs non-parallel drift calculations.
  - `EXP_COUPON/`: Performs expected coupon calculations.
 
### Steps
- Step 09 --> `RWA/Practical/Constant Maturity Treasury/Cleaned/`
- Step 10 --> `RWA/Practical/Constant Maturity Treasury/Differenced/`
- Step 11 --> `RWA/Practical/Constant Maturity Treasury/EXP_DRIFT/`
- Step 12 --> `RWA/Practical/Constant Maturity Treasury/EXP_COUPON/`
- Step 13 --> `RWA/Practical/Constant Maturity Treasury/`
