# Step 07.0.0.1 — Material Event Classification (T+1 Horizon)

## Purpose

This step partitions the full panel of lagged financial reports into three disjoint, mutually exclusive event categories:
- **Failures**: Banks that failed in the next quarter (FAILURE_T1 = 1)
- **Mergers**: Banks that merged in the next quarter (MERGER_T1 = 1)
- **Survivors**: Banks that did neither

This output is used to train classification or forecasting models under a 1-quarter forward-looking window (T+1).

---

## Input

Files must already contain `FAILURE_T1` and `MERGER_T1` columns. Inputs come from:

| Event Type | Path |
|------------|------|
| Raw source for all categories | `Material Events/Mergers/Call Reports/` |
| Failure record table | `Material Events/Failures/Call Reports/` |

---

## Output

| Category   | Output Path                                                   |
|------------|----------------------------------------------------------------|
| Failures   | `Material Events/Failures/Peer Group Failures/Basel III T+1/` |
| Mergers    | `Material Events/Mergers/Peer Group Mergers/Basel III T+1/`   |
| Survivors  | `Material Events/Survivors/Peer Group Survivors/Basel III T+1/` |

Each folder contains CSVs named identically to the originals but filtered based on event classification.

---

## Logic

### Failures

- Source: `Failures/Call Reports/`
- Condition: `FAILURE_T1 == 1`
- Action: Extract and write matching rows.

### Mergers

- Source: `Mergers/Call Reports/`
- Condition: `MERGER_T1 == 1`
- Action: Extract and write matching rows.

### Survivors

- Source: `Mergers/Call Reports/`
- Condition: `FAILURE_T1 != 1` **AND** `MERGER_T1 != 1`
- Action: Remove all failure and merger rows, write the rest.

---

## Columns Required

- `CERT`: Bank identifier
- `FAILURE_T1`: Binary (0/1) flag from previous pipeline steps
- `MERGER_T1`: Binary (0/1) flag from previous pipeline steps

These are used to determine classification logic.

---

## Example Row Filtering

| CERT  | FAILURE_T1 | MERGER_T1 | Category    |
|-------|------------|-----------|-------------|
| 10101 | 1          | 0         | Failure     |
| 20202 | 0          | 1         | Merger      |
| 30303 | 0          | 0         | Survivor    |
| 40404 | 1          | 1         | Failure     |

**Note:** Failures take precedence over mergers if both flags are present.

---

## Outcome (Step 07.0.0.1)

A fully partitioned dataset across all observed banks for each quarter for each peer group:
- Validated for exclusivity
- Harmonized in structure
- Prepared for training or statistical divergence analysis

---

## Next Step

Proceed to **Step 07.1.0.1**:
- Merge label subsets across financial quarters
- Align on multi-quarter lags or prepare for JSD analysis
