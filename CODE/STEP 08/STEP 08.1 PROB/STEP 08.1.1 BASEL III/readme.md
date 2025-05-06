# Step 8.1.1 — Convert Binned Counts to Probabilities

## Purpose

This step normalizes previously binned histogram counts into **probability distributions** over 27 bins for each financial ratio. These distributions represent the empirical behavior of peer groups (Mergers, Failures, Survivors) under Basel III T+1 through T+4 horizons.

These normalized probabilities enable non-parametric divergence metrics such as **Jensen-Shannon Divergence (JSD)**.

---

## Input

From Step 8.0.1, the input files are of the form: `<Peer Group>_Basel3_binned_20.csv`


Located in:

| Peer Group | Horizon  | Directory Location                                                                 |
|------------|----------|-------------------------------------------------------------------------------------|
| Mergers    | T+1–T+4  | `Mergers/JS Divergence/Basel III T+N/Binned/`                                     |
| Failures   | T+1–T+4  | `Failures/JS Divergence/Basel III T+N/Binned/`                                    |
| Survivors  | T+1–T+4  | `Survivors/JS Divergence/Basel III T+N/Binned/`                                   |

Each CSV contains:
- Index: `Bin` (e.g., `[-0.50, -0.40)`, `> 2.00`)
- Columns: financial ratios with raw bin counts

---

## Output

Each binned count file is normalized column-wise into a probability distribution: `probabilities_<OriginalFileName>`


Saved in:

| Peer Group | Horizon  | Output Directory                                                                   |
|------------|----------|-------------------------------------------------------------------------------------|
| Mergers    | T+1–T+4  | `Mergers/JS Divergence/Basel III T+N/Probabilities/`                               |
| Failures   | T+1–T+4  | `Failures/JS Divergence/Basel III T+N/Probabilities/`                              |
| Survivors  | T+1–T+4  | `Survivors/JS Divergence/Basel III T+N/Probabilities/`                             |

Each output CSV has the same bin labels, but each ratio column now sums to 1 (within floating point error). Columns with zero total are flagged and filled with 0-probability.

---

## Example

A binned file:

| Bin         | RCB-0211-1754_q0 | RCB-0211-1754_q0q1 |
|-------------|----------------|--------------|
| [-1.0,-0.9) |      15        |      2       |
| ...         |      ...       |     ...      |
| > 2.0       |       0        |      1       |

Is transformed into:

| Bin         | RCB-0211-1754_q0 | RCB-0211-1754_q0q1 |
|-------------|----------------|--------------|
| [-1.0,-0.9) |    0.1034      |   0.0400     |
| ...         |    ...         |   ...        |
| > 2.0       |    0.0000      |   0.0200     |

---

## Use Case

These probability distributions will be input into **Step 8.2.1.X**:
- Pairwise JSD computation between peer group distributions
- Measurement of structural divergence in financial behaviors over time

This process supports empirical falsification of systemic monotonicity under Basel III and enables quantification of capital misalignment across risk states.

---

## Next Step

Proceed to **Step 8.2.1**:
- Calculate JSD across `(Failures, Mergers, Survivors)` for each ratio
