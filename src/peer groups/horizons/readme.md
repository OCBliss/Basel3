# Calendar-filtered peer-group panels

`Material_events_peer_group_basel3.py` combines quarterly peer-group CSVs for the horizons explicitly requested with `--horizons`.

From the repository root:

```sh
python3 "src/peer groups/horizons/Material_events_peer_group_basel3.py" --horizons 1 2 3 4 --material-dir "Material Events" --quarter-map "Material Events/quarters_basel3.csv"
```

`--horizons` accepts one or more of `1 2 3 4` and is required. The command above runs all four horizons. To run an optional subset, use `--horizons 1 3` instead. `--material-dir` defaults to this repository's `Material Events` directory. `--quarter-map` defaults to `<material-dir>/quarters_basel3.csv` and must provide the `Quarters` column.

For each selected horizon and each of Mergers, Failures and Survivors, the program reads:

```text
Material Events/<group>/Horizons/Basel III T+<h>/*.csv
```

A file is included when the final eight characters of its filename, before `.csv`, occur in `Quarters` after conversion to strings. This is a filename filter; it does not filter individual rows by `RCON9999`.

Matching files are concatenated in directory enumeration order, preserving each file's row order, repeated rows and the column union produced by pandas. Matching CSVs containing only headers still contribute their columns. There is no sorting, deduplication, membership reassignment or ratio transformation.

The resulting panel is written to:

```text
Material Events/<group>/Horizons/Peer_Group_<group>_Basel3_t<h>.csv
```

If no files match the calendar, that output is not written or replaced. Only requested horizons are processed. These panels feed the JSD binning stage.
