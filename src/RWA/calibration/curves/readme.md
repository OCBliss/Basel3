# Cross-maturity NS/NSS repair

[mu.py](mu.py) and [theta.py](theta.py) repair selected anomalous CIR parameter
nodes by fitting the other available maturities on the same observation date.
Both scripts live here because they implement the same repair stage, with
different parameter columns and anomaly thresholds.

## Prepare and run

Install the [repository requirements](../../../../requirements.txt), including
NumPy, pandas and SciPy. First complete [yield calibration](../yields/readme.md)
and the [CURVE assembly recipe](../../../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md).
From `Basel3_repo`, run:

```bash
python3 src/RWA/calibration/curves/mu.py
python3 src/RWA/calibration/curves/theta.py
```

These scripts have no command-line settings or preview mode. `INPUT_FILE`,
`OUTPUT_FILE`, `EXPLOSION_ABS_THRESHOLD` and `MAX_WORKERS` are source constants.
Both commands replace their configured repaired CSV files. Normal rows are
processed locally; anomalous rows use spawned worker processes, up to the lesser
of 28, the available CPU count and the number of anomalous dates.

## File contracts

All paths below are relative to `RWA/Experimental/MLE YIELD/`.

| Script | Input | Output | Finite values selected for repair |
| --- | --- | --- | --- |
| `mu.py` | `CURVE/mu_curve.csv` | `NSS/mu_curve_nss_repaired.csv` | `abs(mu) > 9` |
| `theta.py` | `CURVE/theta_curve.csv` | `NSS/theta_curve_nss_repaired.csv` | `abs(theta) < 0.01` |

Each table requires `observation_date` and all eight parameter columns for
1, 2, 3, 5, 7, 10, 20 and 30 years: `mu1y` through `mu30y`, or `theta1y` through
`theta30y`. Dates and input row order are preserved. Prepare unique, valid date
keys upstream; the repair readers retain dates as text and do not independently
validate date uniqueness. Parameter values are converted to numeric values.

Threshold comparisons are strict: exactly `abs(mu) == 9` or
`abs(theta) == 0.01` is not selected. Missing, nonnumeric and infinite values are
excluded from fitting and are not reconstruction targets. Consequently this is
a threshold-based repair, not a general validation of every original node.

## How a row is repaired

1. Identify anomalous nodes across all eight maturities; exclude them and
   nonfinite values from the fit.
2. Use six-parameter Nelson–Siegel–Svensson (NSS) with at least six remaining
   nodes, or four-parameter Nelson–Siegel (NS) with four or five. Fewer than four
   remaining nodes produces a recorded failure. An NSS optimization failure is
   not automatically retried with NS.
3. Fit bounded, multiple-start least squares with `soft_l1` loss. Choose the
   successful start with the smallest ordinary squared residual sum and report
   its RMSE on the retained nodes.
4. Evaluate only the anomalous maturities. Require every proposed replacement
   to be finite and strictly positive before changing any node in that row.
   Preserve all original parameter values if any candidate fails this check.

The fit may interpolate or extrapolate depending on where the remaining nodes
lie. A low residual on retained maturities does not guarantee a reliable missing
or anomalous maturity. These scripts repair mu and theta separately; they do not
jointly constrain the original CIR drift product `theta * mu`. The
[parameter hierarchy](../../models/parameter_hierarchy/readme.md) uses a separate coupled
stabilization method and should not be silently mixed with these outputs.

## Audit and failures

The output retains the input columns and adds these fields:

| Fields | Meaning |
| --- | --- |
| `anomaly_count`, `anomalous_maturities` | Number and names of selected nodes. |
| `curve_repair_performed`, `curve_fit_success` | True only when the complete candidate repair is accepted; both are false for unchanged normal rows and failed repairs. |
| `curve_fit_error` | Failure reason; empty for accepted repairs and rows with no anomaly. |
| `curve_model`, `curve_fit_rmse` | Accepted model (`NS` or `NSS`) and fit error on retained nodes. |
| `<column>_original`, `<column>_repaired` | Original numeric value and replacement flag for every tenor column. |

Missing required columns fail file processing. Row-level identification,
optimization and positive-domain failures produce warnings and audit records;
the file can still be saved and the command can exit successfully. Inspect
`anomaly_count > 0` together with `curve_fit_success`, not just the process exit
code. Empty input tables are unsupported. Rejection retains potentially unstable
original estimates and is not evidence that those estimates are acceptable.

After reviewing both repaired tables, run
[parameter reconstruction](../../data/parameters/readme.md). Retain the repaired
tables with their audit fields: reconstruction exports only market data and the
three parameter columns. The [NSS output guide](../../../../RWA/Experimental/MLE%20YIELD/NSS/readme.md)
also provides an audit inspection command.

## Verification

Use the repository-local temporary-file setup in the
[test guide](../../../../tests/readme.md), then run:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_calibration.py -v
```

The fixture checks exercise all eight maturities through both repair readers and
the rebuild consumer, including nonpositive candidate rejection, preservation
of an entire row when any replacement is invalid, and short-tenor theta
extrapolation. They do not establish that independent parameter smoothing
identifies latent economic dynamics.
