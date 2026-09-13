# Interest-rate calibration and parameter simulation

This is the executable research code for the [RWA research area](../../RWA/README.md).
It estimates yield-process parameters and models their dynamics. Exposure valuation,
duration-sensitive loss and an RWA capital calculation remain downstream objectives.

## Components

Each component has one guide alongside its implementation:

| Component | Entry point | Role |
| --- | --- | --- |
| [Yield calibration](yield_calibration/readme.md) | `yield_calibration/calibrate.py` | Rolling, causal CIR estimates from eight FRED maturity series |
| [Curve repair](curve_repair/readme.md) | `curve_repair/mu.py`, `curve_repair/theta.py` | NS/NSS repair of selected cross-maturity parameter anomalies |
| [Parameter reconstruction](parameter_rebuild/readme.md) | `parameter_rebuild/rebuild.py` | Date-aligned per-maturity exports for subsequent parameter modeling |
| [Parameter hierarchy](parameter_hierarchy/readme.md) | `parameter_hierarchy/workflow.py`, `parameter_hierarchy/core.py` | Coupled ridge stabilization, second-pass dynamics for mu/theta/sigma and joint scenarios |

The hierarchy's `workflow.py` imports its numerical implementation from `core.py`.
Its first-pass and curve exports are tested through the reconstruction consumer.
The separate legacy NS/NSS procedure remains available for reproducibility; its
independent interpolation and the hierarchy's coupled stabilization are different
methods and must be identified explicitly when comparing results.

## Run the hierarchy

From the repository root, install [requirements](../../requirements.txt) in your
active environment and inspect the configured task:

```bash
python3 -m pip install -r requirements.txt
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
```

Run directly with a new output directory:

```bash
python3 src/RWA/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 256 --steps 20 --substeps 4 --noise-replicates 16
```

See the [workflow configuration guide](../../pipeline/rwa_hierarchy/readme.md)
and [model guide](parameter_hierarchy/readme.md) for settings, contracts and limits.
The eight input series are currently read from local `RWA/FRED/DGS*.csv` files;
these commands do not retrieve new yields from an API.

## Legacy calibration and repair sequence

1. Run [yield calibration](yield_calibration/readme.md).
2. Assemble the three date-aligned parameter panels using the
   [CURVE preparation recipe](../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md).
3. Run [mu and theta curve repair](curve_repair/readme.md), then inspect its audit fields.
4. Run [parameter reconstruction](parameter_rebuild/readme.md) to produce the
   six-column inputs documented in [MLE VOL/RAW](../../RWA/Experimental/MLE%20VOL/RAW/readme.md).

Those commands write their configured historical output locations. Existing CSVs
are preserved by this source reorganization; old results are not evidence of a
fresh run. Rebuild dependent outputs consistently from the same inputs and settings.

## Verification and research status

```bash
python3 -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

Tests exercise chronology, causal cleaning, calibration recovery, whole-row repair
rejection, all eight maturity file contracts, direct/package invocation and the
actual YAML manager on isolated fixtures. The [research evidence](../../.codex-engineering/runs/2026-09-13-capability/RESULTS.md)
records statistical findings and limitations. The finite hierarchy currently
freezes second-level coefficients at the forecast origin; simulated-path recursive
recalibration and exposure-level valuation are unfinished.
