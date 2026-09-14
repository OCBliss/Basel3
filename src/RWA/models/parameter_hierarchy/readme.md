# Interest-rate parameter hierarchy

This workflow calibrates yield dynamics and **mu, theta and sigma processes at
every maturity**, then evolves those three parameter states jointly with yields.
It implements a finite hierarchy for the
[Recursive IRR Model](../../../../PDF/Recursive%20IRR%20Model.pdf): higher-order
coefficients come from applying the same estimation operation to first-pass
parameter histories. Optional elapsed-time calibration uses genuine common-date
observations and their actual calendar intervals.

The [RWA workflow overview](../../readme.md#execution-order) gives the complete
acquisition-to-output sequence. This component performs both calibration passes,
coupled stabilization, dependence estimation and forecasting. The standalone
[NS/NSS repair](../../calibration/curves/readme.md) is a separate legacy experiment.

It also measures a central identification problem: repeated estimation can
produce apparent parameter volatility even when the generating parameters are
constant. Fitting another process to that volatility does not automatically
establish a new economic risk factor.

## Component layout

`workflow.py` handles the command-line interface, both calibration passes, aligned
exports, scenario generation and the completion manifest. It imports `recursive.py`
for pathwise rolling recalibration and `core.py` for the estimator, coupled
stabilization, dependence calculations and simulation step. They share one numerical and file contract within this package.
The companion [reconstruction component](../../data/parameters/readme.md) consumes
compatible RAW/CURVE exports when explicitly directed to the same run.

The implemented stage is parameter calibration and simulation. Exposure valuation
and duration-adjusted RWA are future milestones, not current output labels.

## Run

Install the [repository requirements](../../../../requirements.txt) in an active
Python environment. From the repository root, either entry form displays the CLI:

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
The [Call Report/JSD pipeline](../../../../pipeline/readme.md) has a separate
configuration and execution plan.

`--as-of YYYY-MM-DD` restricts observation dates to that cutoff. `--recent-rows 0`
uses all aligned history. Truncating history explicitly restarts the sequence of
previous-date regularization anchors, so changing that setting can change fits.
Within a fixed start date/settings, adding later observations does not revise
earlier fitted rows. The first full second-pass date is at observation
`yield_window + parameter_window - 1`, using one-based observation numbering.

## Historical time and missing quotes

Defaults remain `--time-basis observation --missing-policy forward-fill` for
reproducibility: causally fill each original DGS series before the common-date
join and assign every retained transition the scalar `--dt` (default `1/252`).
Use this explicit alternative to fit genuine observations on an elapsed-time clock:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-run/series \
  --input-manifest RWA/FRED/snapshots/my-run/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-elapsed-run \
  --time-basis act365f --missing-policy observed \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --forecast-mode recursive --paths 32 --steps 10 --substeps 8
```

`--missing-policy observed` uses the original `DGS<n>` quote column, removes
missing quotes separately by tenor, then keeps dates genuinely observed for
**every** selected maturity. It does not use the snapshot's `yield_clean` fills.
Only blank cells and `.` represent missing quotes; malformed or nonfinite numeric
tokens fail instead of becoming silently imputable observations.
The preserved snapshot still contains its full raw/prepared histories and original
imputation audit. Common-date filtering can discard genuine observations of other
tenors when one tenor is missing; it is a complete-case model, not asynchronous
observation inference. Missingness related to market conditions can bias it.

`--time-basis act365f` assigns historical transition `i` the year fraction
`h_i = (date[i+1] - date[i]).total_seconds() / (365 * 86400)`. The denominator
remains 365 across leap years. ACT/365F requires unique, increasing, timezone-naive
calendar dates without intraday times. Both yield and parameter calibration passes,
standardized dependence residuals and the constant-parameter noise benchmark
use the matching intervals. These switches are independent: observed-only with
an observation clock is a useful simpler comparison, and filling can still be
selected explicitly with ACT/365F. Neither choice establishes the best economic
clock for this market.

`yield_window`, `parameter_window` and `recent_rows` count retained observations;
they do not specify fixed calendar-year spans. `--as-of` is applied before filling
or missing-quote selection, and histories must have enough common dates for both
passes. The manifest records the selected settings, source exclusions and
`time_convention` interval evidence;
`transition_intervals.csv` retains the exact historical transition dates and
year fractions. Source entries report `missing_quotes`, `filled_quotes`,
`excluded_missing_quotes`, `rows_before_alignment`, `rows_after_alignment` and
`excluded_alignment_rows`. Inspect these alongside parameter-identification
diagnostics.

`--dt` remains the **future** reported-step duration in years in both modes.
Forecasts advance at that regular elapsed interval and do not generate a holiday
or business-day forecast calendar. For a one-calendar-day grid pass
`--dt 0.0027397260273972603` (1/365); leaving `--dt` at 1/252 does not mean the ACT/365F
forecast uses consecutive calendar days. Substeps divide each future increment
for numerical integration, without adding calibration observations.

The [elapsed-time tests](../../../../tests/test_rwa_elapsed_time.py) verify
interval-weighted likelihoods, calendar durations, downstream timing contracts
and recursive interval-buffer alignment.

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

Two forecast modes share this state representation. `--forecast-mode frozen`
keeps the second-level coefficients and correlation at their origin values.
`--forecast-mode recursive` recalibrates them independently within each simulated
path from its trailing history. In both modes X, mu, theta and sigma evolve.
The YAML workflows select recursive mode; the direct CLI defaults to frozen for
compatibility with existing commands and comparison runs.

The hierarchy has a finite depth: xi is recomputed as the sigma branch's fitted
diffusion coefficient. It is not an additional independently simulated state.

## Coupled stabilization at likelihood ridges

The existing separate NS/NSS repair scripts are preserved. This workflow offers
a likelihood-constrained alternative to independent parameter interpolation.

Write the drift as `a - b*x`, with `b=theta` and `a=theta*mu`. For chronological
observations with year-fraction intervals `h_i`, define `y_i=diff(x)_i/h_i`.
Conditional Euler variance is `sigma**2*x_i*h_i`. Minimizing the Gaussian
negative log likelihood over a and b therefore reduces to weighted least squares
with weights `h_i/x_i`. The solver includes the admissible boundary solutions and
profiles

```
sigma**2 = mean(h_i * (y_i - a + b*x_i)**2 / x_i).
```

For constant intervals, the common h factor cancels from the regression and this
reduces to the original `1/x` weighted fit. Standardized innovations divide
`diff(x)_i - (a-b*x_i)*h_i` by `sigma*sqrt(x_i*h_i)`, including for dependence
estimation. The Euler approximation still becomes less accurate for larger gaps;
using their actual duration does not turn it into the exact CIR likelihood.

At a fixed b, the unconstrained a is the weighted mean of `y+b*x`; enforce the
positive mean boundary and recompute sigma. This lets a candidate speed change
mu and sigma together while measuring its actual cost against observed rate
transitions. Input normalization preserves the unit transformation: dividing X
by 100 divides mu by 100 and sigma by 10, leaving theta unchanged. Theta has units inverse years; mu has its state's
units and sigma has square-root state units per square-root year. The same
rule applies when the state is an estimated mu, theta or sigma history.

A raw fit is labelled weak when theta is below 1e-4 or no larger than its local
weighted-regression standard error. This is an engineering diagnostic, **not a
confidence interval or identification test**, especially at the boundary.
At theta=0 the raw mu is undefined and is recorded as missing, instead of a huge
apparently precise number. Exactly constant histories are explicitly marked
deterministic/unidentified and have zero fitted diffusion.

For weak fits:

1. Healthy same-date maturity nodes supply a target speed through linear
   interpolation of log(theta) against log(maturity), holding the nearest
   anchor's speed outside the covered maturity range.
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
rolling passes and regularization** on each panel. It preserves the selected
historical interval sequence in generation, both refits and residual scaling. The second-pass diffusion
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
| `transition_intervals.csv` | Exact historical start/end dates and `dt_years` for each retained yield transition |
| `scenarios.npz` | States with axes (path, reported step including origin, state, maturity); state/tenor labels, origin correlation, projection counts and `elapsed_years` |
| `scenario_summary.csv` | Mean and 5/50/95 percentiles by reported step, elapsed years, state and maturity |
| `manifest.json` | Settings, input hashes, units, date range, audit totals, `time_convention`, dependence diagnostics, optional noise benchmark and limitations |

The Python `calibrate_parameters(first_stage, window, ...)` interface also accepts
a long first-stage table assembled from existing repaired parameter files. It
requires date, maturity, mu, theta and sigma columns and refuses missing internal
states or duplicated keys; it does not certify that supplied estimates were
properly repaired. The CLI constructs first-stage histories directly from the
selected yield inputs and settings, then passes them to parameter calibration.

FRED percentage points are retained. The source quote/missingness audit and
selected loading policy determine which dates enter each run. RAW exports contain
the values actually used by the model in both `DGS<n>` and `yield_clean`; in filled
mode the former is therefore not an untouched raw quote column. Keep the original
snapshot as raw evidence. In observed mode both columns contain genuine common-date
quotes. RAW/CURVE dates remain the join keys; elapsed-time mode changes their
spacing and fitted values without adding a timing column to those legacy tables.
Consumers must retain the run manifest and date-derived interval convention.
`time_convention` reports the basis, historical interval count, minimum, maximum
and total historical year fractions, and future step duration. The additive
`elapsed_years` forecast fields use `step * dt` and include zero at the origin;
existing state-array axes and summary columns remain available.


## Recursive forecast operation

Run with an acquired snapshot and a new output directory:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-run/series \
  --input-manifest RWA/FRED/snapshots/my-run/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-recursive-run \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --forecast-mode recursive --recalibrate-every 1 \
  --paths 32 --steps 10 --substeps 8
```

The first reported step uses the calibrated origin coefficients and factor.
Each path then appends its own simulated `[X, mu, theta, sigma]` state and removes
its oldest history row. With ACT/365F, the interval buffer starts with the
historical calendar durations; each appended state adds the scalar future `dt`
and removes the expired interval. Every refit and innovation calculation uses
that matching mixed historical/simulated sequence, including after complete
buffer turnover. At the selected cadence, before drawing the next shock:

1. Fit the mu, theta and sigma histories across all maturities using the existing
   conditional likelihood and coupled ridge stabilization. Prior anchors belong
   to that path's preceding fit.
2. Recompute standardized joint innovations from its complete trailing state
   window. Estimate and shrink the full correlation matrix, then factor it.
3. Advance that path with those coefficients and factor. Euler drift and diffusion
   use the state from the start of each substep. An updated future state cannot
   affect a preceding shock or another path's calibration.

`--recalibrate-every 1` updates before every subsequent reported step; `5` updates
at origins 5, 10, and so on. Zero disables updates and exactly reproduces the
frozen engine's states and projection counts for identical inputs and settings.
No unused recalibration is performed after the final forecast step. History is
updated at the reported observation interval; numerical substeps do not become
extra calibration observations with a different sampling interval.

The simulated first-level parameter states are retained. Recalibration learns
their process coefficients—including xi from the sigma history—and their joint
dependence. It does not overwrite simulated mu/theta/sigma with another estimate
from simulated X, which would impose a different state-observation model.

The result manifest's `recursive_calibration` records each path/origin update,
observed versus simulated history counts, branch/diffusion changes, xi range,
correlation changes, likelihood costs and numerical diagnostics. Existing CSV and
NPZ shapes remain compatible; `scenarios.npz`'s `correlation` is the **origin**
correlation. Later pathwise changes are reported in the manifest, not presented
as a single common future correlation matrix.

The [implementation](recursive.py) uses separate circular buffers and checks
resource bounds before allocating them: 20 million numeric elements, 50 million
window-by-fit work units, 150,000 scalar fits, 10,000 audit records and 250,000
path/substep advances. These are computation limits, not runtime guarantees.
Mixed zero/positive histories requiring a boundary-aware fit, unusable fits or
excessive mean reversion abort the run with path/step context. Failed paths are
never silently dropped or replaced. Choose a new output destination for a retry.

For empirical comparisons, hold the input window and random seed fixed while
varying forecast mode or recalibration cadence. Compare terminal distributions,
including shared-bin JSD sensitivity, alongside held-out outcomes, Monte Carlo
uncertainty and runtime. The [recursive tests](../../../../tests/test_rwa_recursive.py)
independently verify update timing, full-window rollover, path isolation, residual
formulas and frozen equivalence; these correctness checks do not establish which
forecast mode performs better on new observations.

## Verification and remaining RWA work

```sh
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

Tests independently check the likelihood against a nonlinear optimizer, coupled
repair cost, unit transformations, every tenor position, all parameter branches,
date/order/future invariance, drift/covariance, update-order bias, singular
correlation, boundary counts, deterministic refinement, reproducibility, file
contracts through the existing rebuild, and actual pipeline execution.

Use the [test guide](../../../../tests/readme.md) for isolated temporary files and
environment setup. Known-answer and integration tests establish implementation
behavior; broader held-out comparisons are required to assess forecasting value.

Remaining milestones include measurement-error-aware parameter dynamics,
wider held-out evaluation,
and the exposure/cash-flow valuation and capital mapping required to complete
the duration-sensitive RWA objective. No VaR or regulatory capital result is
claimed by this implementation. Elapsed-time handling does not identify latent
parameter dynamics separately from measurement error, model informative missingness,
or make the jointly simulated constant-maturity par-rate curves arbitrage-free
spot/discount curves. HJM or other factor/valuation extensions require their own
curve construction, dynamics assumptions and held-out validation.


## Verified acquired inputs

The [live pipeline](../../../../pipeline/rwa_live/readme.md) supplies both `--input`
and `--input-manifest`. Before fitting, the model checks snapshot completion,
series identity, raw/processed hashes, and reproduces the recorded cleaning from
the raw response. Its result manifest includes `yield_acquisition` with the input
manifest hash, source coverage, retrieval time and imputation policy. With no
`--input-manifest`, standalone historical-file use remains available.

`--as-of` limits observation dates after the whole snapshot is verified; it does
not turn a current-revision download into a historical real-time vintage.
