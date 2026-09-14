# Interest-rate calibration, parameter simulation and the RWA research goal

## Covariance, Cholesky and the recursive factors

- [State factors and fitted parameter names](../src/RWA/models/parameter_hierarchy/readme.md#state-and-coefficient-names)
- [Historical initialization](../src/RWA/models/parameter_hierarchy/readme.md#historical-initialization-estimates-need-their-own-warmup)
- [Covariance formula for all eight maturities](../src/RWA/models/parameter_hierarchy/readme.md#covariance-calculation-for-all-eight-maturities)
- [Repairing every factor at all eight tenors](../src/RWA/models/parameter_hierarchy/readme.md#repairing-each-factor-at-every-tenor)
- [Cholesky calculation and the complete 8×8 factors](../src/RWA/models/parameter_hierarchy/readme.md#cholesky-calculation)
- [Brownian covariance and the correlated shocks](../src/RWA/models/parameter_hierarchy/readme.md#brownian-covariance-and-the-shock-transformation)
- [Every-increment update order](../src/RWA/models/parameter_hierarchy/readme.md#every-increment-calculation)

For rate (PDF X), sigma (ν) and xi (ξ), each increment recalculates a separate
8×8 level covariance, correlation, Cholesky factor and Brownian covariance using
maturities **1, 2, 3, 5, 7, 10, 20 and 30 years**. The factors transform the
three families' shocks after dependence and drift recalibration. The state
updates then proceed xi → sigma using new xi → rate using new sigma; the new
states feed the next rolling window. The linked model guide gives the full
sample-covariance formula, Cholesky recurrence and distinction between C and Q.

Tenor repair covers first-pass μ/θ/σ, all three second-pass parameter branches,
and each recursive family. Healthy maturities anchor weak speeds; the repair
reprofiles the linked coefficients within a likelihood budget. During recursion,
rate/sigma's known higher-state variances remain fixed in that fit. This parameter
repair is distinct from optional correlation conditioning and the legacy NSS
commands; it does not rewrite historical rate quotes.

## Current workflows and commands

The tables below distinguish runnable current stages from the ultimate research
objective. Work from the repository root and install `requirements.txt` in your active
Python environment. Checked-in historical CSVs may predate the current implementation;
use a new generated run and its manifest for reproducible analysis.

| Stage | Instructions |
| --- | --- |
| Source Treasury observations | [FRED inputs](FRED/README.md) |
| Rolling yield calibration | [MLE YIELD/RAW](Experimental/MLE%20YIELD/RAW/readme.md) |
| Align parameter histories across maturities | [MLE YIELD/CURVE](Experimental/MLE%20YIELD/CURVE/readme.md), including the runnable assembly recipe |
| Repair selected mu/theta nodes | [MLE YIELD/NSS](Experimental/MLE%20YIELD/NSS/readme.md), including exact triggers and diagnostics |
| Rebuild per-tenor parameter inputs | [MLE VOL/RAW](Experimental/MLE%20VOL/RAW/readme.md) |
| Retrieve and prepare current yields | [Yield data and snapshots](../src/RWA/data/yields/readme.md) |
| Run retrieval through simulation | [Live pipeline](../pipeline/rwa_live/readme.md) |
| Fit parameter histories and advance rate/sigma/xi | [Active parameter hierarchy](../src/RWA/models/parameter_hierarchy/readme.md) |
| Understand legacy experiments | [Experimental overview](Experimental/readme.md) |
| Understand the historical yield-shock approach | [Practical workflow](Practical/readme.md) |
| Check expected-loss implementation status | [Expected Loss](Practical/Expected%20Loss/readme.md) |

The implementation retains historical mu/theta/sigma estimates and all three
second-pass parameter branches, then advances a rate/sigma/xi trajectory. Its
default rolling history contains 2,520 estimate dates after both calibration
warmups, requiring at least 5,290 common source observations. Every actual
increment recalculates separate family dependence and refits all three CIR
processes before updating xi, sigma with new xi, and rate with new sigma.

Forecast years continue serially from the preceding year's history, RNG and ridge
anchors. The [model output guide](Experimental/HIERARCHY/readme.md) describes
historical tables, yearly trajectories and the exact matrices/shocks archived for
every increment. Optional ACT/365F/observed calibration uses genuine common-date
quotes and actual historical intervals. Default history uses an observation clock
and causal filling; future increments use explicit year fractions.

Portfolio valuation and a capital/RWA mapping remain downstream work. Retain
source provenance, time conventions and calibration audits with generated tables.
See the [test guide](../tests/readme.md) for computational checks; replay and
successful execution do not establish forecast superiority or economic validity.

This project utilizes **CMT data** (Constant Maturity Treasury) from **FRED** (Federal Reserve Economic Data), published daily by the **Board of Governors of the Federal Reserve System (US)** via the *H.15 Selected Interest Rates* release.

CMT series represent **yields on U.S. Treasury securities interpolated to constructed maturities** (e.g., 1, 2, 5, 10, 20, or 30 years). These are not actual bond yields, but **par rates** derived from a monotonically convex interpolation of market data.

The rates are based on indicative bid-side quotes for the most recently auctioned securities. The U.S. Treasury uses them to construct a continuous yield curve — a critical reference for:

- Interest rate analysis  
- Duration exposure  
- Interest rate risk modeling

---

## Research sequence and current status

CMT data supports the following research sequence:

1. **Implemented:** estimate yield-process mu, theta and sigma for each tenor.
2. **Implemented:** estimate second-level dynamics from all three parameter
   histories; initialize rate/sigma/xi and self-calibrate their serial evolution at
   every increment. Fitted histories contain estimation noise, so their dynamics
   are not automatically latent risk.
3. **Unfinished:** reprice securities or maturity-bucket exposures under the
   simulated rates, with cash flows and an explicit valuation convention.
4. **Unfinished:** quantify duration-related losses on government-security
   exposures and derive a justified duration-adjusted RWA measure.

The last two steps are the research objective, not outputs of the current
calibration and simulation commands. See [Expected Loss](Practical/Expected%20Loss/readme.md)
for the missing valuation contract.

---

## Data directories

| Directory                     | Contents                                                                 |
|------------------------------|--------------------------------------------------------------------------|
| `RWA/FRED/` | Historical Treasury observations for eight maturities |
| `RWA/Practical/` | Historical yield-shock and parameter-estimation scripts; proposed valuation stage |
| `RWA/Experimental/` | Rolling yield parameters, curve repairs and parameter-simulation run outputs |

---

## Data source

- **Provider:** Board of Governors of the Federal Reserve System (US)  
- **Publication:** *H.15 Selected Interest Rates*  
- **Frequency:** Daily  
- **Unit:** Percent (not seasonally adjusted)  
- **Source:** [FRED DGS30 series](https://fred.stlouisfed.org/series/DGS30)

> **Methodology:** CMT series are subject to methodological updates by the U.S. Treasury, including changes in input weights and interpolation strategy. For details, refer to the *Treasury Yield Curve Methodology* section in the H.15 documentation.
