# Engineering record

This directory contains the durable research and engineering history visible on
GitHub. Start with the [current checkpoint](CURRENT_TASK.md), then read the
[journal](JOURNAL.md). The journal preserves failed approaches, corrections,
acceptance criteria, tested results and unfinished work.

| Record | Purpose |
| --- | --- |
| [Git workflow](GIT_WORKFLOW.md) | Active branch, publishing, stable integration and SSH |
| [Calibration evidence](runs/2026-09-13/readme.md) | Chronology and downstream NSS compatibility |
| [Hierarchy evidence](runs/2026-09-13-capability/readme.md) | Endogenous parameter dynamics and model limitations |
| [Component organization](runs/2026-09-13-layout/readme.md) | Path migration, integration checks and documentation audit |
| [Regression commands](../tests/readme.md) | Repeat isolated verification from the repository root |

Source, tests, usage guides, journal entries and selected research evidence are
committed together at meaningful checkpoints. The initial archive includes both
real-data scenario arrays, manifests, summaries, validation scripts and failed
test logs so the results can be inspected. Temporary fixtures and caches under
each run's `tmp/` and `cache/` directories are ignored. Ad hoc hierarchy outputs
under `RWA/Experimental/HIERARCHY/` are also ignored; retain evidence for a reported
finding explicitly in a dated run folder.

All project activity stays inside `Basel3_repo`. A routine check can use the
commands in the tests guide; research reproduction commands are in each run's
README. Keep old evidence intact and use a new output directory for a new run.
Do not treat a successful implementation, a passing test suite or a small
forecast comparison as proof of economic validity or scientific novelty.
