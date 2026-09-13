# Historical yield-shock workflow and proposed valuation

This directory holds the earlier Treasury cleaning, differencing, drift and
parameter-estimation experiments. Duration-adjusted RWA remains a research
objective. These scripts do not allocate losses to Call Report government-security
exposures, price a portfolio, or calculate a capital/RWA measure.

The intended extension is to estimate duration-related losses across Treasury
maturities and connect them to the government securities reported in Call Report
schedules RCONA549–RCONA555. That exposure and valuation integration is unfinished;
see [Expected Loss](Expected%20Loss/readme.md) for the required contract.

## Directory guide

| Historical stage | Purpose and status |
| --- | --- |
| [Cleaned](Constant%20Maturity%20Treasury/Cleaned/README.md) | Merge six FRED maturity series by date; legacy filesystem-wide root discovery |
| [Differenced](Constant%20Maturity%20Treasury/Differenced/README.md) | Compute row-offset yield changes; chronological interpretation depends on input ordering |
| [EXP_DRIFT](Constant%20Maturity%20Treasury/EXP_DRIFT/readme.md) | Average the retained changes in one selected input file |
| [EXP_COUPON](Constant%20Maturity%20Treasury/EXP_COUPON/readme.md) | Estimate CIR or AR(1) parameters; does not calculate coupon cash flows |
| [Bond valuation proposal](Constant%20Maturity%20Treasury/readme.md) | Intended pricing and return calculations; no implementation currently present |

The first three legacy scripts search the filesystem for a global path file.
The parameter experiment expects a `CODE` ancestor that does not match this
checkout. They are retained for research history and are not safe current
repository-root entry points. Their data has not been regenerated during the
source reorganization.

## Current executable interest-rate workflow

For current commands, prerequisites, inputs and outputs, use the
[yield calibration](../../src/RWA/calibration/yields/readme.md),
[curve repair](../../src/RWA/calibration/curves/readme.md) and
[parameter simulation](../../src/RWA/models/parameter_hierarchy/readme.md) guides.
These implement calibration and simulation; they do not complete the proposed
valuation and duration-adjusted RWA stages above.
