# Parameter-hierarchy model runs

Each child directory is one complete calibration/simulation run. Generated runs
are excluded from Git; this guide is tracked. Source quotes and prepared snapshots
live separately under [FRED snapshots](../../FRED/snapshots/readme.md). Never edit
or combine generated files merely because their filenames match across runs.

## Produce a new run

Install the [repository requirements](../../../requirements.txt), obtain the
[snapshot inputs](../../../src/RWA/data/yields/readme.md), then run from
the repository root with a new destination:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-run/series \
  --input-manifest RWA/FRED/snapshots/my-run/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-elapsed-run \
  --time-basis act365f --missing-policy observed \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --forecast-mode recursive --paths 32 --steps 10 --substeps 8
```

Do not create `my-elapsed-run` beforehand. Replace the snapshot name with an
existing verified snapshot and choose a new model name on every run. To use
historical `RWA/FRED/DGS*.csv` files, omit both input arguments. See the
[model guide](../../../src/RWA/models/parameter_hierarchy/readme.md) for all
settings and the [live pipeline](../../../pipeline/rwa_live/readme.md) to acquire
and model together.

## Stage order and settings

The model verifies a supplied snapshot, loads and aligns quotes, calibrates
rolling yield parameters across maturities, applies the same process to each
mu/theta/sigma history, estimates full joint innovation dependence, then simulates
and optionally evaluates constant-parameter estimation noise. It writes the
completion manifest last. No output directory is created before the analytical
stages finish; a later export failure can leave partial files without a manifest.

The command above selects genuine common-date observations and ACT/365F historical
intervals. Defaults remain `observation` with `forward-fill`; those settings give
the previous equal-duration transition convention. Windows and `recent_rows` count
observations, not fixed calendar years. The future `--dt` remains a scalar year
fraction (default 1/252); no holiday forecast calendar is generated. Both rolling
passes, dependence, noise controls and recursive buffers use the matching
historical interval sequence, replacing expired intervals with future dt as paths
advance.

## Files and next consumers

| File | Contents and interpretation |
| --- | --- |
| `yield_parameters.csv` | Date/maturity first-pass fits, raw estimates and ridge audits |
| `parameter_dynamics.csv` | Date/maturity/parameter second-pass fits and ridge audits; sigma branch diffusion is xi |
| `transition_intervals.csv` | Retained historical start/end dates and their `dt_years` |
| `RAW/DGS<n>_with_parameters.csv` | Model-used yields and chronological first-pass parameters; warmup remains missing; one-based CSV row label |
| `CURVE/{mu,theta,sigma}_curve.csv` | Date-keyed wide maturity panels from the same fits |
| `scenarios.npz` | `(path, step including origin, state, maturity)` states; state order X/mu/theta/sigma, maturities, origin correlation, projection counts, `elapsed_years` |
| `scenario_summary.csv` | Mean and 5/50/95 percentiles by step, elapsed years, state and maturity |
| `manifest.json` | Completion status, settings, source hashes/provenance, time convention, likelihood/dependence/recursive audits and optional noise evidence |

FRED yield values remain percentage points. RAW's DGS and `yield_clean` columns
both hold the values used by the model: filled values in forward-fill mode,
genuine common-date values in observed mode. Original quote missingness remains
in the source snapshot. RAW/CURVE column schemas do not encode their clock;
keep the manifest and interval file with any extracted tables. Forecast elapsed
years are `step * dt`, starting at zero, rather than future observation dates.

The [reconstruction consumer](../../../src/RWA/data/parameters/readme.md) accepts
compatible RAW/CURVE schemas when explicitly directed to one consistent run.
Its legacy six-column export omits timing/provenance audits. New analytical
consumers should retain those original audits. Exposure/cash-flow valuation and
a capital mapping remain future stages; no generated file is a duration-adjusted
RWA result.

## Audit and failure behavior

Inspect weak and regularized fits, likelihood costs, boundary projections,
source exclusions and `time_convention` before interpreting scenarios. It records
historical interval count/range/total and future duration. A mixed zero/positive
history requiring a different likelihood, unusable fit or excessive step-scale
mean reversion aborts; failed paths are not dropped. Existing destinations and
paths resolving outside the repository are rejected. Follow the model guide's
workload bounds and choose a new destination after correcting a failure.

ACT/365F handles unequal observation gaps but retains the conditional Gaussian
Euler approximation. Genuine-date intersection can induce missingness selection;
rolling estimates still contain measurement error. Simulated constant-maturity
par rates are not guaranteed arbitrage-free spot/discount curves. Neither passing
tests nor successful simulation establishes economic validity or forecast
superiority. Use the [model guide](../../../src/RWA/models/parameter_hierarchy/readme.md)
for model assumptions and the [test guide](../../../tests/readme.md) for
reproducible checks. A generated manifest records the settings and diagnostics
for its own run; retain that evidence when comparing clocks, missingness policies,
recursive update frequencies or estimation-noise controls.
