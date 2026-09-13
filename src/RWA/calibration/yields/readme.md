# Rolling yield calibration

[calibrate.py](calibrate.py) estimates CIR mean reversion (`theta`), mean level
(`mu`) and diffusion (`sigma`) for eight Treasury maturity histories. It is the
first stage of the established RAW → CURVE → NSS → reconstruction workflow.
The separate [parameter hierarchy](../../models/parameter_hierarchy/readme.md) extends
calibration to the estimated parameter histories and has its own entry point.

## Run

Install the [repository requirements](../../../../requirements.txt) in your active
Python environment. Run this command from `Basel3_repo`:

```bash
python3 src/RWA/calibration/yields/calibrate.py
```

This program has no command-line settings or preview mode. Its settings are
constants in `calibrate.py`: `WINDOW_SIZE = 2520`, `DT = 1/252`, the eight
`CSV_FILES`, and `OUTPUT_DIR`. Running it creates the configured output directory
and replaces existing output files of the same names. It does not download data.

## Inputs and outputs

| Location | Contract |
| --- | --- |
| `RWA/FRED/DGS{1,2,3,5,7,10,20,30}.csv` | Each file needs `observation_date` and its named yield column, such as `DGS10`. At least 2,520 observations are required with the default window. |
| `RWA/Experimental/MLE YIELD/RAW/DGS*_with_parameters.csv` | Original input columns and row order, a one-based CSV index, and added `yield_clean`, `theta`, `mu`, `sigma` columns. |

See the [RAW output guide](../../../../RWA/Experimental/MLE%20YIELD/RAW/readme.md)
for the exported files. Keep FRED yields in their existing percentage-point
units; the program does not convert percentages into decimal rates.

## Estimation and chronology

The conditional Gaussian Euler model uses
`X_next = X + theta * (mu - X) * DT + sigma * sqrt(X * DT) * Z`.
L-BFGS-B minimizes its negative log likelihood with a positive lower bound of
`1e-6` for each parameter. Each maturity runs in its own process, up to the
available CPU count; each process defaults to one native numerical thread.

For an estimate dated `t`, the fit uses the trailing window ending at `t`, in
oldest-first order. A successful earlier fit supplies the next optimizer's
starting point. Sorting is internal, so newest-first, oldest-first and shuffled
inputs retain their original presentation order in the output. The earliest
`WINDOW_SIZE - 1` dates have missing parameters because a full window is absent.

Missing or nonnumeric yields are filled only from earlier chronological quotes.
Invalid, missing or duplicate dates, an unknown initial quote, nonfinite or
nonpositive cleaned yields, and insufficient history stop that maturity's
processing. An unsuccessful optimizer instead records three missing parameters
for that window and resets the warm start. Other maturity files can already
have been written if a worker subsequently fails; inspect the complete run.

## Continue the workflow

Assemble the date-keyed `mu_curve.csv`, `theta_curve.csv` and `sigma_curve.csv`
using the [CURVE preparation instructions](../../../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md).
Then run [cross-maturity repair](../curves/readme.md) followed by
[parameter reconstruction](../../data/parameters/readme.md). Curve assembly is
a separate preparation step, not an output automatically produced here.

Earlier versions calibrated newest-first histories in the wrong transition
direction. Regenerate dependent curves from the corrected RAW estimates before
combining their results; moving this source file does not regenerate historical
CSV files. The fixed `DT` treats successive observations as equally spaced and
does not account separately for calendar gaps. Positive optimizer bounds do not
resolve weak parameter identification or establish the risk model's validity.

## Verification

Use the repository-local temporary-file setup in the
[test guide](../../../../tests/readme.md), then run:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_calibration.py -v
```

The checks cover likelihood direction, trailing dates, input-order invariance,
unchanged past estimates when future observations are added, causal filling,
invalid inputs, warm-start recovery, and compatibility with curve repair and
reconstruction on isolated fixtures.
