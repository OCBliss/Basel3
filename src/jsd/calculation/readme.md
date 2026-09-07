# Step 8.2 — Jensen-Shannon Comparisons Across Selected Horizons

`Material_events_JSD_basel3.py` calculates the existing three comparisons for each selected horizon and bin width:

- Survivors vs. Failures
- Survivors vs. Mergers
- Mergers vs. Failures

From the repository root:

```bash
python3 "src/jsd/calculation/Material_events_JSD_basel3.py" --horizons 1 2 3 4 --bins 20 30 50 100
```

Both `--horizons` and `--bins` are required. Horizons are integers from 1 through 4. Bin widths are positive integers matching the central interval count in the PMF filename, including 20, 30, 50, and 100. `--material-dir` optionally overrides the Material Events directory supplied by `Basel3_Global_Filepath.py`.

The pipeline YAML defaults to all four horizons and all four original bin specifications. A smaller selection, such as `--horizons 1 3 --bins 20 50`, is optional.

Only the selected horizons and bin widths are read. Other bin files left in the same probability directories are excluded. The pipeline calls this script directly and passes these arguments in its YAML `args` list.

## Inputs

For horizon `h`, the three input directories are:

- `Material Events/Survivors/JS Divergence/Basel III T+h/Probabilities/`
- `Material Events/Failures/JS Divergence/Basel III T+h/Probabilities/`
- `Material Events/Mergers/JS Divergence/Basel III T+h/Probabilities/`

PMF filenames end with `_binned_<width>.csv`. A width is compared only when a matching file exists in all three group directories. Each input contains a `Bin` column and the probability columns produced by the PMF stage.

## Calculation

The calculation preserves the original horizon scripts:

1. Align each pair of PMFs by `Bin`, filling bins missing from either group with zero.
2. Compare the columns shared by that pair, retaining their order from the first group.
3. Convert nonnumeric or missing values to zero and normalize each vector when its sum is positive. An all-zero vector remains zero.
4. Compute `m = 0.5 * (p + q)` and `sqrt(0.5 * KL(p || m) + 0.5 * KL(q || m))`.

KL uses the natural logarithm and replaces values below `1e-15` with `1e-15` inside each KL calculation. This retains the existing square-root calculation and treatment of zero PMFs.

## Outputs

For each selected horizon and matched bin width, output goes to `Material Events/JSD/BASEL III T+h/`:

- `JSD_survivors_vs_failures_<width>.csv`
- `JSD_survivors_vs_mergers_<width>.csv`
- `JSD_mergers_vs_failures_<width>.csv`

Each file contains one row labeled `Bin=JSD`, followed by the comparison values for its common probability columns.
