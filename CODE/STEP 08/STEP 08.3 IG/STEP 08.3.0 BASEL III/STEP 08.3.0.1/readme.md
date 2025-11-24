# Step 8.3.0.1 — Information Gain Column Filtering After JSD Outputs

This step proccesses the JSD outputs temporally produced in:

- `Material Events/JSD/BASEL III T+1/`
- `Material Events/JSD/BASEL III T+2/`
- `Material Events/JSD/BASEL III T+3/`
- `Material Events/JSD/BASEL III T+4/`

and applies an information-gain style filter:

- keep onl those columns whose JSD value is above a threshold (T)
  
## Purpose

The purpose of this is to identify **high-signal variables** removing columns whose JSD values are too small (i.e., columns that provide very little divergence/information between outcomes)

This implements a hard threshold:

- Variables with **JSD < T** → removed
- Variables with **JSD ≥ T** → kept

For:

- Survivors vs. Failures  
- Survivors vs. Mergers  
- Mergers vs. Failures

## 📁 Output Directories

Filtered files are written to:

- Material Events/IG/
  - BASEL III T+1/
  - BASEL III T+2/
  - BASEL III T+3/
  - BASEL III T+4/

with identical filenames, e.g.:

- `JSD_[peer group1]_vs_[peer group 2]_[bin].csv`

## Next Step

- Step 08.3.0.2
