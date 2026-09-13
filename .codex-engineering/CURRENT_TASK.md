# Current engineering checkpoint

All project work stays in Basel3_repo. Read AGENTS.md and JOURNAL.md first.

## Substantive milestone: pathwise recursive calibration

B3-20260913-03 implements path-conditioned rolling recalibration of all three
parameter-process branches and full joint innovation dependence. Source:
src/RWA/models/parameter_hierarchy/recursive.py. Both RWA YAML workflows select
recursive mode; the direct CLI retains its frozen default for compatibility.
At each selected origin, each path refits mu/theta/sigma process coefficients
and dependence from its own trailing state history before the next shock. Xi is
recomputed from the sigma branch. Simulated first-level states are preserved.

The final full suite passed 198 tests in 45.096 seconds. Twelve independent
recursive tests cover exact frozen equivalence, causal timing, path isolation,
all branches, residual equations, buffer turnover, bounds and actual CLI.
Actual latest and held-out comparisons completed using 32 paths/10 steps and
cadences 0, 1 and 5. All paths remained positive and likelihood costs stayed <=2;
per-path parameter diffusion and dependence changed. Held-out energy-score
Monte Carlo intervals include zero, so no superiority conclusion is warranted.
See runs/2026-09-13-recursive/readme.md and its original evidence. Full configured
live acquisition plus 256-path/20-step recursive validation is recorded there.
Publication verification follows in the journal; a local file is not publication.

## Completed supporting work and architecture

Commit 119b928 published live FRED retrieval, preserved raw quotes, bounded causal
cleaning, freshness checks, immutable snapshots and raw-to-clean verification.
It also established stable src/RWA domains: data, calibration and models. Source
and guides were independently retrieved from GitHub after the push/pull cycle.
Data acquisition, cleaning, guides and organization never count as the substantive
research task. They are required supporting work to anticipate and complete.

## Research context

PDF/Recursive IRR Model.pdf remains the RWA design objective. For each parameter
p in mu/theta/sigma, dp=theta_p*(mu_p-p)*dt+sigma_p*sqrt(p)*dW_p. sigma_sigma
corresponds to xi when the PDF's nu is first-pass sigma. The adaptive closure
refits these coefficients but does not add an independently simulated xi state
or reset simulated parameter states using new yield MLEs.

Preserve estimation-noise controls and likelihood/ridge findings in
runs/2026-09-13-capability/RESULTS.md. The recursive comparison uses JSD with
multiple shared bin counts and an independent frozen-sample reference, plus a
held-out proper score; do not select a favorable bin count or equate stochastic
variation with improved economic identification.

Next work must choose and finish another substantive analytical/model capability
from the PDF and evidence. Candidates include measurement-error/elapsed-time-aware
parameter dynamics, stronger held-out recursive evaluation, or exposure/cash-flow
valuation. Acquisition showed that filling changes ten-year zero-increment mass
from 7.76% to 11.56%; dropping rows alone also creates irregular intervals. Keep
missingness distinguishable and do not label an observation cutoff as historical
real-time-vintage data.

## Standing execution and schedule

Research, hypothesize, implement, compare alternatives, validate, harden, document,
commit/push immediately, pull and review globally. Main is the active branch;
GitHub SSH works. Preserve source data and concurrent user edits. Add new source
components within the responsible existing domain instead of one top folder per
task. The sole existing schedule was verified ACTIVE every two hours, with its
next run stored around 17:01 PDT on 2026-09-13 at inspection. Preserve subsequent
user schedule changes; never restore obsolete daily settings or create duplicates.
