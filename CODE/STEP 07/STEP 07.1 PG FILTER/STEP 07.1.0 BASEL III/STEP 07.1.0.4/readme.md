# Step 7.1.0.4 — Date-Filtered Event Panel Aggregation

## Purpose

This step consolidates T+4 peer-group event data (failures, mergers, survivors) across valid quarters defined in `quarters_basel3.csv`. It performs strict date filtering by filename suffix (`YYYYMMDD`) and outputs unified CSVs per event class.

---

## Input

Each folder contains quarter-specific CSVs output from Step 07.0.0.4:

| Event Type | Input Folder |
|------------|---------------|
| Failures   | `Material Events/Failures/Peer Group Failures/Basel III T+4` |
| Mergers    | `Material Events/Mergers/Peer Group Mergers/Basel III T+4`   |
| Survivors  | `Material Events/Survivors/Peer Group Survivors/Basel III T+4` |

**Date Filter Source**:
- `quarters_basel3.csv` must contain a column named `Quarters` formatted as `YYYYMMDD`.

---

## Output

| Event Type | Output File |
|------------|-------------|
| Failures   | `Peer_Group_Failures_Basel3_t4.csv` |
| Mergers    | `Peer_Group_Mergers_Basel3_t4.csv` |
| Survivors  | `Peer_Group_Survivors_Basel3_t4.csv` |

These are saved to their respective parent directories.

---

## Logic

1. **Iterate Files**: All `.csv` files in each peer group directory are considered.
2. **Extract Date**: For each file, the last 8 characters (before `.csv`) are interpreted as the file's quarter (`YYYYMMDD`).
3. **Filter**: A file is included only if this date exists in the `quarters_basel3.csv` list.
4. **Concatenate**: Matching files are concatenated into a single output CSV.
5. **Preserve Schema**: Output preserves column structure and includes only rows for valid quarters.

---

## Benefits

- **Temporal Consistency**: Only includes records from relevant financial periods.
- **Panel Readiness**: Produces finalized datasets for direct modeling, training, or longitudinal analysis.
- **Integrity Check**: Skips unexpected or malformed filenames and logs mismatches by default.

---

## Output Preview

Final CSVs contain:
- All financial and lagged features (e.g., `RCB-0211-1754_q0`, `RCB-0211-1754_q0q1`, etc.)
- Entity identifiers like `CERT`
- Financial quarter `RCON9999`
- Outcome labels (`FAILURE_T4`, `MERGER_T4`, etc.)
- Temporal validity ensured by cross-check with `quarters_basel3.csv`

---

## Next Step

`concurrent_groups` to **Steps 8.0.1, 8.0.2, 8.0.3, 8.0.4**:
- Performs concurrent binning (bin sizes 20, 30, 50, 100) for PMF generation.

