# JSD binning

`Material_events_JSD_binning_basel3.py` replaces the four binning scripts. It reads the selected peer-group horizon files and produces a separate histogram for each group, horizon, and selected central bin count.

Run from the repository root:

```bash
python3 src/jsd/binning/Material_events_JSD_binning_basel3.py \
  --horizons 1 2 3 4 --bins1 20 30 50 100 --bins2 5 --bins3 1 \
  --material-dir "Material Events"
```

`--horizons` and `--bins1` are required. Any selection of horizons 1–4 is supported. `--bins1` accepts one or more positive central bin counts; `--bins2` defaults to 5, and `--bins3` accepts only 1 for the final unbounded interval.

The pipeline YAML defaults to all four horizons and all four original central bin counts, as shown above. A smaller selection, such as `--horizons 1 3`, is optional.

## Inputs and outputs

For each of Mergers, Failures, and Survivors, the input is:

`Material Events/{Group}/Horizons/Peer_Group_{Group}_Basel3_t{horizon}.csv`

The first two columns remain excluded as the bank and reporting-quarter keys. Each remaining column is converted to numeric values; missing or nonnumeric values are omitted from that column's histogram.

Outputs retain the existing filenames:

`Material Events/{Group}/JS Divergence/Basel III T+{horizon}/Binned/Peer_Group_{Group}_Basel3_t{horizon}_binned_{bins1}.csv`

Only selected horizons and bin counts are processed. A missing selected peer file is an error. The filename identifies the central bin count; changing `--bins2` updates that selected output rather than creating another filename.

## Three coverage areas and boundary behavior

The three areas remain the central range from −1 to 1, the range from 1 to 2, and one unbounded upper interval. With `--bins2 5 --bins3 1`, the total rows are:

| Central bins | Total bins |
|---|---|
| 20 | 26 |
| 30 | 36 |
| 50 | 56 |
| 100 | 106 |

The original scripts repeated the edge at 2, producing an extra `[2.00, 2.00)` row. Complete runs of all four original scripts confirmed that row was zero in every column of all 48 outputs. The consolidated script removes this duplicate edge only.

Existing `numpy.histogram` endpoint placement is retained: exactly 1 enters the first interval starting at 1; exactly 2 enters the final interval starting at 2. The final label is now `[2.00, inf)` so it describes the retained placement instead of the original `> 2.00` label. Assigning exactly 2 to the preceding interval would be a separate change to counts and is not included here.

Across the complete local verification inputs, every count remained identical after deleting the empty row and updating the final label. Histogram mass, ratio-column order, group separation, and output filenames are unchanged. The following PMF stage retains the same bin labels and normalizes each ratio column independently.
