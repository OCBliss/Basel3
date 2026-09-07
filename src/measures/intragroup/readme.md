# Step 8.3.0.1 — Intragroup Column Filtering After JSD Outputs

`JSD_intragroup_filter.py` keeps columns whose first-row numeric value meets the selected threshold. Its purpose is to identify high-signal variables by removing columns with small JSD values.

The existing threshold rule is retained:

- Values below `T` are removed.
- Values greater than or equal to `T` are kept.
- Missing or nonnumeric first-row values are removed, including the `Bin=JSD` label column.

## Run the Filter

From the repository root:

```sh
python3 src/measures/intragroup/JSD_intragroup_filter.py --horizons 1 2 3 4 --bins 20 30 50 100 --material-dir "Material Events" --threshold 0.3
```

The command above runs the original full selection. For an optional subset, use `--horizons 1 3 --bins 20 50`.

`--horizons` is required and accepts one or more of `1 2 3 4`. `--bins` is required and accepts the positive central bin counts encoded in the JSD filenames. `--material-dir` defaults to the repository's Material Events directory. `--threshold` defaults to `0.3`.

For each selected horizon, the program reads selected `_<count>.csv` files from:

```text
Material Events/JSD/BASEL III T+<horizon>/
```

It writes the retained columns under the same filenames in:

```text
Material Events/IG/BASEL III T+<horizon>/
```

The configured inputs are the three comparisons: survivors vs. failures, survivors vs. mergers, and mergers vs. failures. Unselected horizons and bin suffixes are not processed. The filter selects columns and preserves the existing rows.

## YAML Arguments

The pipeline passes its shared horizon and central-bin selections directly:

```yaml
"8.3.0.1":
  path: "measures/intragroup/JSD_intragroup_filter.py"
  args: ["--horizons", "{horizons}", "--material-dir", "Material Events", "--bins", "{bins1}", "--threshold", 0.3]
```

`parameters.horizons` and `parameters.bins1` also expand the task's declared input/output paths in `pipeline/pipeline_config_dynamic.yaml`. The same selected combinations therefore continue from JSD calculation into this final filter. See the [pipeline guide](../../../pipeline/readme.md) for the shared parameter block and full artifact declarations.
