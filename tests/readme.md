# Tests

Install the [project requirements](../requirements.txt) in the active Python
environment. The suite uses `unittest`; SciPy supplies independent optimizers
for the calibration checks. Run commands from the repository root.

## Complete suite

The following environment keeps test fixtures and caches in an ignored directory:

```bash
mkdir -p .cache/tests/tmp .cache/tests/matplotlib
export TMPDIR="$PWD/.cache/tests/tmp"
export XDG_CACHE_HOME="$PWD/.cache/tests"
export MPLCONFIGDIR="$PWD/.cache/tests/matplotlib"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -v
```

Tests create isolated inputs and mock network responses where needed. They do not
require private research records or previously generated analytical outputs.

## Component coverage

| Tests | Behavior checked |
| --- | --- |
| `test_ffiec_preparation.py` | Download planning, archive verification, safe extraction, cache reuse and recovery |
| `test_call_report*.py`, `test_dynamic_ratios.py` | Ratio definitions, missing-value handling, form/date selection and historical bank alignment |
| `test_material_events.py`, `test_peer_groups.py` | Event flags, CLI selection, cohort membership and calendar filtering |
| `test_jsd_binning.py`, `test_jsd_calculation.py`, `test_analysis_pipeline.py` | Histogram boundaries, PMFs, distribution comparisons and downstream filtering |
| `test_repository_portability.py` | Checkout names, local path boundaries and interpreter handling |
| `test_pipeline_manager.py` | Configuration validation, parameters, dependencies and task execution |
| `test_rwa_calibration.py` | Chronological calibration, curve repair and downstream file contracts |
| `test_rwa_hierarchy.py` | Historical calibration, likelihood/ridge contracts and all parameter branches |
| `test_rwa_recursive.py` | Ordered xi/sigma/rate updates, every-increment recalibration, causal histories and serial continuation |
| `test_rwa_covariance.py` | Three separate family covariances, factor identities, regularization and Brownian transforms |
| `test_rwa_covariance_archive.py` | Complete increment records, checksums, coefficient/shock replay data and interrupted writes |
| `test_rwa_annual_walk.py` | Historical initialization, preserved starting histories, yearly continuation and model-output integration |
| `test_rwa_conditioned_fit.py` | Conditional drift likelihoods with varying right-endpoint diffusion histories and ridge constraints |
| `test_rwa_walk_verification.py` | File integrity, rolling covariance/shock replay, yearly restart continuity and optional recalibration |
| `test_rwa_elapsed_time.py` | Irregular historical intervals, time units, both estimation passes, recursion and verified-input integration |
| `test_rwa_yield_data.py` | Response failures, freshness/gap rules, immutable outputs and raw-to-clean provenance |

For example, run focused model tests with the same environment:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

The [RWA execution guide](../src/RWA/readme.md) maps these contracts to the model's
processing stages and generated artifacts. Regression success establishes the
checked computational behavior; scientific claims require separate empirical
validation with appropriate controls and held-out data.
