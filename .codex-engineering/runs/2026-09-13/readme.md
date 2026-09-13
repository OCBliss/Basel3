# Chronological RWA calibration evidence

This archive records the calibration repair that preceded the substantive
[parameter hierarchy](../2026-09-13-capability/readme.md). It includes the failing
temporal tests, revised implementation checks, real eight-tenor window comparison,
NSS diagnosis and regression logs. See [the journal](../../JOURNAL.md) for the
sequence, acceptance criteria and interpretation. Failed logs are retained as
history and are not the final result.

`validate_real_windows.py` compares current calibration with the historical
`269f948` implementation, checks both date orders, and exercises downstream
curve repair and reconstruction on isolated fixtures. Its result is
`real-windows.json`; source CSV hashes are checked. It needs the root requirements
and Git history containing that revision.

To repeat without replacing this archive, run from `Basel3_repo` and choose a new
directory at the same depth:

```bash
mkdir .codex-engineering/runs/calibration-recheck
cp .codex-engineering/runs/2026-09-13/validate_real_windows.py \
  .codex-engineering/runs/calibration-recheck/
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  .codex-engineering/runs/calibration-recheck/validate_real_windows.py
```

The script creates its scratch directory inside the new run folder. The broader
[regression commands](../../../tests/readme.md) provide explicit cache and
temporary-directory settings. Repeating against a later source revision is a
new experiment and may produce different results.
