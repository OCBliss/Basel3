# Regression checks

Run from `Basel3_repo` with the [project requirements](../requirements.txt)
installed in the active Python environment. Tests use `unittest`; SciPy is needed
for the independent optimizer and existing RWA calibration checks.

Keep test temporary files and caches inside this repository:

```bash
mkdir -p .codex-engineering/runs/local-check/tmp
mkdir -p .codex-engineering/runs/local-check/cache/matplotlib
export TMPDIR="$PWD/.codex-engineering/runs/local-check/tmp"
export XDG_CACHE_HOME="$PWD/.codex-engineering/runs/local-check/cache"
export MPLCONFIGDIR="$XDG_CACHE_HOME/matplotlib"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -v
```

For a focused RWA check, use the same environment:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_calibration.py -v
python3 -B -m unittest discover -s tests -p test_rwa_hierarchy.py -v
```

The suite covers Call Report preparation and ratios, material events, peer
groups, binning, PMFs, JSD, filtering, task-manager execution, chronological RWA
calibration and the new parameter hierarchy. RWA checks include independent
likelihood comparisons, causality, ridge budgets, all maturity/parameter branches,
joint simulation, numerical boundaries and actual downstream file consumers on
isolated fixtures. Test success does not establish the economic model's validity.

The RWA checks also verify the component layout under `src/RWA`: the yield
calibrator, curve repairs and parameter rebuild resolve the same repository data
root, and the hierarchy works both as a Python module and as a script invoked
from another directory. The manager test reads the real hierarchy YAML, checks
its relocated script target and runs it against isolated inputs.

The implementation published in `fc52dd5` passed **147 tests**. The [recorded
log](../.codex-engineering/runs/2026-09-13-capability/verified-suite.log) and
[research results](../.codex-engineering/runs/2026-09-13-capability/RESULTS.md)
separate regression evidence from empirical model assessment. Document any later
test count or result with its revision and command in the journal.

The [component-organization checkpoint](../.codex-engineering/runs/2026-09-13-layout/readme.md)
passed **149 tests** after relocation, including the two additional entry-point
and shared-data-root checks. Its recorded log covers the full repository suite.


The yield-acquisition milestone adds 37 tests for parser failures, gap/freshness
rules, bounded HTTP behavior, immutable output, verified raw-to-clean provenance
and the actual model CLI. The complete suite passed **186 tests**; the live manager
also completed acquisition through simulation. See the
[acquisition evidence](../.codex-engineering/runs/2026-09-13-yield-acquisition/readme.md).


The recursive engine adds 12 independent tests and brings the full suite to
**198 passing tests**. They check exact frozen-mode equivalence, each path's
causal history, rolling-window replacement, all parameter branches, correlation
inputs, resource guards and the actual CLI. See the
[recursive evidence](../.codex-engineering/runs/2026-09-13-recursive/readme.md).
