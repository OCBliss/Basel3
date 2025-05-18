# Step 12 — Estimate Mean Reversion Dynamics via CIR Model

## Purpose

This step fits a **Cox-Ingersoll-Ross (CIR)** model to historical yield data for each constant maturity Treasury series. The CIR model is commonly used in financial modeling due to its:

- **Mean-reverting behavior**
- Non-negativity constraint on rates
- Usefulness in forward drift calibration under Basel III scenarios

This output can be used to simulate yield paths or calculate expected coupons under stochastic dynamics.

---

## Input

Constant Maturity Treasury rate CSVs downloaded from FRED:

- `RWA/`
  - `/FRED/`
    - DGS1.csv
    - DGS3.csv
    - DGS5.csv
    - DGS10.csv
    - DGS20.csv
    - DGS30.csv


Each file must contain:
- `observation_date` (datetime)
- The rate column (e.g., `DGS10`) as a percentage

---

## Output

A CSV file summarizing CIR parameter estimates for each term:

- `/RWA/Practical/Constant Maturity Treasury/EXP_COUPON/CIR_parameters_summary.csv`


The output has the structure:

| Parameters             | DGS1  | DGS3  | DGS5  | DGS10 | DGS20 | DGS30 |
|------------------------|-------|-------|-------|-------|-------|-------|
| Mean Reversion Speed θ | 0.99  | 1.15  | 0.84  | 0.76  | 0.62  | 0.51  |
| Long-Term Mean μ       | 0.03  | 0.035 | 0.04  | 0.045 | 0.05  | 0.053 |
| Volatility σ           | 0.012 | 0.011 | 0.010 | 0.009 | 0.008 | 0.007 |

---

## Methodology

For each term (e.g., DGS10):

1. Load and clean data:
   - Sort by `observation_date`
   - Drop NaNs
   - Convert from percentage to decimal

2. Fit the CIR model:

   \[
   dr_t = \theta (\mu - r_t) dt + \sigma \sqrt{r_t} dW_t
   \]

   via maximum likelihood estimation (`scipy.optimize.minimize`) using:

   - 252 business days per year
   - Daily observations

3. Save:  
   - **Mean Reversion Speed** `θ`  
   - **Long-Term Mean** `μ`  
   - **Volatility** `σ`

---

## Configuration

- **Model Type:** `"CIR"` or `"AR1"`  
  - CIR (default) fits non-linear, mean-reverting model with square-root diffusion
  - AR1 fits a linear autoregressive process as fallback

- **Multiprocessing:** Uses all available cores for speed.

---

## Use Cases

- **Coupon drift forecasting**
- **Yield curve simulations**
- **Stochastic RWA and duration-adjusted loss modeling**
- **Input to PDMM-Heston or Monte Carlo term structure engines**

---

## Next Step

Proceed to **Step 12**:
- Generate stochastic rate paths or coupon shock matrices
- Integrate CIR parameters into simulated capital depletion scenarios
