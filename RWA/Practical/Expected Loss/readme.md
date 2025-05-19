# Placeholder for Practical Expected Loss

- `RWA/`:
  - `Practical`: Simplified non-parallel yield shock calculation
    - `Constant Maturity Treasury/`
      - `Cleaned/`
      - `Differenced/`: Calculates only the positive yield shocks over a rolling time horizon. Any values below a threshold are filtered out to model only the downside deviation (risk of loss).
      - `EXP_DRIFT/`: Calculates the independent rate rates for each maturity.
      - `EXP_COUPON/`: Expected coupon calculations for RWA.
    - `Expected Loss/`: Place the expected loss calculations here from Step 13.
