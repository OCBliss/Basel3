# Step 8.0.1 — Variable Binning for JS Divergence Analysis

## Purpose

This step transforms raw financial ratio features for each peer group (Failures, Mergers, Survivors) into **binned histograms**. These are used to compute pairwise Jensen-Shannon divergence (JSD) in subsequent steps.

It discretizes continuous ratio changes into (20+5+2) bins, reflecting both symmetry and tail behavior, to enable robust non-parametric distribution comparisons.

---

## Input

CSV files representing peer group composition at future event horizons:

| Event Type | Time Horizon | Input File |
|------------|--------------|-------------|
| Mergers    | T+1 to T+4    | `Peer_Group_Mergers_Basel3_t{N}.csv` |
| Failures   | T+1 to T+4    | `Peer_Group_Failures_Basel3_t{N}.csv` |
| Survivors  | T+1 to T+4    | `Peer_Group_Survivors_Basel3_t{N}.csv` |

Each file is located in its respective `Peer Group` directory and contains:
- ID columns (e.g., `CERT`, `RCON9999`)
- Quarterly ratio columns (`VAR_q0`, `VAR_q0q1`, etc.)

---

## Binning Strategy

Each numeric column is binned into:

- **20 bins from -1 to 1** using `np.linspace(-1, 1, 21)`
- **5 bins from (1.0, 2.0]**: `[(1.0, 1.2], (1.2, 1.4], ..., (1.8, 2.0]]`
- **1 bin for values > 2**

This creates **20 + 5 + 1 = 26** total bins.

---

## Output

For each `(group, time horizon)` combination:

| Group     | Time Horizon | Output Folder |
|-----------|--------------|----------------|
| Mergers   | T+1–T+4       | `Mergers/JS Divergence/Basel III T+N/Binned/` |
| Failures  | T+1–T+4       | `Failures/JS Divergence/Basel III T+N/Binned/` |
| Survivors | T+1–T+4       | `Survivors/JS Divergence/Basel III T+N/Binned/` |

Each output file is named: `<OriginalFileName>_binned_20.csv`


And contains a DataFrame:

| Bin Label        | Ratio_1 | Ratio_2 | ... |
|------------------|---------|---------|-----|
| [-1.00, -0.90)   |   45    |   17    |     |
| ...              |         |         |     |
| > 2.00           |    3    |    0    |     |

---

## Use Case

These binned matrices will be used in **Step 8.1.1** to create probability mass functions used later in **Step 8.2.0.X** to compute **Jensen-Shannon Divergence (JSD)** across peer groups at various Basel III regulatory horizons. This enables systemic comparison of distributional divergence in financial behavior prior to failure or merger events.

---

## Next Step

Proceed to **Step 8.1.1**:
- Compute PMFs for peer groups (e.g., Failures vs Survivors)

