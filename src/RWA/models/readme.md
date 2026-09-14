# Interest-rate models

This domain defines joint stochastic state evolution, dependence assumptions and
scenario-producing workflows. [Data](../data/readme.md) owns observations and
prepared tables; [calibration](../calibration/readme.md) contains the established
standalone yield fitting and curve-repair sequence.

The implemented model is the
[parameter hierarchy](parameter_hierarchy/readme.md). It fits observed yields,
stabilizes weak estimates, estimates dynamics for each mu/theta/sigma history,
and simulates rates and parameters jointly. `workflow.py` provides the CLI and
file contracts, `core.py` implements numerical operations, and `recursive.py`
updates coefficients and dependence within each simulated path.

## Entry points

From the repository root, with [requirements](../../../requirements.txt) installed:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py --help
python3 -m src.RWA.models.parameter_hierarchy.workflow --help
```

The [model guide](parameter_hierarchy/readme.md) documents full commands, inputs,
outputs, mathematical assumptions and diagnostics. The existing
[local-input pipeline](../../../pipeline/rwa_hierarchy/readme.md) uses this same
entry point. Choose new run directories and preserve source/provenance records.

## Implemented boundary

The hierarchy supports a frozen benchmark and a recursive engine that refits
parameter dynamics and dependence within each simulated path. The pipeline
configurations select recursive mode. Optional ACT/365F history with genuine
common-date quotes propagates actual durations through both calibration passes,
dependence, noise controls and recursive buffers. The default fixed observation
clock is retained for reproducibility. Exposure pricing and capital mapping are
subsequent model components.
Estimated parameter dynamics can include calibration noise; simulation alone
does not establish an additional economic risk factor or forecasting superiority.

Run the model checks with repository-local temporary/cache settings from the
[test guide](../../../tests/readme.md):

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

The tests cover numerical expectations, causality, scenario dependence, package
and direct invocation, exported data contracts and the actual pipeline manager.
