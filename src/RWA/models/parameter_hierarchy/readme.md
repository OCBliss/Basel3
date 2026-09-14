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

## Guide contents

- [State factors and fitted coefficient names](#state-and-coefficient-names)
- [Historical initialization and the 2,520-row window](#historical-initialization-estimates-need-their-own-warmup)
- [Every-increment dependency and update order](#every-increment-calculation)
- [Covariance calculation for all eight maturities](#covariance-calculation-for-all-eight-maturities)
- [Cholesky calculation](#cholesky-calculation)
- [Brownian covariance and the shock transformation](#brownian-covariance-and-the-shock-transformation)
- [Repairing each factor at every tenor](#repairing-each-factor-at-every-tenor)
- [Calibration and coupled ridge treatment](#calibration-and-coupled-ridge-treatment)
- [Run commands](#run-from-the-repository-root), [saved outputs](#outputs-and-compatibility) and [verification](#verify-a-completed-run)

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

Here **state factor** means one maturity-indexed rate, sigma or xi process.
The eight tenor components within a family are the variables whose covariance
is estimated. These factors are distinct from the numerical Cholesky factor L,
which is a matrix used to transform shocks. Historical `mu` (μ, long-run mean),
`theta` (θ, mean-reversion speed) and fitted `sigma` are calibration outputs;
their names do not create extra latent-factor families. Each recursive state's
fresh drift fit likewise has a speed and long-run mean, while its actual diffusion
multiplier follows the ordered higher-state dependency below.

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

[Covariance estimation](covariance.py) works on the current history with default
shape `(2520, 3, 8)`. The three families are rate (PDF X), sigma (PDF ν) and xi
(PDF ξ). Every family uses this exact maturity order on **both** matrix axes:

| Matrix position | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Treasury maturity in years | 1 | 2 | 3 | 5 | 7 | 10 | 20 | 30 |

Each actual increment recreates three separate 8×8 level covariance matrices C,
three 8×8 correlations R, three 8×8 Cholesky factors L, and three 8×8 Brownian
covariances Q. The two covariance sets are **{C_rate, C_sigma, C_xi}** and
**{Q_rate, Q_sigma, Q_xi}**. A Cholesky factor is not an additional covariance.
Each C or Q stores all 64 entries, with eight entries in each maturity row;
symmetry relates pairs of entries but does not change the stored 8×8 shape.
Together the two covariance sets contain six matrices, or 384 stored entries.

| Archive array | Meaning and default shape |
| --- | --- |
| `factor_covariance` | Rolling sample level covariances C; `(3,8,8)` |
| `raw_correlation` | C normalized by its marginal standard deviations; `(3,8,8)` |
| `correlation` | R actually used to correlate shocks; `(3,8,8)` |
| `cholesky` | Lower-triangular L satisfying LLᵀ = R; `(3,8,8)` |
| `brownian_covariance` | Conditional Brownian-increment covariances Q = hR; `(3,8,8)` |
| `normal_shocks` | Three independent standard-normal eight-vectors; `(3,8)` |
| `brownian_increments` | Three realized transformed eight-vectors; `(3,8)` |

### Covariance calculation for all eight maturities

Let $f\in\{\mathrm{rate},\mathrm{sigma},\mathrm{xi}\}$ denote one family, and let
$Y^{(f)}_{s,i}$ be its history value at row $s$ and maturity position $i$.
There are $n=2520$ rows by default. The initial rows are the aligned historical
states; each completed increment replaces the oldest row with the new simulated
states. All calculations below use the current buffer **before the next shock**.
Historical calibration and any accepted parameter repairs establish sigma and xi
history before it enters this calculation. Rate history retains the model-used
source yields; a parameter repair does not rewrite those historical rate quotes.
At a recursive increment, C describes the already available state buffer; refitting
its coefficients does not retroactively replace the buffered states.

For every $i,j\in\{1,2,3,4,5,6,7,8\}$, compute the sample mean and covariance:

$$
\bar Y^{(f)}_i=\frac{1}{n}\sum_{s=1}^{n}Y^{(f)}_{s,i},\qquad
C^{(f)}_{ij}=\frac{1}{n-1}\sum_{s=1}^{n}
\left(Y^{(f)}_{s,i}-\bar Y^{(f)}_i\right)
\left(Y^{(f)}_{s,j}-\bar Y^{(f)}_j\right).
$$

The divisor is **n−1** (`ddof=1`). The sample mean above centers the covariance;
it is not the fitted CIR long-run mean μ. These are covariances of state
**levels**, with one equal-weight row per retained observation or increment.
They are not covariances of pooled innovations or time-weighted increments.
Historical transition lengths enter CIR calibration separately.

For each of the three families, the complete matrix has the following layout
(the family superscript is suppressed only to keep the entries readable):

$$
C=\begin{bmatrix}
C_{11}&C_{12}&C_{13}&C_{14}&C_{15}&C_{16}&C_{17}&C_{18}\\
C_{21}&C_{22}&C_{23}&C_{24}&C_{25}&C_{26}&C_{27}&C_{28}\\
C_{31}&C_{32}&C_{33}&C_{34}&C_{35}&C_{36}&C_{37}&C_{38}\\
C_{41}&C_{42}&C_{43}&C_{44}&C_{45}&C_{46}&C_{47}&C_{48}\\
C_{51}&C_{52}&C_{53}&C_{54}&C_{55}&C_{56}&C_{57}&C_{58}\\
C_{61}&C_{62}&C_{63}&C_{64}&C_{65}&C_{66}&C_{67}&C_{68}\\
C_{71}&C_{72}&C_{73}&C_{74}&C_{75}&C_{76}&C_{77}&C_{78}\\
C_{81}&C_{82}&C_{83}&C_{84}&C_{85}&C_{86}&C_{87}&C_{88}
\end{bmatrix}\in\mathbb R^{8\times8}.
$$

The diagonal entries are the eight level variances. Each off-diagonal entry is
the covariance between the two labelled maturities. Normalize with the diagonal
matrix of standard deviations:

$$
D^{(f)}=\operatorname{diag}\!\left(\sqrt{C^{(f)}_{11}},\sqrt{C^{(f)}_{22}},
\sqrt{C^{(f)}_{33}},\sqrt{C^{(f)}_{44}},\sqrt{C^{(f)}_{55}},
\sqrt{C^{(f)}_{66}},\sqrt{C^{(f)}_{77}},\sqrt{C^{(f)}_{88}}\right),
$$

$$
R^{(f)}_{\mathrm{raw}}=(D^{(f)})^{-1}C^{(f)}(D^{(f)})^{-1},\qquad
R^{(f)}_{\mathrm{raw},ij}=\frac{C^{(f)}_{ij}}{\sqrt{C^{(f)}_{ii}C^{(f)}_{jj}}}.
$$

Each correlation matrix has diagonal one. The implementation assigns that
diagonal exactly after normalization to remove floating-point roundoff.
`--correlation-regularization 0` uses this empirical correlation unchanged.
If an alpha in `(0,1]` is explicitly requested, the matrix actually factored is

$$
R^{(f)}=(1-\alpha)R^{(f)}_{\mathrm{raw}}+\alpha I_8.
$$

At the default $\alpha=0$, $R^{(f)}=R^{(f)}_{\mathrm{raw}}$. The archive retains
the unchanged C, raw correlation and chosen alpha. This adjustment is explicit;
it does not recover missing information. Zero-variance columns fail because
normalization is undefined. Rank-deficient empirical correlations fail by
default; unusable Cholesky factors also fail explicitly.

### Cholesky calculation

For **each family separately**, calculate the lower-triangular 8×8 matrix
$L^{(f)}$ satisfying

$$
L^{(f)}(L^{(f)})^{\mathsf T}=R^{(f)}.
$$

The entrywise Cholesky–Banachiewicz recurrence is, for $j=1,2,3,4,5,6,7,8$:

$$
L^{(f)}_{jj}=\sqrt{R^{(f)}_{jj}-\sum_{k=1}^{j-1}(L^{(f)}_{jk})^2},
$$

$$
L^{(f)}_{ij}=\frac{R^{(f)}_{ij}-\sum_{k=1}^{j-1}L^{(f)}_{ik}L^{(f)}_{jk}}
{L^{(f)}_{jj}},\qquad i=j+1,\ldots,8,
$$

$$
L^{(f)}_{ij}=0\quad\text{for }i<j.
$$

The empty sum at $j=1$ is zero. Each positive diagonal pivot is calculated
before the entries below it; later columns subtract products already accounted
for by earlier columns. All three full factors have this 8×8 layout:

$$
L=\begin{bmatrix}
L_{11}&0&0&0&0&0&0&0\\
L_{21}&L_{22}&0&0&0&0&0&0\\
L_{31}&L_{32}&L_{33}&0&0&0&0&0\\
L_{41}&L_{42}&L_{43}&L_{44}&0&0&0&0\\
L_{51}&L_{52}&L_{53}&L_{54}&L_{55}&0&0&0\\
L_{61}&L_{62}&L_{63}&L_{64}&L_{65}&L_{66}&0&0\\
L_{71}&L_{72}&L_{73}&L_{74}&L_{75}&L_{76}&L_{77}&0\\
L_{81}&L_{82}&L_{83}&L_{84}&L_{85}&L_{86}&L_{87}&L_{88}
\end{bmatrix}\in\mathbb R^{8\times8}.
$$

The implementation calls `numpy.linalg.cholesky(R)` for this factorization;
it does not maintain a separate handwritten recurrence. The archive records
all three resulting factors. They are recreated from the current history before
every increment, including the first increment and every substep, before new
normal vectors are drawn. No pooled cross-family factor is estimated or applied.

### Brownian covariance and the shock transformation

For each family draw an eight-component column vector
$z^{(f)}\sim\mathcal N(0,I_8)$. The three normal vectors are independent. With
actual increment length $h=dt/\mathrm{substeps}$ in years, apply the factor once:

$$
\Delta W^{(f)}=\sqrt h\,L^{(f)}z^{(f)},\qquad
\Delta W^{(f)}_i=\sqrt h\sum_{j=1}^{i}L^{(f)}_{ij}z^{(f)}_j,
\quad i=1,2,3,4,5,6,7,8.
$$

Conditioning on the rolling history that produced L gives

$$
Q^{(f)}=\operatorname{Cov}(\Delta W^{(f)}\mid\text{current history})
=hL^{(f)}I_8(L^{(f)})^{\mathsf T}=hR^{(f)}\in\mathbb R^{8\times8}.
$$

Thus every Brownian marginal has variance h, while each off-diagonal entry is
$Q^{(f)}_{ij}=hR^{(f)}_{ij}$. Each **realized** $\Delta W^{(f)}$ is an eight-vector;
its conditional covariance Q is the full 8×8 matrix. C has the squared units of
its state family, R is dimensionless, and Q has units of elapsed years.

The model uses level correlations as its cross-maturity Brownian dependence
assumption. It factors the unit-diagonal R because the SDE separately supplies
the diffusion magnitude: xi's fitted diffusion, new xi for sigma, and new sigma
for rate, each multiplied by the square root of the receiving state. Factoring
C in this shock transformation would also inject historical level standard
deviations into those SDE amplitudes, double-counting a scale the stated model
does not put into its Brownian drivers. Q therefore describes the drivers before
state-dependent multipliers; it is not the covariance of the final state changes.

After dependence is refreshed, every increment also fits xi's free-diffusion
CIR coefficients and rate/sigma drifts conditional on their known varying
higher-state histories. The [ordered update](#every-increment-calculation) then
advances **xi → sigma using new xi → rate using new sigma** with the newly
transformed shocks. Those results enter the next rolling covariance and refit
window. Independent Gaussian families follow the PDF's independent-Z equations;
no additional nonzero instantaneous cross-family rho is imposed. The nonlinear
higher-state multipliers still couple the evolving families.

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

### Repairing each factor at every tenor

All eight columns—**1, 2, 3, 5, 7, 10, 20 and 30 years**—are fitted before
weak-node repair targets are selected. These are per-tenor marginal or conditional
Euler likelihood fits with cross-tenor repair anchors. The covariance calculation
is separate; the estimator is not a full multivariate joint likelihood.

| Stage, across all eight tenors | Estimated quantities | Action for a weak tenor |
| --- | --- | --- |
| First historical pass on yields | Each tenor's μ, θ and σ | Reprofile the mean and diffusion together at an admissible anchored speed |
| Second pass on the entire μ history | Speed, long-run mean and diffusion of μ | Apply the same coupled free-diffusion repair within this branch |
| Second pass on the entire θ history | Speed, long-run mean and diffusion of θ | Apply the same coupled free-diffusion repair within this branch |
| Second pass on the entire σ history | Speed, long-run mean and diffusion of σ; its diffusion initializes xi history | Apply the same coupled free-diffusion repair within this branch |
| Every increment: rate family | Speed and long-run mean conditional on sigma history | Reprofile drift while holding the known varying sigma history and transition variances fixed |
| Every increment: sigma family | Speed and long-run mean conditional on xi history | Reprofile drift while holding the known varying xi history and transition variances fixed |
| Every increment: xi family | Speed, long-run mean and free diffusion | Reprofile the mean and diffusion together at an admissible anchored speed |

For each panel, [core.py](core.py) applies the following procedure:

1. Fit every tenor and diagnose a weak speed when θ is below `1e-4` per year
   or no greater than its local regression standard error. Healthy fits remain
   unchanged. A deterministic/unidentified free-diffusion history remains flagged.
2. Sort healthy tenor nodes by maturity and interpolate **log θ against log
   maturity** to propose each weak node's speed. This covers every weak maturity,
   including the 1-year and 30-year endpoints. Outside the healthy-node span,
   `numpy.interp` uses the nearest healthy endpoint speed; it does not extrapolate
   a new slope. One healthy node supplies its speed to all weak targets.
3. If every node is weak, use that tenor's prior calibrated speed. At the first
   fit without a prior, use `--fallback-theta` (default 0.25 per year). These
   fallback sources remain explicit in the audit.
4. Refit at the proposed speed. For a free-diffusion fit, this profiles the drift
   intercept a = θμ, hence μ, and residual diffusion σ together. For a conditioned
   fit, it profiles the intercept and μ while keeping the supplied higher-state
   history and its variances fixed. This preserves the coefficient relationship
   used by that tenor's own transition likelihood.
5. Accept the target only when its negative-log-likelihood increase is at most
   `--nll-budget` (default 2.0). Otherwise, perform **45 bisection iterations**
   along the segment from the raw optimum's speed toward the target, retaining
   an admissible profiled candidate. A target is not forced through the budget.
6. Preserve raw estimates, the target, anchor source, accepted change, likelihood
   cost and usability diagnosis. The original weak flag survives an accepted
   repair: regularization does not demonstrate that identification was recovered.

This is **log-linear tenor anchoring with coupled likelihood profiling**. It does
not independently smooth μ, θ and σ or claim improved forecast performance.
The standalone legacy [mu NS/NSS repair](../../calibration/curves/mu.py) and
[theta NS/NSS repair](../../calibration/curves/theta.py), documented in the
[curve-repair guide](../../calibration/curves/readme.md), are separate commands.
They are not invoked by this recursive workflow, and there is no separate NSS
repair of sigma in the current model.

Parameter healing and correlation conditioning act on different objects. The
repair above changes fitted coefficients subject to their likelihoods; it does
not rewrite historical raw rates or smooth the 64 entries of C. The explicit
correlation alpha changes R before Cholesky while retaining raw C and R. Alpha
is zero by default: there is no automatic matrix repair. Undefined variances,
invalid factors or unusable accepted coefficients fail rather than becoming
silently replaced observations or simulated states.

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
