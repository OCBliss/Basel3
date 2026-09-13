# Proposed bond pricing and horizon-return stage

This directory groups the historical Treasury preparation experiments. The
bond-pricing functions described below are a proposed interface: no implementation
of these functions or executable bond-valuation entry point is currently present
in the repository. The previous README's numeric YTM, bond-price and return
examples were not verified outputs of current code and have been removed.

The current executable work is
[interest-rate calibration and parameter simulation](../../../src/RWA/readme.md).
Portfolio valuation and duration-adjusted RWA remain unfinished research goals.

## Intended inputs

A valuation implementation needs a security's current price, coupon rate and
payment frequency, coupon dates, valuation date, horizon date and maturity date.
It also needs an explicit scenario discounting or repricing convention and
scenario probabilities. Historical [yield changes](EXP_DRIFT/readme.md) and
[parameter estimates](EXP_COUPON/readme.md) alone do not supply that full contract.
The latter are CIR/AR(1) estimates, not calculated coupon cash flows.

## Proposed calculations

| Proposed function | Intended responsibility |
| --- | --- |
| `years_to_maturity()` | Remaining life under a specified day-count convention |
| `generate_payment_dates()` | Coupon and principal payment schedule |
| `bond_price()` | Discounted cash flows under the selected yield/curve convention |
| `calculate_ytm()` | Yield consistent with a price and cash-flow schedule |
| `accrued_coupon_interest()` | Accrued interest under the chosen convention |
| `expected_return()` | Aggregate scenario holding-period returns with explicit weights |

The earlier research outline reprices a bond from an initial yield under a
specified horizon yield shift and combines its price change with received or
accrued coupon amounts. The implementation must settle cash-flow timing and clean
versus dirty prices before that outline becomes a valid return calculation.
A single deterministic yield shift does not itself establish a path-dependent
interest-rate model or an expected return across scenarios.

## Historical preparation and next implementation

The existing preparation sequence is [Cleaned](Cleaned/README.md),
[Differenced](Differenced/README.md), [EXP_DRIFT](EXP_DRIFT/readme.md), and
[EXP_COUPON](EXP_COUPON/readme.md). Their guides describe actual legacy behavior
and execution limitations. No command is provided here for nonexistent pricing
code. The [Expected Loss status](../Expected%20Loss/readme.md) records the missing
exposure, valuation, loss-measure and capital-mapping decisions.
