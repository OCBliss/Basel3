# Convert selected binned counts to PMFs

`Material_events_JSD_probabilities_basel3.py` normalizes histogram counts for explicitly selected horizons and central bin counts.

Run from the repository root:

```bash
python3 src/jsd/pmf/Material_events_JSD_probabilities_basel3.py \
  --horizons 1 2 3 4 --bins 20 30 50 100 --material-dir "Material Events"
```

Both `--horizons` and `--bins` are required. `--horizons` selects values from 1–4; `--bins` selects the positive central bin counts represented by `_binned_{count}.csv` filenames.

The pipeline YAML defaults to all four horizons and all four original bin specifications. Smaller selections are optional.

For each selected horizon and each of Mergers, Failures, and Survivors, input files are read from:

`Material Events/{Group}/JS Divergence/Basel III T+{horizon}/Binned/`

Only files ending in a selected `_binned_{count}.csv` suffix are processed. Selecting 20 does not select 120 or another existing bin specification. Every selected count must have a matching input file in each selected group/horizon directory. Unselected horizons are not opened.

The `Bin` column and its order are retained. Each other column is divided by its own total. A zero-total column remains all zero, preserving the original handling.

Outputs are written to:

`Material Events/{Group}/JS Divergence/Basel III T+{horizon}/Probabilities/probabilities_{original_filename}`

With the default second and third coverage counts, 20/30/50/100 central bins produce 26/36/56/106 PMF rows. The final interval is `[2.00, inf)`. See the [binning guide](../binning/readme.md) for exact endpoint behavior.

Each group, horizon, bin specification, and ratio column is normalized independently. The resulting files feed the selected-horizon JSD calculation.
