# Date-aligned CIR parameter curves

This folder contains the wide maturity panels used by the legacy NS/NSS repair
and parameter reconstruction stages. It rearranges existing rolling estimates;
assembly itself does not fit a curve, interpolate dates or repair a ridge.

## File contracts

| File | Required columns after `observation_date` | Consumer |
| --- | --- | --- |
| `mu_curve.csv` | `mu1y, mu2y, mu3y, mu5y, mu7y, mu10y, mu20y, mu30y` | [mu repair](../../../../src/RWA/mu_curve_nss_repair.py) |
| `theta_curve.csv` | `theta1y, theta2y, theta3y, theta5y, theta7y, theta10y, theta20y, theta30y` | [theta repair](../../../../src/RWA/theta_curve_nss_repair%2A.py) |
| `sigma_curve.csv` | `sigma1y, sigma2y, sigma3y, sigma5y, sigma7y, sigma10y, sigma20y, sigma30y` | [parameter rebuild](../../../../src/RWA/CMT_data_parameters_rebuild.py) |

Each date must occur at most once in each table. Align maturities by date, never
by CSV row position: the stored DGS files can have different date coverage and
ordering. Keep unavailable estimates as missing. In particular, do not backfill
the early rolling-window warmup with estimates learned later.

`mu` retains the yield units of the first pass; the FRED inputs are in percent.
`theta` is the mean-reversion coefficient with time measured in years by
`DT = 1/252`. `sigma` is the CIR square-root diffusion coefficient, not the
standard deviation of yields. Assembly performs no unit conversion.

## Prepare curves from first-pass RAW files

First run [rolling calibration](../RAW/readme.md) if you need fresh estimates.
Install the root requirements and run the following from `Basel3_repo`. The
recipe reads the eight `RAW/DGS<n>_with_parameters.csv` files, checks required
columns and unique dates, and **replaces these three curve CSVs**. Use source
files from one consistent calibration run. Historical checked-in CSVs are not
silently regenerated when the Python implementation changes.

```bash
python3 - <<'PYCODE'
from pathlib import Path
import pandas as pd

root = Path.cwd()
source = root / "RWA/Experimental/MLE YIELD/RAW"
destination = root / "RWA/Experimental/MLE YIELD/CURVE"
tenors = (1, 2, 3, 5, 7, 10, 20, 30)
parameters = ("mu", "theta", "sigma")
series = {parameter: [] for parameter in parameters}

for tenor in tenors:
    path = source / f"DGS{tenor}_with_parameters.csv"
    frame = pd.read_csv(path, usecols=["observation_date", *parameters])
    dates = pd.to_datetime(frame["observation_date"], errors="raise")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError(f"Missing or duplicate dates: {path}")
    frame.index = pd.DatetimeIndex(dates, name="observation_date")
    for parameter in parameters:
        values = pd.to_numeric(frame[parameter], errors="raise")
        series[parameter].append(values.rename(f"{parameter}{tenor}y"))

# Validate/read all eight files before writing any curve. Outer alignment keeps
# every source date and leaves missing maturity/date combinations unavailable.
curves = {
    parameter: pd.concat(columns, axis=1, join="outer").sort_index()
    for parameter, columns in series.items()
}
destination.mkdir(parents=True, exist_ok=True)
for parameter, curve in curves.items():
    path = destination / f"{parameter}_curve.csv"
    curve.to_csv(path, index=True, date_format="%Y-%m-%d")
    print(f"Wrote {path}: {len(curve)} dates, {len(curve.columns)} maturities")
PYCODE
```

The recipe intentionally ignores the unnamed, one-based CSV row-index column in
legacy RAW exports. It preserves missing values and sorts output dates ascending.
It does not infer a shared calibration provenance from filenames or remove
unreliable estimates; review the run settings and subsequent repair diagnostics.

The [new parameter hierarchy](../../../../src/RWA/parameter_hierarchy.md) also
exports `CURVE/` inside its own selected output directory. Those panels come
from its coupled stabilization. Do not mix them into an older NS/NSS run without
explicitly choosing that methodology and a consistent set of RAW inputs.

## Run the consumers

```bash
python3 src/RWA/mu_curve_nss_repair.py
python3 'src/RWA/theta_curve_nss_repair*.py'
```

Read the [NSS guide](../NSS/readme.md) and review its audits before continuing:

```bash
python3 src/RWA/CMT_data_parameters_rebuild.py
```

The rebuild takes mu/theta from `../NSS/` and sigma from this directory. It joins
by date, preserves each RAW yield file's row order, and reports missing matches.
See [MLE VOL/RAW](../../MLE%20VOL/RAW/readme.md) for the resulting file contract.
