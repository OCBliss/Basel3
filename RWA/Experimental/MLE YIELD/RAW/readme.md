# First-pass CIR yield parameter histories

This directory contains one rolling-calibration file per Treasury maturity:
`DGS{1,2,3,5,7,10,20,30}_with_parameters.csv`.

## Generate

From `Basel3_repo`, after installing the root requirements:

```bash
python3 -m pip install -r requirements.txt
python3 src/RWA/calibration/yields/calibrate.py
```

The [source](../../../../src/RWA/calibration/yields/calibrate.py) reads the corresponding
`RWA/FRED/DGS<n>.csv` files with `observation_date` and `DGS<n>` columns. The
script creates this directory and replaces each maturity's output. Settings are
source constants (`WINDOW_SIZE = 2520`, `DT = 1/252`); it has no CLI overrides.
Up to eight maturity processes run concurrently. An incomplete multi-file run
must not be treated as a consistent complete calibration.

## Output columns

| Column | Meaning |
| --- | --- |
| unnamed first column | Preserved one-based CSV row label; not the date key |
| `observation_date`, `DGS<n>` | Original date and quoted yield |
| `yield_clean` | Numeric yield, filled only from an earlier dated observation |
| `theta` | Fitted mean-reversion speed |
| `mu` | Fitted mean yield level |
| `sigma` | Fitted square-root diffusion coefficient |

Other original input columns are retained. Dates are sorted internally for
estimation, then outputs return to the original input order. For a fit dated t,
the 2,520-observation window ends at t. The earliest 2,519 dates have no fit;
a failed optimizer fit also leaves missing parameters and resets the next warm
start. Duplicate/invalid dates, nonpositive cleaned yields and missing leading
yields are rejected. Input percent units are retained.

The likelihood is the Gaussian Euler approximation to
`dX = theta*(mu-X)*dt + sigma*sqrt(X)*dW`, with conditional variance
`sigma**2 * X * dt`. Consecutive observations use the same time step; calendar
holidays and gaps do not create variable time steps in this implementation.

## Next stages and historical data

Use the [CURVE assembly recipe](../CURVE/readme.md) to form date-keyed maturity
panels, then [repair mu/theta](../NSS/readme.md) and reconstruct
[second-pass input files](../../MLE%20VOL/RAW/readme.md).

The existing tracked CSVs predate the chronological calibration repair. Their
presence does not mean the current implementation generated or validated them.
For isolated checks, use the [test guide](../../../../tests/readme.md) and
`test_rwa_calibration.py`; do not run a full historical overwrite merely to check
that a command is documented.
