# Outcome cohorts and observation horizons

Run these stages after the material-event flagging stages, from `Basel3_repo`
with the root requirements installed:

```bash
python3 "src/peer groups/base/Material_events_peer_group_basel3.py" \
  --horizons 1 2 3 4 --material-dir "Material Events"
python3 "src/peer groups/horizons/Material_events_peer_group_basel3.py" \
  --horizons 1 2 3 4 --material-dir "Material Events"
```

The [base stage](base/readme.md) selects quarterly Failures, Mergers and Survivors
using the corresponding future-event flags. It writes quarterly files into each
group's `Horizons/Basel III T+<h>/` directory. Failure and merger flags can overlap;
the code does not make them mutually exclusive.

The [horizon stage](horizons/readme.md) selects quarter files using
`Material Events/quarters_basel3.csv` and produces one concatenated panel per
group/horizon under `Material Events/<Group>/Horizons/`. Those panels feed
[JSD](../jsd/readme.md). Existing selected output files can be replaced on rerun.
Use the same horizon selection throughout, or set it once in the
[pipeline YAML](../../pipeline/readme.md).
