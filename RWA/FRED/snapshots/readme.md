# Preserved Treasury yield snapshots

Each child directory is a separately retrieved FRED snapshot. Generated snapshots
are excluded from Git; this guide is tracked. The historical DGS files one level
above remain preserved inputs. Acquisition never overwrites an existing snapshot.

## Create a snapshot

Install [requirements](../../../requirements.txt) and run from the repository root:

```bash
python3 src/RWA/data/yields/acquire.py \
  --output RWA/FRED/snapshots/my-run \
  --start 2010-01-01 --max-fill-days 7 --max-age-days 7
```

Choose a new name and do not create that child directory beforehand. `--end`
accepts an inclusive `YYYY-MM-DD` observation cutoff and defaults to the local
current date. The source guide documents supported maturity subsets, bounded
network retries, size/time limits and freshness checks. Every model run should
record the particular snapshot it consumed, rather than selecting a directory by
its apparent recency.

## Contents and preparation

| File | Contract |
| --- | --- |
| `raw/fred.csv` | Original downloaded bytes, including observations beyond locally enforced bounds when the provider returns them |
| `series/DGS<n>.csv` | Ascending supported `observation_date,DGS<n>,yield_clean,is_imputed,source_date` history |
| `snapshot.json` | Completion marker, requested interval, retrieval time, hashes, source identities and quality counts |

Original DGS cells preserve quotes and missingness; `yield_clean` uses bounded
causal forward-fill. `source_date` names the genuine quote behind a prepared
value. Leading unsupported rows and dates beyond the common last-genuine quote
are excluded; absent provider dates are not synthesized. Freshness uses each last
genuine quote. Units remain percentage points. The manifest is written last;
handled export failure removes only the new incomplete directory. See the
[acquisition guide](../../../src/RWA/data/yields/readme.md) for exact validation,
gap bounds and failure behavior.

## Model consumer

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-run/series \
  --input-manifest RWA/FRED/snapshots/my-run/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-elapsed-run \
  --time-basis act365f --missing-policy observed \
  --yield-window 2520 --parameter-window 252 --recent-rows 3024 \
  --paths 32 --steps 10 --substeps 8
```

The model verifies hashes and regenerates preparation from raw bytes before using
the snapshot. In the optional observed/ACT/365F mode above, it fits original DGS
quotes only on genuine common dates and divides historical calendar gaps by 365
days; the preserved prepared series and their fill audit stay unchanged. Defaults
remain forward-fill and the fixed observation clock. Windows count observations,
and future `--dt` is a separate scalar year fraction. Model outputs and exact
historical intervals belong in the [model run directory](../../Experimental/HIERARCHY/readme.md).

Verification uses the snapshot's recorded observation cutoff; an old snapshot
remains reproducible but is not silently made fresh. Acquire a new snapshot for
new observations. Retrieved history contains revisions available at retrieval;
an older `--end` or model `--as-of` is not historical real-time-vintage retrieval.
Missing-date selection, measurement error and economic validity require separate
analysis. No snapshot contains exposure valuation or regulatory capital results.
