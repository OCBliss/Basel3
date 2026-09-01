# Dynamic Call Report panel

Pipeline step 4.0 writes the final files to
`data/CSV/Dynamic_Lag/Cleaned/`.

For each `Cleaned_Call_Report_<YYYYMMDD>.csv`, the current ratios come from the
Interleaved file. The date-aware Call Report methods calculate the same ratios
at `P1Q`, `P2Q`, and `P3Q`. Historical institutions are aligned to the current
panel by FDIC `CERT`, preserving the acquisition boundary used by the original
pipeline.

Each output file is named
`Dynamic_Cleaned_Call_Report_<YYYYMMDD>.csv` and begins with `CERT` and
`RCON9999`. Every ratio then has four columns:

- `<ratio>_q0`
- `<ratio>_q0q1`
- `<ratio>_q0q2`
- `<ratio>_q0q3`

The change columns equal `q0 / lag - 1`. A zero denominator produces zero; a
missing current or historical value remains missing.
The retired distributed cleaner filled every blank with zero; the consolidated
stage does not convert an unavailable filing into a reported zero.
