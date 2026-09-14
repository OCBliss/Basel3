# Historical row-offset Treasury yield changes

The [legacy source](Constant_Maturity_Treasury_Differenced5a.py) subtracts yield
observations separated by a fixed number of rows and retains changes above a
threshold. It does not simulate future yields, compute portfolio losses or
produce duration-adjusted RWA.

## Execution status

The script resolves `src/Basel3_Global_Filepath.py` from its enclosing repository
and uses the helper's `BASEL3_ROOT`. It executes at import and replaces existing
outputs. To reproduce the retained row-offset calculation, run explicitly from
the repository root with [requirements](../../../../requirements.txt) installed:

```bash
python3 "RWA/Practical/Constant Maturity Treasury/Differenced/Constant_Maturity_Treasury_Differenced5a.py"
```

The numerical behavior below describes a historical experiment, not a validated
forecasting method or an active pipeline stage. For active calibration and
simulation commands, use [the source guide](../../../../src/RWA/readme.md).

## Input and output contract

The code reads every CSV in `RWA/Practical/Constant Maturity Treasury/Cleaned/`.
It expects `observation_date` first and numeric maturity columns after it. Inputs
with fewer than two columns or no more than `offset` rows are printed and skipped.
It writes `differenced_<original_file>.csv` into this directory, replacing any
same-named file. Output dates are the input dates starting at row `offset`.

## Exact transformation and chronology

Settings in `process_cleaned_files` default to `offset=252` and `threshold=0.0`.
For each maturity and input row `i >= offset`, the calculation is:

```text
change[i] = input_rate[i] - input_rate[i - offset]
```

Only values strictly greater than the threshold are written; all others become
blank cells. The code does not sort or verify dates. On ascending input, the
subtraction compares a rate with an older observation. The legacy
[Cleaned stage](../Cleaned/README.md) instead emits descending dates, so row `i`
is older than row `i - offset`: the saved value is older minus newer, labelled
with the older date. Calling this an ordinary year-ahead yield increase would
misstate the implementation. Also, 252 rows need not span one calendar year.

The filtering produces a selected subset of changes, not the complete shock
distribution. It cannot by itself support an unconditional expected change or
tail-loss calculation. The next [EXP_DRIFT stage](../EXP_DRIFT/readme.md) averages
the retained values; review this ordering and selection before interpreting
those averages. Checked-in CSVs are historical outputs of this row-offset
calculation; they are not validated future scenarios.
