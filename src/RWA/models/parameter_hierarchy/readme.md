# Interest-rate parameter hierarchy

This workflow extends the existing sigma-only second pass in
`RWA/Experimental/RWA_Heston_MLE_vol_test.py` to **mu, theta and sigma at every
maturity**, then evolves those three states jointly with the yield. It is an
executable stage toward `PDF/Recursive IRR Model.pdf`, incorporating the author's
clarification that higher-order dynamics come from applying the same estimation
operation to the first-pass parameter histories.

It also measures a central identification problem: repeated estimation can
produce apparent parameter volatility even when the generating parameters are
constant. Fitting another process to that volatility does not automatically
establish a new economic risk factor.

## Component layout

`workflow.py` handles the command-line interface, both calibration passes, aligned
exports, scenario generation and the completion manifest. It imports `core.py`,
which implements the estimator, coupled stabilization, dependence calculations and
simulation step. They share one numerical and file contract within this package.
The companion [reconstruction component](../../data/parameters/readme.md) consumes
compatible RAW/CURVE exports when explicitly directed to the same run.

The implemented stage is parameter calibration and simulation. Exposure valuation
and duration-adjusted RWA are future milestones, not current output labels.

## Run

Python 3.8+, NumPy and pandas are required; the existing environment is supported.
From `Basel3_repo`, either entry form can display the CLI:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py --help
python3 -m src.RWA.models.parameter_hierarchy.workflow --help
```

Run a calibration and simulation:

```sh
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 256 --steps 20 --substeps 4 --noise-replicates 16
```

Choose a **new** output directory for each run. Project input and output paths
must resolve inside this repository, including through symlinks. The workflow
does not overwrite existing calibration files or historical outputs. No output
directory is created until calibration, simulation and the optional benchmark
have finished. The manifest is written last; a directory without its completion
manifest may contain partial output and must not be treated as a completed run.

The manager can execute the separate configuration:

```sh
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml
```

Change that configuration's `output_dir` before a subsequent run. Its default
noise benchmark is disabled (`noise_replicates: 0`); use at least two replicates
to enable it. More replicates improve resolution but do not cure model error.
The default 20-task Call Report/JSD workflow is unchanged.

`--as-of YYYY-MM-DD` restricts observed information to that date. `--recent-rows 0`
uses all aligned history. Truncating history explicitly restarts the sequence of
previous-date regularization anchors, so changing that setting can change fits.
Within a fixed start date/settings, adding later observations does not revise
earlier fitted rows. The first full second-pass date is at observation
`yield_window + parameter_window - 1`, using one-based observation numbering.

## Model and finite hierarchy

For each maturity i, the first pass estimates the existing Euler CIR form:

```
dX = theta * (mu - X) dt + sigma * sqrt(X) dW_X.
```

For every p in {mu, theta, sigma}, the second pass estimates:

```
dp = theta_p * (mu_p - p) dt + sigma_p * sqrt(p) dW_p.
```

Thus `sigma_sigma` is xi in the paper's volatility equation when its nu is
identified with first-pass sigma. The conditional variance of `dp` over a small
interval is `sigma_p**2 * p * dt`, not `sigma_p**2`. The two other branches describe
stochastic drift parameters. A single maturity has four simulated states and
nine second-level coefficients. Eight maturities have 32 joint state components.

The current closure freezes the nine second-level coefficients and the joint
correlation at the forecast origin. X, mu, theta and sigma themselves all evolve.
Historical calibration is rolling and causal. **Pathwise recalibration on
simulated histories is not yet implemented.** A separately evolving xi state
would require another explicit estimation level. These distinctions prevent a
finite hierarchy from being presented as the completed recursive PDF model.

## Coupled stabilization at likelihood ridges

The existing separate NS/NSS repair scripts are preserved. This workflow offers
a likelihood-constrained alternative to independent parameter interpolation.

Write the drift as `a - b*x`, with `b=theta` and `a=theta*mu`. For chronological
observations define `y=diff(x)/dt`. Conditional Euler variance is `sigma**2*x*dt`.
Minimizing the Gaussian negative log likelihood over a and b therefore reduces
to weighted least squares with weights `1/x`. The solver includes the admissible
boundary solutions and profiles

```
sigma**2 = dt * mean((y - a + b*x)**2 / x).
```

At a fixed b, the unconstrained a is the weighted mean of `y+b*x`; enforce the
positive mean boundary and recompute sigma. This lets a candidate speed change
mu and sigma together while measuring its actual cost against observed rate
transitions. Input normalization preserves the unit transformation: dividing X
by 100 divides mu by 100 and sigma by 10, leaving theta unchanged.

A raw fit is labelled weak when theta is below 1e-4 or no larger than its local
weighted-regression standard error. This is an engineering diagnostic, **not a
confidence interval or identification test**, especially at the boundary.
At theta=0 the raw mu is undefined and is recorded as missing, instead of a huge
apparently precise number. Exactly constant histories are explicitly marked
deterministic/unidentified and have zero fitted diffusion.

For weak fits:

1. Healthy same-date maturity nodes supply a target speed through linear
   interpolation of log(theta) against log(maturity), with endpoint extrapolation.
2. If there are no healthy nodes, use the previous date's stabilized speeds.
3. At initialization without either source, use the explicit `--fallback-theta`
   setting (default 0.25 per year).
4. Profile mu and sigma at that target. Accept it only within `--nll-budget`
   of the raw optimum; otherwise move only as far toward the target as that
   budget permits. The default budget 2.0 is a tunable regularization allowance,
   not a statistical confidence guarantee.

All maturities and all parameter branches undergo the same diagnostic. Healthy
fits remain unchanged. Raw estimates, the anchor source, target, likelihood cost,
and weak/regularized/deterministic flags are retained. A regularized fit **keeps
its weak flag**. It is usable for an explicitly conditional model, not thereby
identified. A zero budget can leave an undefined mean; downstream fitting then
fails explicitly. No invented state fills that gap.

Anchor changes and shared anchors can induce jumps, flattening and dependence in
the repaired histories. The noise benchmark reruns this mechanism as well as the
estimator. Future research should compare temporal/cross-maturity regularizers
and tune their strengths on data that were not used to choose those strengths.

## Joint shocks and discretization

At the forecast origin, compute drift-adjusted, diffusion-standardized residuals
from aligned trailing histories. The state order is X across maturities, then mu,
theta and sigma. Estimate the **full** correlation, including cross-parameter
and cross-maturity blocks. These are proxy innovations based on estimated
parameters; their correlation can include estimation-induced dependence.

Shrink the sample correlation toward identity by the explicit `--shrinkage`
fraction (default .05), then factor it as `C=L*L.T`. This handles sample rank
deficiency. It is not a nearest-correlation-matrix algorithm. Diagnostics include
the minimum eigenvalue, largest correlation adjustment, constant columns and
number of aligned transitions. Constant residual columns receive zero
off-diagonal correlations; zero diffusion still produces no stochastic shock.

Every Euler increment evaluates all coefficients on the **old** state. This
implements equations 2.7–2.8 of the PDF. The page-4 suggestion to use newly
updated correlated coefficients changes conditional drift. In particular,
using updated sigma in the rate diffusion adds approximately
`rho_Xsigma * xi * sqrt(sigma*X) * dt`. An antithetic numerical experiment checks
that term and confirms its absence in the implemented simultaneous update.
Correlation is estimated before generating forecast shocks.

There are four internal Euler increments per reported observation by default.
Increase `--substeps` to check convergence. A mean-reversion speed exceeding the
internal step scale is rejected. Negative proposed states are projected to zero
as in the PDF; counts are retained by state and maturity. Projection does not
prove distributional accuracy or satisfy the Feller condition. Mixed zero and
positive histories are rejected by the calibration likelihood, which has no
boundary transition law. An identically zero history is handled deterministically.

The basic Euler convention and its convergence assumptions are described by
[Higham, Mao and Stuart (2002), section 2](https://www.maths.ed.ac.uk/~dhigham/Publications/P44.pdf).
That paper is not a convergence proof for this projected hierarchy.

## Estimation-noise benchmark

`--noise-replicates N` fixes the fitted first-stage parameters, generates N yield
panels with their estimated cross-tenor dependence, and reruns **both complete
rolling passes and regularization** on each panel. The second-pass diffusion
estimates form a conditional reference distribution. The report includes the
observed coefficient, null median, null 95th percentile, exceedance fraction,
failed replicates and their reasons. Any failed replicate makes `comparable`
false; failures are not silently dropped from an apparently complete benchmark.

Nonzero diffusion under this null is evidence that the estimation procedure can
create apparent parameter dynamics. The benchmark is conditional on fitted
parameters, Gaussian Euler simulation, chosen windows and repair settings. Its
exceedance fractions are **not calibrated p-values**, and its variance is not
automatically subtracted from the observed process. It measures a confounding
mechanism rather than assuming a decomposition that has not been established.

The likelihood remains the repository's Gaussian Euler approximation, not the
exact CIR transition density or a joint latent-state likelihood. Differences
between Euler and more accurate multifactor likelihood methods are investigated
by [Ait-Sahalia and Kimmel (2010), sections 1–2](https://www.princeton.edu/~yacine/affinets.pdf).
This workflow does not implement that paper's estimator or inherit its results.

## Files and interfaces

| Output | Contract |
|---|---|
| `yield_parameters.csv` | Long date/maturity table; fitted mu/theta/sigma plus raw estimates and regularization diagnostics |
| `parameter_dynamics.csv` | Long date/maturity/parameter table; theta/mu/sigma describe the named parameter process, with the same diagnostics |
| `RAW/DGS*_with_parameters.csv` | Existing first-stage column contract and one-based row labels, chronological order, unavailable warmup retained as missing |
| `CURVE/{mu,theta,sigma}_curve.csv` | Existing date-keyed maturity-column contract, generated from the stabilized fits |
| `scenarios.npz` | States with axes (path, reported step including origin, state, maturity); state/tenor labels, correlation and projection counts |
| `scenario_summary.csv` | Mean and 5/50/95 percentiles by reported step, state and maturity |
| `manifest.json` | Settings, input hashes, units, date range, audit totals, dependence diagnostics, optional noise benchmark and limitations |

The Python `calibrate_parameters(first_stage, window, ...)` interface also accepts
a long first-stage table assembled from existing repaired parameter files. It
requires date, maturity, mu, theta and sigma columns and refuses missing internal
states or duplicated keys; it does not certify that supplied estimates were
properly repaired. The CLI regenerates the necessary first-stage history from
FRED because archived repository estimates predate the chronology correction.

FRED percentages are retained. Quote dates are inner-joined across maturities;
each series is forward-filled only from earlier quotes before the join. Filled
quotes are counted. The fixed dt convention treats successive retained rows as
equally spaced and does not implement irregular-calendar transition durations.

## Verification and remaining RWA work

```sh
python3 -m unittest discover -s tests -p test_rwa_hierarchy.py -v
python3 -m unittest discover -s tests -v
```

Tests independently check the likelihood against a nonlinear optimizer, coupled
repair cost, unit transformations, every tenor position, all parameter branches,
date/order/future invariance, drift/covariance, update-order bias, singular
correlation, boundary counts, deterministic refinement, reproducibility, file
contracts through the existing rebuild, and actual pipeline execution.

The research record in `.codex-engineering/runs/2026-09-13-capability/` includes
actual eight-tenor outputs, constant-versus-varying parameter controls, a small
held-out comparison against frozen first-stage parameters, and finite-horizon
moment checks. These are initial validation evidence, not a demonstration of
superior forecasts or economic novelty.

Remaining milestones include measurement-error-aware parameter dynamics,
pathwise recursive calibration and covariance updates, wider held-out evaluation,
and the exposure/cash-flow valuation and capital mapping required to complete
the duration-sensitive RWA objective. No VaR or regulatory capital result is
claimed by this implementation.


## Verified acquired inputs

The [live pipeline](../../../../pipeline/rwa_live/readme.md) supplies both `--input`
and `--input-manifest`. Before fitting, the model checks snapshot completion,
series identity, raw/processed hashes, and reproduces the recorded cleaning from
the raw response. Its result manifest includes `yield_acquisition` with the input
manifest hash, source coverage, retrieval time and imputation policy. With no
`--input-manifest`, standalone historical-file use remains available.

`--as-of` limits observation dates after the whole snapshot is verified; it does
not turn a current-revision download into a historical real-time vintage.
