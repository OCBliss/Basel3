# Downloaded FFIEC schedules

The Call Report preparation stage downloads and extracts quarterly single-period
archives into `FFIEC CDR Call Bulk All Schedules YYYYMMDD/` directories here.
The TXT schedules are generated local inputs and are excluded from Git.

From the repository root:

```bash
python3 "src/call reports/prepare_call_reports.py" --plan
python3 "src/call reports/prepare_call_reports.py"
```

The first command lists required quarters; the second retrieves and verifies
them. ZIP caches and per-quarter checksums are written under `data/FFIEC/`.
The subsequent [conversion stage](../../src/call%20reports/readme.md) reads these
TXT files and uses the POR schedule to attach FDIC certificate numbers.

The two tracked quarterly README files preserve FFIEC notices from historical
exports. Their processing timestamps describe those exports, not the vintage
of a new download. Consult the newly generated preparation manifest and file
checksums for the data used by a current run. See the [data guide](../readme.md)
for refresh and cache behavior.
