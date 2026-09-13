# Dynamic Call Report ratios

The [variable catalogue](variables/readme.md) lists all 76 ratio names and their
current calculations, including the form and date rules.

Pipeline step 4.0 runs `Dynamic_Ratios.py` after the numeric Call Report and
current-quarter ratio files have been written.

Inputs:

- `data/CSV/Cleaned/Cleaned_Call_Report_<YYYYMMDD>.csv`
- `data/CSV/Interleaved/Cleaned_Call_Report_<YYYYMMDD>.csv`
- `data/CSV/quarter_flag.csv`

The current values come from the Interleaved file. The explicit entries in
`Call_Reports_v4_0.py`, using the separate `Call_Report.py` API, calculate `P1Q`, `P2Q`, and `P3Q`. Lag results merge on
`CERT`, matching the original distributed-lag pipeline.

For every ratio, the output contains:

- `<ratio>_q0`
- `<ratio>_q0q1 = q0 / P1Q - 1`
- `<ratio>_q0q2 = q0 / P2Q - 1`
- `<ratio>_q0q3 = q0 / P3Q - 1`

A true zero denominator produces zero. A missing value remains missing.
This deliberately replaces the former blanket `fillna(0)`: an unavailable
filing is not treated as a reported economic zero.

Output files are written directly to
`data/CSV/Dynamic_Lag/Cleaned/Dynamic_Cleaned_Call_Report_<YYYYMMDD>.csv`.
`CERT` and `RCON9999` remain the first two columns for downstream
material-event flagging.
