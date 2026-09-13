# Experimental interest-rate workflows

The current code supports both the legacy sequence of separately stored calibration
and NS/NSS repair files and a new finite parameter hierarchy. This directory also
contains historical scripts and CSVs. Use the explicit entry points below; do not
assume every old experiment is executable against the present folder layout.

## Legacy yield and repair sequence

Run from `Basel3_repo` with the root requirements installed. The complete sequence
and file contracts are documented in [MLE YIELD](MLE%20YIELD/readme.md):

| Order | Command or preparation | Output guide |
| --- | --- | --- |
| 1 | `python3 src/RWA/yield_calibration/calibrate.py` | [First-pass RAW](MLE%20YIELD/RAW/readme.md) |
| 2 | Run the Python assembly recipe | [Date-aligned CURVE panels](MLE%20YIELD/CURVE/readme.md) |
| 3 | `python3 src/RWA/curve_repair/mu.py` and `python3 src/RWA/curve_repair/theta.py` | [NSS repairs and audits](MLE%20YIELD/NSS/readme.md) |
| 4 | `python3 src/RWA/parameter_rebuild/rebuild.py` | [Reconstructed MLE VOL/RAW](MLE%20VOL/RAW/readme.md) |

The first pass uses 2,520 observations, `dt = 1/252`, and chronological trailing
windows across eight maturities. The repair stage uses finite-value threshold
rules and NS/NSS cross-maturity fits. Inspect failed rows and positivity checks
before rebuilding. The commands can replace their configured output CSVs;
historical checked-in files are not automatically refreshed by code changes.

## Active endogenous parameter hierarchy

```bash
python3 src/RWA/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 256 --steps 20 --substeps 4 --noise-replicates 16
```

Choose a new output directory each time. This workflow applies coupled ridge
stabilization to yield fits and models the histories of **mu, theta and sigma**.
It produces joint rate/parameter scenarios, RAW/CURVE exports and a completion
manifest; the optional benchmark evaluates estimation-induced parameter dynamics.
It uses its own consistent FRED-to-scenarios run and does not read old NSS outputs
automatically. See [the model and CLI guide](../../src/RWA/parameter_hierarchy/readme.md)
and [the real-data/synthetic results](../../.codex-engineering/runs/2026-09-13-capability/RESULTS.md).

The separate [pipeline configuration](../../pipeline/rwa_hierarchy/config.yaml)
points to the same `parameter_hierarchy/workflow.py` entry point. Set its
`output_dir` to a new repository-local run directory before execution. Its
default `noise_replicates` is zero; the explicit CLI example above enables that
diagnostic with 16 replicates. The main Call Report/JSD configuration does not
run this workflow automatically.

## Historical experiment status

`RWA_Heston_MLE_vol_test.py` contains the earlier sigma-only second pass but has
legacy path, input-filename and window/filling assumptions and runs at import.
The [MLE VOL guide](MLE%20VOL/readme.md) explains its relationship to current code.
The runnable source lives in [src/RWA](../../src/RWA/readme.md).

The finite hierarchy is a baseline toward the recursive-model PDF. It does not
yet provide pathwise recalibration or an exposure-level RWA valuation. Repeated
estimation and regularization can themselves create apparent parameter volatility;
read the evidence before interpreting it as an additional economic risk factor.
