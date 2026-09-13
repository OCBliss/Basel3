# Current engineering checkpoint

All project work stays in Basel3_repo. Read AGENTS.md and JOURNAL.md first.

## Completed supporting work

Verified live yield acquisition through parameter simulation. The user explicitly
clarified that acquisition, cleaning and documentation never count as the
substantive research task. These are completed prerequisites.
Implemented FRED HTTPS retrieval, preserved raw quotes, bounded causal cleaning,
genuine-quote freshness, immutable snapshots and raw-to-clean provenance checks.
The actual pipeline/rwa_live/config.yaml connects retrieval to the hierarchy.
Live run: eight tenors, 4,354 common rows through 2026-09-10, 4,040 first-pass and
6,096 second-pass rows, 256 paths/20 steps. All 186 tests passed in 44.087 seconds.
See runs/2026-09-13-yield-acquisition/readme.md for evidence and reproduction.
Publication verification follows in the journal. Active substantive task:
implement pathwise recursive recalibration of mu/theta/sigma dynamics and joint
dependence, validate it against the frozen engine, and publish it in this run.

## Stable architecture

src/RWA has three domains: data, calibration and models. Data owns yields and
parameter reconstruction; calibration owns yield estimates and NS/NSS repair;
models owns the parameter hierarchy and simulation. Add components under their
responsible domain instead of a new top-level folder for each task. One README
per component; update imports, YAML, consumers and tests when moving code.

## Research context and next substantive work

The PDF/Recursive IRR Model.pdf remains the RWA design objective. The existing
finite hierarchy learns mu/theta/sigma histories across maturities, heals ridge
conditions jointly, then fits a second CIR process to each parameter branch.
For each p, dp=theta_p*(mu_p-p)*dt+sigma_p*sqrt(p)*dW_p. sigma_sigma corresponds
to xi when the PDF's nu is identified with first-pass sigma. Estimated parameter
volatility includes estimation noise; preserve the controls and findings in
runs/2026-09-13-capability/RESULTS.md. JSD/distributional reasoning is part of the
repository methodology; choose alternatives using evidence, not convention.

The completed acquisition run adds evidence that causal filling changes the
increment distribution: ten-year zero changes 11.56% versus 7.76% with missing rows
dropped; square-root JSD about 0.0455. Dropping rows alone also creates irregular
elapsed-time transitions. Explicit interval/imputation-aware estimation is a
substantive next candidate alongside estimation-noise-aware parameter dynamics
and the PDF's pathwise recursive calibration. Choose and finish one coherent
capability after reading complete execution paths and prior evidence.

Current model closure freezes second-level coefficients at forecast origin.
Exposure valuation and RWA capital mapping are downstream milestones. New snapshots
contain current-revision data; an observation cutoff is not a historical vintage.
Do not state that FRED's historical DGS30 download has a multi-year missing gap:
the inspected response contains 994 numeric quotes during the noted discontinuation.
See the preserved raw response and corrected research finding.

## Standing execution and schedule

Research, hypothesize, implement, compare alternatives, validate, harden, document,
commit/push immediately, pull and review globally. The current main is the active
branch; GitHub SSH works. Preserve source data and concurrent user edits.
The existing schedule was verified ACTIVE every two hours, with next run stored
around 17:01 PDT on 2026-09-13 at inspection. Preserve subsequent user schedule
changes; do not restore earlier daily settings or create a duplicate schedule.
