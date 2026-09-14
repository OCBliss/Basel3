# Result filtering and cohort aggregation

Install the root requirements and run commands from the repository root after their
upstream outputs exist. These scripts serve different downstream steps.

The [intragroup filter](intragroup/readme.md) is the final configured pipeline
stage. It reads pairwise JSD results and retains columns whose first-row numeric
distance is at least the threshold, writing the selected files to
`Material Events/IG/BASEL III T+<horizon>/`:

```bash
python3 src/measures/intragroup/JSD_intragroup_filter.py \
  --horizons 1 2 3 4 --bins 20 30 50 100 \
  --material-dir "Material Events" --threshold 0.3
```

The [intergroup-named script](intergroup/readme.md) concatenates the three cohort
panels for each of four horizons. It is separate from the configured pipeline
and does not itself calculate another divergence:

```bash
python3 src/measures/intergroup/JSD_intergroup_call_reports.py
```

Its inputs are `Material Events/<Group>/Horizons/Peer_Group_<Group>_Basel3_t<h>.csv`.
It writes `Material Events/IG/Call Reports/RAW/Call_Report_Basel3_t<h>.csv`.
It has no command-line selection options, runs at import, and prints missing-file
messages while continuing with available groups. Check all expected inputs before
interpreting its combined outputs. Both programs can replace selected existing
outputs; the intragroup script's guide describes its explicit selection behavior.
