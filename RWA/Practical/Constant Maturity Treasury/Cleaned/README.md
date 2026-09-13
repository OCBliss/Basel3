# Historical date alignment of Treasury yields

The [legacy source](Constant_Treasury_Maturity_Cleaned2a.py) merges six FRED
Constant Maturity Treasury series into a wide date-indexed table. This produces
yield observations for research; it does not calculate security duration, losses,
or duration-adjusted RWA.

## Execution status

The script searches the entire filesystem for `Basel3_Global_Filepath.py`, imports
it, and uses its `ROOT_DIR`. It executes while being imported. These defaults do
not satisfy the current repository-only path boundary, so it is retained as a
historical experiment, not an active entry point. For current data handling and
calibration commands, use [yield calibration](../../../../src/RWA/yield_calibration/readme.md)
or [parameter simulation](../../../../src/RWA/parameter_hierarchy/readme.md).
Do not import the legacy file merely to inspect it.

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

Checked-in CSVs are historical artifacts; this documentation update did not
regenerate them. The downstream [Differenced stage](../Differenced/README.md)
subtracts rows at a 252-observation offset without sorting dates, so its sign and
date interpretation must be reviewed against this descending ordering. A merged
yield table alone is not a validated input to the unfinished
[valuation stage](../readme.md).
