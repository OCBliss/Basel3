# Parameter-process modeling and legacy volatility files

The first yield calibration produces mu, theta and sigma histories. Applying a
second rolling calibration to those histories estimates dynamics of the
parameters themselves. For the sigma branch, the second-pass diffusion coefficient
initializes the historical xi state. During forecasts, xi evolves under its own
recalibrated CIR process; it is not reset to each new fitted diffusion estimate.
The [model guide](../../../src/RWA/models/parameter_hierarchy/readme.md) specifies the notation,
three-state update, units and limitations.

## Active executable workflow

Run from the repository root with the root requirements installed. Choose a new output
directory each time:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/parameter-run \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

This fits historical yields and every mu/theta/sigma branch across eight
maturities. The default initialization needs at least 5,290 common source rows
to retain 2,520 aligned rate/sigma/xi history dates after both warmups. It then
advances one serial trajectory, refreshing dependence and coefficients at every
actual increment in the order xi → sigma using new xi → rate using new sigma.

Historical calibration tables and RAW/CURVE exports accompany yearly trajectories,
per-increment covariance/shock archives and completion manifests. No independent
ensemble paths or ensemble-quantile summaries are generated. The chosen new output
directory preserves this legacy folder. See the [output guide](../HIERARCHY/readme.md).

## What is in this folder

[RAW](RAW/readme.md) holds historical reconstructed per-tenor yield/parameter
files. The current reconstruction command is:

```bash
python3 src/RWA/data/parameters/rebuild.py
```

That command joins repaired curves; it does not estimate second-pass parameters.
See RAW's guide for exact filenames, schemas and the mismatch with historical
`*_vol_with_parameters.csv` names.

The older [RWA_Heston_MLE_vol_test.py](../RWA_Heston_MLE_vol_test.py) shows the
sigma-only second-pass experiment, producing `theta_vol`, `mu_vol` and `vol_vol`.
Its path helper resolves to this repository's `src/Basel3_Global_Filepath.py`.
It still expects `MLE YIELD/DGS<n>_vol.csv`, uses file-order filling/windows,
and executes at import. Its input names do not match the rebuilt filenames. It is retained
as research history and is not the runnable entry point documented above.

## Interpretation and verification

Second-pass volatility can arise from noisy rolling estimates and repair
transitions even when underlying parameters are constant. Recalibration does not
separate that estimation noise from latent risk. Optional ACT/365F/observed mode
uses genuine common-date quotes and historical year fractions in both passes and
recursive buffers. This does not establish economic identification or forecasting
superiority.

Read the [model guide](../../../src/RWA/models/parameter_hierarchy/readme.md) for
the distinction between fitted diffusion coefficients and evolved volatility
states. Retain the [generated covariance and calibration records](../HIERARCHY/readme.md)
when examining the ordered recursion. Use the [test guide](../../../tests/readme.md)
for deterministic, covariance, replay and integration checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```
