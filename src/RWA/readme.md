# Interest-rate calibration and parameter simulation

This is the executable research code for the [RWA research area](../../RWA/README.md).
It estimates yield-process parameters and models their dynamics. Exposure valuation,
duration-sensitive loss and an RWA capital calculation remain downstream objectives.

## Domain organization

The top level has three stable domains. New work belongs to its domain; folders
are not created just because a task or scheduled run was completed. Each directory
has one README, and implementation details are documented with their component.

| Domain | Responsibility |
| --- | --- |
| [Data](data/readme.md) | Yield acquisition/preparation and reconstruction of parameter tables |
| [Calibration](calibration/readme.md) | Standalone yield estimation and cross-maturity curve repair |
| [Models](models/readme.md) | Coupled parameter dynamics and stochastic simulation |

The existing analytical components sit within those domains:

| Component | Entry point | Role |
| --- | --- | --- |
| [Yield data](data/yields/readme.md) | `data/yields/acquire.py` | Download, preserve and validate a fresh eight-maturity FRED snapshot |
| [Yield calibration](calibration/yields/readme.md) | `calibration/yields/calibrate.py` | Rolling, causal CIR estimates from eight FRED maturity series |
| [Curve repair](calibration/curves/readme.md) | `calibration/curves/mu.py`, `calibration/curves/theta.py` | NS/NSS repair of selected cross-maturity parameter anomalies |
| [Parameter reconstruction](data/parameters/readme.md) | `data/parameters/rebuild.py` | Date-aligned per-maturity exports for subsequent parameter modeling |
| [Parameter hierarchy](models/parameter_hierarchy/readme.md) | `models/parameter_hierarchy/workflow.py`, `models/parameter_hierarchy/core.py` | Coupled ridge stabilization, second-pass dynamics for mu/theta/sigma and joint scenarios |

The hierarchy's `workflow.py` imports its numerical implementation from `core.py`.
Its first-pass and curve exports are tested through the reconstruction consumer.
The separate legacy NS/NSS procedure remains available for reproducibility; its
independent interpolation and the hierarchy's coupled stabilization are different
methods and must be identified explicitly when comparing results.

## Run retrieval, calibration and simulation together

The [live pipeline](../../pipeline/rwa_live/readme.md) downloads fresh FRED yields,
validates and records cleaning, verifies snapshot provenance, then runs the model.
Choose new snapshot/output directories in its configuration before each run:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

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
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 256 --steps 20 --substeps 4 --noise-replicates 16
```

See the [workflow configuration guide](../../pipeline/rwa_hierarchy/readme.md)
and [model guide](models/parameter_hierarchy/readme.md) for settings, contracts and limits.
These standalone model commands read the existing local `RWA/FRED/DGS*.csv` files.
Use the live pipeline above for acquisition and verified snapshot input.

## Legacy calibration and repair sequence

1. Run [yield calibration](calibration/yields/readme.md).
2. Assemble the three date-aligned parameter panels using the
   [CURVE preparation recipe](../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md).
3. Run [mu and theta curve repair](calibration/curves/readme.md), then inspect its audit fields.
4. Run [parameter reconstruction](data/parameters/readme.md) to produce the
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
records statistical findings and limitations. The model supports both frozen and
pathwise recursive parameter/dependence calibration. The YAML workflows select
recursive mode; exposure-level valuation is a separate downstream stage.
