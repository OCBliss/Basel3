# Quarterly peer groups

`Material_events_peer_group_basel3.py` writes Failures, Mergers and Survivors files for the horizons explicitly requested with `--horizons`.

From the repository root:

```sh
python3 "src/peer groups/base/Material_events_peer_group_basel3.py" --horizons 1 2 3 4 --material-dir "Material Events"
```

`--horizons` accepts one or more of `1 2 3 4` and is required. The command above runs all four horizons. To run an optional subset, use `--horizons 1 3` instead. `--material-dir` defaults to this repository's `Material Events` directory. `--input-dir` overrides the source directory, which otherwise resolves to `<material-dir>/Mergers/Call Reports`.

For each selected horizon `h`, the existing input flags determine membership:

| Output group | Row selection |
| --- | --- |
| Failures | `FAILURE_Th == 1` |
| Mergers | `MERGER_Th == 1` |
| Survivors | Neither selected flag equals `1`, after converting those two flag columns to numeric with invalid values becoming missing |

Failure and merger selections are independent. A row with both flags set appears in both event files. The survivor conversions affect only its own output copy for that horizon. The script reads each input report once and preserves all other columns, repeated rows and input row order. It uses the material-event flags already computed upstream.

Each group is written under:

```text
Material Events/<group>/Horizons/Basel III T+<h>/
```

Merger filenames remain unchanged. For Failures and Survivors, a leading `Mergers_` is replaced with the group name; other filenames receive the group prefix. Empty selections produce a CSV containing the original headers. Only requested horizons are written.

The next stage reads these quarterly CSVs and combines the files admitted by `quarters_basel3.csv`. Keeping that CSV boundary preserves the established data flow.
