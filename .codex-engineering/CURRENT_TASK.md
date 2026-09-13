# Active capability checkpoint

Read this file and JOURNAL.md before continuing. All project activity stays inside
/Users/johnnywaller/Desktop/Basel_III/Basel3_repo. Preserve existing local edits.

## Status

- B3-20260913-02: PDF-aligned endogenous parameter-process hierarchy.
- COMPLETED selected parameter-hierarchy milestone. Implemented and verified:
  three second-pass parameter branches, coupled ridge regularization, joint
  stochastic-parameter forecast baseline, and an estimation-noise benchmark.
  The full PDF remains unfinished: no pathwise recalibration or RWA valuation yet.
- Latest verification: 147 tests passed in 41.384 s. See the completion entry in
  JOURNAL.md and runs/2026-09-13-capability/RESULTS.md for evidence and limitations.
- The previous B3-20260913-01 calibration repair is completed and recorded in the
  journal; preserve it. Historical starting revision was 269f9487975d03e93bdea3b869785258e4972da5
  on refactor. Both completed milestones are now committed and published on main
  in fc52dd58fbc23062bb5d47b974fb18088aaae836.

## Governing user clarification

The four-page PDF/Recursive IRR Model.pdf describes the ultimate RWA objective.
Read the existing code as part of that design. The first calibration already
produces chronological mu, theta, sigma estimates for each maturity. Heal ridge
conditions across the maturity panel before learning higher-order dynamics.
Apply the same rolling estimation process to EACH estimated parameter series,
mu, theta, sigma, producing volatility of mu, volatility of theta, and volatility
of sigma endogenously. The existing experimental sigma-only second pass is an
implementation starting point, not evidence that this hierarchy is absent.

Notation to maintain: X is the observed yield/rate state in the existing code;
mu is its fitted mean level, itself a time-varying parameter series under this
extension. For p in {mu, theta, sigma}, the second pass produces (theta_p, mu_p,
sigma_p). Its model is dp = theta_p*(mu_p-p)*dt + sigma_p*sqrt(p)*dW_p.
For the sigma process, sigma_sigma supplies the xi diffusion coefficient in the
paper's volatility equation when nu is identified with first-pass sigma. The
conditional increment variance is sigma_p^2*p*dt, not merely sigma_p^2.
The two other second-pass diffusion coefficients describe stochastic drift
parameters; they must not all be called one xi or collapsed together.

## Evidence and coverage

- All four PDF pages extracted to runs/2026-09-13-capability/model.txt; pages 2-4
  visually inspected from the rendered PNGs in that same evidence directory.
- Fully read src/RWA/quasi-MLE-Euler.py and CMT_data_parameters_rebuild.py;
  inspected both NSS fit/repair paths and their maturity thresholds. Existing
  repair scripts assess all eight maturity columns, using separate mu>9 and
  theta<0.01 triggers; positivity guards do not resolve identification.
- Fully read RWA/Experimental/RWA_Heston_MLE_vol_test.py. It applies the same
  Gaussian Euler CIR likelihood to sigma and emits theta_vol, mu_vol, vol_vol.
  It still has legacy CODE-path lookup, chronology/fill/window limitations, and
  runs at import. Do not execute it directly against historical outputs.
- Rebuild joins repaired mu/theta plus unmodified sigma curves into per-tenor
  files with observation_date, DGS column, yield_clean, theta, mu, sigma.
- Earlier coverage: legacy yield script, four Practical scripts, default pipeline
  manager. Broad Call Report/JSD coverage is partial, not a full-codebase reading.

## Research obligations for implementation

1. Preserve first-pass raw estimates, identify ridge severity, and validate any
   repair against observed transition likelihood/drift/diffusion. Jointly assess
   mu/theta so smoothing them separately does not silently alter theta*mu.
2. Generalize the sigma-only second pass to all three parameter series and all
   maturities using causal aligned histories, explicit warmup and diagnostics.
3. Separate apparent parameter volatility arising from rolling-window estimation
   and repair transitions from evidence for stochastic parameter dynamics. Use
   synthetic constant-parameter and time-varying-parameter controls.
4. Specify hierarchy depth/closure. A second pass estimates xi; it does not alone
   specify an additional independent stochastic process for xi itself. Reapply
   the estimator if another level is intended, with a finite stopping rule.
5. Correlate innovations across tenors and parameter processes. Jointly simulating
   X, mu, theta, sigma requires a 4d-dimensional driving-noise representation
   (32 components for eight tenors), before any extra xi-state extension.
6. Resolve PDF left-point Euler equations versus page-4 updated-coefficient prose.
   Correlated contemporaneous coefficients introduce drift terms; derive and test
   the chosen convention. Correlation estimates must be available before shocks.
7. Per-path recursive recalibration, numerical boundaries, failure handling,
   performance, meaningful held-out comparisons, and eventual valuation/RWA
   mapping remain necessary downstream work, not completed capabilities.

## Completed implementation and next action

Implemented source: src/RWA/cir_hierarchy.py and parameter_hierarchy.py, with
parameter_hierarchy.md specifying the mathematics and finite hierarchy closure.
The standalone pipeline configuration is pipeline/pipeline_config_rwa_hierarchy.yaml.
The existing calibration/NSS/rebuild scripts and default Call Report/JSD pipeline
remain intact. Source exports were tested through the actual rebuild consumer;
the actual manager executed the new config on isolated fixtures.

Read runs/2026-09-13-capability/RESULTS.md before selecting further work. Key
findings: 16 constant-parameter benchmark replicates generated larger apparent
sigma volatility than the observed 7/10/20/30-year coefficients; fixed-parameter
synthetic controls generated substantial mu/theta volatility; held-out forecasts
were effectively tied with fixed parameters. Regularization is useful for a
conditional executable model but does not identify latent economic dynamics.

There is no unfinished implementation within this completed milestone. The next
scheduled run should advance the RWA PDF with one substantive milestone: assess
estimation-noise-aware parameter dynamics versus pathwise recursive calibration
using the preserved baseline and evidence. Do not treat completion of this
finite hierarchy as completion of the whole PDF. Preserve all source edits and
archived evidence, and use a new output directory for any repeated CLI run.

## Method selection standard from the user

Do not default to industry convention or low-order moment statistics. Trace the
research purpose and existing analytical methods first, including the repository's
JSD comparison of failure/merger/survivor ratio distributions across horizons and
bin specifications. Conditional moment checks validate a simulator, not its
economic model. Assess distributional shape, tails, dependence and regime behavior
where relevant; choose and validate methods accordingly. JSD is an informed
candidate for RWA distributional checks, not an automatic universal metric. Read
the latest journal clarification before choosing the next research milestone.

## Current Git workflow

The user has authorized regular commits, fetches, pushes and branch integration.
Work on main and publish coherent verified checkpoints so GitHub reflects progress.
All existing refactor commits, including the remote LICENSE.md deletion, have
been integrated into main. Transfer subsequent stable verified milestones back
to refactor using the workflow in GIT_WORKFLOW.md, then return to main. Read
AGENTS.md at the repository root before continuing. The current Mac has a working
repository-local SSH identity selection; fetching and pushing main were verified.
