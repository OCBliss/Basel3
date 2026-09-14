# Treasury yield acquisition and preparation

[acquire.py](acquire.py) downloads Treasury Constant Maturity yields, preserves the
source CSV and creates validated per-maturity inputs for
[interest-rate calibration and simulation](../../models/parameter_hierarchy/readme.md).
Supported maturities are 1, 2, 3, 5, 7, 10, 20 and 30 years.

## Download a new snapshot

Install the [repository requirements](../../../../requirements.txt) in your active
Python environment. Run from the repository root; the output directory must not already
exist, and all project paths must resolve inside the repository.

```bash
python3 -m pip install -r requirements.txt
python3 src/RWA/data/yields/acquire.py --help
python3 src/RWA/data/yields/acquire.py \
  --output RWA/FRED/snapshots/my-yield-snapshot \
  --start 2000-01-01 --max-fill-days 7 --max-age-days 7
```

Do not create the snapshot directory first. Each new download uses a new name;
completed snapshots and the historical `RWA/FRED/DGS*.csv` inputs are not replaced.
This is a complete snapshot download, not an incremental append to old CSVs.

| Option | Default | Meaning |
| --- | --- | --- |
| `--output` | Required | New snapshot directory inside the repository |
| `--start` | `2000-01-01` | Inclusive first permitted observation date; the model separately checks estimate-history warmups |
| `--end` | Local current date | Inclusive last permitted observation date, in `YYYY-MM-DD` form |
| `--maturities` | `1 2 3 5 7 10 20 30` | Distinct supported maturities; a subset can be requested explicitly |
| `--max-fill-days` | `7` | Maximum calendar-day separation between genuine quotes and permitted fill age; must be at least 1 |
| `--max-age-days` | `7` | Maximum calendar-day age of each tenor's last genuine quote relative to the requested end; zero is allowed |

For a fixed observation interval, add an explicit `--end YYYY-MM-DD`. That fixes
the observation cutoff, not the historical version of the data. A request with
an older end date is checked for freshness against that date, not against today.

## Transport and source

The implementation makes one HTTPS GET for all requested series to FRED's public
`https://fred.stlouisfed.org/graph/fredgraph.csv` endpoint. It sends series IDs and
date bounds, then enforces the requested date range locally because a combined
graph response can include observations outside those bounds. FRED documents
CSV downloads from its graphs in its
[download guide](https://fredhelp.stlouisfed.org/fred/data/downloading/using-the-download-data-link/).

This public CSV route requires no API key. It is separate from the
[keyed FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html),
which is not implemented here. There is no login or API-key setup command.

The downloader allows at most three attempts for connection/time-out failures,
interrupted chunked bodies, HTTP 429 and HTTP 5xx. It uses 10-second connection
and 30-second read timeouts, disables redirects and caps the downloaded body at
8 MiB. Permanent HTTP errors, HTML responses and oversized responses fail. These
are connection/read limits, not a guaranteed total runtime deadline.

## Cleaning and common history

The parser requires the requested series columns, unique valid ISO dates and
well-formed rows. It accepts an empty cell or `.` as a missing quote; arbitrary
nonnumeric tokens, infinities and nonpositive genuine quotes fail. Nonpositive
rates are rejected for compatibility with the current CIR model, not clipped
into artificial positive observations. Yield units remain percentage points.

Preparation follows this order:

1. Filter to the requested date interval and sort ascending. An observation
   outside that interval cannot supply a fill.
2. For each tenor, keep its original quotes and fill missing cells only from an
   earlier genuine quote. Record the imputation flag and that quote's date.
3. Reject a genuine-quote gap or fill that exceeds `max_fill_days`. Reject a
   tenor whose last genuine quote is too old relative to the requested end.
4. Exclude a tenor's unsupported leading rows and restrict every series to the
   earliest last-genuine-quote date across the requested maturities. No terminal
   fill pretends that all maturities were observed through a later date.
5. Record the common date range and per-tenor quality counts. Retain each tenor's
   supported earlier history before the common start when needed to causally
   fill its first common-date observation. The model inner-joins only after
   per-tenor filling.

Dates absent from the provider response are not synthesized, so weekends are not
inserted as new observations. A missing holiday cell already present in the
response can be filled within the configured limits. These source-quality limits
are independent of the model's optional calendar-time calibration clock.

## Snapshot files and provenance

| File | Contents |
| --- | --- |
| `raw/fred.csv` | Preserved downloaded CSV bytes, before local filtering or normalization |
| `series/DGS<n>.csv` | Ascending supported history for each requested tenor |
| `snapshot.json` | Completion status, retrieval timestamp, requested interval, vintage description, raw/source hashes and quality report |

The [snapshot-folder guide](../../../../RWA/FRED/snapshots/readme.md) describes
storage, reruns and the next consumer. Each prepared series has:

```text
observation_date,DGS<n>,yield_clean,is_imputed,source_date
```

`DGS<n>` preserves genuine numeric quotes and leaves source missing cells blank.
`yield_clean` carries the bounded causal fill. `source_date` identifies the actual
quote behind that value; `is_imputed` distinguishes a fill from an observation.
The original bytes are retained for exact source inspection.

Quality metadata reports common start/end and row count, first/last genuine
quotes, excluded leading/trailing rows, filled-quote counts and oldest fill age.
`snapshot.json` is written last, after all histories validate and export. A
handled publication failure removes only the new incomplete snapshot directory.
Existing output is rejected before downloading. No completion manifest means no
completed snapshot.

## Pass a verified snapshot into the model

The default model requires 2,520 aligned estimate dates **after** both calibration
warmups. Its minimum common source count is `2520 + 252 + 2520 - 2 = 5290`.
The explicit early start in the acquisition example provides a longer candidate
history; the actual usable common count is checked by the model. Acquisition's
own start setting does not guarantee sufficient calibration history. Do not pad
missing estimates or truncate the inputs below the model's full requirement.

```bash
python3 src/RWA/models/parameter_hierarchy/workflow.py \
  --input RWA/FRED/snapshots/my-yield-snapshot/series \
  --input-manifest RWA/FRED/snapshots/my-yield-snapshot/snapshot.json \
  --output RWA/Experimental/HIERARCHY/my-snapshot-model \
  --yield-window 2520 --parameter-window 252 --history-window 2520 \
  --years 1 --steps-per-year 252 --substeps 1 --seed 1234
```

To use genuine common-date quotes with historical elapsed-time calibration, add
`--time-basis act365f --missing-policy observed` to the model command. The model
reads the original `DGS<n>` values, removes missing observations and intersects
genuine dates across maturities. It leaves this snapshot and its bounded fills
unchanged. ACT/365F uses actual retained-date gaps divided by 365 days throughout
both historical calibration passes and recursive state refits. Windows count
observations or fitted dates; every simulated substep enters the rolling history
with its own year fraction. Defaults remain `observation` and `forward-fill`.

The model's scalar `--dt` is the reported future year-fraction increment (default
1/252); its product with `--steps-per-year` must equal one. Every numerical substep
recalculates dependence and calibration. ACT/365F history does not supply a future
holiday calendar. Years continue serially from the previous ending history and RNG.
The model writes exact historical intervals and elapsed forecast times in its own
[output directory](../../../../RWA/Experimental/HIERARCHY/readme.md). See the
[model guide](../../models/parameter_hierarchy/readme.md) for mathematics and limits.

`--input-manifest` verifies the complete maturity/path contract and all preserved
raw/prepared hashes, then repeats preparation from the raw bytes. Both regenerated
quality metadata and normalized CSV bytes must match the snapshot. Editing a
prepared CSV and merely updating its hash therefore fails verification.
The model records the verified snapshot's identity and quality under
`yield_acquisition` in its result manifest. This is reproducibility and consistency
verification, not cryptographic proof of the external provider's identity.

A previously acquired snapshot remains a reproducible input: verification uses
its recorded requested end, rather than silently redefining freshness as today's
date. For an updated live forecast, acquire a new snapshot. To run acquisition
and modeling together, use the [live pipeline](../../../../pipeline/rwa_live/readme.md).

## Interpretation and verification

Snapshots contain the revisions available at retrieval. `--end` or the model's
`--as-of` restricts observation dates but does not reconstruct information known
at an earlier historical date. FRED's
[real-time-period documentation](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
explains the separate vintage dimension. No historical real-time-vintage retrieval
or exposure-level duration-adjusted RWA calculation is implemented here.

Use the repository-local temporary/cache setup in the
[test guide](../../../../tests/readme.md), then run:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_yield_data.py -v
```

Tests cover causal filling and support, interval bounds, long gaps, stale quotes,
malformed responses, bounded network failures, non-overwrite behavior, path
escapes, failed-publication cleanup, provenance tampering and the real model CLI.
They use isolated fixtures rather than downloading or overwriting production data.
