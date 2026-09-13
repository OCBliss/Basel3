# Rolling yield calibration and cross-maturity preparation

This workflow calibrates a CIR yield process separately for the eight Treasury
maturities, organizes the fitted parameter histories by date, and repairs selected
mu/theta anomalies before preparing second-pass inputs.

Run commands from `Basel3_repo` with the root requirements installed. These legacy
commands write their configured output locations and can replace existing CSVs.

| Order | Stage | How to run and inspect it |
| --- | --- | --- |
| 1 | [RAW](RAW/readme.md) | `python3 src/RWA/quasi-MLE-Euler.py` fits trailing yield windows |
| 2 | [CURVE](CURVE/readme.md) | Run the documented Python assembly recipe to align mu/theta/sigma across maturities |
| 3 | [NSS](NSS/readme.md) | Run the mu and quoted theta repair commands, then inspect row/node audits |
| 4 | [MLE VOL/RAW](../MLE%20VOL/RAW/readme.md) | `python3 src/RWA/CMT_data_parameters_rebuild.py` reconstructs per-tenor histories |

The first-pass model is `dX = theta*(mu-X)*dt + sigma*sqrt(X)*dW`.
The current calibration uses 2,520 observations per trailing window and
`dt = 1/252`; it attaches each fit to the last date in that window. It preserves
input row order, leaves unavailable warmup estimates missing, and uses only
historically available observations for filling and optimizer warm starts.

The tracked CSVs in these directories are historical research outputs. Current
code fixes do not rewrite them automatically; regenerate a complete consistent
chain before treating old and new outputs as comparable. The NS/NSS stage only
repairs its configured finite-value threshold violations, not every identification
problem, and reconstruction does not propagate the repair audit columns.

For jointly simulated mu/theta/sigma dynamics and an estimation-noise diagnostic,
use the separate [endogenous hierarchy](../../../src/RWA/parameter_hierarchy.md).
It generates its own RAW/CURVE exports in a new chosen output folder. The default
Call Report/JSD pipeline does not run either RWA workflow automatically.
