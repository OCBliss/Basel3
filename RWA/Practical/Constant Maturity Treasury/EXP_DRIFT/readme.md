# Historical average of retained Treasury yield changes

The [legacy source](Constant_Maturity_Treasury_exp_drift_v3.py) computes a column
mean from a selected differenced file. When the upstream threshold is zero, this
is the average of retained positive row differences, not an unconditional yield
drift, simulated rate path or duration-adjusted RWA calculation.

## Execution status

The entry point resolves `src/Basel3_Global_Filepath.py` from its enclosing
repository and uses the helper's `BASEL3_ROOT`. To reproduce the historical
summary, run from the repository root with [requirements](../../../../requirements.txt)
installed and a differenced input available:

```bash
python3 "RWA/Practical/Constant Maturity Treasury/EXP_DRIFT/Constant_Maturity_Treasury_exp_drift_v3.py"
```

This replaces the fixed summary output. It is not integrated into the active
interest-rate pipeline. Current calibration and simulation commands are in
[the source guide](../../../../src/RWA/readme.md).

## Inputs, selection and output

The script lists `differenced_*.csv` under
`RWA/Practical/Constant Maturity Treasury/Differenced/` and selects the **first**
match in filesystem listing order. It does not process every match or sort them.
No matches raise an error. The selected file must contain all six columns:

```text
DGS1,DGS3,DGS5,DGS10,DGS20,DGS30
```

All six columns are converted to numeric with invalid values made missing. The
script calculates each mean with missing values excluded, rounds to ten decimal
places and writes one row to `expected_drift_summary.csv` in this directory.
The output schema is `file,DGS1,DGS3,DGS5,DGS10,DGS20,DGS30`; the `file` field
records the selected input name. Existing same-named output is replaced.

## Interpretation and future use

The [Differenced guide](../Differenced/README.md) explains that the subtraction
is based on row position and inherits descending ordering from the old cleaning
stage. Consequently the retained positive values must not automatically be
interpreted as chronological yield increases. Missing/filtered changes are not
included in the mean, so this result is conditional on that selection.

Using these summaries for stress scenarios, portfolio repricing or capital
assessment is a proposed extension requiring a validated chronological contract
and a valuation implementation. None is performed by this averaging script.
For a historical CSV, confirm its input file, date ordering and retained-change
selection before interpreting the reported mean.
See [the valuation proposal](../readme.md) and [Expected Loss status](../../Expected%20Loss/readme.md).
