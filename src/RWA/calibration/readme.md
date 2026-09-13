# Interest-rate calibration

This domain estimates yield-process parameters and repairs selected anomalies in
cross-maturity parameter curves. Its components share the calibration problem,
while [data](../data/readme.md) owns acquisition/preparation and
[models](../models/readme.md) owns coupled parameter dynamics and simulation.

| Component | Purpose | Entry points |
| --- | --- | --- |
| [Yield estimation](yields/readme.md) | Causal rolling CIR calibration of observed yields | `yields/calibrate.py` |
| [Curve repair](curves/readme.md) | NS/NSS repair of selected mu/theta anomalies across maturities | `curves/mu.py`, `curves/theta.py` |

## Existing file-based sequence

Run from the repository root with [requirements](../../../requirements.txt)
installed. The component guides give settings, input schemas and audit behavior.

```bash
python3 src/RWA/calibration/yields/calibrate.py
```

Then assemble consistent date-aligned parameter panels using the
[CURVE recipe](../../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md), and run:

```bash
python3 src/RWA/calibration/curves/mu.py
python3 src/RWA/calibration/curves/theta.py
```

Review accepted and failed repairs before
[reconstructing parameter histories](../data/parameters/readme.md). These commands
replace their configured historical output files; moving the source folders does
not regenerate data or certify older results.

The [parameter hierarchy](../models/parameter_hierarchy/readme.md) uses a separate
coupled stabilization method and calibrates parameter histories within its own
workflow. Independent curve smoothing and coupled model calibration have
different assumptions; neither guarantees recovery of weakly identified latent
parameters. Calibration outputs alone are not duration-adjusted RWA.

## Verification

```bash
python3 -B -m unittest discover -s tests -p test_rwa_calibration.py -v
```

Use the repository-local temporary/cache settings in the
[test guide](../../../tests/readme.md). Fixtures verify causal estimates,
whole-row repair rejection, eight-maturity contracts and reconstruction consumers.
