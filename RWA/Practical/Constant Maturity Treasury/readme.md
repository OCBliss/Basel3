# Step 13 — Bond Pricing and Expected Return Under Yield Shift

⚠️ ATTENTION: Start with **Step 09** [here](https://github.com/OCBliss/Basel3/tree/main/RWA/Practical/Constant%20Maturity%20Treasury/Cleaned)

## Purpose

This step calculates the **expected return** of a fixed-coupon bond over a defined forward horizon, accounting for:

- **Accrued coupon interest**
- **Yield-to-maturity (YTM) recalibration**
- **Interest rate shifts**
- **Price impact due to forward rate shocks**

This framework supports Basel III RWA modeling by allowing precise loss estimation under simulated yield curve changes.

- From **Step 11** we pull the expected non-parallel shift from [here](https://github.com/OCBliss/Basel3/tree/main/RWA/Practical/Constant%20Maturity%20Treasury/EXP_DRIFT)
- From **Step 12** we pull the expected coupons from [here](https://github.com/OCBliss/Basel3/tree/main/RWA/Practical/Constant%20Maturity%20Treasury/EXP_COUPON)

---

## Inputs

Bond and scenario parameters:

- **Current bond price** (e.g., $1000.00)
- **Coupon rate** (e.g., 2%)
- **Payment frequency** (e.g., semiannual = 2)
- **Pricing date** and **interest rate change date**
- **Maturity date**
- **Simulated yield change** (e.g., +1%)

---

## Core Functions

| Function                       | Description                                                                 |
|-------------------------------|-----------------------------------------------------------------------------|
| `years_to_maturity()`         | Computes remaining time in years between pricing and maturity              |
| `generate_payment_dates()`    | Creates all future payment dates from start to maturity                    |
| `bond_price()`                | Prices the bond using discounted cash flow model                           |
| `calculate_ytm()`             | Solves for internal rate of return (YTM) given price                       |
| `accrued_coupon_interest()`   | Estimates pro-rata interest earned between coupon periods                  |
| `expected_return()`           | Computes return as: (accrued + price change) ÷ initial price               |

---

## Output

Console output displays:

- Calculated YTM: **2.0000%**
- Future Bond Price on `pricing_date`: **$877.84**
- Expected Return from `pricing_date` to `interest_rate_change_date`: **-12.2155%**



You can repurpose this output into shock-response plots or integrate it into scenario-based capital loss estimation matrices.

---

## Methodology

Given a bond priced on `t_j` and revalued at `t_{j+k}` under a yield shift:

1. Compute `YTM(t_j)` via root-finding
2. Simulate `YTM(t_{j+k}) = YTM(t_j) + Δy`
3. Reprice bond at `t_{j+k}` under new yield


This framework isolates **interest rate path dependency** while accounting for timing of payments and discounting.

---

## Use Case

- **Stress testing bond portfolios under yield shock scenarios**
- **Duration-based risk attribution**
- **Simulated market value loss under Basel III stress matrices**
- **Coupon-driven return decomposition for capital adequacy metrics**

---

## Next Step

Proceed to **Step 14**:
- Integrate bond-level return impacts into aggregated loss forecasts
- Match forward drift-adjusted scenarios with PDMM-Heston dynamics

