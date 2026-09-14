# Experimental interest-rate workflows

The current code supports both the legacy sequence of separately stored calibration
and NS/NSS repair files and the recursive rate/sigma/xi model. This directory also
contains historical scripts and CSVs. Use the explicit entry points below; do not
assume every old experiment is executable against the present folder layout.

## Legacy yield and repair sequence

Run from the repository root with the root requirements installed. The complete sequence
and file contracts are documented in [MLE YIELD](MLE%20YIELD/readme.md):

| Order | Command or preparation | Output guide |
| --- | --- | --- |
| 1 | `python3 src/RWA/calibration/yields/calibrate.py` | [First-pass RAW](MLE%20YIELD/RAW/readme.md) |
| 2 | Run the Python assembly recipe | [Date-aligned CURVE panels](MLE%20YIELD/CURVE/readme.md) |
| 3 | `python3 src/RWA/calibration/curves/mu.py` and `python3 src/RWA/calibration/curves/theta.py` | [NSS repairs and audits](MLE%20YIELD/NSS/readme.md) |
| 4 | `python3 src/RWA/data/parameters/rebuild.py` | [Reconstructed MLE VOL/RAW](MLE%20VOL/RAW/readme.md) |

The first pass uses 2,520 observations, `dt = 1/252`, and chronological trailing
windows across eight maturities. The repair stage uses finite-value threshold
rules and NS/NSS cross-maturity fits. Inspect failed rows and positivity checks
before rebuilding. The commands can replace their configured output CSVs;
historical checked-in files are not automatically refreshed by code changes.

## Active recursive model

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

Choose a new output directory each time. Both historical estimation passes and
coupled ridge treatment run internally, retaining every mu/theta/sigma branch.
Initialization requires at least 5,290 common source observations at the defaults
to retain 2,520 aligned estimate dates after warmup. The historical state families
are rates, first-pass sigma and the sigma branch's fitted diffusion, xi.

Every actual increment, including the first and every numerical substep,
recomputes three separate cross-maturity dependence structures and refits all
three state families. It updates xi, then sigma with new xi, then rates with new
sigma. Subsequent years continue the same history and random stream.

Outputs include historical RAW/CURVE exports plus serial-year trajectories,
per-increment covariance/shock archives and completion manifests. See the
[output guide](HIERARCHY/readme.md), [model guide](../../src/RWA/models/parameter_hierarchy/readme.md)
and [execution map](../../src/RWA/readme.md#execution-order).
The [existing-input pipeline](../../pipeline/rwa_hierarchy/readme.md) invokes the
same entry point; the [live pipeline](../../pipeline/rwa_live/readme.md) acquires
and verifies its inputs first. The Call Report/JSD pipeline remains separate.

Optional `--time-basis act365f --missing-policy observed` uses genuine common-date
quotes and actual historical gaps. Default historical settings retain the fixed
observation clock and causal filling. Forecast time is an explicit year fraction;
windows count estimates/observations. Preserve manifests and historical intervals
with extracted parameter tables.

## Historical experiment status

`RWA_Heston_MLE_vol_test.py` contains the earlier sigma-only second pass but has
legacy input-filename and window/filling assumptions and runs at import. Its
path helper resolves from this repository's `src/` directory; that does not
resolve the input and modeling limitations.
The [MLE VOL guide](MLE%20VOL/readme.md) explains its relationship to current code.
The runnable source lives in [src/RWA](../../src/RWA/readme.md).

The recursive model follows the PDF's ordered dependence-to-volatility-to-rate
updates using the CIR/initialization conventions in the model guide. It does not
provide exposure-level valuation or a capital/RWA calculation. Repeated
estimation and regularization can themselves create apparent volatility; a
completed trajectory does not establish an additional economic risk factor.
