# Endogenous parameter hierarchy evidence

Read [RESULTS.md](RESULTS.md) for the implemented capability, findings, numerical
checks and remaining limitations. The [source guide](../../../src/RWA/models/parameter_hierarchy/readme.md)
documents the model and output contracts.

| Evidence | Contents |
| --- | --- |
| `real-eight-tenor/` | Initial 1-increment scenarios and 16-replicate estimation-noise benchmark |
| `real-eight-tenor-refined/` | Same calibration with four internal increments per reported step |
| `validation-results.json` | Paired synthetic controls, held-out comparisons and refinement |
| `calibration-benchmark.json` | Raw solver timing and objective comparisons on actual windows |
| `verified-suite.log` | Final 147-test regression result |
| Other `*.log` files | Intermediate successes, failures and experimental output |
| `model.txt`, `model-page-*.png` | Extracted/rendered PDF inspection evidence; original PDF remains authoritative |

Each real-data directory contains `RAW/`, `CURVE/`, long calibration tables,
scenario summaries, `scenarios.npz`, and a completion `manifest.json`. See
[the model's file contracts](../../../src/RWA/models/parameter_hierarchy/readme.md#files-and-interfaces).

From `Basel3_repo`, with root requirements installed, reproduce the refined
real-data configuration in a new output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B src/RWA/models/parameter_hierarchy/workflow.py \
  --output .codex-engineering/runs/hierarchy-recheck/real-eight-tenor \
  --recent-rows 2792 --yield-window 2520 --parameter-window 252 \
  --paths 1024 --steps 20 --substeps 4 --noise-replicates 16
```

The archived initial benchmark used `--substeps 1`; the refined archived run used
`--substeps 4 --noise-replicates 0`. Their calibration CSVs were identical. The
command above combines refined simulation with a newly executed noise diagnostic.

For synthetic controls, held-out comparisons and refinement, copy the validation
script to a new directory at the same depth so its output does not replace the
archive:

```bash
mkdir -p .codex-engineering/runs/hierarchy-recheck
cp .codex-engineering/runs/2026-09-13-capability/validate_hierarchy.py \
  .codex-engineering/runs/hierarchy-recheck/
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  .codex-engineering/runs/hierarchy-recheck/validate_hierarchy.py
```

It writes `validation-results.json` next to the copied script. Use a distinct run
name for subsequent repetitions. Reproductions read the current source/data, so
record their revision and hashes. The small archived held-out comparison did not
demonstrate forecasting superiority, and parameter volatility can reflect
estimation and regularization effects.
