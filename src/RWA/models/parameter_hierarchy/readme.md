# Recursive rate, volatility and volatility-of-volatility model

This component builds historical CIR parameter estimates for eight Treasury
maturities and advances one continuing trajectory of **rate, sigma and xi**.
Every actual Euler increment recomputes three separate cross-maturity dependence
structures and recalibrates all three state families before applying their shocks.
The update order is **dependence → xi → sigma using new xi → rate using new sigma**.

The [RWA execution map](../../readme.md#execution-order) connects acquisition,
historical estimation and this model. The [research PDF](../../../../PDF/Recursive%20IRR%20Model.pdf)
motivates the recursive update. The implementation uses the CIR interpretation
and initialization convention described below; it does not implement exposure
valuation, loss aggregation or a duration-adjusted RWA calculation.

## Component responsibilities

| Source | Responsibility |
| --- | --- |
| [workflow.py](workflow.py) | Input verification, both historical calibration passes, aligned state initialization, serial years and file exports |
| [core.py](core.py) | Free-diffusion and conditioned CIR likelihoods, fitted drift coefficients and coupled ridge treatment |
| [recursive.py](recursive.py) | Every-increment dependence, calibration, ordered state advancement and continuation state |
| [covariance.py](covariance.py) | Separate level correlations, Cholesky factors and Brownian transformations |
| [covariance_archive.py](covariance_archive.py) | Validated increment records, checksums and completion markers |
| [verify.py](verify.py) | File integrity, deterministic archive replay and optional recalibration checks |

## Run from the repository root

Install [requirements](../../../../requirements.txt), acquire a sufficiently long
[verified snapshot](../../data/yields/readme.md), then choose a new output directory:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-yield-snapshot/series \
  --input-manifest RWA/FRED/snapshots/my-yield-snapshot/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-run \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

Do not pre-create the output directory. To use historical `RWA/FRED/DGS*.csv`
without snapshot verification, omit both input arguments. Both entry forms show
all options:

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py --help
python3 -m src.RWA.models.parameter_hierarchy.workflow --help
```

The [existing-input configuration](../../../../pipeline/rwa_hierarchy/readme.md)
and [live acquisition configuration](../../../../pipeline/rwa_live/readme.md) run
this same entry point. Change their output names before a new run.

## Historical initialization: estimates need their own warmup

`--yield-window 2520` specifies the observations used for each historical yield
fit; it does **not** provide 2,520 dates of fitted parameters from only 2,520 quotes.
The workflow performs these causal rolling operations:

1. Fit rate histories across every maturity to produce `mu`, `theta` and `sigma`
   histories, including coupled likelihood-budgeted stabilization.
2. Apply the same CIR estimator separately to **all three** parameter histories.
   Each branch retains its own speed, long-run mean, diffusion and audits in
   `parameter_dynamics.csv`.
3. Align actual rates, first-pass `sigma`, and the second-pass diffusion of the
   `sigma` branch. These form the historical `rate`, `sigma`, `xi` state families.
4. Keep the last `--history-window` aligned dates for the ongoing recursive window.
   Its default is **2,520 dates of estimates**, with sufficient earlier observations
   for both calibration warmups.

The minimum number of common source observations is
`yield_window + parameter_window + history_window - 2`: **5,290** with the defaults.
Missing-quote selection can reduce the usable count. Acquire sufficiently early
history rather than padding unavailable estimates. The first-pass exports retain
at least 2,520 parameter dates plus the history needed by the second pass; the
second-pass output retains all three parameter branches.

`--recent-rows 0` uses all selected source history. A positive value explicitly
truncates it and must still satisfy the required warmups. Truncation restarts
previous-date ridge anchors and can change estimates. Within a fixed start and
settings, later observations cannot enter earlier calibration windows.

## State and coefficient names

| Name | Meaning |
| --- | --- |
| `rate` | Observed or simulated Treasury rate; X in the PDF, also called the rate/μ process in the research description |
| `sigma` | Rate diffusion state; ν in the PDF |
| `xi` | Volatility-of-sigma state, initialized from the sigma branch's fitted diffusion history |
| Fitted `theta` | Mean-reversion speed for the named state family |
| Fitted `long_run_mean` | Its fitted equilibrium level; distinct from the rate state |
| Archived `diffusion` | Actual multiplier used in the transition: new sigma for rate, new xi for sigma, or the freely fitted diffusion for xi |

The historical tables keep their established `theta`, `mu`, `sigma` column names;
there `mu` means a fitted long-run mean. The simulation has three state families,
not separate stochastic states for every historical coefficient column.

Historical xi uses the `Vol(nu)` identification in equations 2.3/2.9. Forecast xi
is a CIR state whose coefficients are reestimated from its own rolling history,
following the PDF's CIR prose and page-four shock ordering. It is not forcibly
reset to the sigma fit's diffusion after every step. Likewise, simulated sigma
is not overwritten by the rate fit's diffusion. The historical fitted diffusion estimates remain in the calibration tables.
During recursion, lower-family variance is conditioned on its known varying
higher-state history; no replacement constant diffusion is fitted. Thus the implementation does not impose
an instantaneous equality between each evolved state and a newly fitted volatility.

## Every-increment calculation

For each actual increment of length `h = dt / substeps`, including the first:

1. Compute each family's level covariance from the available rolling history,
   normalize its correlation and calculate its separate Cholesky factor.
2. Refit xi's full CIR coefficients at every maturity. Refit rate and sigma
   drift coefficients conditionally on their known varying volatility histories.
   Use coupled ridge treatment and matching historical transition intervals.
3. Draw three independent standard-normal vectors, one per family, and transform
   each exactly once with its own factor: `dW_family = sqrt(h) * L_family @ Z_family`.
4. Update xi, then sigma with new xi, then rate with new sigma. Apply the
   nonnegativity projection to each updated state before its dependent stage uses it.
5. Archive the exact matrices, fitted coefficients, shocks, states and audits;
   append the new state to the rolling history and remove its oldest row.

Writing `k` and `m` for each family's fresh speed and long-run mean, and `c_xi`
for xi's freely fitted diffusion, the updates are:

```text
xi_new    = max(xi    + k_xi*(m_xi-xi)*h       + c_xi*sqrt(xi)*dW_xi, 0)
sigma_new = max(sigma + k_sigma*(m_sigma-sigma)*h + xi_new*sqrt(sigma)*dW_sigma, 0)
rate_new  = max(rate  + k_rate*(m_rate-rate)*h + sigma_new*sqrt(rate)*dW_rate, 0)
```

Rate and sigma have no newly fitted scalar diffusion during recursion. Their
transition multipliers are the newly evolved higher states shown above.
Each family's drift and square-root state use its pre-increment value; the
multipliers passed upward are the newly updated xi and sigma. There is no option
to freeze coefficients or skip intermediate covariance updates. Increasing
`--substeps` increases both the number of numerical updates and recalibrations.

## Separate factor and Brownian covariances

For each family, the archive distinguishes:

| Array | Mathematical meaning |
| --- | --- |
| `factor_covariance` | Sample covariance C of historical state levels, divisor `n-1` |
| `raw_correlation` | Level covariance normalized by its marginal standard deviations |
| `correlation` | R actually used to correlate shocks |
| `cholesky` | Lower-triangular L satisfying `L @ L.T = R` |
| `brownian_covariance` | Conditional Brownian-increment covariance Q = `h * R` |
| `brownian_increments` | Realized vector `sqrt(h) * L @ Z` |

Each matrix array has shape `(3, maturity, maturity)`: three distinct 8×8 matrices
for eight tenors. Each realized shock family is an eight-element vector, not an
8×8 matrix. C describes state-level dispersion; Q describes Brownian increments
before the model's state-dependent diffusion multipliers. No pooled cross-family
matrix is estimated or applied.

`--correlation-regularization 0` preserves the empirical correlations by default.
Rank deficiency, undefined zero-variance correlations and invalid Cholesky factors
fail explicitly. An explicitly requested alpha in `(0, 1]` replaces R with
`(1-alpha)*raw_correlation + alpha*I`; the unchanged C, raw correlation and alpha
are retained. This is an explicit modeling adjustment, not a recovery of missing
information. It does not make a zero-variance correlation defined.

Independent Gaussian families follow the PDF's independent-Z equations. A
separate nonzero instantaneous cross-family rho is not imposed. Sigma and rate
still depend on the updated lower-level states through the ordered equations.
Correlations are calculated from state levels, not pooled standardized innovations.

## Calibration and coupled ridge treatment

Historical initialization uses free-diffusion CIR fits for rates and all three
parameter branches. The terminal xi process also uses a free-diffusion fit during
every recursive increment. For `dY = theta*(mu-Y)*dt + sigma*sqrt(Y)*dW`, write the drift as `a-b*Y`,
where `b=theta` and `a=theta*mu`. With chronological intervals `h_i`, the Gaussian
Euler likelihood reduces to weighted least squares of `diff(Y)/h_i` with weights
`h_i/Y_i`. The fitted diffusion satisfies

```text
sigma**2 = mean(h_i * (diff(Y)_i/h_i - a + b*Y_i)**2 / Y_i).
```

The solver includes admissible boundary solutions. At a fixed candidate speed,
it reprofiles the mean and diffusion together; it does not interpolate them
independently. A speed below `1e-4` or no larger than its local regression standard
error is flagged weak. This diagnostic is not a confidence interval or proof of
identification. Zero raw speed makes the mean undefined; constant histories are
marked deterministic/unidentified.

Healthy maturity nodes provide log-speed/log-maturity anchors. If none are
available, use the previous calibrated speeds; at initialization without those,
use the explicit `--fallback-theta` setting (default 0.25 per year). Move toward
an anchor only within `--nll-budget` (default 2.0) of the raw likelihood optimum.
This budget is a regularization allowance, not a confidence guarantee. Raw estimates, anchor sources,
targets, likelihood costs and weak/regularized flags are retained. A regularized
fit keeps its weak flag. The anchoring and likelihood-budget rule applies to all historical parameter
branches and all three recursive state families. Rate and sigma recursion use
the conditional likelihood below rather than reprofiling an invented scalar
diffusion.

For a lower state Y with known higher-state history A, the ordered model uses
right-endpoint A in every historical transition:

```text
Var(Delta Y_i | available states) = A[i+1]**2 * Y[i] * h[i]
y[i] = Delta Y_i / h[i]
weight[i] = h[i] / (A[i+1]**2 * Y[i])
```

Here A is sigma for rate and xi for sigma. Historical right-endpoint values are
already known when the current window is fitted. Weighted least squares estimates
the drift `a - theta*Y`; the conditional Gaussian likelihood retains those known,
varying variances when evaluating candidate ridge repairs. It does not estimate
a constant diffusion and then replace it during simulation. This matches the
page-four dependency order: the new higher state determines the lower transition's
variance. Unusable zero/nonfinite conditional variances fail explicitly.

The increment archive's `diffusion` column records the multiplier actually applied:
new sigma for the rate row, new xi for the sigma row, and the free CIR diffusion
for xi. Calibration audits identify `diffusion_source`, so an applied state value
cannot be mistaken for a lower-family fitted volatility parameter.

FRED rates remain percentage points. A speed has inverse-year units, a mean has
its state's units, and a CIR diffusion has square-root state units per square-root
year. Scaling a state by 1/100 scales its fitted mean by 1/100 and diffusion by
1/10. Repeated estimation and overlapping windows can create apparent volatility
and dependence; stabilization does not separate that estimation noise from latent
risk. The likelihood remains a Gaussian Euler approximation, not an exact CIR
transition or a joint latent-state estimator.

## Time, serial years and continuation

Defaults are `--years 1 --steps-per-year 252 --dt 0.003968253968253968 --substeps 1`.
`steps_per_year * dt` must equal one year. To use a 365-step year, set both
`--steps-per-year 365` and `--dt 0.0027397260273972603`. Substeps divide each reported
step and are archived individually. They also enter the rolling calibration
history with their actual `dt/substeps` duration.

`--years 2` continues year two from year one's final history, coefficients/anchors
and random-generator state. It does not restart at the historical origin or create
an ensemble of independent one-year paths. Each `year_NNNN/` stores the year's
trajectory, increment archive, restart data and completion manifest. The workflow
writes its root completion manifest only after all requested years finish.

Historical defaults use `--time-basis observation --missing-policy forward-fill`.
For genuine quotes and actual calendar gaps, select
`--time-basis act365f --missing-policy observed`. Observed mode intersects genuine
original DGS dates across maturities. ACT/365F uses date gaps divided by 365 days
in calibration; it retains a 365 denominator across leap years. Windows count
retained observations/estimates, not fixed calendar-day spans. Each simulated
increment replaces one historical row and its matching interval.

The snapshot retains its original quotes, missingness and preparation audit.
`--as-of` limits observation dates before model selection; it does not reconstruct
historical real-time data vintages. The future clock is an explicit regular year
fraction and does not generate a holiday/business-day calendar.

## Outputs and compatibility

The [model-output guide](../../../../RWA/Experimental/HIERARCHY/readme.md) specifies
files and dimensions. Historical exports retain `yield_parameters.csv`,
`parameter_dynamics.csv`, `RAW/`, `CURVE/` and `transition_intervals.csv`.
`initial_history.npz` preserves the complete starting `history`, matching
`history_dt`, `maturities`, `state_names` and ISO-string `dates`. Its default
history shape is `(2520, 3, 8)`. The root manifest's `files_sha256` seals this
initialization and the historical CSV exports for later verification.
Year directories contain `trajectory.csv`, `trajectory.npz`, `covariance/`,
`restart.npz` and `manifest.json`. Trajectory elapsed years are measured from the
overall forecast origin; covariance elapsed years are relative to their year
directory's start. Add the year index minus one when placing an increment archive
on the overall forecast clock. Covariance archives contain an increment NPZ
for every actual step plus a checksum index and completion manifest.

This is an incompatible simulation-output change. The former four-state ensemble
`scenarios.npz` and `scenario_summary.csv` are not current outputs. Consumers must
read the three state labels and the serial-year/step axes; they must not interpret
years as independent paths or calculate ensemble quantiles from them.

RAW/CURVE tables retain their date-keyed schemas. RAW DGS and `yield_clean` hold
the model-used values, so keep the source snapshot to distinguish original quotes
from fills. The CSV schemas alone do not identify the historical clock; retain
the root manifest and transition-interval file with downstream extracts.

## Verify a completed run

Use the portable verifier from the repository root after the run has completed:

```bash
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run
```

It checks the root and yearly file hashes, reconstructs each rolling history from
`initial_history.npz`, and verifies the family level covariances, correlations,
Cholesky factors and Brownian covariances. It replays the archived normal shocks
and ordered xi → sigma → rate updates without drawing new randomness. It also
checks the clocks, reported trajectories and continuation histories across years.
Missing, inconsistent or modified evidence fails verification.

For a deeper check, recompute every increment's conditional rate/sigma drift fits
and free-diffusion xi fit, including causal ridge anchors:

```bash
python3 src/RWA/models/parameter_hierarchy/verify.py \
  --input RWA/Experimental/HIERARCHY/my-run --recalibrate
```

Recalibration adds the fitting cost for the whole archived trajectory. Default
verification checks applied coefficients through their archived transitions;
`--recalibrate` additionally checks that they follow from the saved histories and
calibration settings. Both checks assess consistency of the recorded run. They do not establish
forecast skill or independently authenticate the original source quotes.

## Failure handling and verification

The engine limits a run segment to 1,000,000 actual increments and 20,000,000
allocated numerical elements. Window/fit work estimates describe expected effort;
they do not silently reduce the history or skip recalibrations.

Invalid or insufficient histories, unusable fits, undefined correlations,
nonfinite states and incompatible settings fail explicitly. Negative proposals
are projected and audited; mixed zero/positive histories requiring a different
likelihood can fail on the next calibration. A zero or failed state is not
silently filled. Existing destinations and paths escaping the repository are
rejected. A streamed run can retain partial evidence after failure; the relevant
completion manifest distinguishes it from a completed result.

Use the [test guide](../../../../tests/readme.md) for isolated temporary/cache
settings and the available deterministic, covariance, replay and integration
checks:

```bash
python3 -B -m unittest discover -s tests -p 'test_rwa_*.py' -v
```

Inspect the actual test results and generated run audits. Neither successful
execution nor replay proves forecast superiority, economic identification or an
arbitrage-free discount curve. Exposure cash flows, valuation conventions,
loss/risk measures and capital mapping remain downstream work.
