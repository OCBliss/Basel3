# Historical date alignment of Treasury yields

The [legacy source](Constant_Treasury_Maturity_Cleaned2a.py) merges six FRED
Constant Maturity Treasury series into a wide date-indexed table. This produces
yield observations for research; it does not calculate security duration, losses,
or duration-adjusted RWA.

## Execution status

The script resolves `src/Basel3_Global_Filepath.py` from its enclosing repository
and uses the helper's `BASEL3_ROOT`. It executes while being imported and replaces
its fixed output, so invoke it explicitly to reproduce the historical procedure.
From the repository root, with [requirements](../../../../requirements.txt) installed:

```bash
python3 "RWA/Practical/Constant Maturity Treasury/Cleaned/Constant_Treasury_Maturity_Cleaned2a.py"
```

This legacy merge is not part of the active acquisition pipeline. For current
snapshot validation and bounded filling, use [yield acquisition](../../../../src/RWA/data/yields/readme.md);
for calibrated scenarios, use [parameter simulation](../../../../src/RWA/models/parameter_hierarchy/readme.md).

## Inputs and output

The legacy code expects `RWA/FRED/DGS<n>.csv` for maturities 1, 3, 5, 10, 20 and
30 years, each with `observation_date` and its `DGS<n>` yield column. DGS1 is
required; other missing files or files without the date key are printed and
skipped. It outer-joins the available series by date and writes:

```text
RWA/Practical/Constant Maturity Treasury/Cleaned/combined_fred_treasury_data.csv
```

The output has one date column and the available maturity columns. Dates are
parsed and sorted **descending** before missing values are filled with `bfill`.
Because rows are descending, the row below is an **older observation**. This is
not a fill from a chronologically future rate. The script performs no maturity
interpolation, unit conversion, rate-model fit or provenance validation.
Existing same-named output is replaced when the script runs.

## Interpretation and next consumer

Checked-in CSVs are historical artifacts; their presence does not establish
validation by the current acquisition workflow. The downstream [Differenced stage](../Differenced/README.md)
subtracts rows at a 252-observation offset without sorting dates, so its sign and
date interpretation must be reviewed against this descending ordering. A merged
yield table alone is not a validated input to the unfinished
[valuation stage](../readme.md).
