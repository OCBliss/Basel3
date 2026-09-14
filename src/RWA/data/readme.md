# Interest-rate data

This domain owns external observations and the preparation of consistent tables
for analytical consumers. Data handling is kept separate from calibration
algorithms and stochastic models.

| Component | Responsibility | Instructions |
| --- | --- | --- |
| `yields/` | Yield acquisition, validation and preparation | [Yield-data guide](yields/readme.md) |
| `parameters/` | Reconstruct per-maturity histories from date-aligned parameter curves | [Parameter-data guide](parameters/readme.md) |

Start with the yield-data guide for source settings, refresh behavior, cleaning,
provenance and output locations. Historical observations in `RWA/FRED` remain
separate from new acquisition runs. A local CSV is not evidence that it is
current or came from a reproducible download. The model can use genuine
common-date quotes and ACT/365F historical gaps while preserving the snapshot
preparation and imputation audit. The [yield-data guide](yields/readme.md) explains
how that optional policy differs from the reproducible forward-fill default.

Parameter reconstruction reads the established RAW yield files, NSS-repaired mu
and theta, and the corresponding sigma curves. From the repository root, after
installing [requirements](../../../requirements.txt) and completing the input
stages, its command is:

```bash
python3 src/RWA/data/parameters/rebuild.py
```

That command replaces its configured legacy output files, joins on unique dates
and preserves unmatched values as missing. Follow the component guide before
running it; reconstruction is not a statistical fit or validation of repaired
parameters.

Prepared yield data is consumed by [calibration](../calibration/readme.md) and
[models](../models/readme.md). Keep raw sources, cleaned observations, estimated
parameters and simulated trajectories distinguishable by their schema and provenance.
No data component calculates exposure-level losses or duration-adjusted RWA.
