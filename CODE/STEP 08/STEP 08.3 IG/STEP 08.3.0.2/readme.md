# Step 08.3.0.2 — Call Report Concatenation by Outcome & Basel Horizon

This step takes the peer-group–aligned call-report datasets for:

- Survivors
- Mergers
- Failures

across the four Basel III horizons:

- t1
- t2
- t3
- t4

and concatenates them into unified combined files, one per horizon.

The output is a set of 4 merged datasets that contain all institutions (survivors + mergers + failures) for each T-horizon, preserving row structure and variable alignment.

---

## Purpose

This script performs the first aggregation step after peer-group alignment.

It takes three CSVs for each time horizon:

- `Peer_Group_Survivors_Basel3_t1.csv`
- `Peer_Group_Mergers_Basel3_t1.csv`
- `Peer_Group_Failures_Basel3_t1.csv`

and concatenates them vertically into:

- `Call_Report_Basel3_t1.csv`

It does the same for t2, t3, and t4.

This ensures that all call-report data sharing the same regulatory horizon (T+1 … T+4) are placed into a common dataset for downstream analysis (e.g., IG pruning, feature selection, classifier training).

---

## Input Directory Structure

The script expects the following folder organization:

- Material Events/
    - Survivors/
        - Peer Group Survivors/
            - Peer_Group_Survivors_Basel3_t1.csv
            - Peer_Group_Survivors_Basel3_t2.csv
            - ...
    - Mergers/
        - Peer Group Mergers/
            - Peer_Group_Mergers_Basel3_t1.csv
            - Peer_Group_Mergers_Basel3_t2.csv
            - ...
    - Failures/
        - Peer Group Failures/
            - Peer_Group_Failures_Basel3_t1.csv
            - Peer_Group_Failures_Basel3_t2.csv
            - ...

Each folder contains one file per Basel horizon (t1, t2, t3, t4).

## Outputs

- We end up with a similar format as `STEP 03` but with more granularity and filtration by only the relevant variables according to that bin/PMF construction.
- The call reports variables are reconstructed so that we can see the individual institution data per time horizon across all quarters instead per quarter.
- This will facilitate the intra-group distance calculation, i.e., an idiosyncratic measure of banks that are out-of-sync with peers

