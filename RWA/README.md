# Interest-rate calibration, parameter simulation and the RWA research goal

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
| Fit and simulate mu/theta/sigma dynamics | [Active parameter hierarchy](../src/RWA/models/parameter_hierarchy/readme.md) |
| Understand legacy experiments | [Experimental overview](Experimental/readme.md) |
| Understand the historical yield-shock approach | [Practical workflow](Practical/readme.md) |
| Check expected-loss implementation status | [Expected Loss](Practical/Expected%20Loss/readme.md) |

The current implementation calibrates interest-rate processes and simulates their
parameter dynamics, including pathwise recursive recalibration of parameter
processes and joint dependence. Portfolio valuation and a final capital/RWA
mapping are downstream stages. Optional ACT/365F calibration uses genuine
common-date Treasury observations and their actual historical year fractions
through both estimation passes, dependence, noise controls and recursive buffers.
Defaults retain the observation clock and forward-fill for reproducibility.
Window sizes count observations; the future forecast step remains a scalar
year fraction. The [model output guide](Experimental/HIERARCHY/readme.md) explains
the generated manifest, historical interval table, parameter audits and scenario
outputs. Retain these together: a parameter CSV alone does not identify its input
snapshot, calibration clock, missingness policy or simulation settings. See the
[test guide](../tests/readme.md) for portable implementation checks; successful
execution does not establish forecast superiority or economic validity.

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
   histories and simulate their joint evolution with rates. The fitted histories
   contain estimation noise, so their dynamics are not automatically latent risk.
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
