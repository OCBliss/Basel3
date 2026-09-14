# Interest-rate models

This domain owns recursive state evolution and its numerical/audit interfaces.
[Data](../data/readme.md) owns observations and prepared tables;
[calibration](../calibration/readme.md) contains standalone yield fitting and
NS/NSS repair experiments.

The [parameter hierarchy](parameter_hierarchy/readme.md) estimates historical
mu/theta/sigma and every second-pass parameter branch, then initializes three
state histories: rate, sigma and xi. It recomputes separate family covariances
and refits all three CIR processes before every actual increment. The dependency
order is xi → sigma using new xi → rate using new sigma. Rate/sigma drift fits
condition on known varying higher-state histories; xi retains a free-diffusion
CIR fit. The archived multiplier identifies which source actually drove each step.

## Entry points

From the repository root, with [requirements](../../../requirements.txt) installed:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py --help
python3 -m src.RWA.models.parameter_hierarchy.workflow --help
```

The [model guide](parameter_hierarchy/readme.md) documents initialization, history
requirements, serial years, output archives, timing and failure handling.
The [RWA execution map](../readme.md#execution-order) covers the full sequence.
Existing-input and live pipelines use the same model entry point.

## Numerical components and boundary

`workflow.py` coordinates historical calibration and serial simulation;
`core.py` supplies CIR estimation and coupled ridge treatment. `covariance.py`
keeps state-level and Brownian covariances distinct for each family, and
`covariance_archive.py` records every applied matrix, fitted coefficient and shock.
`verify.py` checks hashes, reconstructs the rolling histories and replays the
archived updates; its `--recalibrate` option also repeats the fits.
One package README defines their shared contract.

Default initialization retains 2,520 estimate dates after calibration warmups.
Each subsequent year continues the previous history, random stream and anchors.
There are no independent ensemble paths, frozen-coefficient mode or skipped
calibration increments. Optional ACT/365F history propagates actual date gaps;
future increments use their explicit year fractions.

Estimated dynamics can contain calibration noise. Exposure pricing and a capital
mapping remain subsequent components. Use the [test guide](../../../tests/readme.md)
for deterministic numerical, covariance, replay and integration checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```
