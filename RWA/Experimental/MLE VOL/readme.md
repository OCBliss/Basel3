# Parameter-process modeling and legacy volatility files

The first yield calibration produces mu, theta and sigma histories. Applying a
second rolling calibration to those histories estimates dynamics of the
parameters themselves. For the sigma branch, the second-pass diffusion coefficient
supplies xi under the model's stated identification of the volatility state.
The [model guide](../../../src/RWA/parameter_hierarchy/readme.md) specifies the notation,
finite hierarchy, units and limitations.

## Active executable workflow

Run from `Basel3_repo` with the root requirements installed. Choose a new output
directory each time:

```bash
python3 src/RWA/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/parameter-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 256 --steps 20 --substeps 4 --noise-replicates 16
```

This reads all eight FRED maturities, fits and stabilizes first-pass yield
parameters, then fits separate mu/theta/sigma processes. It generates joint
rate/parameter scenarios and an optional constant-parameter reference for apparent
estimation-induced dynamics. It writes `parameter_dynamics.csv`, first-pass
outputs, `scenarios.npz`, `scenario_summary.csv` and a completion `manifest.json`
under the chosen new output directory. It does not overwrite this legacy folder.
Use `--noise-replicates 0` to omit that diagnostic when it is not needed for a run.

## What is in this folder

[RAW](RAW/readme.md) holds historical reconstructed per-tenor yield/parameter
files. The current reconstruction command is:

```bash
python3 src/RWA/parameter_rebuild/rebuild.py
```

That command joins repaired curves; it does not estimate second-pass parameters.
See RAW's guide for exact filenames, schemas and the mismatch with historical
`*_vol_with_parameters.csv` names.

The older [RWA_Heston_MLE_vol_test.py](../RWA_Heston_MLE_vol_test.py) shows the
sigma-only second-pass experiment, producing `theta_vol`, `mu_vol` and `vol_vol`.
It searches for a legacy `CODE` directory, expects `MLE YIELD/DGS<n>_vol.csv`,
uses file-order filling/windows, and executes at import. Those defaults do not
match the current repository layout or the rebuilt filenames. It is retained
as research history and is not the runnable entry point documented above.

## Interpretation and verification

Second-pass volatility can arise from noisy rolling estimates and repair
transitions even when the generating parameters are constant. The
[archived experiments](../../../.codex-engineering/runs/2026-09-13-capability/RESULTS.md)
measure that issue; they do not establish forecasting superiority or complete
PDF-level recursive valuation. The current hierarchy freezes second-level
coefficients over a forecast and does not recalibrate every simulated path.

```bash
python3 -B -m unittest discover -s tests -p test_rwa_hierarchy.py -v
```

See [tests](../../../tests/readme.md) for isolated temporary/cache settings and the
broader regression suite.
