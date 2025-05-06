# Step 8.2.0.1 — Jensen-Shannon Divergence Between Peer Groups (T+1 Horizon)

## Purpose

This module computes **Jensen-Shannon Divergence (JSD)** between normalized probability distributions derived from binned financial metrics (Step 8.1.1). It enables quantification of **structural divergence** between:

- Survivors vs. Failures  
- Survivors vs. Mergers  
- Mergers vs. Failures  

All comparisons are performed **per financial ratio** for each matching suffix (e.g., `_20.csv`), which corresponds to a specific date or time bin.

---

## Input

This script consumes probability-distribution `.csv` files created in **Step 8.1.1**, located in:

| Group      | Path Example                                                                 |
|------------|-------------------------------------------------------------------------------|
| Survivors  | `Survivors/JS Divergence/Basel III T+1/Probabilities`                        |
| Failures   | `Failures/JS Divergence/Basel III T+1/Probabilities`                         |
| Mergers    | `Mergers/JS Divergence/Basel III T+1/Probabilities`                          |

Each file must share a consistent suffix (e.g., `_20.csv`), and contain:
- A `Bin` column
- Normalized probability columns (summing to 1 per column)

---

## Output

All output `.csv` files are stored in: `Material Events/JSD/BASEL III T+1/`


For each matched suffix (e.g., `_20`), the following files are produced:

- `JSD_survivors_vs_failures_20.csv`
- `JSD_survivors_vs_mergers_20.csv`
- `JSD_mergers_vs_failures_20.csv`

Each output file contains a single row labeled `Bin=JSD`, with JSD values per financial ratio column.

---

## Methodology

For each ratio:
1. Extract its probability vector `p` from one group and `q` from the other
2. Normalize both (in case of rounding error)
3. Compute: M = 0.5 * (p + q)
JSD(p, q) = sqrt(0.5 * KL(p || M) + 0.5 * KL(q || M))

where `KL` is the Kullback–Leibler divergence.

---

## Matching Mechanism

Files are matched using their filename suffix:
- For `Peer_Group_Survivors_Basel3_binned_20.csv`, the suffix is `20`
- Only suffixes common to all three directories (Survivors, Failures, Mergers) are processed

---

## Example

### Input:

- `Survivors/JS Divergence/Basel III T+1/Probabilities/Peer_Group_Survivors_Basel3_binned_20.csv`
- `Failures/JS Divergence/Basel III T+1/Probabilities/Peer_Group_Failures_Basel3_binned_20.csv`
- `Mergers/JS Divergence/Basel III T+1/Probabilities/Peer_Group_Mergers_Basel3_binned_20.csv`


### Output:

- `JSD_survivors_vs_failures_20.csv`
- `JSD_survivors_vs_mergers_20.csv`
- `JSD_mergers_vs_failures_20.csv`


