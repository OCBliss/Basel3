# Historical CIR and AR(1) parameter-estimation experiment

Despite the `EXP_COUPON` directory name, the
[legacy source](autoregressive_fitting_v3a.py) estimates rate-process parameters.
It does not calculate coupon cash flows, expected bond returns, portfolio losses
or duration-adjusted RWA.

## Execution status and current alternative

The file looks for a `CODE` ancestor and loads `Basel3_Global_Filepath.py` from
it before defining its workflow. This does not match the current repository
layout. It also imports `statsmodels`, which is not part of the root requirements.
These are historical defaults, not a working setup command for a fresh clone.
The active [yield calibration](../../../../src/RWA/yield_calibration/readme.md)
and [parameter simulation](../../../../src/RWA/parameter_hierarchy/readme.md)
guides provide current commands, prerequisites and independently tested behavior.

## Legacy inputs and fitting

The experiment targets DGS1, DGS3, DGS5, DGS10, DGS20 and DGS30. For each name it
selects the most recently modified matching CSV in `RWA/FRED/`, sorts observations
ascending, drops missing rates and divides percent yields by 100. A prefix match
is used for filenames, so historical input selection also needs review.

Its CIR branch uses a Gaussian Euler approximation to:

```text
dr = theta * (mu - r) * dt + sigma * sqrt(r) * dW
```

Here `dt = 1/252`; bounded `scipy.optimize.minimize` estimates theta, mu and sigma
with lower bounds of 0.001. The optional AR(1) branch uses a fitted lag-one
coefficient and residual dispersion. AR(1) is selected explicitly with
`model_type="AR1"`; it is not an automatic fallback after a failed CIR fit.
The worker pool is limited to the smaller of series count and available CPUs.
Series failures are printed and leave blank result columns.

## Output and interpretation

The legacy output is `CIR_parameters_summary.csv` in this folder. It has a
`Parameters` index with rows `Mean Reversion Speed`, `Long-Term Mean` and
`Volatility`, plus the six series columns. Values are rounded to four decimal
places. Same-named output is replaced by a run. The checked-in CSV is a historical
artifact; this documentation update does not establish that it was regenerated
or validated against current source.

A fitted CIR sigma is a square-root diffusion coefficient, not a coupon estimate.
The AR(1) residual standard deviation and CIR coefficient have different meanings.
The current yield-calibration workflow retains FRED percent units, whereas this
legacy experiment converts rates to decimal units; their fitted parameters must
not be interchanged without an explicit consistent model/unit conversion.

Using fitted dynamics for coupon forecasting, scenario valuation or a capital
mapping remains downstream work. See [the valuation proposal](../readme.md) and
[Expected Loss status](../../Expected%20Loss/readme.md) for that unfinished goal.
