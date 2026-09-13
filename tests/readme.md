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

The implementation published in `fc52dd5` passed **147 tests**. The [recorded
log](../.codex-engineering/runs/2026-09-13-capability/verified-suite.log) and
[research results](../.codex-engineering/runs/2026-09-13-capability/RESULTS.md)
separate regression evidence from empirical model assessment. Document any later
test count or result with its revision and command in the journal.
